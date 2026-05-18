import sqlite3
from datetime import datetime, date
from pathlib import Path
from flask import Flask, g, render_template, request, redirect, url_for, jsonify, flash

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "finance.db"

app = Flask(__name__)
app.secret_key = "local-dev-only"

CURRENCIES = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CNY": "¥",
    "INR": "₹",
    "CAD": "CA$",
    "AUD": "A$",
    "CHF": "CHF",
    "SGD": "S$",
    "HKD": "HK$",
    "KRW": "₩",
    "BRL": "R$",
    "MXN": "MX$",
    "ZAR": "R",
}

DEFAULT_CATEGORIES = [
    ("Salary", "income"),
    ("Other Income", "income"),
    ("Groceries", "expense"),
    ("Rent", "expense"),
    ("Utilities", "expense"),
    ("Transport", "expense"),
    ("Dining", "expense"),
    ("Entertainment", "expense"),
    ("Health", "expense"),
    ("Shopping", "expense"),
    ("Other", "expense"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK (kind IN ('income','expense')),
            monthly_budget REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT NOT NULL,
            amount REAL NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('income','expense')),
            category_id INTEGER,
            note TEXT,
            payment_method TEXT NOT NULL DEFAULT 'debit' CHECK (payment_method IN ('credit','debit','cash')),
            person TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()}
    if "payment_method" not in cols:
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'debit'"
        )
    if "person" not in cols:
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN person TEXT NOT NULL DEFAULT ''"
        )
    cur = conn.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO categories (name, kind) VALUES (?, ?)",
            DEFAULT_CATEGORIES,
        )
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('currency', 'USD')"
    )
    conn.commit()
    conn.close()


def get_currency():
    row = get_db().execute("SELECT value FROM settings WHERE key = 'currency'").fetchone()
    code = row["value"] if row else "USD"
    return code, CURRENCIES.get(code, "$")


def month_key(d: str) -> str:
    return d[:7]


@app.route("/")
def dashboard():
    db = get_db()
    today = date.today()
    ym = request.args.get("month", today.strftime("%Y-%m"))

    totals = db.execute(
        """
        SELECT kind, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE substr(tx_date, 1, 7) = ?
        GROUP BY kind
        """,
        (ym,),
    ).fetchall()
    summary = {"income": 0.0, "expense": 0.0}
    for r in totals:
        summary[r["kind"]] = r["total"]
    summary["net"] = summary["income"] - summary["expense"]

    by_cat = db.execute(
        """
        SELECT c.name AS name, c.kind AS kind, c.monthly_budget AS budget,
               COALESCE(SUM(t.amount), 0) AS spent
        FROM categories c
        LEFT JOIN transactions t
          ON t.category_id = c.id AND substr(t.tx_date, 1, 7) = ?
        GROUP BY c.id
        ORDER BY c.kind, c.name
        """,
        (ym,),
    ).fetchall()

    expense_chart = [
        {"name": r["name"], "spent": r["spent"]}
        for r in by_cat if r["kind"] == "expense" and r["spent"] > 0
    ]

    recent = db.execute(
        """
        SELECT t.id, t.tx_date, t.amount, t.kind, t.note, t.payment_method, t.person, c.name AS category
        FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
        ORDER BY t.tx_date DESC, t.id DESC
        LIMIT 10
        """
    ).fetchall()

    months = db.execute(
        "SELECT DISTINCT substr(tx_date,1,7) AS m FROM transactions ORDER BY m DESC"
    ).fetchall()
    month_options = sorted({r["m"] for r in months} | {ym, today.strftime("%Y-%m")}, reverse=True)

    return render_template(
        "dashboard.html",
        summary=summary,
        by_cat=by_cat,
        expense_chart=expense_chart,
        recent=recent,
        month=ym,
        month_options=month_options,
    )


@app.route("/transactions")
def transactions_list():
    db = get_db()
    rows = db.execute(
        """
        SELECT t.id, t.tx_date, t.amount, t.kind, t.note, t.payment_method, t.person, c.name AS category
        FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
        ORDER BY t.tx_date DESC, t.id DESC
        """
    ).fetchall()
    cats = db.execute("SELECT * FROM categories ORDER BY kind, name").fetchall()
    return render_template("transactions.html", rows=rows, categories=cats, today=date.today().isoformat())


@app.route("/transactions/add", methods=["POST"])
def add_transaction():
    db = get_db()
    f = request.form
    try:
        amount = float(f["amount"])
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (KeyError, ValueError) as e:
        flash(f"Invalid amount: {e}", "error")
        return redirect(url_for("transactions_list"))

    tx_date = f.get("tx_date") or date.today().isoformat()
    kind = f.get("kind", "expense")
    category_id = f.get("category_id") or None
    note = f.get("note", "").strip()
    payment_method = f.get("payment_method", "debit")
    if payment_method not in ("credit", "debit", "cash"):
        payment_method = "debit"
    person = f.get("person", "").strip()

    db.execute(
        "INSERT INTO transactions (tx_date, amount, kind, category_id, note, payment_method, person) VALUES (?,?,?,?,?,?,?)",
        (tx_date, amount, kind, category_id, note, payment_method, person),
    )
    db.commit()
    flash("Transaction added", "success")
    return redirect(url_for("transactions_list"))


@app.route("/transactions/<int:tx_id>/delete", methods=["POST"])
def delete_transaction(tx_id):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    db.commit()
    return redirect(request.referrer or url_for("transactions_list"))


@app.route("/categories", methods=["GET", "POST"])
def categories_view():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            kind = request.form.get("kind", "expense")
            budget = float(request.form.get("monthly_budget") or 0)
            if name:
                try:
                    db.execute(
                        "INSERT INTO categories (name, kind, monthly_budget) VALUES (?,?,?)",
                        (name, kind, budget),
                    )
                    db.commit()
                    flash("Category added", "success")
                except sqlite3.IntegrityError:
                    flash("Category name already exists", "error")
        elif action == "update_budgets":
            for key, val in request.form.items():
                if key.startswith("budget_"):
                    cid = int(key.split("_", 1)[1])
                    try:
                        b = float(val or 0)
                    except ValueError:
                        b = 0
                    db.execute("UPDATE categories SET monthly_budget = ? WHERE id = ?", (b, cid))
            db.commit()
            flash("Budgets updated", "success")
        elif action == "delete":
            cid = int(request.form["id"])
            db.execute("DELETE FROM categories WHERE id = ?", (cid,))
            db.commit()
            flash("Category deleted", "success")
        return redirect(url_for("categories_view"))

    cats = db.execute("SELECT * FROM categories ORDER BY kind, name").fetchall()
    return render_template("categories.html", categories=cats)


@app.template_filter("money")
def money_filter(v):
    _, sym = get_currency()
    try:
        return f"{sym}{float(v):,.2f}"
    except (TypeError, ValueError):
        return f"{sym}0.00"


@app.context_processor
def inject_currency():
    code, sym = get_currency()
    return {"currency_code": code, "currency_symbol": sym, "currencies": CURRENCIES}


@app.route("/settings/currency", methods=["POST"])
def set_currency():
    code = request.form.get("currency", "USD")
    if code not in CURRENCIES:
        code = "USD"
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('currency', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (code,),
    )
    db.commit()
    return redirect(request.referrer or url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
