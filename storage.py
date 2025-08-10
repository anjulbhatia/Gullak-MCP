# storage.py
import duckdb
from datetime import date
from typing import List, Optional, Dict, Any

DB_FILE = "gullakai.db"

class Storage:
    def __init__(self, db_file=DB_FILE):
        self.conn = duckdb.connect(db_file)
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount DOUBLE NOT NULL,
            PRIMARY KEY (month, category)
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            category TEXT NOT NULL,
            amount DOUBLE NOT NULL,
            note TEXT
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS debts_bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            description TEXT NOT NULL,
            amount DOUBLE NOT NULL,
            due_date DATE,
            is_paid BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

    # --- Budgets ---
    def set_budget(self, month: str, category: str, amount: float):
        self.conn.execute("""
        INSERT INTO budgets (month, category, amount) VALUES (?, ?, ?)
        ON CONFLICT (month, category) DO UPDATE SET amount=excluded.amount;
        """, [month.capitalize(), category.capitalize(), amount])

    def edit_budget(self, month: str, category: str, amount: float):
        self.conn.execute("""
        UPDATE budgets SET amount = ? WHERE month = ? AND category = ?
        """, [amount, month.capitalize(), category.capitalize()])

    def delete_budget(self, month: str, category: str):
        self.conn.execute("""
        DELETE FROM budgets WHERE month = ? AND category = ?
        """, [month.capitalize(), category.capitalize()])

    def get_budgets(self, month: str) -> List[Dict[str, Any]]:
        res = self.conn.execute("""
        SELECT category, amount FROM budgets WHERE month = ?
        """, [month.capitalize()]).fetchall()
        return [{"category": r[0], "amount": r[1]} for r in res]

    # --- Expenses ---
    def log_expense(self, date_: date, category: str, amount: float, note: Optional[str] = None):
        self.conn.execute("""
        INSERT INTO expenses (date, category, amount, note) VALUES (?, ?, ?, ?)
        """, [date_, category.capitalize(), amount, note])

    def edit_expense(self, expense_id: int, category: Optional[str] = None,
                     amount: Optional[float] = None, note: Optional[str] = None):
        fields, values = [], []
        if category:
            fields.append("category = ?")
            values.append(category.capitalize())
        if amount is not None:
            fields.append("amount = ?")
            values.append(amount)
        if note is not None:
            fields.append("note = ?")
            values.append(note)
        if not fields:
            return
        values.append(expense_id)
        self.conn.execute(f"""
        UPDATE expenses SET {", ".join(fields)} WHERE id = ?
        """, values)

    def delete_expense(self, expense_id: int):
        self.conn.execute("DELETE FROM expenses WHERE id = ?", [expense_id])

    def get_expenses(self, month: str) -> List[Dict[str, Any]]:
        res = self.conn.execute("""
        SELECT id, date, category, amount, note
        FROM expenses
        WHERE STRFTIME(date, '%B') = ?
        ORDER BY date
        """, [month.capitalize()]).fetchall()
        return [{"id": r[0], "date": str(r[1]), "category": r[2], "amount": r[3], "note": r[4]} for r in res]

    # --- Debts/Bills ---
    def add_debt(self, description: str, amount: float):
        self.conn.execute("""
        INSERT INTO debts_bills (type, description, amount, is_paid) VALUES ('debt', ?, ?, FALSE)
        """, [description, amount])

    def add_bill(self, description: str, amount: float, due_date: date):
        self.conn.execute("""
        INSERT INTO debts_bills (type, description, amount, due_date, is_paid) VALUES ('bill', ?, ?, ?, FALSE)
        """, [description, amount, due_date])

    def mark_paid(self, debt_bill_id: int):
        self.conn.execute("UPDATE debts_bills SET is_paid = TRUE WHERE id = ?", [debt_bill_id])

    def delete_debt_bill(self, debt_bill_id: int):
        self.conn.execute("DELETE FROM debts_bills WHERE id = ?", [debt_bill_id])

    def get_debts_bills(self) -> List[Dict[str, Any]]:
        res = self.conn.execute("""
        SELECT id, type, description, amount, due_date, is_paid, created_at
        FROM debts_bills ORDER BY created_at DESC
        """).fetchall()
        return [{
            "id": r[0],
            "type": r[1],
            "description": r[2],
            "amount": r[3],
            "due_date": str(r[4]) if r[4] else None,
            "is_paid": bool(r[5]),
            "created_at": str(r[6])
        } for r in res]
