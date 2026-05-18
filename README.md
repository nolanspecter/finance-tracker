# finance-tracker

Local-only Flask app to track income, expenses, and budgets. Data lives in `finance.db` (SQLite) next to `app.py` and is gitignored — your financial data never leaves your machine.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Features
- Income & expense transactions with categories
- Payment method tagging (credit / debit / cash)
- "Who" field to track who made the transaction
- Monthly dashboard with totals and a category breakdown chart
- Per-category monthly budgets with progress bars
- User-selectable currency (USD, EUR, GBP, JPY, INR, and more)

## Data
- `finance.db` — local SQLite file (gitignored)
- Default categories are seeded on first run; edit them under **Categories & Budgets**
