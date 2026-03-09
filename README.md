# Indian Stock Screener

A terminal-based fundamental analysis tool for Indian listed stocks. Fetches financial data from two sources, runs quantitative screening checks, and optionally generates AI-powered narrative analysis using Claude.

---

## What It Does

- **Single stock deep-dive** — growth metrics, profitability, debt health, shareholding pattern, valuation ratios, historical P/E context (1Y / 5Y / 10Y), working capital, FCF trend, and red flag detection
- **Batch scan** — screen a watchlist of symbols and display a comparison table sorted by score
- **Google Sheets sync** — scan your portfolio sheet and write scores + ratings directly back to it, with week-on-week change tracking
- **AI narrative** (optional, requires Anthropic API key) — Claude analyses price action vs fundamentals over a chosen time horizon (6M / 1Y / 2Y / 3Y) and gives a 6-month forward prediction with risks, catalysts, and confidence level
- **PDF audit scan** (optional) — downloads quarterly audit reports from screener.in and flags auditor qualifications, going concern opinions, emphasis of matter, and CARO issues

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Screen a single stock
python -m screener screen RELIANCE.NS

# Screen with AI narrative + audit scan
python -m screener screen TCS.NS --ai

# Batch scan from a watchlist file
python -m screener scan --watchlist stocks.txt

# Batch scan with inline symbols
python -m screener scan --symbols "INFY.NS,WIPRO.NS,TCS.NS"

# Export results to CSV
python -m screener scan --watchlist stocks.txt --output results.csv

# Filter batch results by minimum score
python -m screener scan --watchlist stocks.txt --min-score 60

# Sync scores to a Google Sheet
python -m screener sync-sheet <SPREADSHEET_ID> --credentials service_account.json

# Clear cache for a symbol (force fresh data)
python -m screener clear-cache RELIANCE.NS

# Clear all cached data
python -m screener clear-cache
```

The `run.sh` script auto-creates a `.venv` and routes all commands correctly:

```bash
./run.sh RELIANCE.NS                        # screen
./run.sh sync-sheet <ID> --credentials k.json
./run.sh scan --symbols "TCS.NS,INFY.NS"
./run.sh clear-cache
```

---

## Google Sheets Sync

Reads stock symbols from **column B** of your sheet and writes results back:

| Column | Content |
|--------|---------|
| C — Score | Numeric score (e.g. `71`) — sortable |
| D — Comments | Rating + week-on-week change (e.g. `BUY (+7)`) |

### Setup

1. Enable **Google Sheets API** and **Google Drive API** in [Google Cloud Console](https://console.cloud.google.com)
2. Create a **Service Account** → download the JSON key file
3. Share your Google Sheet with the service account email (Editor access)

```bash
# Dry run — see output without writing to sheet
python -m screener sync-sheet <SPREADSHEET_ID> --credentials service_account.json --dry-run

# Live run
python -m screener sync-sheet <SPREADSHEET_ID> --credentials service_account.json

# Or use env var
export GOOGLE_SHEETS_CREDENTIALS=service_account.json
python -m screener sync-sheet <SPREADSHEET_ID>
```

The run **fails fast** — if any symbol errors, the process exits immediately and nothing is written to the sheet.

---

## AI Mode

Run any screen with `--ai` to unlock:

1. **Horizon selection** — arrow-key menu to choose how far back to look (6 months, 1 year, 2 years, 3 years)
2. **Audit PDF scan** — downloads and analyses quarterly audit reports for the chosen period
3. **Claude narrative** — historical trend analysis + 6-month forward prediction with risks and catalysts
4. **Follow-up Q&A** — type questions about the analysis directly in the terminal

```bash
export ANTHROPIC_API_KEY=your_key_here
python -m screener screen RELIANCE.NS --ai
```

---

## Screening Score

Every stock gets a **combined score out of 100** based on weighted checks across two screeners:

| Component | Weight |
|-----------|--------|
| BasicScreener (growth, margins, OCF quality) | 40% |
| AdvancedScreener (ROE/ROCE, debt, promoter, valuation) | 60% |

| Rating | Score |
|--------|-------|
| STRONG BUY | 80–100 |
| BUY | 60–79 |
| WATCH | 40–59 |
| AVOID | 20–39 |
| SELL | 0–19 |

Growth scoring uses the **worse of 3Y and 5Y averages** — a stock with strong 5Y history but recent collapse will be penalised. Red flags deduct −5 points each (configurable).

---

## What Gets Checked

### Basic (Growth & Quality)
| Check | Threshold |
|-------|-----------|
| Revenue YoY growth | worst of 3Y / 5Y avg ≥ 10% |
| PAT YoY growth | worst of 3Y / 5Y avg ≥ 10% |
| PAT QoQ (chronic loss) | if QoQ suppressed due to majority-loss quarters → −10 pts + RED flag |
| EBITDA margin | ≥ 10% (non-financial only; annual for real estate / construction) |
| OCF / EBITDA ratio | ≥ 1.0 excellent · ≥ 0.85 good · ≥ 0.7 acceptable (Ind AS 116 sectors — primary metric) |
| OCF / PAT ratio | ≥ 0.75 (standard sectors only — hidden for Ind AS 116 and financial sectors) |
| Gross NPA % | ≤ 1.5% +15 · ≤ 3% +10 · ≤ 5% −5 · ≤ 7% −10 · > 7% −15 (financial sector only) |
| Net NPA % | ≤ 0.5% +10 · ≤ 1% +5 · ≤ 2% −5 · ≤ 3% −10 · > 3% −15 (financial sector only) |
| NPA 1Y trend | Gross NPA improved > 1pp: +5 · worsened > 1pp: −5 (financial sector only) |

### Advanced (Health & Valuation)
| Check | Threshold |
|-------|-----------|
| ROE | ≥ 30%: +10 · ≥ 15%: +5 · 0–15%: −5 · −10–0%: −10 · < −10%: −15 (RED flag if negative) |
| ROCE | ≥ 24%: +8 · ≥ 12%: +4 · 0–12%: −4 · −5–0%: −8 · < −5%: −12 (RED flag if negative) |
| Debt/Equity | < 1.0 (red > 2.0); financial sector: < 5.0 (red > 8.0) |
| Interest coverage | > 3x (red < 1.5x) |
| Net Debt / EBITDA | < 3x (hidden for real estate — negative EBITDA makes it misleading) |
| P/E vs 5Y historical mean | flag + score match: cheap < 0.90x mean, expensive > 1.15x mean |
| PEG ratio | < 0.75 cheap · < 1.5 fair · > 2.5 expensive (uses 3Y profit CAGR — same as screener.in) |
| P/B ratio | < 5x |
| EV/EBITDA | < 20x |
| Promoter pledge | < 10% (red > 25%) |
| Promoter holding QoQ | increase = green, decrease = watch |
| FII holding QoQ | ≥ +1% = bullish signal |
| FII + DII both selling QoQ | both ≤ −1% simultaneously → −10 pts + RED flag (institutional exit) |
| Public holding | > 30% → −5 pts (high retail float = weak institutional/promoter conviction) |
| Debtor days | < 90 days |
| Inventory days | < 120 days |
| Net Cash Flow (annual) | YoY trend — 1Y / 3Y / 5Y Δ% |

### Real Estate Metrics (real estate / construction companies only)
| Check | Threshold |
|-------|-----------|
| Pre-sales coverage | Customer Advances / Borrowings ≥ 1.0x excellent · ≥ 0.5x acceptable · < 0.3x red |
| Net debt post-advances | (Borrowings − Cash − Customer Advances) / Equity < 1.0x good · > 2.0x red |
| Inventory velocity | Inventory / Annual Revenue < 2 years good · > 4 years red |

All thresholds are configurable in `config/thresholds.yaml`.

---

## Financial Sector Handling

Banks, NBFCs, HFCs, and insurance companies are detected automatically by sector. Sector-specific behaviour:

- **OCF/PAT ratio** — hidden (loan disbursements are operating outflows; negative OCF is normal)
- **EBITDA margin** — not shown (banks use NIM instead)
- **D/E thresholds** — relaxed (< 5.0 normal, > 8.0 red)
- **NPA scoring** — Gross NPA % and Net NPA % replace margin checks, with graduated scoring (not binary) and 1Y trend bonus/penalty. Shown in a separate "Asset Quality" section with its own score contribution.
- **Revenue row** — falls back to "Interest Earned" / "Total Income" label variants used by screener.in for banks

---

## Ind AS 116 / Lease-Heavy Sector Handling

Cinema chains (PVR INOX), airlines, QSR chains, retailers, telecom, and hospitality companies capitalise long-term operating leases under Ind AS 116. This creates:

- **ROU (Right-of-Use) asset** on the balance sheet
- **Depreciation** on the ROU asset + **interest** on the lease liability flowing through P&L
- Net result: PAT can be negative even when actual operations are highly cash-generative

**Why OCF/PAT breaks for these companies:** The lease payments flow through the balance sheet (liability repayment), not through OCF. PAT includes the full depreciation + interest charge from leases. A cinema chain like PVR INOX can have 30% EBITDA margin and healthy OCF, yet report negative PAT. The OCF/PAT ratio will be a large negative number — meaningless as a quality signal.

**The CLI automatically handles this:**

| Normal Check | Ind AS 116 Behaviour |
|---|---|
| OCF/PAT ratio | **Replaced by OCF/EBITDA** — scored as primary cash quality metric |
| OCF/PAT flag | **Hidden** — suppressed to avoid false red flags |
| OCF/EBITDA | Shown for all companies; labelled `(primary — Ind AS 116)` for lease-heavy |

**OCF/EBITDA thresholds:**

| Ratio | Interpretation |
|-------|----------------|
| ≥ 1.0 | Excellent — collecting more cash than operating profit |
| ≥ 0.85 | Good |
| ≥ 0.70 | Acceptable |
| < 0.70 | Investigate |

**Detection:** The screener detects lease-heavy companies by sector/industry keywords (cinema, multiplex, aviation, QSR, retail, telecom, etc.) **and** by a mathematical fallback — if OCF/EBITDA > 0.5 AND OCF/PAT < −5, it auto-classifies as lease-heavy regardless of how yfinance labels the sector. This catches companies like Devyani International (sector = "Consumer Cyclical" but is a QSR operator).

---

## Real Estate Sector Handling

Real estate developers (Godrej Properties, DLF, Prestige, etc.) have unique balance sheet dynamics that standard metrics miss:

- **Customer Advances** — homebuyers pay upfront for under-construction flats; this liability offsets the risk of high borrowings
- **Inventory** — land + under-construction projects that may take 2–5 years to convert to revenue
- **Negative EBITDA on consolidated P&L** is common — SPV subsidiaries recognise full construction costs before revenue recognition

**The CLI shows a dedicated "Real Estate Metrics" section with three checks:**

| Metric | What It Measures |
|--------|-----------------|
| Pre-sales Coverage | Customer Advances ÷ Borrowings — how much of the debt is pre-funded by buyers |
| Net Debt Post-Advances | (Borrowings − Cash − Customer Advances) ÷ Equity — true leveraged exposure after netting advances |
| Inventory Velocity | Inventory ÷ Annual Revenue — how many years to sell through the current project pipeline |

**Note on EBITDA:** Screener fetches the consolidated P&L where project construction costs from SPV subsidiaries are included before revenue is recognised (Ind AS 115 completion method). This can make EBITDA appear negative even for profitable developers. Always compare standalone OPM alongside consolidated for real estate companies.

---

## Data Sources

| Source | Data Provided |
|--------|--------------|
| **yfinance** | Current price, historical P/E (1Y / 5Y / 10Y), price trend |
| **screener.in** | All financials — P&L (quarterly + annual), balance sheet (incl. Cash Equivalents, LT/ST Borrowings via internal API), cash flow, shareholding pattern (promoter / FII / DII / public), promoter pledge, working capital ratios, quarterly audit PDF links |

All financial statement data comes exclusively from screener.in. yfinance is used only for price data.

Both sources are cached locally as CSV files with a 24-hour TTL. The fetcher tries the consolidated URL first and falls back to standalone if the consolidated page has no data columns.

---

## Watchlist File Format

One symbol per line. Lines starting with `#` are comments.

```
# Nifty 50 picks
RELIANCE.NS
TCS.NS
HDFCBANK.NS
# INFY.NS  <- excluded
NESTLEIND.NS
```

---

## Project Structure

```
stock-screener/
├── SCREENING_GUIDE.md          # Standalone quarterly audit reference
├── requirements.txt
├── run.sh                      # Preferred entry point — auto venv + routing
├── config/
│   └── thresholds.yaml         # All configurable thresholds
└── screener/
    ├── cli.py                   # Typer CLI: screen, scan, sync-sheet, clear-cache, version
    ├── data/
    │   ├── yfinance_fetcher.py  # Price, historical P/E
    │   └── screener_in.py       # All financials, shareholding, ratios, audit PDFs
    ├── analysis/
    │   ├── basic_screen.py      # Revenue / PAT / margin / OCF / NPA quality
    │   └── advanced_screen.py   # ROE / ROCE / debt / promoter / valuation / FCF
    ├── integrations/
    │   └── google_sheets.py     # Google Sheets read/write via service account
    └── reports/
        └── formatter.py         # Rich terminal tables + CSV export
```

---

## Screening Guide

`SCREENING_GUIDE.md` is a standalone quarterly audit reference covering:

- P&L quality checks (revenue, EBITDA, PAT)
- OCF/PAT and OCF/EBITDA quality analysis (incl. Ind AS 116 lease-heavy exception)
- Auditor opinion red phrases
- Debt health analysis
- Promoter & institutional activity
- Valuation ratio interpretation (P/E, PEG with 3Y growth, P/B, EV/EBITDA)
- Red flag checklist
- Sector-specific notes (financial sector, Ind AS 116 lease-heavy, real estate)
- Quantitative scorecard template
