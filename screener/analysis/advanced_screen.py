"""Advanced screener: ROE, ROCE, debt health, promoter/FII activity, valuations."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import math

import pandas as pd
import yaml

from screener.analysis.basic_screen import FlagLevel, ScreenFlag, _is_financial


def _load_cfg() -> dict:
    return yaml.safe_load(
        (Path(__file__).parent.parent.parent / "config" / "thresholds.yaml").read_text()
    )


@dataclass
class AdvancedScreenResult:
    symbol: str
    # Profitability ratios
    roe_pct: Optional[float] = None
    roce_pct: Optional[float] = None
    # Debt health
    de_ratio: Optional[float] = None
    interest_coverage: Optional[float] = None
    net_debt_to_ebitda: Optional[float] = None
    # Valuation
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    peg_ratio: Optional[float] = None
    # Shareholding
    promoter_holding_pct: Optional[float] = None
    promoter_pledge_pct: Optional[float] = None
    promoter_holding_delta: Optional[float] = None      # QoQ
    promoter_holding_6q_delta: Optional[float] = None  # 6-quarter change
    pledge_delta: Optional[float] = None
    pledge_6q_delta: Optional[float] = None
    fii_holding_pct: Optional[float] = None
    fii_holding_delta: Optional[float] = None           # QoQ
    fii_holding_6q_delta: Optional[float] = None       # 6-quarter change
    dii_holding_pct: Optional[float] = None
    dii_holding_delta: Optional[float] = None           # QoQ
    dii_holding_6q_delta: Optional[float] = None       # 6-quarter change
    public_holding_pct: Optional[float] = None
    public_holding_delta: Optional[float] = None        # QoQ
    public_holding_6q_delta: Optional[float] = None    # 6-quarter change
    # Working capital
    debtor_days: Optional[float] = None
    inventory_days: Optional[float] = None
    days_payable: Optional[float] = None
    cash_conversion_cycle: Optional[float] = None
    # FCF
    fcf_latest: Optional[float] = None
    fcf_trend: Optional[str] = None
    revenue_quality_score: Optional[float] = None  # 0-10
    # Cash Equivalents trend — screener.in balance sheet (₹ Cr)
    si_cash_equivalents: Optional[float] = None
    si_cash_eq_1y_pct: Optional[float] = None
    si_cash_eq_3y_pct: Optional[float] = None
    si_cash_eq_5y_pct: Optional[float] = None
    # Debt quality — screener.in balance sheet (₹ Cr)
    si_long_term_borrowings: Optional[float] = None
    si_short_term_borrowings: Optional[float] = None
    si_total_borrowings: Optional[float] = None
    si_borrowings_1y_pct: Optional[float] = None
    si_borrowings_3y_pct: Optional[float] = None
    si_borrowings_5y_pct: Optional[float] = None
    # Historical PE — 1Y
    pe_mean_historical: Optional[float] = None
    pe_median_historical: Optional[float] = None
    pe_min_historical: Optional[float] = None
    pe_max_historical: Optional[float] = None
    pe_periods: Optional[int] = None
    # Historical PE — 5Y
    pe_mean_5y: Optional[float] = None
    pe_median_5y: Optional[float] = None
    pe_min_5y: Optional[float] = None
    pe_max_5y: Optional[float] = None
    pe_periods_5y: Optional[int] = None
    # Historical PE — 10Y
    pe_mean_10y: Optional[float] = None
    pe_median_10y: Optional[float] = None
    pe_min_10y: Optional[float] = None
    pe_max_10y: Optional[float] = None
    pe_periods_10y: Optional[int] = None
    # Flags
    flags: list[ScreenFlag] = field(default_factory=list)
    red_flag_count: int = 0
    score: int = 0
    score_breakdown: dict = field(default_factory=dict)  # section → points


def _last_val(series: pd.Series) -> Optional[float]:
    s = series.apply(pd.to_numeric, errors="coerce").dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _pct_change_periods(series: pd.Series, periods: int) -> Optional[float]:
    """% change between last value and `periods` quarters ago."""
    s = series.apply(pd.to_numeric, errors="coerce").dropna()
    if len(s) < periods + 1:
        return None
    prev = s.iloc[-(periods + 1)]
    curr = s.iloc[-1]
    if prev == 0 or pd.isna(prev) or pd.isna(curr):
        return None
    return round(((curr - prev) / abs(prev)) * 100, 2)


def _trend(series: pd.Series, window: int = 4) -> str:
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



class AdvancedScreener:
    """Analyses debt, promoter/FII activity, valuations, working capital."""

    def __init__(self):
        self.cfg = _load_cfg()

    def screen(
        self,
        symbol: str,
        price_info: Optional[dict],
        shareholding: Optional[dict],
        si_ratios: Optional[dict],
        historical_pe: Optional[dict] = None,
        si_wc_ratios: Optional[dict] = None,
        si_balance_df: Optional[pd.DataFrame] = None,
        si_annual_df: Optional[pd.DataFrame] = None,
        sector: Optional[str] = None,
        eps_yoy_pct: Optional[float] = None,
        pat_yoy_pct: Optional[float] = None,
    ) -> AdvancedScreenResult:
        result = AdvancedScreenResult(symbol=symbol)
        financial = _is_financial(sector)
        # financial_sector overrides only the keys it defines; missing keys fall back to debt config
        cfg_d = {**self.cfg["debt"], **(self.cfg["financial_sector"] if financial else {})}
        cfg_v = self.cfg["valuation"]
        cfg_s = self.cfg["shareholding"]

        self._fill_ratios(result, price_info, si_ratios)
        # PEG = P/E / growth rate — use max(EPS, PAT) to avoid dilution distortion
        growth_for_peg = max(v for v in [eps_yoy_pct, pat_yoy_pct] if v is not None and v > 0) if any(v is not None and v > 0 for v in [eps_yoy_pct, pat_yoy_pct]) else None
        if result.pe_ratio and result.pe_ratio > 0 and growth_for_peg:
            result.peg_ratio = round(result.pe_ratio / growth_for_peg, 2)
        self._fill_debt_from_si(result, si_ratios, si_balance_df, si_annual_df, financial)
        self._fill_balance_sheet_si(result, si_balance_df)
        self._fill_shareholding(result, shareholding)
        self._fill_working_capital_from_si(result, si_wc_ratios)
        self._fill_fcf_from_si(result, si_balance_df)
        self._fill_historical_pe(result, historical_pe)
        self._apply_flags(result, cfg_d, cfg_v, cfg_s)
        result.red_flag_count = sum(1 for f in result.flags if f.level == FlagLevel.RED)
        result.score = self._compute_score(result, cfg_d, cfg_v, cfg_s)
        return result

    def _fill_ratios(self, result: AdvancedScreenResult, price_info: Optional[dict], si_ratios: Optional[dict]) -> None:
        """Fill ratios from screener.in first, fall back to yfinance."""
        if si_ratios:
            roe = si_ratios.get("roe")
            roce = si_ratios.get("roce")
            result.roe_pct = None if (roe is None or (isinstance(roe, float) and math.isnan(roe))) else roe
            result.roce_pct = None if (roce is None or (isinstance(roce, float) and math.isnan(roce))) else roce
            def _clean(v):
                return None if (v is None or (isinstance(v, float) and math.isnan(v))) else v
            result.pe_ratio = _clean(si_ratios.get("pe"))
            result.pb_ratio = _clean(si_ratios.get("pb"))
            result.de_ratio = _clean(si_ratios.get("de_ratio"))

        # Fill gaps from price_info (yfinance)
        if price_info:
            if result.pe_ratio is None:
                result.pe_ratio = price_info.get("pe_ratio")
            if result.pb_ratio is None:
                result.pb_ratio = price_info.get("pb_ratio")

    def _fill_debt_from_si(
        self,
        result: AdvancedScreenResult,
        si_ratios: Optional[dict],
        si_balance_df: Optional[pd.DataFrame],
        si_annual_df: Optional[pd.DataFrame],
        financial: bool,
    ) -> None:
        """Compute debt metrics entirely from screener.in data."""
        from screener.analysis.basic_screen import _si_clean, _si_row_series

        # D/E already filled from si_ratios in _fill_ratios — nothing extra needed

        if si_annual_df is None or si_annual_df.empty:
            return

        # Operating Profit = EBITDA proxy (screener.in annual P&L)
        op_s = _si_row_series(si_annual_df, ["Operating Profit", "EBITDA"])
        interest_s = _si_row_series(si_annual_df, ["Interest"])

        annual_ebitda = None
        if op_s is not None and not op_s.dropna().empty:
            annual_ebitda = float(op_s.dropna().iloc[-1])  # Cr

        # Interest Coverage = Operating Profit / Interest
        if interest_s is not None and not interest_s.dropna().empty:
            last_interest = float(interest_s.dropna().iloc[-1])
            if last_interest and last_interest > 0 and annual_ebitda is not None and annual_ebitda > 0:
                result.interest_coverage = round(annual_ebitda / last_interest, 2)

        # Net Debt / EBITDA — use Borrowings from balance sheet
        if si_balance_df is not None and not si_balance_df.empty and annual_ebitda:
            bor_s = _si_row_series(si_balance_df, ["Borrowings"])
            if bor_s is not None and not bor_s.dropna().empty:
                borrowings_cr = float(bor_s.dropna().iloc[-1])
                result.net_debt_to_ebitda = round(borrowings_cr / annual_ebitda, 2)

    def _fill_shareholding(self, result: AdvancedScreenResult, shareholding: Optional[dict]) -> None:
        if not shareholding:
            return
        result.promoter_holding_pct = shareholding.get("promoter_pct")
        result.promoter_holding_delta = shareholding.get("promoter_delta")
        result.promoter_holding_6q_delta = shareholding.get("promoter_6q_delta")
        result.promoter_pledge_pct = shareholding.get("promoter_pledge_pct")
        result.pledge_delta = shareholding.get("pledge_delta")
        result.pledge_6q_delta = shareholding.get("pledge_6q_delta")
        result.fii_holding_pct = shareholding.get("fii_pct")
        result.fii_holding_delta = shareholding.get("fii_delta")
        result.fii_holding_6q_delta = shareholding.get("fii_6q_delta")
        result.dii_holding_pct = shareholding.get("dii_pct")
        result.dii_holding_delta = shareholding.get("dii_delta")
        result.dii_holding_6q_delta = shareholding.get("dii_6q_delta")
        result.public_holding_pct = shareholding.get("public_pct")
        result.public_holding_delta = shareholding.get("public_delta")
        result.public_holding_6q_delta = shareholding.get("public_6q_delta")

    def _fill_working_capital_from_si(
        self, result: AdvancedScreenResult, si_wc: Optional[dict]
    ) -> None:
        """Override working capital fields with screener.in annual Ratios data (authoritative)."""
        if not si_wc:
            return
        if si_wc.get("debtor_days") is not None:
            result.debtor_days = si_wc["debtor_days"]
        if si_wc.get("inventory_days") is not None:
            result.inventory_days = si_wc["inventory_days"]
        if si_wc.get("days_payable") is not None:
            result.days_payable = si_wc["days_payable"]
        if si_wc.get("ccc") is not None:
            result.cash_conversion_cycle = si_wc["ccc"]

    def _fill_balance_sheet_si(
        self, result: AdvancedScreenResult, si_balance_df: Optional[pd.DataFrame]
    ) -> None:
        """Parse Cash Equivalents and Borrowings (LT/ST) from screener.in balance sheet (₹ Cr)."""
        if si_balance_df is None or si_balance_df.empty:
            return

        from screener.analysis.basic_screen import _si_clean

        cols = list(si_balance_df.columns)
        end = len(cols) - 1 if str(cols[-1]).strip().upper() == "TTM" else len(cols)

        def _row_series(keywords: list[str], exact: bool = False) -> Optional[pd.Series]:
            for _, row in si_balance_df.iterrows():
                label = str(row.iloc[0]).lower().strip()
                match = (label in [k.lower() for k in keywords]) if exact else any(kw.lower() in label for kw in keywords)
                if match:
                    vals = [_si_clean(row.iloc[i]) for i in range(1, end)]
                    return pd.Series(vals, dtype=float)
            return None

        def _annual_pct(s: pd.Series, periods: int) -> Optional[float]:
            clean = s.dropna()
            if len(clean) < periods + 1:
                return None
            prev, curr = clean.iloc[-(periods + 1)], clean.iloc[-1]
            if prev == 0 or pd.isna(prev) or pd.isna(curr):
                return None
            return round(((curr - prev) / abs(prev)) * 100, 2)

        def _latest(s: Optional[pd.Series]) -> Optional[float]:
            if s is None:
                return None
            c = s.dropna()
            return float(c.iloc[-1]) if not c.empty else None

        # Cash Equivalents (sub-row under Other Assets on screener.in)
        cash_s = _row_series(["Cash Equivalents", "Cash and Cash Equivalents", "Cash & Cash Equivalents", "Cash equivalents"])
        if cash_s is not None and not cash_s.dropna().empty:
            result.si_cash_equivalents = _latest(cash_s)
            result.si_cash_eq_1y_pct = _annual_pct(cash_s, 1)
            result.si_cash_eq_3y_pct = _annual_pct(cash_s, 3)
            result.si_cash_eq_5y_pct = _annual_pct(cash_s, 5)

        # Total Borrowings (parent row — label is "Borrowings+" in screener.in)
        total_bor_s = _row_series(["Borrowings+"], exact=True)
        if total_bor_s is None:
            total_bor_s = _row_series(["Total Borrowings", "Total Debt"])
        # Long-term and Short-term sub-rows
        lt_s = _row_series(["Long term Borrowings", "Long Term Borrowing", "Long-term Borrowing"])
        st_s = _row_series(["Short term Borrowings", "Short Term Borrowing", "Short-term Borrowing"])

        if total_bor_s is not None and not total_bor_s.dropna().empty:
            result.si_total_borrowings = _latest(total_bor_s)
            result.si_borrowings_1y_pct = _annual_pct(total_bor_s, 1)
            result.si_borrowings_3y_pct = _annual_pct(total_bor_s, 3)
            result.si_borrowings_5y_pct = _annual_pct(total_bor_s, 5)

        result.si_long_term_borrowings = _latest(lt_s)
        result.si_short_term_borrowings = _latest(st_s)

        # Compute D/E ratio from balance sheet if not already set from si_ratios
        if result.de_ratio is None and result.si_total_borrowings is not None:
            eq_cap_s = _row_series(["Equity Capital", "Share Capital"])
            reserves_s = _row_series(["Reserves"])
            eq_cap = _latest(eq_cap_s) or 0.0
            reserves = _latest(reserves_s) or 0.0
            equity = eq_cap + reserves
            if equity > 0:
                result.de_ratio = round(result.si_total_borrowings / equity, 2)

    def _fill_fcf_from_si(self, result: AdvancedScreenResult, si_balance_df: Optional[pd.DataFrame]) -> None:
        """FCF latest value is passed via BasicScreenResult.si_fcf_annual — set at call site in screen()."""
        # FCF is already available on BasicScreenResult.si_fcf_annual (OCF + ICF from screener.in).
        # Nothing to compute here — fcf_latest/fcf_trend are populated by the caller if needed.
        pass

    def _fill_historical_pe(self, result: AdvancedScreenResult, historical_pe: Optional[dict]) -> None:
        if not historical_pe:
            return
        result.pe_mean_historical = historical_pe.get("mean_pe")
        result.pe_median_historical = historical_pe.get("median_pe")
        result.pe_min_historical = historical_pe.get("min_pe")
        result.pe_max_historical = historical_pe.get("max_pe")
        result.pe_periods = historical_pe.get("periods")
        result.pe_mean_5y = historical_pe.get("mean_pe_5y")
        result.pe_median_5y = historical_pe.get("median_pe_5y")
        result.pe_min_5y = historical_pe.get("min_pe_5y")
        result.pe_max_5y = historical_pe.get("max_pe_5y")
        result.pe_periods_5y = historical_pe.get("periods_5y")
        result.pe_mean_10y = historical_pe.get("mean_pe_10y")
        result.pe_median_10y = historical_pe.get("median_pe_10y")
        result.pe_min_10y = historical_pe.get("min_pe_10y")
        result.pe_max_10y = historical_pe.get("max_pe_10y")
        result.pe_periods_10y = historical_pe.get("periods_10y")

    def _apply_flags(
        self,
        result: AdvancedScreenResult,
        cfg_d: dict,
        cfg_v: dict,
        cfg_s: dict,
    ) -> None:
        # --- Debt flags ---
        if result.de_ratio is not None:
            if result.de_ratio > cfg_d["de_ratio_red"]:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Debt", f"Very high D/E ratio: {result.de_ratio:.2f}x (alert > {cfg_d['de_ratio_red']}x)"))
            elif result.de_ratio > cfg_d["de_ratio_max"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Debt", f"Elevated D/E ratio: {result.de_ratio:.2f}x (max {cfg_d['de_ratio_max']}x)"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Debt", f"Healthy D/E ratio: {result.de_ratio:.2f}x"))

        if result.interest_coverage is not None:
            if result.interest_coverage < cfg_d["interest_coverage_red"]:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Debt", f"Critical interest coverage: {result.interest_coverage:.2f}x (min {cfg_d['interest_coverage_red']}x)"))
            elif result.interest_coverage < cfg_d["interest_coverage_min"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Debt", f"Low interest coverage: {result.interest_coverage:.2f}x (min {cfg_d['interest_coverage_min']}x)"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Debt", f"Good interest coverage: {result.interest_coverage:.2f}x"))

        if result.net_debt_to_ebitda is not None and result.net_debt_to_ebitda > cfg_d["net_debt_ebitda_max"]:
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Debt", f"High Net Debt/EBITDA: {result.net_debt_to_ebitda:.2f}x (max {cfg_d['net_debt_ebitda_max']}x)"))

        # --- ROE/ROCE flags ---
        cfg_prof = self.cfg["profitability"]
        if result.roe_pct is not None:
            if result.roe_pct < cfg_prof["roe_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Profitability", f"Low ROE: {result.roe_pct:.1f}% (min {cfg_prof['roe_min_pct']}%)"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Profitability", f"Strong ROE: {result.roe_pct:.1f}%"))

        if result.roce_pct is not None:
            if result.roce_pct < cfg_prof["roce_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Profitability", f"Low ROCE: {result.roce_pct:.1f}% (min {cfg_prof['roce_min_pct']}%)"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Profitability", f"Strong ROCE: {result.roce_pct:.1f}%"))

        # --- Promoter flags ---
        if result.promoter_pledge_pct is not None:
            if result.promoter_pledge_pct > cfg_s["promoter_pledge_red_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Promoter", f"Very high promoter pledge: {result.promoter_pledge_pct:.1f}% (alert > {cfg_s['promoter_pledge_red_pct']}%)"))
            elif result.promoter_pledge_pct > cfg_s["promoter_pledge_max_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Promoter", f"Elevated promoter pledge: {result.promoter_pledge_pct:.1f}%"))

        if result.pledge_delta is not None and result.pledge_delta > cfg_s["promoter_pledge_increase_alert"]:
            result.flags.append(ScreenFlag(FlagLevel.RED, "Promoter", f"Promoter pledge increased QoQ: +{result.pledge_delta:.1f}%"))

        if result.promoter_holding_delta is not None:
            if result.promoter_holding_delta < -cfg_s["promoter_holding_decrease_alert"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Promoter", f"Promoter reducing stake: {result.promoter_holding_delta:.1f}% QoQ"))
            elif result.promoter_holding_delta > 0:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Promoter", f"Promoter increasing stake: +{result.promoter_holding_delta:.1f}% QoQ"))

        # FII activity
        if result.fii_holding_delta is not None:
            if result.fii_holding_delta >= cfg_s["fii_increase_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Institutional", f"FII buying: +{result.fii_holding_delta:.1f}% QoQ"))
            elif result.fii_holding_delta <= -cfg_s["fii_increase_min_pct"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Institutional", f"FII selling: {result.fii_holding_delta:.1f}% QoQ"))

        # --- Valuation flags ---
        # P/E vs 5Y historical mean — flag matches scoring buckets
        pe_mean_ref = result.pe_mean_5y or result.pe_mean_historical
        if result.pe_ratio and result.pe_ratio > 0 and pe_mean_ref and pe_mean_ref > 0:
            ratio = result.pe_ratio / pe_mean_ref
            pct_above = (ratio - 1) * 100
            if ratio < 0.70:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Valuation",
                    f"P/E {result.pe_ratio:.1f}x is {abs(pct_above):.0f}% below 5Y mean {pe_mean_ref:.1f}x — historically cheap"))
            elif ratio < 0.90:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Valuation",
                    f"P/E {result.pe_ratio:.1f}x is below 5Y mean {pe_mean_ref:.1f}x"))
            elif ratio <= 1.15:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Valuation",
                    f"P/E {result.pe_ratio:.1f}x near 5Y mean {pe_mean_ref:.1f}x"))
            elif ratio <= 1.40:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Valuation",
                    f"P/E {result.pe_ratio:.1f}x is {pct_above:.0f}% above 5Y mean {pe_mean_ref:.1f}x — expensive vs history"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Valuation",
                    f"P/E {result.pe_ratio:.1f}x is {pct_above:.0f}% above 5Y mean {pe_mean_ref:.1f}x — very expensive vs history"))
        elif result.pe_ratio and result.pe_ratio > 0:
            # No historical mean available — just show absolute P/E level
            if result.pe_ratio < cfg_v["pe_max"]:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Valuation", f"P/E {result.pe_ratio:.1f}x — below {cfg_v['pe_max']}x threshold"))
            elif result.pe_ratio < cfg_v["pe_red"]:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Valuation", f"P/E {result.pe_ratio:.1f}x — elevated (max {cfg_v['pe_max']}x)"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Valuation", f"P/E {result.pe_ratio:.1f}x — very expensive (red > {cfg_v['pe_red']}x)"))

        if result.pb_ratio is not None and result.pb_ratio > cfg_v["pb_max"]:
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Valuation", f"High P/B: {result.pb_ratio:.1f}x (max {cfg_v['pb_max']}x)"))

        if result.ev_ebitda is not None and result.ev_ebitda > cfg_v["ev_ebitda_max"]:
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Valuation", f"High EV/EBITDA: {result.ev_ebitda:.1f}x (max {cfg_v['ev_ebitda_max']}x)"))

        if result.peg_ratio is not None:
            peg_max = cfg_v["peg_max"]
            if result.peg_ratio < 0.75:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Valuation", f"PEG {result.peg_ratio:.2f} — growth on sale (< 0.75)"))
            elif result.peg_ratio <= peg_max:
                result.flags.append(ScreenFlag(FlagLevel.GREEN, "Valuation", f"PEG {result.peg_ratio:.2f} — fair value vs growth"))
            elif result.peg_ratio <= 2.5:
                result.flags.append(ScreenFlag(FlagLevel.YELLOW, "Valuation", f"PEG {result.peg_ratio:.2f} — expensive relative to growth (max {peg_max})"))
            else:
                result.flags.append(ScreenFlag(FlagLevel.RED, "Valuation", f"PEG {result.peg_ratio:.2f} — very expensive vs growth"))


        # --- FCF flags ---
        if result.fcf_latest is not None and result.fcf_latest < 0:
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "CashFlow", "Negative FCF in latest quarter"))
        if result.fcf_trend == "deteriorating":
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "CashFlow", "FCF trend deteriorating"))
        elif result.fcf_trend == "improving":
            result.flags.append(ScreenFlag(FlagLevel.GREEN, "CashFlow", "FCF trend improving"))

        # --- Working capital deterioration ---
        cfg_wc = self.cfg["working_capital"]
        if result.debtor_days is not None and result.debtor_days > cfg_wc["debtor_days_max"]:
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "WorkingCapital", f"High debtor days: {result.debtor_days:.0f} (max {cfg_wc['debtor_days_max']})"))
        if result.inventory_days is not None and result.inventory_days > cfg_wc["inventory_days_max"]:
            result.flags.append(ScreenFlag(FlagLevel.YELLOW, "WorkingCapital", f"High inventory days: {result.inventory_days:.0f} (max {cfg_wc['inventory_days_max']})"))

    def _compute_score(
        self,
        result: AdvancedScreenResult,
        cfg_d: dict,
        cfg_v: dict,
        cfg_s: dict,
    ) -> int:
        cfg_prof = self.cfg["profitability"]
        score = 50
        bd: dict = {"profitability": 0, "debt": 0, "shareholding": 0, "valuation": 0, "penalties": 0}

        # ROE (max ±10)
        if result.roe_pct is not None:
            pts = 10 if result.roe_pct >= cfg_prof["roe_min_pct"] * 2 else \
                   5 if result.roe_pct >= cfg_prof["roe_min_pct"] else -5
            score += pts
            bd["profitability"] += pts

        # ROCE (max ±8)
        if result.roce_pct is not None:
            pts = 8 if result.roce_pct >= cfg_prof["roce_min_pct"] * 2 else \
                  4 if result.roce_pct >= cfg_prof["roce_min_pct"] else -4
            score += pts
            bd["profitability"] += pts

        # D/E ratio (max ±12)
        if result.de_ratio is not None:
            pts = 12 if result.de_ratio < 0.5 else \
                   6 if result.de_ratio < cfg_d["de_ratio_max"] else \
                  -6 if result.de_ratio < cfg_d["de_ratio_red"] else -12
            score += pts
            bd["debt"] += pts

        # Interest coverage (max ±6)
        if result.interest_coverage is not None:
            pts = 6 if result.interest_coverage >= cfg_d.get("interest_coverage_min", 3) * 2 else \
                  3 if result.interest_coverage >= cfg_d.get("interest_coverage_min", 3) else -6
            score += pts
            bd["debt"] += pts

        # FCF (max ±5)
        if result.fcf_latest is not None:
            pts = 5 if result.fcf_latest > 0 else -5
            score += pts
            bd["debt"] += pts

        # Promoter pledge (max ±10)
        if result.promoter_pledge_pct is not None:
            pts = 5 if result.promoter_pledge_pct == 0 else \
                  2 if result.promoter_pledge_pct <= cfg_s["promoter_pledge_max_pct"] else \
                 -5 if result.promoter_pledge_pct <= cfg_s["promoter_pledge_red_pct"] else -10
            score += pts
            bd["shareholding"] += pts
        if result.pledge_delta and result.pledge_delta > cfg_s["promoter_pledge_increase_alert"]:
            score -= 10
            bd["shareholding"] -= 10

        # Promoter holding QoQ (max ±8)
        if result.promoter_holding_delta is not None:
            pts = 6 if result.promoter_holding_delta > 1.0 else \
                  2 if result.promoter_holding_delta > 0 else \
                 -8 if result.promoter_holding_delta < -cfg_s["promoter_holding_decrease_alert"] else -3
            score += pts
            bd["shareholding"] += pts
        # 6Q trend reinforces signal
        if result.promoter_holding_6q_delta is not None:
            pts = 2 if result.promoter_holding_6q_delta > 2.0 else \
                 -2 if result.promoter_holding_6q_delta < -3.0 else 0
            score += pts
            bd["shareholding"] += pts

        # FII activity (max ±6)
        if result.fii_holding_delta is not None:
            pts = 6 if result.fii_holding_delta >= cfg_s["fii_increase_min_pct"] * 2 else \
                  3 if result.fii_holding_delta >= cfg_s["fii_increase_min_pct"] else \
                 -6 if result.fii_holding_delta <= -cfg_s["fii_increase_min_pct"] * 2 else \
                 -3 if result.fii_holding_delta <= -cfg_s["fii_increase_min_pct"] else 0
            score += pts
            bd["shareholding"] += pts
        # DII (max ±3)
        if result.dii_holding_delta is not None:
            pts = 3 if result.dii_holding_delta >= cfg_s["fii_increase_min_pct"] else \
                 -3 if result.dii_holding_delta <= -cfg_s["fii_increase_min_pct"] else 0
            score += pts
            bd["shareholding"] += pts

        # PEG ratio (max ±6)
        if result.peg_ratio is not None and result.peg_ratio > 0:
            pts = 6 if result.peg_ratio < 0.75 else \
                  3 if result.peg_ratio <= cfg_v["peg_max"] else \
                 -4 if result.peg_ratio <= 2.5 else -6
            score += pts
            bd["valuation"] += pts

        # Historical P/E vs mean (max ±8)
        pe_mean_ref = result.pe_mean_5y or result.pe_mean_historical
        if result.pe_ratio and result.pe_ratio > 0 and pe_mean_ref and pe_mean_ref > 0:
            ratio = result.pe_ratio / pe_mean_ref
            pts = 8 if ratio < 0.70 else \
                  4 if ratio < 0.90 else \
                  0 if ratio <= 1.15 else \
                 -4 if ratio <= 1.40 else -8
            score += pts
            bd["valuation"] += pts

        # Red flag penalty
        red_flags = [f for f in result.flags if f.level == FlagLevel.RED]
        penalty = result.red_flag_count * self.cfg["scoring"]["weights"]["red_flag_penalty"] * -1
        score -= penalty
        bd["penalties"] = -penalty
        bd["penalty_flags"] = [f.message for f in red_flags]

        result.score_breakdown = bd
        return max(0, min(100, score))
