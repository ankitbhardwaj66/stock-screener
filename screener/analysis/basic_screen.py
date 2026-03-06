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
    si_pat_annual: Optional[float] = None      # Annual PAT (used in OCF/PAT ratio)
    si_net_cf_annual: Optional[float] = None  # Net Cash Flow
    si_net_cf_1y_pct: Optional[float] = None  # Net Cash Flow 1Y % change
    si_net_cf_3y_pct: Optional[float] = None  # Net Cash Flow 3Y % change
    si_net_cf_5y_pct: Optional[float] = None  # Net Cash Flow 5Y % change
    si_ocf_trend: Optional[str] = None      # 5yr trend of annual OCF
    si_ocf_pat_ratio: Optional[float] = None  # annual OCF / annual PAT
    # Asset quality — financial sector only
    gross_npa_pct: Optional[float] = None
    gross_npa_1y_chg: Optional[float] = None   # pp change vs 1 year ago
    gross_npa_2y_chg: Optional[float] = None   # pp change vs 2 years ago
    gross_npa_3y_chg: Optional[float] = None   # pp change vs 3 years ago
    net_npa_pct: Optional[float] = None
    net_npa_1y_chg: Optional[float] = None
    net_npa_2y_chg: Optional[float] = None
    net_npa_3y_chg: Optional[float] = None
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


def _si_pct_change(series: pd.Series, periods: int) -> Optional[float]:
    """% change between the latest value and `periods` years ago in a screener.in series."""
    clean = series.dropna()
    if len(clean) < periods + 1:
        return None
    prev, curr = clean.iloc[-(periods + 1)], clean.iloc[-1]
    if prev == 0 or pd.isna(prev) or pd.isna(curr):
        return None
    return round(((curr - prev) / abs(prev)) * 100, 2)


class BasicScreener:
    """Analyses quarterly income/cashflow for basic quality signals."""

    def __init__(self):
        self.cfg = _load_cfg()

    def screen(
        self,
        symbol: str,
        si_quarterly_df: Optional[pd.DataFrame] = None,
        si_annual_df: Optional[pd.DataFrame] = None,
        si_cashflow_df: Optional[pd.DataFrame] = None,
        sector: Optional[str] = None,
    ) -> BasicScreenResult:
        """All financial data from screener.in exclusively."""
        result = BasicScreenResult(symbol=symbol)
        cfg_g = self.cfg["growth"]
        cfg_p = self.cfg["profitability"]

        si_ok = si_quarterly_df is not None and not si_quarterly_df.empty
        ann_ok = si_annual_df is not None and not si_annual_df.empty

        if not si_ok:
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Data", "No screener.in quarterly data available"))
            result.score = 0
            return result

        financial = _is_financial(sector)

        # ── Revenue ────────────────────────────────────────────────────────
        # Banks use "Interest Earned" / "Revenue from operations" instead of "Sales"
        rev_keys = ["Sales", "Revenue from operations", "Revenue"]
        if financial:
            rev_keys = ["Interest Earned", "Interest Income", "Revenue from operations", "Total Income", "Sales", "Revenue"]
        rev = _si_row_series(si_quarterly_df, rev_keys)
        if rev is not None and not rev.dropna().empty:
            result.revenue_latest = float(rev.dropna().iloc[-1]) * 1e7  # Cr → INR
            result.revenue_qoq_pct = _avg_qoq_pct(rev, 5)
            ann_rev = _si_row_series(si_annual_df, rev_keys) if ann_ok else None
            result.revenue_yoy_pct = _avg_qoq_pct(ann_rev, 5) if (ann_rev is not None and not ann_rev.dropna().empty) else _avg_yoy_pct(rev, 5)
            result.revenue_yoy_3y_pct = _avg_qoq_pct(ann_rev, 3) if (ann_rev is not None and not ann_rev.dropna().empty) else _avg_yoy_pct(rev, 3)

        # ── PAT / Net Profit ───────────────────────────────────────────────
        pat_keys = ["Net Profit", "PAT", "Profit after tax"]
        pat = _si_row_series(si_quarterly_df, pat_keys)
        if pat is not None and not pat.dropna().empty:
            result.pat_latest = float(pat.dropna().iloc[-1]) * 1e7  # Cr → INR
            result.pat_qoq_pct = _avg_qoq_pct(pat, 5)
            ann_pat = _si_row_series(si_annual_df, pat_keys) if ann_ok else None
            result.pat_yoy_pct = _avg_qoq_pct(ann_pat, 5) if (ann_pat is not None and not ann_pat.dropna().empty) else _avg_yoy_pct(pat, 5)
            result.pat_yoy_3y_pct = _avg_qoq_pct(ann_pat, 3) if (ann_pat is not None and not ann_pat.dropna().empty) else _avg_yoy_pct(pat, 3)

        # ── EPS ────────────────────────────────────────────────────────────
        eps = _si_row_series(si_quarterly_df, ["EPS in Rs", "EPS"])
        if eps is not None and not eps.dropna().empty:
            result.eps_latest = float(eps.dropna().iloc[-1])
            result.eps_qoq_pct = _avg_qoq_pct(eps, 5)
            ann_eps = _si_row_series(si_annual_df, ["EPS in Rs", "EPS"]) if ann_ok else None
            result.eps_yoy_pct = _avg_qoq_pct(ann_eps, 5) if (ann_eps is not None and not ann_eps.dropna().empty) else _avg_yoy_pct(eps, 5)
            result.eps_yoy_3y_pct = _avg_qoq_pct(ann_eps, 3) if (ann_eps is not None and not ann_eps.dropna().empty) else _avg_yoy_pct(eps, 3)

        # ── EBITDA / Operating margin — screener.in OPM% ──────────────────
        opm_pct = _si_row_series(si_quarterly_df, ["OPM %", "OPM%", "OPM"])
        if opm_pct is not None and not opm_pct.dropna().empty:
            result.ebitda_margin_latest_pct = round(float(opm_pct.dropna().iloc[-1]), 2)
            result.ebitda_margin_trend = _trend(opm_pct, window=8)

        # ── Annual cash flows — screener.in ───────────────────────────────
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
                result.si_net_cf_1y_pct = _si_pct_change(ncf_s, 1)
                result.si_net_cf_3y_pct = _si_pct_change(ncf_s, 3)
                result.si_net_cf_5y_pct = _si_pct_change(ncf_s, 5)
            if result.si_ocf_annual is not None and result.si_icf_annual is not None:
                result.si_fcf_annual = result.si_ocf_annual + result.si_icf_annual

            # OCF/PAT ratio using annual data — more reliable than quarterly
            if ann_ok and result.si_ocf_annual is not None:
                ann_pat = _si_row_series(si_annual_df, ["Net Profit", "PAT", "Profit after tax"])
                if ann_pat is not None and not ann_pat.dropna().empty:
                    ann_pat_latest = float(ann_pat.dropna().iloc[-1])
                    if ann_pat_latest != 0:
                        result.si_pat_annual = ann_pat_latest
                        result.si_ocf_pat_ratio = round(result.si_ocf_annual / ann_pat_latest, 2)
                        # Prefer annual OCF/PAT ratio over quarterly
                        result.ocf_pat_ratio = result.si_ocf_pat_ratio

        # ── NPA (financial sector only) ────────────────────────────────────
        if financial:
            def _npa_chg(series: pd.Series, periods: int) -> Optional[float]:
                """Absolute pp change: latest minus N quarters ago (4Q = 1Y)."""
                s = series.dropna()
                idx = periods * 4  # quarters per year
                if len(s) < idx + 1:
                    return None
                curr, prev = float(s.iloc[-1]), float(s.iloc[-(idx + 1)])
                return round(curr - prev, 2)

            gnpa = _si_row_series(si_quarterly_df, ["Gross NPA"])
            nnpa = _si_row_series(si_quarterly_df, ["Net NPA"])
            if gnpa is not None and not gnpa.dropna().empty:
                result.gross_npa_pct = float(gnpa.dropna().iloc[-1])
                result.gross_npa_1y_chg = _npa_chg(gnpa, 1)
                result.gross_npa_2y_chg = _npa_chg(gnpa, 2)
                result.gross_npa_3y_chg = _npa_chg(gnpa, 3)
            if nnpa is not None and not nnpa.dropna().empty:
                result.net_npa_pct = float(nnpa.dropna().iloc[-1])
                result.net_npa_1y_chg = _npa_chg(nnpa, 1)
                result.net_npa_2y_chg = _npa_chg(nnpa, 2)
                result.net_npa_3y_chg = _npa_chg(nnpa, 3)

        # --- Flags ---
        self._apply_flags(result, cfg_g, cfg_p, sector=sector)
        result.score = self._compute_score(result, cfg_g, cfg_p, sector=sector)
        return result

    def _apply_flags(
        self,
        result: BasicScreenResult,
        cfg_g: dict,
        cfg_p: dict,
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

        # NPA quality — financial sector only
        if financial:
            cfg_fin = self.cfg["financial_sector"] if hasattr(self, 'cfg') else {}
            gnpa_green = cfg_fin.get("gross_npa_green_pct", 3.0)
            gnpa_red   = cfg_fin.get("gross_npa_red_pct", 7.0)
            nnpa_green = cfg_fin.get("net_npa_green_pct", 1.0)
            nnpa_red   = cfg_fin.get("net_npa_red_pct", 3.0)
            if result.gross_npa_pct is not None:
                if result.gross_npa_pct > gnpa_red:
                    result.flags.append(ScreenFlag(FlagLevel.RED, "AssetQuality", f"High Gross NPA: {result.gross_npa_pct:.2f}% (red > {gnpa_red}%)"))
                elif result.gross_npa_pct > gnpa_green:
                    result.flags.append(ScreenFlag(FlagLevel.YELLOW, "AssetQuality", f"Elevated Gross NPA: {result.gross_npa_pct:.2f}% (green < {gnpa_green}%)"))
                else:
                    result.flags.append(ScreenFlag(FlagLevel.GREEN, "AssetQuality", f"Healthy Gross NPA: {result.gross_npa_pct:.2f}%"))
            if result.net_npa_pct is not None:
                if result.net_npa_pct > nnpa_red:
                    result.flags.append(ScreenFlag(FlagLevel.RED, "AssetQuality", f"High Net NPA: {result.net_npa_pct:.2f}% (red > {nnpa_red}%)"))
                elif result.net_npa_pct > nnpa_green:
                    result.flags.append(ScreenFlag(FlagLevel.YELLOW, "AssetQuality", f"Elevated Net NPA: {result.net_npa_pct:.2f}% (green < {nnpa_green}%)"))
                else:
                    result.flags.append(ScreenFlag(FlagLevel.GREEN, "AssetQuality", f"Well provisioned Net NPA: {result.net_npa_pct:.2f}%"))

        # OCF quality — not applicable for financial sector (lending = negative OCF by nature)
        if financial:
            result.flags.append(ScreenFlag(FlagLevel.GREEN, "CashQuality", "Financial sector — OCF/FCF checks not applicable (loan disbursements are operating cash outflows)"))
        else:
            if result.ocf_pat_ratio is not None:
                ocf_trend_check = result.si_ocf_trend or result.ocf_trend
                if result.ocf_pat_ratio < 0:
                    result.flags.append(ScreenFlag(FlagLevel.RED, "CashQuality", f"Negative OCF despite PAT: OCF/PAT = {result.ocf_pat_ratio:.2f}"))
                    if ocf_trend_check == "stable":
                        result.flags.append(ScreenFlag(FlagLevel.RED, "CashQuality", "Chronic negative OCF — has been negative for years, not a temporary dip"))
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

        def _growth_pts(pct5y, pct3y, threshold):
            """Score growth using the worse of 3Y and 5Y averages to avoid masking recent deterioration."""
            candidates = [p for p in (pct5y, pct3y) if p is not None]
            if not candidates:
                return None
            pct = min(candidates)  # penalise if either period is bad
            return (15 if pct >= threshold * 2 else
                     8 if pct >= threshold else
                     2 if pct >= 0 else -15)

        # Revenue growth (max ±15)
        rev_pts = _growth_pts(result.revenue_yoy_pct, result.revenue_yoy_3y_pct, cfg_g["revenue_yoy_min_pct"])
        if rev_pts is not None:
            score += rev_pts
            bd["growth"] += rev_pts

        # PAT growth (max ±15)
        pat_pts = _growth_pts(result.pat_yoy_pct, result.pat_yoy_3y_pct, cfg_g["pat_yoy_min_pct"])
        if pat_pts is not None:
            score += pat_pts
            bd["growth"] += pat_pts

        # EBITDA margin (max ±10) — not applicable for financial sector
        if not financial and result.ebitda_margin_latest_pct is not None:
            pts = 10 if result.ebitda_margin_latest_pct >= 20 else \
                   5 if result.ebitda_margin_latest_pct >= cfg_p["ebitda_margin_min_pct"] else -5
            score += pts
            bd["profitability"] += pts
        if not financial and result.ebitda_margin_trend == "improving":
            score += 5
            bd["profitability"] += 5
        elif not financial and result.ebitda_margin_trend == "deteriorating":
            score -= 10
            bd["profitability"] -= 10

        # NPA scoring — financial sector only (replaces EBITDA margin, max ±20)
        if financial:
            cfg_fin = self.cfg["financial_sector"]
            gnpa_green = cfg_fin.get("gross_npa_green_pct", 3.0)
            gnpa_red   = cfg_fin.get("gross_npa_red_pct", 7.0)
            nnpa_green = cfg_fin.get("net_npa_green_pct", 1.0)
            nnpa_red   = cfg_fin.get("net_npa_red_pct", 3.0)
            if result.gross_npa_pct is not None:
                pts = 10 if result.gross_npa_pct <= gnpa_green else \
                       0 if result.gross_npa_pct <= gnpa_red else -10
                score += pts
                bd["profitability"] += pts
            if result.net_npa_pct is not None:
                pts = 10 if result.net_npa_pct <= nnpa_green else \
                       0 if result.net_npa_pct <= nnpa_red else -10
                score += pts
                bd["profitability"] += pts

        # OCF quality (max ±15) — skipped for financial sector
        if not financial and result.ocf_pat_ratio is not None:
            pts = 10 if result.ocf_pat_ratio >= 1.0 else \
                   5 if result.ocf_pat_ratio >= cfg_p["ocf_pat_ratio_min"] else \
                  -5 if result.ocf_pat_ratio >= 0 else -15
            score += pts
            bd["cash_quality"] += pts
            # Extra penalty for chronic negative OCF (not just a one-off dip)
            ocf_trend_check = result.si_ocf_trend or result.ocf_trend
            if result.ocf_pat_ratio < 0 and ocf_trend_check == "stable":
                score -= 5
                bd["cash_quality"] -= 5

        # Red flag penalties — only for categories NOT already captured in numeric scoring above.
        # Growth (revenue/PAT) and CashQuality (OCF) and Margin are already scored numerically,
        # so we skip their red flags here to avoid double-counting.
        _ALREADY_SCORED = {"Growth", "Margin", "CashQuality", "AssetQuality"}
        red_flags = [f for f in result.flags if f.level == FlagLevel.RED and f.category not in _ALREADY_SCORED]
        penalty = len(red_flags) * 5
        score -= penalty
        bd["penalties"] = -penalty
        bd["penalty_flags"] = [f.message for f in red_flags]

        result.score_breakdown = bd
        return max(0, min(100, score))
