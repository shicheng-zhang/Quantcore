import duckdb
import os
import threading


class PaperLedger:
    def __init__(self, db_path="data/paper_broker.duckdb"):
        os.makedirs("data", exist_ok=True)
        self.con = duckdb.connect(db_path)
        # FIX #7: Reentrant lock serializes all DuckDB access.
        # DuckDB is NOT safe for concurrent multi-threaded reads/writes.
        self._lock = threading.RLock()
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
        with self._lock:
            try:
                cash = self.con.execute("SELECT cash FROM account").fetchone()[0]
                initial = self.con.execute("SELECT initial_cash FROM account").fetchone()[0]
                positions = self.con.execute(
                    "SELECT symbol, qty, avg_cost FROM positions WHERE qty != 0"
                ).fetchall()
                return {"cash": cash, "initial_cash": initial, "positions": positions}
            except Exception as e:
                print(f"[LEDGER ERROR] get_state: {e}")
                return {"cash": 1000000.0, "initial_cash": 1000000.0, "positions": []}

    def reset_account(self):
        with self._lock:
            self.con.execute("DELETE FROM positions")
            self.con.execute("DELETE FROM trades")
            self.con.execute("UPDATE account SET cash = initial_cash")

    def execute_fill(self, symbol, side, qty, price, slip_bps, commission):
        # FIX #7: All writes serialized under RLock to prevent DuckDB corruption
        with self._lock:
            try:
                cost = qty * price
                slip_cost = cost * (slip_bps / 10000.0)

                if side == "BUY":
                    self.con.execute(
                        "UPDATE account SET cash = cash - ?",
                        [cost + slip_cost + commission]
                    )
                else:
                    self.con.execute(
                        "UPDATE account SET cash = cash + ?",
                        [cost - slip_cost - commission]
                    )

                pos = self.con.execute(
                    "SELECT qty, avg_cost FROM positions WHERE symbol = ?",
                    [symbol]
                ).fetchone()
                curr_qty, curr_avg = pos if pos else (0.0, 0.0)

                if side == "BUY":
                    new_qty = curr_qty + qty
                    new_avg = ((curr_qty * curr_avg) + cost) / new_qty if new_qty > 0 else price
                else:
                    new_qty = curr_qty - qty
                    new_avg = curr_avg

                self.con.execute("""
                    INSERT INTO positions (symbol, qty, avg_cost) VALUES (?, ?, ?)
                    ON CONFLICT (symbol) DO UPDATE SET qty = ?, avg_cost = ?
                """, [symbol, new_qty, new_avg, new_qty, new_avg])

                self.con.execute("""
                    INSERT INTO trades (ts, symbol, side, qty, price, slippage_bps, commission)
                    VALUES (current_timestamp, ?, ?, ?, ?, ?, ?)
                """, [symbol, side, qty, price, slip_bps, commission])

                print(f"[LEDGER] FILLED: {side} {qty} {symbol} @ {price}")
            except Exception as e:
                print(f"[LEDGER ERROR] execute_fill: {e}")

    def get_recent_trades(self, limit=20):
        with self._lock:
            try:
                return self.con.execute(
                    "SELECT * FROM trades ORDER BY ts DESC LIMIT ?",
                    [limit]
                ).fetchall()
            except:
                return []
