import duckdb
import os
import time

class PaperLedger:
    def __init__(self, db_path="data/paper_broker.duckdb"):
        os.makedirs("data", exist_ok=True)
        self.con = duckdb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS account (cash DOUBLE, initial_cash DOUBLE);
            CREATE TABLE IF NOT EXISTS positions (symbol VARCHAR PRIMARY KEY, qty DOUBLE, avg_cost DOUBLE);
            CREATE TABLE IF NOT EXISTS trades (ts TIMESTAMP, symbol VARCHAR, side VARCHAR, qty DOUBLE, price DOUBLE, slippage_bps DOUBLE, commission DOUBLE);
        """)
        if self.con.execute("SELECT count(*) FROM account").fetchone()[0] == 0:
            self.con.execute("INSERT INTO account VALUES (1000000.0, 1000000.0)")

    def get_state(self):
        cash = self.con.execute("SELECT cash FROM account").fetchone()[0]
        initial = self.con.execute("SELECT initial_cash FROM account").fetchone()[0]
        positions = self.con.execute("SELECT symbol, qty, avg_cost FROM positions WHERE qty != 0").fetchall()
        return {"cash": cash, "initial_cash": initial, "positions": positions}

    def reset_account(self):
        self.con.execute("DELETE FROM positions")
        self.con.execute("DELETE FROM trades")
        self.con.execute("UPDATE account SET cash = initial_cash")

    def execute_fill(self, symbol, side, qty, price, slip_bps, commission):
        # 1. Update Cash
        cost = qty * price
        slip_cost = cost * (slip_bps / 10000.0)
        total_cost = cost + slip_cost + commission

        if side == "BUY":
            self.con.execute(f"UPDATE account SET cash = cash - {total_cost}")
        else:
            self.con.execute(f"UPDATE account SET cash = cash + {cost - slip_cost - commission}")

        # 2. Update Positions
        pos = self.con.execute(f"SELECT qty, avg_cost FROM positions WHERE symbol = '{symbol}'").fetchone()
        if not pos:
            pos = (0, 0)

        curr_qty, curr_avg = pos
        if side == "BUY":
            new_qty = curr_qty + qty
            new_avg = ((curr_qty * curr_avg) + cost) / new_qty if new_qty > 0 else price
        else:
            new_qty = curr_qty - qty
            new_avg = curr_avg # Avg cost doesn't change on sell

        self.con.execute(f"""
            INSERT INTO positions (symbol, qty, avg_cost) VALUES ('{symbol}', {new_qty}, {new_avg})
            ON CONFLICT (symbol) DO UPDATE SET qty = {new_qty}, avg_cost = {new_avg}
        """)

        # 3. Log Trade
        self.con.execute(f"""
            INSERT INTO trades (ts, symbol, side, qty, price, slippage_bps, commission)
            VALUES (current_timestamp, '{symbol}', '{side}', {qty}, {price}, {slip_bps}, {commission})
        """)

        return {"new_qty": new_qty, "new_avg": new_avg}

    def get_recent_trades(self, limit=20):
        return self.con.execute(f"SELECT * FROM trades ORDER BY ts DESC LIMIT {limit}").fetchall()
