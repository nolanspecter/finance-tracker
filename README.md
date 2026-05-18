# Personal Finance

Local-only Flask app to track income, expenses, and budgets. Data lives in `finance.db` (SQLite) next to `app.py` and is gitignored.

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
- Monthly dashboard with totals and a category breakdown chart
- Per-category monthly budgets with progress bars

## Data
- `finance.db` — local SQLite file (gitignored)
- Default categories are seeded on first run; edit them under **Categories & Budgets**
