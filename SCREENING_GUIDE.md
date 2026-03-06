# Indian Stock Screening Guide — Quarterly Audit Reference

A standalone reference for evaluating Indian listed companies each quarter. Use this alongside the CLI tool or independently for manual analysis.

---

## Table of Contents

1. [Quarterly P&L Quality](#1-quarterly-pl-quality)
2. [Debt Health Analysis](#2-debt-health-analysis)
3. [Promoter & Institutional Activity](#3-promoter--institutional-activity)
4. [Valuation Ratios](#4-valuation-ratios)
5. [Red Flag Checklist](#5-red-flag-checklist)
6. [Sector-Specific Notes](#6-sector-specific-notes)
7. [Quantitative Scorecard — CLI Scoring Reference](#7-quantitative-scorecard--cli-scoring-reference)

---

## 1. Quarterly P&L Quality

### 1.1 Revenue (Net Sales)

| Signal | Threshold | Action |
|--------|-----------|--------|
| Strong growth | YoY > 15% | Positive |
| Acceptable growth | YoY 10–15% | Neutral |
| Weak growth | YoY 0–10% | Watch |
| Revenue decline | YoY < 0% | RED FLAG |
| Revenue recognition change | Note in results | Investigate |

**Key checks:**
- Compare standalone vs consolidated revenue — large divergence can hide holding company losses
- Check if growth is organic or acquisition-driven (check balance sheet for goodwill spike)
- Revenue with rising debtors = possible channel stuffing

**CLI shows three growth views:** Avg QoQ % (5Q), Avg YoY % (3Y), Avg YoY % (5Y).
The 3Y vs 5Y comparison is key — if 3Y is accelerating above 5Y, growth is picking up; if 3Y is below 5Y, growth is fading.

### 1.2 EBITDA Margin

EBITDA = Operating Profit before depreciation, interest, and tax.

| Signal | Threshold |
|--------|-----------|
| High-quality | Margin > 20% |
| Acceptable | Margin 10–20% |
| Low quality | Margin < 10% |
| Deteriorating | 8-quarter declining trend |

**Calculation:** `EBITDA Margin = EBITDA / Net Sales × 100`

Watch for: margins recovering only due to cost cuts (not revenue growth) — unsustainable.

> **Note for financial companies (NBFCs, banks, HFCs):** The EBITDA margin shown is OPM% from screener.in, which for financial companies reflects the spread/NIM, not traditional EBITDA. Values of 70–90% are normal and expected.

### 1.3 PAT (Profit After Tax)

PAT quality matters more than PAT quantum.

**Key checks:**
- **Exceptional items**: Strip them out. Compare recurring PAT YoY.
- **Other income**: If "Other Income" > 20% of PBT, the business may not be generating real operating profit.
- **Tax rate anomalies**: Unusually low effective tax rate (<15%) — check for deferred tax assets or one-time exemptions.
- **Minority interest**: In consolidated results, large minority interest deductions can distort PAT picture.

### 1.4 EPS (Earnings Per Share)

- Use **Diluted EPS** for proper comparison (accounts for warrants, ESOPs)
- EPS declining despite PAT rising → check for fresh equity dilution (QIP, rights issue, ESOPs)
- If PAT YoY (5Y) >> EPS YoY (5Y), the company has significantly diluted shares over 5 years
- Consistent EPS growth of 15%+ YoY over 4+ quarters = quality signal

### 1.5 Operating Cash Flow (OCF) Quality

**The most important number that analysts overlook.**

```
OCF/PAT Ratio = Operating Cash Flow / Net Profit After Tax
```

| Ratio | Interpretation |
|-------|----------------|
| > 1.0 | Excellent — company collecting more cash than it reports as profit |
| 0.75–1.0 | Good |
| 0.5–0.75 | Mediocre — watch receivables |
| < 0.5 | Poor — profits may be paper gains |
| < 0 | RED FLAG — negative OCF despite positive PAT |

**OCF declining while PAT rising** = one of the strongest red flags in Indian markets. Classic signs of:
- Aggressive revenue recognition
- Rising debtors (customers not paying)
- Inventory pile-up
- Related party transactions inflating paper profits

**CLI shows** the OCF/PAT ratio with the actual annual figures used `(OCF -81 / PAT 107 Cr)`, a **5-year trend direction** (improving ↑ / stable → / deteriorating ↓), and a ✓/✗ pass/fail check.

> **Important:** The OCF/PAT ratio always uses **annual** OCF and **annual** PAT (full fiscal year). The "Latest Value" column in Growth Metrics shows the most recent **quarterly** PAT, which will be ~¼ of the annual figure. Do not confuse the two when verifying the ratio manually.

> **⚠ Financial sector exception:** For banks, NBFCs, HFCs, and insurance companies, negative OCF is **normal and expected**. Loan disbursements are classified as operating cash outflows under accounting standards. The CLI automatically detects financial sector companies and skips the OCF/PAT check entirely for them. A `[GREEN] CashQuality: Financial sector — OCF/FCF checks not applicable` flag will appear in the output.

---

## 2. Debt Health Analysis

### 3.1 Key Debt Ratios

**Debt/Equity Ratio (D/E)**
```
D/E = Total Borrowings / (Equity Capital + Reserves)
```

> **CLI data source:** D/E is taken from screener.in's top ratios panel when available. If not shown there (screener.in omits it for some stocks), it is computed directly from the balance sheet as `Borrowings / (Equity Capital + Reserves)`.


| D/E | Signal | Note |
|-----|--------|------|
| < 0.5 | Debt-free / very low debt | |
| 0.5–1.0 | Conservative | |
| 1.0–2.0 | Moderate — monitor | |
| > 2.0 | HIGH RISK | |
| > 3.0 | RED FLAG | Except banks/NBFCs |

> **Financial sector D/E thresholds (CLI):** NBFCs and HFCs have leverage as a core business requirement. The CLI uses relaxed thresholds: ≤ 5.0x = acceptable, > 8.0x = red flag. D/E of 1.5–4x is typical and healthy for well-run NBFCs.

**Interest Coverage Ratio (ICR)**
```
ICR = EBIT / Interest Expense
```

| ICR | Signal |
|-----|--------|
| > 5x | Very safe |
| 3–5x | Comfortable |
| 1.5–3x | Caution |
| < 1.5x | RED FLAG — barely covering interest |
| < 1.0x | CRITICAL — interest not covered |

**Net Debt / EBITDA**
```
Net Debt = Total Debt − Cash & Equivalents
Net Debt/EBITDA = Net Debt / Annual EBITDA
```

| Ratio | Signal |
|-------|--------|
| < 1x | Very comfortable |
| 1–2x | Manageable |
| 2–3x | Watch |
| > 3x | Concerning |
| > 5x | RED FLAG |

> **Tip:** A company can have a low D/E but high Net Debt/EBITDA if earnings are thin relative to debt. Check both. The D/E looks at asset cover; Net Debt/EBITDA measures how many years of operating profit to repay debt.

### 3.2 Debt Quality Checks

- **Short-term vs Long-term debt**: High short-term debt (CP, working capital loans) in a rising interest rate cycle = refinancing risk
- **Debt vs Revenue growth**: Debt growing faster than revenue = leverage without proportionate growth
- **Debt for capex vs operations**: Debt taken for capacity expansion is acceptable; debt to fund operations is a red flag
- **Promoter-level debt**: Check if promoters have pledged shares to borrow — company balance sheet may look clean but promoter is leveraged

### 3.3 Contingent Liabilities

Found in notes to accounts. Include:
- Disputed tax demands
- Pending litigation
- Bank guarantees
- Performance guarantees

**Red flag**: Contingent liabilities > 50% of Net Worth

Always read management commentary on probability of crystallization.

### 3.4 Working Capital Analysis

```
Debtor Days = (Trade Receivables / Net Sales) × 365
Inventory Days = (Inventory / COGS) × 365
Days Payable = (Trade Payables / COGS) × 365
Cash Conversion Cycle = Debtor Days + Inventory Days − Days Payable
```

**CLI thresholds:**

| Metric | Max (YELLOW flag) |
|--------|------------------|
| Debtor Days | > 90 days |
| Inventory Days | > 120 days |

**Warning signs:**
- Debtor days rising QoQ → customers not paying, or aggressive revenue recognition
- Inventory days rising → demand slowdown or procurement issues
- Creditor days falling rapidly → losing supplier confidence

---

## 3. Promoter & Institutional Activity

### 4.1 Promoter Holding

| Holding % | Interpretation |
|-----------|----------------|
| > 60% | Strong promoter control |
| 40–60% | Normal |
| 25–40% | Low — vulnerable to takeover |
| < 25% | Very low — investigate |

**Promoter Buying (increase in stake):**
- Promoters buying open market → strong confidence signal
- Creeping acquisition (buying up to 5% per year without open offer) → accumulation

**Promoter Selling:**
- Selling > 2% in a quarter → investigate reason
- Selling through bulk/block deals → may be distress or diversification
- Selling after stock split/bonus → may be suspect

**CLI tracks both QoQ change and 6-quarter trend:**

| QoQ Change | Score Impact |
|------------|-------------|
| > +1% | +6 |
| 0 to +1% | +2 |
| 0 to −2% | −3 |
| < −2% | −8 |

6-quarter trend reinforces the QoQ signal: sustained buying > +2% over 6Q adds +2 pts; sustained selling < −3% over 6Q subtracts −2 pts.

### 4.2 Promoter Pledge

**Pledge mechanics**: Promoter borrows money by pledging shares. If stock price falls below margin, lender can sell shares → cascade fall.

| Pledge % of Promoter Holding | Risk | CLI Score |
|------------------------------|------|-----------|
| 0% | No risk | +5 |
| < 10% | Low | +2 |
| 10–25% | Moderate — monitor | −5 |
| > 25% | HIGH RISK | −10 |

**Critical signal**: Pledge percentage increasing > 5% QoQ → immediate −10 pts and RED flag.

### 4.3 FII/FPI Activity

FII (Foreign Institutional Investors) / FPI (Foreign Portfolio Investors) are sophisticated, information-rich investors.

| Signal | Interpretation |
|--------|----------------|
| FII buying ≥ +1% QoQ | Bullish — international money coming in |
| FII holding steady | Neutral |
| FII selling ≥ −1% QoQ | Caution — may signal concerns |
| FII selling + DII buying | Transition — domestic confidence |
| Both FII + DII selling | RED FLAG |

**Key nuance**: FII selling may be due to global EM outflows (macro, not company-specific). Check broader FII activity before concluding.

**CLI Scoring — FII Activity (max ±6 pts):**

| FII QoQ Change | Score Impact |
|----------------|-------------|
| ≥ +2% | +6 |
| ≥ +1% | +3 |
| 0 to −1% | 0 |
| ≤ −1% | −3 |
| ≤ −2% | −6 |

### 4.4 DII Activity

DII (Domestic Institutional Investors) = Mutual Funds + Insurance companies + Pension funds.

- DII often provides support during FII selling (counter-cyclical)
- Systematic buying from DII (MF SIP flows) provides floor
- DII reducing despite FII buying = unusual, investigate

**CLI Scoring — DII Activity (secondary signal, max ±3 pts):**

| DII QoQ Change | Score Impact |
|----------------|-------------|
| ≥ +1% | +3 |
| 0 to −1% | 0 |
| ≤ −1% | −3 |

### 4.5 Shareholding Concentration Risk

- If top 5 shareholders hold > 80%, liquidity is thin
- Free float < 15% → large bid-ask spreads, manipulation risk
- High HNI (High Net Worth Individual) concentration → volatile moves

---

## 4. Valuation Ratios

### 5.1 Price to Earnings (P/E)

```
P/E = Market Price / Earnings Per Share (EPS)
Trailing P/E = Price / Last 12 months EPS
Forward P/E = Price / Next 12 months estimated EPS
```

**P/E context matters more than absolute number:**
- A P/E of 50 for a 40% growth company may be cheap (PEG < 1.25)
- A P/E of 15 for a declining business is expensive

Absolute P/E thresholds are **not used for scoring** — a P/E of 60 may be cheap for a stock that historically trades at 80, and a P/E of 10 may be expensive for a stock that historically trades at 8. The CLI shows current P/E for reference only and scores entirely on the historical mean comparison below.

**Historical P/E vs Mean (the only P/E signal that matters for scoring):**

Compare the current P/E to the stock's own 5-year (or 1-year) mean P/E. This accounts for sector-specific re-rating and is far more useful than an absolute P/E threshold.

```
Ratio = Current P/E / Historical Mean P/E  (5Y preferred, 1Y fallback)
```

| Ratio | Interpretation | CLI Score |
|-------|----------------|-----------|
| < 0.70 | Trading at steep discount to own history — strong value | +8 |
| 0.70–0.90 | Moderately undervalued | +4 |
| 0.90–1.15 | Fair value — near historical average | 0 |
| 1.15–1.40 | Moderately overvalued | −4 |
| > 1.40 | Significantly above historical average — priced for perfection | −8 |

The CLI shows historical ranges for 1Y, 5Y, and 10Y with "▼ X% below — cheap" or "▲ X% above — expensive" labels.

### 5.2 Price to Book (P/B)

```
P/B = Market Cap / Book Value of Equity
```

Most useful for capital-intensive businesses: banks, insurance, metals, cement.

| P/B Range | Signal |
|-----------|--------|
| < 1x | Cheap — trading below book value |
| 1–2x | Reasonable |
| 2–5x | Premium for quality |
| > 5x | Only justified for very high ROE businesses |

**CLI threshold:** P/B > 5x raises a YELLOW flag.

**Buffett rule**: Buy when P/B is low AND ROE is consistently high.

### 5.3 EV/EBITDA

```
Enterprise Value = Market Cap + Total Debt − Cash
EV/EBITDA = Enterprise Value / EBITDA (annualized)
```

Preferred over P/E for capital-intensive or leveraged companies because it ignores capital structure.

| EV/EBITDA | Signal |
|-----------|--------|
| < 8x | Cheap |
| 8–15x | Reasonable |
| 15–20x | Growth premium |
| > 20x | Expensive |

**CLI threshold:** EV/EBITDA > 20x raises a YELLOW flag.

### 5.4 PEG Ratio

```
PEG = P/E Ratio / EPS Growth Rate (%)
```

| PEG | Interpretation |
|-----|----------------|
| < 0.75 | Undervalued relative to growth |
| 0.75–1.25 | Fair value |
| 1.25–2.0 | Slight premium |
| > 2.0 | Expensive relative to growth |

Rule of thumb: PEG < 1 = growth is "on sale".

### 5.5 Dividend Yield

```
Dividend Yield = Annual DPS / Market Price × 100
```

- Yield > 3% for a growing company → often mispriced by market
- Dividend cuts despite rising PAT → management not sharing profits (governance concern)
- Very high yield (>8%) for a regular company → may be a dividend trap (yield due to falling stock price)

---

## 5. Red Flag Checklist

### 6.1 Balance Sheet Red Flags

- [ ] D/E > 2x (non-financial company)
- [ ] Contingent liabilities > 50% of Net Worth
- [ ] Large loans/advances to subsidiaries or related parties (that are loss-making)
- [ ] Goodwill > 30% of total assets (acquisition addiction)
- [ ] Reserves declining despite reported profits
- [ ] Cash declining while debt rising
- [ ] Book value declining — equity erosion

### 6.2 P&L Red Flags

- [ ] Revenue declining YoY
- [ ] PAT declining while revenue growing (margin collapse)
- [ ] Other Income > 20% of PBT (operating business weak)
- [ ] EPS dilution far larger than PAT dilution (heavy fresh equity at poor timing)
- [ ] Exceptional/extraordinary items in 3+ consecutive quarters (normalizing the extraordinary)
- [ ] Effective tax rate < 15% without clear explanation

### 6.3 Cash Flow Red Flags

- [ ] Negative OCF with positive PAT *(except financial sector — see Section 6.1)*
- [ ] Chronic negative OCF with a stable (non-improving) trend — company structurally burning cash
- [ ] Consistently negative FCF for 3+ years (capex-heavy without visible payoff)
- [ ] Investing cash outflows > operating cash inflows without a clear capex story
- [ ] Cash from financing (borrowing) used to pay dividends

### 6.4 Promoter / Management Red Flags

- [ ] Promoter pledge > 25% of their holding
- [ ] Promoter pledge increasing > 5% QoQ
- [ ] Promoter selling via block deals while announcing buybacks
- [ ] Frequent management changes (CEO/CFO/auditor)
- [ ] Company has multiple subsidiaries in tax havens
- [ ] Related party transactions growing faster than revenue
- [ ] Promoter salary/perquisites growing faster than PAT

### 6.5 Qualitative Red Flags

- [ ] Qualified / Adverse audit opinion
- [ ] "Going concern" in auditor's report
- [ ] SEBI action: insider trading probe, order for forensic audit
- [ ] Promoter arrested or under investigation
- [ ] Company switching auditors frequently
- [ ] BSE/NSE surveillance actions (GSM, ASM framework)
- [ ] Media reports of corporate governance issues

---

## 6. Sector-Specific Notes

### 7.1 Banking, NBFCs & Housing Finance Companies

**The CLI automatically detects financial sector companies** (via yfinance sector tag) and applies sector-aware scoring:

| Normal Check | Financial Sector Behaviour |
|---|---|
| OCF/PAT ratio | **Skipped** — loan disbursements are operating outflows by accounting convention |
| Negative OCF flag | **Skipped** — normal for lenders |
| Negative FCF flag | **Skipped** |
| D/E ≤ 1.0 threshold | **Relaxed** to ≤ 5.0x (NBFC norm) |
| D/E red flag at 2.0x | **Relaxed** to 8.0x |

**Key metrics to use instead:**

| Metric | What It Measures | Threshold |
|--------|-----------------|-----------|
| NIM (Net Interest Margin) | Spread on loans vs deposits | > 3% (banks), > 4% (NBFCs) |
| GNPA / NNPA % | Gross / Net Non-Performing Assets | GNPA < 3%, NNPA < 1% |
| PCR (Provision Coverage Ratio) | % of bad loans covered by provisions | > 70% |
| CAR / CRAR | Capital Adequacy Ratio | > 15% |
| ROA | Return on Assets | > 1.5% (banks) |
| ROE | Return on Equity | > 15% |

**Watch for:**
- NPA slippages quarter-over-quarter
- Restructured loans (hidden NPAs)
- Concentration in stressed sectors (real estate, infra)
- Aggressive loan growth without capital raising

### 7.2 IT / Software

**Key metrics:**

| Metric | Threshold |
|--------|-----------|
| Revenue growth (CC) | > 10% YoY |
| EBIT Margin | > 20% |
| Attrition Rate | < 15% |
| Utilisation Rate | > 80% |
| Days Sales Outstanding (DSO) | < 70 days |

**Watch for:**
- Deal wins declining
- Large deals > 10 years (may have thin margins baked in)
- Revenue from top 5 clients > 40% (concentration risk)
- Visa issues for US-dependent revenue

### 7.3 Pharmaceuticals

**Key metrics:**

| Metric | Threshold |
|--------|-----------|
| R&D as % of Revenue | > 6% |
| Gross Margin | > 55% |
| Export % | Higher = better (US generics is premium) |
| EBITDA Margin | > 20% |

**Watch for:**
- FDA import alerts (Warning Letters, Import Alerts)
- ANDA approvals pipeline
- US price erosion in generic drugs
- Domestic MR-to-revenue ratio (large field force without proportionate revenue)
- API vs formulations mix (formulations = better margins)

### 7.4 FMCG

**Key metrics:**

| Metric | Threshold |
|--------|-----------|
| Volume growth | > 5% YoY |
| EBITDA Margin | > 18% |
| Return on Capital | > 30% |
| Market Share | Stable/growing |

**Watch for:**
- Volume vs price-led growth (volume = organic demand, price = inflation pass-through)
- Raw material cost pressure (palm oil, crude derivatives, packaging)
- Distribution expansion vs same-store revenue
- Private label competition in modern trade

### 7.5 Infrastructure / Capital Goods

**Key metrics:**

| Metric | Threshold |
|--------|-----------|
| Order Book / Revenue | 2.5–3.5x (2-3 year visibility) |
| Order Inflow Growth | > 20% |
| Working Capital Days | < 120 |
| D/E | < 0.5 (construction), < 1.5 (project companies) |

**Watch for:**
- Order cancellations / modifications
- Receivables from government (delayed payments are common)
- Subcontracting margins being squeezed
- Debt funding bridge between order execution and payment

---

## 7. Quantitative Scorecard — CLI Scoring Reference

Both screeners start at a neutral **50** and are adjusted up or down. The final score is:

```
Final Score = BasicScore × 40% + AdvancedScore × 60%
```

The CLI displays a **Score Breakdown panel** after the header showing every section's raw points, its weight, and its effective contribution to the final score. This makes it transparent why the score is what it is.

### 8.1 Basic Score Components (weight: 40%)

Starting score: **50**

| Component | Criteria | Points |
|-----------|----------|--------|
| **Revenue YoY Growth** | ≥ 20%: +15 · ≥ 10%: +8 · ≥ 0%: +2 · < 0%: −15 | ±15 |
| **PAT YoY Growth** | ≥ 20%: +15 · ≥ 10%: +8 · ≥ 0%: +2 · < 0%: −15 | ±15 |
| **EBITDA Margin** | ≥ 20%: +10 · ≥ 10%: +5 · < 10%: −5 | ±10 |
| **EBITDA Trend** | Improving: +5 · Stable: 0 · Deteriorating: −10 | ±10 |
| **OCF/PAT Ratio** ¹ | ≥ 1.0: +10 · ≥ 0.75: +5 · ≥ 0: −5 · < 0: −15 | ±15 |
| **Red Flag Penalty** | −5 per RED flag | variable |

> ¹ OCF/PAT check is **skipped entirely** for financial sector companies (banks, NBFCs, HFCs, insurance). No points added or deducted.

YoY growth uses **annual data** from screener.in (5 fiscal years) as the primary source, falling back to quarterly YoY averages when annual data is unavailable.

### 8.2 Advanced Score Components (weight: 60%)

Starting score: **50**

| Component | Criteria | Points |
|-----------|----------|--------|
| **ROE** | ≥ 30%: +10 · ≥ 15%: +5 · < 15%: −5 | ±10 |
| **ROCE** | ≥ 24%: +8 · ≥ 12%: +4 · < 12%: −4 | ±8 |
| **D/E Ratio** ² | < 0.5: +12 · < 1.0: +6 · < 2.0: −6 · ≥ 2.0: −12 | ±12 |
| **Interest Coverage** | ≥ 6x: +6 · ≥ 3x: +3 · < 3x: −6 | ±6 |
| **FCF (latest qtr)** | Positive: +5 · Negative: −5 | ±5 |
| **Promoter Pledge** | 0%: +5 · ≤ 10%: +2 · ≤ 25%: −5 · > 25%: −10 | ±10 |
| **Pledge increase QoQ** | > 5% increase: −10 | −10 |
| **Promoter Holding QoQ** | > +1%: +6 · > 0%: +2 · > −2%: −3 · ≤ −2%: −8 | ±8 |
| **Promoter Holding 6Q** | > +2%: +2 · < −3%: −2 | ±2 |
| **FII Activity QoQ** | ≥ +2%: +6 · ≥ +1%: +3 · ≤ −1%: −3 · ≤ −2%: −6 | ±6 |
| **DII Activity QoQ** | ≥ +1%: +3 · ≤ −1%: −3 | ±3 |
| **P/E Ratio** | Display only — not scored. Absolute P/E is context-dependent. | — |
| **PEG Ratio** ⁴ | < 0.75: +6 · ≤ 1.5: +3 · ≤ 2.5: −4 · > 2.5: −6 | ±6 |
| **P/E vs 5Y Mean** ³ | < 0.70×: +8 · < 0.90×: +4 · ≤ 1.15×: 0 · ≤ 1.40×: −4 · > 1.40×: −8 | ±8 |
| **Red Flag Penalty** | −5 per RED flag | variable |

> ² Financial sector D/E thresholds: < 5.0: +6 · < 8.0: −6 · ≥ 8.0: −12 (relaxed for NBFCs/banks/HFCs)
>
> ³ Falls back to 1Y historical mean if 5Y data is unavailable.
>
> ⁴ PEG = P/E ÷ EPS YoY growth %. Only shown when both P/E and positive EPS growth are available. Not computed when EPS growth is negative (negative PEG is meaningless).

### 8.3 Score Breakdown Panel (CLI output)

The CLI prints a breakdown table after the header panel showing:

```
Component                        Raw        Wt    → Score
────────────────────────────────────────────────────────
Base (start of both screeners)    50         —      +50 pts
────────────────────────────────────────────────────────
Basic Screener  (×0.4)
  Growth                         +30 pts    ×0.4   +12 pts
  Profitability                  +10 pts    ×0.4    +4 pts
  Cash Quality                    +0 pts    ×0.4    +0 pts
  Penalties                       +0 pts    ×0.4    +0 pts
────────────────────────────────────────────────────────
Advanced Screener  (×0.6)
  Profitability                   +9 pts    ×0.6    +5 pts
  Debt Health                     +6 pts    ×0.6    +4 pts
  Shareholding                    -8 pts    ×0.6    -5 pts
  Valuation                      +18 pts    ×0.6   +11 pts
  Penalties                       +0 pts    ×0.6    +0 pts
════════════════════════════════════════════════════════
TOTAL                                               +81 pts
```

Each section title in the report also shows its raw point contribution: `Growth Metrics  (+30 pts)`.

### 8.4 Score Interpretation

| Score | Rating | Suggested Action |
|-------|--------|-----------------|
| 80–100 | **STRONG BUY** | High conviction, size up position |
| 60–79 | **BUY** | Good entry, standard position size |
| 40–59 | **WATCH** | Monitor for improvement, don't buy yet |
| 20–39 | **AVOID** | Multiple concerns, stay away |
| < 20 | **SELL** | Consider exiting, serious red flags |

### 8.5 Manual Scorecard (for offline use)

| # | Parameter | Your Assessment | Max | Notes |
|---|-----------|----------------|-----|-------|
| 1 | Revenue Growth YoY (3Y + 5Y avg) | | 15 | |
| 2 | PAT Growth YoY (3Y + 5Y avg) | | 15 | |
| 3 | EBITDA Margin + Trend | | 20 | |
| 4 | OCF Quality (OCF/PAT ratio) | | 15 | Skip for financials |
| 5 | ROE | | 10 | |
| 6 | ROCE | | 8 | |
| 7 | Debt Health (D/E + ICR + FCF) | | 18 | Adjust for financials |
| 8 | Promoter Pledge + Holding Change | | 20 | |
| 9 | FII + DII Activity | | 9 | |
| 10 | Valuation (P/E + vs history) | | 18 | |
| 11 | Red Flags (count) | | penalty | −5 per RED flag |
| — | **TOTAL** | | **~120** | normalise to 100 |

---

## Quick Reference Card

### Must-Check 5 Things Every Quarter

1. **OCF vs PAT** — Did cash flow match profit? (OCF/PAT < 0.5 = investigate; skip for NBFCs/banks)
2. **Promoter Pledge** — Did pledge % go up? (Any increase = flag; > 5% QoQ = RED)
3. **Debtor Days** — Are customers paying faster or slower? (> 90 days = YELLOW)
4. **Audit Opinion** — Any qualifications or emphasis of matter?
5. **Debt + Interest Coverage** — Can company service its debt comfortably?

### 3Y vs 5Y YoY — Reading the Growth Story

| Pattern | What It Means |
|---------|---------------|
| 3Y >> 5Y | Growth accelerating — business momentum building |
| 3Y ≈ 5Y | Consistent compounder |
| 3Y << 5Y | Growth fading — high base effect or business slowdown |
| PAT 5Y high, EPS 5Y low | Heavy equity dilution over 5 years — check if capital deployed well |

### Sources for Indian Stock Data

| Source | Best For | Free? |
|--------|----------|-------|
| screener.in | Financial ratios, shareholding, peer comparison | Yes (basic) |
| moneycontrol.com | News, management interviews, shareholding | Yes |
| bseindia.com | Official filings, quarterly results PDF | Yes |
| nseindia.com | Bulk/block deals, insider trading data | Yes |
| ratestar.in | Credit ratings, NCD/bond details | Yes |
| capitaline.com | Deep historical data, segment breakdowns | Paid |
| Investor Relations page | Management commentary, concall transcripts | Yes |

### Concall Transcript Analysis — 5 Key Questions

1. What is management saying about the next 2–3 quarters? (Forward guidance)
2. What are the reasons for any margin pressure? Are they temporary?
3. Is the management blaming external factors for every bad metric?
4. What is the capital allocation plan — buyback, capex, dividends, acquisitions?
5. How many times does management use the word "headwinds" vs "opportunities"?

---

*This guide is for educational purposes. Always do your own due diligence. Past performance is not indicative of future returns.*
