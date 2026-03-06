# Indian Stock Screener

A terminal-based fundamental analysis tool for Indian listed stocks. Fetches financial data from two sources, runs quantitative screening checks, and optionally generates AI-powered narrative analysis using Claude.

---

## What It Does

- **Single stock deep-dive** — growth metrics, profitability, debt health, shareholding pattern, valuation ratios, historical P/E context (1Y / 5Y / 10Y), working capital, FCF trend, and red flag detection
- **Batch scan** — screen a watchlist of symbols and display a comparison table sorted by score
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

# Clear cache for a symbol (force fresh data)
python -m screener clear-cache RELIANCE.NS

# Clear all cached data
python -m screener clear-cache
```

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

Red flags deduct points (configurable in `config/thresholds.yaml`). Each red flag applies a −5 point penalty by default.

---

## What Gets Checked

### Basic (Growth & Quality)
| Check | Threshold |
|-------|-----------|
| Revenue YoY growth | ≥ 10% |
| PAT YoY growth | ≥ 10% |
| EBITDA margin | ≥ 10% |
| OCF / PAT ratio | ≥ 0.75 |

### Advanced (Health & Valuation)
| Check | Threshold |
|-------|-----------|
| ROE | ≥ 15% |
| ROCE | ≥ 12% |
| Debt/Equity | < 1.0 (red > 2.0) |
| Interest coverage | > 3x (red < 1.5x) |
| Net Debt / EBITDA | < 3x |
| P/E ratio | < 40x (red > 60x) |
| P/B ratio | < 5x |
| EV/EBITDA | < 20x |
| Promoter pledge | < 10% (red > 25%) |
| Promoter holding QoQ | increase = green, decrease = watch |
| FII holding QoQ | ≥ +1% = bullish signal |
| Debtor days | < 90 days |
| Inventory days | < 120 days |
| P/E vs 5Y historical mean | < 0.75x mean = historically cheap |
| Net Cash Flow (annual) | YoY trend — 1Y / 3Y / 5Y Δ% |

All thresholds are configurable in `config/thresholds.yaml`.

---

## Data Sources

| Source | Data Provided |
|--------|--------------|
| **yfinance** | Current price, historical P/E (1Y / 5Y / 10Y), price trend |
| **screener.in** | All financials — P&L (quarterly + annual), balance sheet (incl. Cash Equivalents, LT/ST Borrowings via internal API), cash flow, shareholding pattern (promoter / FII / DII / public), promoter pledge, working capital ratios, quarterly audit PDF links |

All financial statement data (revenue, PAT, OCF, debt, cash equivalents) comes exclusively from screener.in. yfinance is used only for price data.

Both sources are cached locally as CSV files with a 24-hour TTL to avoid repeated network calls.

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
├── config/
│   └── thresholds.yaml         # All configurable thresholds
└── screener/
    ├── cli.py                   # Typer CLI: screen, scan, clear-cache, version
    ├── data/
    │   ├── yfinance_fetcher.py  # Price, financials, historical P/E
    │   └── screener_in.py       # Shareholding, ratios, working capital, audit PDFs
    ├── analysis/
    │   ├── basic_screen.py      # Revenue / PAT / margin / OCF quality
    │   └── advanced_screen.py   # ROE / ROCE / debt / promoter / valuation / FCF
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
- Sector-specific notes
- Quantitative scorecard template
