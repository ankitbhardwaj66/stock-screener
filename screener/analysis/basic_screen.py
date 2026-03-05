"""Basic screener: revenue, PAT, EBITDA, EPS, OCF quality."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml


_FINANCIAL_KEYWORDS = ("financial", "bank", "nbfc", "insurance", "lending", "housing finance", "asset management")


def _is_financial(sector: Optional[str]) -> bool:
    if not sector:
        return False
    s = sector.lower()
    return any(kw in s for kw in _FINANCIAL_KEYWORDS)


def _load_cfg() -> dict:
    return yaml.safe_load(
        (Path(__file__).parent.parent.parent / "config" / "thresholds.yaml").read_text()
    )


class FlagLevel(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


@dataclass
class ScreenFlag:
    level: FlagLevel
    category: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level.value}] {self.category}: {self.message}"


@dataclass
class BasicScreenResult:
    symbol: str
    # Growth metrics
    revenue_qoq_pct: Optional[float] = None
    revenue_yoy_pct: Optional[float] = None       # avg YoY over 5Y
    revenue_yoy_3y_pct: Optional[float] = None    # avg YoY over 3Y
    pat_qoq_pct: Optional[float] = None
    pat_yoy_pct: Optional[float] = None
    pat_yoy_3y_pct: Optional[float] = None
    eps_qoq_pct: Optional[float] = None
    eps_yoy_pct: Optional[float] = None
    eps_yoy_3y_pct: Optional[float] = None
    # Margin
    ebitda_margin_latest_pct: Optional[float] = None
    ebitda_margin_trend: Optional[str] = None  # improving | stable | deteriorating
    # Cash quality (yfinance quarterly — fallback)
    ocf_pat_ratio: Optional[float] = None
    ocf_trend: Optional[str] = None  # improving | stable | deteriorating
    # Absolute latest values
    revenue_latest: Optional[float] = None
    pat_latest: Optional[float] = None
    eps_latest: Optional[float] = None
    ocf_latest: Optional[float] = None
    # Annual cash flows from screener.in (primary, in Crores)
    si_ocf_annual: Optional[float] = None   # Cash from Operating Activity
    si_icf_annual: Optional[float] = None   # Cash from Investing Activity
    si_fcf_annual: Optional[float] = None   # FCF = OCF + ICF
    si_cff_annual: Optional[float] = None   # Cash from Financing Activity
    si_net_cf_annual: Optional[float] = None  # Net Cash Flow
    si_ocf_trend: Optional[str] = None      # 5yr trend of annual OCF
    si_ocf_pat_ratio: Optional[float] = None  # annual OCF / annual PAT
    # Flags and score
    flags: list[ScreenFlag] = field(default_factory=list)
    score: int = 0
    score_breakdown: dict = field(default_factory=dict)  # section → points


def _safe_pct_change(series: pd.Series, periods: int = 1) -> Optional[float]:
    """Safe percentage change, handles NaN/zero."""
    try:
        s = series.dropna()
        if len(s) < periods + 1:
            return None
        prev = s.iloc[-(periods + 1)]
        curr = s.iloc[-1]
        if prev == 0 or pd.isna(prev) or pd.isna(curr):
            return None
        return round(((curr - prev) / abs(prev)) * 100, 2)
    except Exception:
        return None


def _avg_qoq_pct(series: pd.Series, n: int = 5) -> Optional[float]:
    """Average QoQ % change over the last n quarters (smoothed momentum)."""
    try:
        s = series.dropna()
        if len(s) < n + 1:
            return None
        changes = s.pct_change().dropna()
        if len(changes) < n:
            return None
        avg = changes.iloc[-n:].mean() * 100
        return round(float(avg), 2)
    except Exception:
        return None


def _avg_yoy_pct(series: pd.Series, n: int = 5) -> Optional[float]:
    """Average of the last n YoY % changes (each quarter vs same quarter 1 year prior)."""
    try:
        s = series.dropna()
        if len(s) < n + 4:
            return None
        changes = []
        for i in range(n):
            curr = s.iloc[-(1 + i)]
            prev = s.iloc[-(5 + i)]   # 4 quarters back = same quarter last year
            if prev == 0 or pd.isna(prev) or pd.isna(curr):
                continue
            changes.append(((curr - prev) / abs(prev)) * 100)
        if not changes:
            return None
        return round(sum(changes) / len(changes), 2)
    except Exception:
        return None


def _trend(series: pd.Series, window: int = 4) -> str:
    """Determine trend of last N values: improving/stable/deteriorating."""
    try:
        s = series.dropna().tail(window)
        if len(s) < 3:
            return "insufficient_data"
        diffs = s.diff().dropna()
        pos = (diffs > 0).sum()
        neg = (diffs < 0).sum()
        if pos >= len(diffs) * 0.6:
            return "improving"
        elif neg >= len(diffs) * 0.6:
            return "deteriorating"
        return "stable"
    except Exception:
        return "unknown"


def _find_col(df: pd.DataFrame, keywords: list[str]) -> Optional[str]:
    """Find column containing any of the keywords (case-insensitive)."""
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw.lower() in col_lower for kw in keywords):
            return col
    return None


def _col_as_series(df: pd.DataFrame, col: str) -> pd.Series:
    """Return a numeric Series for col, safely handling duplicate column names."""
    result = df[col]
    if isinstance(result, pd.DataFrame):
        result = result.iloc[:, 0]  # duplicate columns → take first
    return result.apply(pd.to_numeric, errors="coerce")


def _si_clean(val: str) -> float:
    """Parse screener.in cell values: '2,008', '2%', '16.94', '-', etc."""
    s = str(val).strip().replace(",", "").replace("%", "").replace("₹", "").replace("Cr.", "")
    if not s or s in ("-", "", "NA", "N/A", "--"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def _si_row_series(si_df: pd.DataFrame, keywords: list[str], skip_ttm: bool = False) -> Optional[pd.Series]:
    """
    Extract a time series from screener.in DataFrame.
    Structure: rows = metrics, cols = [label_col, period1, period2, ..., periodN]
    Returns a numeric Series indexed 0..N-1 (chronological, oldest→newest).
    skip_ttm=True drops the last column if its header is 'TTM'.
    """
    cols = list(si_df.columns)
    # Determine which column indices to include (skip label col 0, optionally skip TTM)
    end_idx = len(cols)
    if skip_ttm and str(cols[-1]).strip().upper() == "TTM":
        end_idx -= 1

    for _, row in si_df.iterrows():
        label = str(row.iloc[0]).lower().strip()
        if any(kw.lower() in label for kw in keywords):
            vals = [_si_clean(row.iloc[i]) for i in range(1, end_idx)]
            return pd.Series(vals, dtype=float)
    return None


class BasicScreener:
    """Analyses quarterly income/cashflow for basic quality signals."""

    def __init__(self):
        self.cfg = _load_cfg()

    def screen(
        self,
        symbol: str,
        income_df: Optional[pd.DataFrame],
        cashflow_df: Optional[pd.DataFrame],
        si_quarterly_df: Optional[pd.DataFrame] = None,
        si_annual_df: Optional[pd.DataFrame] = None,
        si_cashflow_df: Optional[pd.DataFrame] = None,
        sector: Optional[str] = None,
    ) -> BasicScreenResult:
        """
        si_quarterly_df (screener.in) is used as the PRIMARY source for Revenue/PAT/EPS/margin.
        income_df (yfinance) is the FALLBACK when screener.in data is unavailable.
        cashflow_df (yfinance) is used for OCF (screener.in cash flow is annual-only).
        """
        result = BasicScreenResult(symbol=symbol)
        cfg_g = self.cfg["growth"]
        cfg_p = self.cfg["profitability"]

        si_ok = si_quarterly_df is not None and not si_quarterly_df.empty

        if not si_ok and (income_df is None or income_df.empty):
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Data", "No quarterly income data available"))
            result.score = 0
            return result

        # ── Revenue ────────────────────────────────────────────────────────
        if si_ok:
            rev = _si_row_series(si_quarterly_df, ["Sales", "Revenue"])
        else:
            rev = None
        if rev is None or rev.dropna().empty:
            # fallback to yfinance
            rev_col = _find_col(income_df, ["Revenue", "Sales", "Total Revenue"]) if income_df is not None else None
            rev = _col_as_series(income_df, rev_col) if rev_col else None

        _si_source = si_ok  # track whether values come from screener.in (Crores) or yfinance (abs INR)
        ann_ok = si_annual_df is not None and not si_annual_df.empty

        if rev is not None and not rev.dropna().empty:
            raw_latest = float(rev.dropna().iloc[-1])
            result.revenue_latest = raw_latest * 1e7 if _si_source else raw_latest
            result.revenue_qoq_pct = _avg_qoq_pct(rev, 5)
            # YoY: prefer annual data (last 5 fiscal years), fall back to quarterly
            ann_rev = _si_row_series(si_annual_df, ["Sales", "Revenue"]) if ann_ok else None
            result.revenue_yoy_pct = _avg_qoq_pct(ann_rev, 5) if (ann_rev is not None and not ann_rev.dropna().empty) else _avg_yoy_pct(rev, 5)
            result.revenue_yoy_3y_pct = _avg_qoq_pct(ann_rev, 3) if (ann_rev is not None and not ann_rev.dropna().empty) else _avg_yoy_pct(rev, 3)

        # ── PAT / Net Profit ───────────────────────────────────────────────
        if si_ok:
            pat = _si_row_series(si_quarterly_df, ["Net Profit", "PAT"])
        else:
            pat = None
        if pat is None or pat.dropna().empty:
            pat_col = _find_col(income_df, ["Net_Income", "Net Income", "PAT", "Profit after tax"]) if income_df is not None else None
            pat = _col_as_series(income_df, pat_col) if pat_col else None
            _si_source = False  # fell back to yfinance

        if pat is not None and not pat.dropna().empty:
            raw_latest = float(pat.dropna().iloc[-1])
            result.pat_latest = raw_latest * 1e7 if _si_source else raw_latest
            result.pat_qoq_pct = _avg_qoq_pct(pat, 5)
            ann_pat = _si_row_series(si_annual_df, ["Net Profit", "PAT"]) if ann_ok else None
            result.pat_yoy_pct = _avg_qoq_pct(ann_pat, 5) if (ann_pat is not None and not ann_pat.dropna().empty) else _avg_yoy_pct(pat, 5)
            result.pat_yoy_3y_pct = _avg_qoq_pct(ann_pat, 3) if (ann_pat is not None and not ann_pat.dropna().empty) else _avg_yoy_pct(pat, 3)

        # ── EPS ────────────────────────────────────────────────────────────
        if si_ok:
            eps = _si_row_series(si_quarterly_df, ["EPS in Rs", "EPS"])
        else:
            eps = None
        if eps is None or eps.dropna().empty:
            eps_col = _find_col(income_df, ["EPS", "Basic EPS", "Diluted EPS"]) if income_df is not None else None
            eps = _col_as_series(income_df, eps_col) if eps_col else None

        if eps is not None and not eps.dropna().empty:
            result.eps_latest = float(eps.dropna().iloc[-1])   # EPS is ₹/share — no unit conversion
            result.eps_qoq_pct = _avg_qoq_pct(eps, 5)
            ann_eps = _si_row_series(si_annual_df, ["EPS in Rs", "EPS"]) if ann_ok else None
            result.eps_yoy_pct = _avg_qoq_pct(ann_eps, 5) if (ann_eps is not None and not ann_eps.dropna().empty) else _avg_yoy_pct(eps, 5)
            result.eps_yoy_3y_pct = _avg_qoq_pct(ann_eps, 3) if (ann_eps is not None and not ann_eps.dropna().empty) else _avg_yoy_pct(eps, 3)

        # ── EBITDA / Operating margin ──────────────────────────────────────
        if si_ok:
            # screener.in provides OPM % directly — use it
            opm_pct = _si_row_series(si_quarterly_df, ["OPM %", "OPM%", "OPM"])
            if opm_pct is not None and not opm_pct.dropna().empty:
                result.ebitda_margin_latest_pct = round(float(opm_pct.dropna().iloc[-1]), 2)
                result.ebitda_margin_trend = _trend(opm_pct, window=8)
        if result.ebitda_margin_latest_pct is None and income_df is not None:
            # fallback: compute from yfinance EBITDA / Revenue
            ebitda_col = _find_col(income_df, ["EBITDA"])
            rev_col_yf = _find_col(income_df, ["Revenue", "Sales", "Total Revenue"])
            if ebitda_col and rev_col_yf:
                ebitda = _col_as_series(income_df, ebitda_col)
                rev_yf = _col_as_series(income_df, rev_col_yf)
                ebitda_margin = (ebitda / rev_yf * 100).replace([np.inf, -np.inf], np.nan)
                if not ebitda_margin.dropna().empty:
                    result.ebitda_margin_latest_pct = round(float(ebitda_margin.dropna().iloc[-1]), 2)
                    result.ebitda_margin_trend = _trend(ebitda_margin, window=8)

        # ── OCF quality — yfinance quarterly (fallback) ───────────────────
        if cashflow_df is not None and not cashflow_df.empty:
            ocf_col = _find_col(cashflow_df, ["OCF", "Operating Cash Flow"])
            if ocf_col:
                ocf = _col_as_series(cashflow_df, ocf_col)
                result.ocf_latest = float(ocf.dropna().iloc[-1]) if not ocf.dropna().empty else None
                result.ocf_trend = _trend(ocf, window=6)
                if result.pat_latest and result.pat_latest != 0 and result.ocf_latest is not None:
                    result.ocf_pat_ratio = round(result.ocf_latest / result.pat_latest, 2)

        # ── Annual cash flows — screener.in (primary, reliable) ───────────
        if si_cashflow_df is not None and not si_cashflow_df.empty:
            ocf_s = _si_row_series(si_cashflow_df, ["Cash from Operating", "Operating Activity", "operating"])
            icf_s = _si_row_series(si_cashflow_df, ["Cash from Investing", "Investing Activity", "investing"])
            cff_s = _si_row_series(si_cashflow_df, ["Cash from Financing", "Financing Activity", "financing"])
            ncf_s = _si_row_series(si_cashflow_df, ["Net Cash Flow", "Net Cash", "net cash"])

            if ocf_s is not None and not ocf_s.dropna().empty:
                result.si_ocf_annual = float(ocf_s.dropna().iloc[-1])
                result.si_ocf_trend = _trend(ocf_s, window=5)
            if icf_s is not None and not icf_s.dropna().empty:
                result.si_icf_annual = float(icf_s.dropna().iloc[-1])
            if cff_s is not None and not cff_s.dropna().empty:
                result.si_cff_annual = float(cff_s.dropna().iloc[-1])
            if ncf_s is not None and not ncf_s.dropna().empty:
                result.si_net_cf_annual = float(ncf_s.dropna().iloc[-1])
            if result.si_ocf_annual is not None and result.si_icf_annual is not None:
                result.si_fcf_annual = result.si_ocf_annual + result.si_icf_annual

            # OCF/PAT ratio using annual data — more reliable than quarterly
            if ann_ok and result.si_ocf_annual is not None:
                ann_pat = _si_row_series(si_annual_df, ["Net Profit", "PAT"])
                if ann_pat is not None and not ann_pat.dropna().empty:
                    ann_pat_latest = float(ann_pat.dropna().iloc[-1])
                    if ann_pat_latest != 0:
                        result.si_ocf_pat_ratio = round(result.si_ocf_annual / ann_pat_latest, 2)
                        # Prefer annual OCF/PAT ratio over quarterly
                        result.ocf_pat_ratio = result.si_ocf_pat_ratio

        # --- Flags ---
        self._apply_flags(result, cfg_g, cfg_p, income_df, cashflow_df, sector=sector)
        result.score = self._compute_score(result, cfg_g, cfg_p, sector=sector)
        return result

    def _apply_flags(
        self,
        result: BasicScreenResult,
        cfg_g: dict,
        cfg_p: dict,
        income_df: pd.DataFrame,
        cashflow_df: Optional[pd.DataFrame],
        sector: Optional[str] = None,
    ) -> None:
        financial = _is_financial(sector)
        # Revenue growth
        if result.revenue_yoy_pct is not None:
            if result.revenue_yoy_pct < 0:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Growth", f"Revenue declining YoY: {result.revenue_yoy_pct:.1f}%"))
            elif result.revenue_yoy_pct < cfg_g["revenue_yoy_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Growth", f"Weak revenue growth YoY: {result.revenue_yoy_pct:.1f}% (min {cfg_g['revenue_yoy_min_pct']}%)"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Growth", f"Revenue growth YoY: {result.revenue_yoy_pct:.1f}%"))

        # PAT growth
        if result.pat_yoy_pct is not None:
            if result.pat_yoy_pct < 0:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Growth", f"PAT declining YoY: {result.pat_yoy_pct:.1f}%"))
            elif result.pat_yoy_pct < cfg_g["pat_yoy_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Growth", f"Weak PAT growth YoY: {result.pat_yoy_pct:.1f}%"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Growth", f"PAT growth YoY: {result.pat_yoy_pct:.1f}%"))

        # EPS growth
        if result.eps_yoy_pct is not None:
            if result.eps_yoy_pct < 0:
                result.flags.append(ScreenFlag(FlagLevel.RED, "EPS", f"EPS declining YoY: {result.eps_yoy_pct:.1f}%"))
            elif result.eps_yoy_pct < cfg_g["eps_yoy_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "EPS", f"EPS growth weak: {result.eps_yoy_pct:.1f}%"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "EPS", f"EPS growth YoY: {result.eps_yoy_pct:.1f}%"))

        # EBITDA margin
        if result.ebitda_margin_latest_pct is not None:
            if result.ebitda_margin_latest_pct < cfg_p["ebitda_margin_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Margin", f"Low EBITDA margin: {result.ebitda_margin_latest_pct:.1f}%"))
        if result.ebitda_margin_trend == "deteriorating":
            result.flags.append(ScreenFlag(FlagLevel.RED, "Margin", "EBITDA margin deteriorating over 8 quarters"))
        elif result.ebitda_margin_trend == "improving":
            result.flags.append(ScreenFlag(FlagLevel.GREEN, "Margin", "EBITDA margin improving trend"))

        # OCF quality — not applicable for financial sector (lending = negative OCF by nature)
        if financial:
            result.flags.append(ScreenFlag(FlagLevel.GREEN, "CashQuality", "Financial sector — OCF/FCF checks not applicable (loan disbursements are operating cash outflows)"))
        else:
            if result.ocf_pat_ratio is not None:
                if result.ocf_pat_ratio < 0:
                    result.flags.append(ScreenFlag(FlagLevel.RED, "CashQuality", f"Negative OCF despite PAT: OCF/PAT = {result.ocf_pat_ratio:.2f}"))
                elif result.ocf_pat_ratio < cfg_p["ocf_pat_ratio_min"]:
                    result.flags.append(ScreenFlag(FlagLevel.YELLOW, "CashQuality", f"Low OCF/PAT ratio: {result.ocf_pat_ratio:.2f} (min {cfg_p['ocf_pat_ratio_min']})"))
                else:
                    result.flags.append(ScreenFlag(FlagLevel.GREEN, "CashQuality", f"Strong OCF quality: {result.ocf_pat_ratio:.2f}x"))

            # PAT rising + OCF declining = earnings quality concern
            if result.pat_yoy_pct is not None and result.pat_yoy_pct > 10:
                ocf_trend_check = result.si_ocf_trend or result.ocf_trend
                if ocf_trend_check == "deteriorating":
                    result.flags.append(ScreenFlag(FlagLevel.RED, "CashQuality", "PAT rising but OCF declining — earnings quality concern"))

            # Negative FCF flag
            if result.si_fcf_annual is not None and result.si_fcf_annual < 0:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "CashQuality", f"Negative FCF: ₹{result.si_fcf_annual:,.0f} Cr — investing more than operating cash generated"))

    def _compute_score(self, result: BasicScreenResult, cfg_g: dict, cfg_p: dict, sector: Optional[str] = None) -> int:
        financial = _is_financial(sector)
        score = 50
        bd: dict = {"growth": 0, "profitability": 0, "cash_quality": 0, "penalties": 0}

        # Revenue growth (max ±15)
        if result.revenue_yoy_pct is not None:
            pts = 15 if result.revenue_yoy_pct >= cfg_g["revenue_yoy_min_pct"] * 2 else \
                   8 if result.revenue_yoy_pct >= cfg_g["revenue_yoy_min_pct"] else \
                   2 if result.revenue_yoy_pct >= 0 else -15
            score += pts
            bd["growth"] += pts

        # PAT growth (max ±15)
        if result.pat_yoy_pct is not None:
            pts = 15 if result.pat_yoy_pct >= cfg_g["pat_yoy_min_pct"] * 2 else \
                   8 if result.pat_yoy_pct >= cfg_g["pat_yoy_min_pct"] else \
                   2 if result.pat_yoy_pct >= 0 else -15
            score += pts
            bd["growth"] += pts

        # EBITDA margin (max ±10)
        if result.ebitda_margin_latest_pct is not None:
            pts = 10 if result.ebitda_margin_latest_pct >= 20 else \
                   5 if result.ebitda_margin_latest_pct >= cfg_p["ebitda_margin_min_pct"] else -5
            score += pts
            bd["profitability"] += pts
        if result.ebitda_margin_trend == "improving":
            score += 5
            bd["profitability"] += 5
        elif result.ebitda_margin_trend == "deteriorating":
            score -= 10
            bd["profitability"] -= 10

        # OCF quality (max ±15) — skipped for financial sector
        if not financial and result.ocf_pat_ratio is not None:
            pts = 10 if result.ocf_pat_ratio >= 1.0 else \
                   5 if result.ocf_pat_ratio >= cfg_p["ocf_pat_ratio_min"] else \
                  -5 if result.ocf_pat_ratio >= 0 else -15
            score += pts
            bd["cash_quality"] += pts

        # Red flag penalties
        red_count = sum(1 for f in result.flags if f.level == FlagLevel.RED)
        penalty = red_count * 5
        score -= penalty
        bd["penalties"] = -penalty

        result.score_breakdown = bd
        return max(0, min(100, score))
