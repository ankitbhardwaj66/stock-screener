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
| EBITDA margin | ≥ 10% (non-financial only) |
| OCF / PAT ratio | ≥ 0.75 (non-financial only) |
| Gross NPA % | ≤ 3% green, > 7% red (financial sector only) |
| Net NPA % | ≤ 1% green, > 3% red (financial sector only) |

### Advanced (Health & Valuation)
| Check | Threshold |
|-------|-----------|
| ROE | ≥ 15% |
| ROCE | ≥ 12% |
| Debt/Equity | < 1.0 (red > 2.0); financial sector: < 5.0 (red > 8.0) |
| Interest coverage | > 3x (red < 1.5x) |
| Net Debt / EBITDA | < 3x |
| P/E vs 5Y historical mean | flag + score match: cheap < 0.90x mean, expensive > 1.15x mean |
| P/B ratio | < 5x |
| EV/EBITDA | < 20x |
| Promoter pledge | < 10% (red > 25%) |
| Promoter holding QoQ | increase = green, decrease = watch |
| FII holding QoQ | ≥ +1% = bullish signal |
| Debtor days | < 90 days |
| Inventory days | < 120 days |
| Net Cash Flow (annual) | YoY trend — 1Y / 3Y / 5Y Δ% |

All thresholds are configurable in `config/thresholds.yaml`.

---

## Financial Sector Handling

Banks, NBFCs, HFCs, and insurance companies are detected automatically by sector. Sector-specific behaviour:

- **OCF/PAT ratio** — hidden (loan disbursements are operating outflows; negative OCF is normal)
- **EBITDA margin** — not shown (banks use NIM instead)
- **D/E thresholds** — relaxed (< 5.0 normal, > 8.0 red)
- **NPA scoring** — Gross NPA % and Net NPA % replace margin checks, with 1Y/2Y/3Y trend columns
- **Revenue row** — falls back to "Interest Earned" / "Total Income" label variants used by screener.in for banks

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
- Auditor opinion red phrases
- Debt health analysis
- Promoter & institutional activity
- Valuation ratio interpretation
- Red flag checklist
- Sector-specific notes (financial sector adjustments)
- Quantitative scorecard template
