"""Analytics engine wrapping the C++ core for web API."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import os

import logging
yf_logger = logging.getLogger('yfinance')
yf_logger.setLevel(logging.CRITICAL)

import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
from typing import Dict, List, Any
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))
try:
    import quantcore.quantcore_cpp as core
    HAS_CPP = True
except ImportError as e:
    core = None
    HAS_CPP = False
    # Fallback will use pure-python implementations
    print(f"[WARN] quantcore_cpp not available ({e}); using Python fallback — build with 'cmake .. && make' for C++ acceleration")

from python.quantcore.logging_config import get_logger
from python.quantcore.data.provider import fetch_history_max, fetch_ohlcv

logger = get_logger(__name__)
if not HAS_CPP:
    logger.warning("C++ engine not found — AnalyticsEngine running in Python fallback mode (slower, but functional)")

# ——— Pure-Python fallback for feature_engine when C++ not built ———
class _FallbackFeatureEngine:
    @staticmethod
    def rolling_mean(prices, window):
        import pandas as pd
        s = pd.Series(prices)
        return s.rolling(window).mean().where(pd.notna(s.rolling(window).mean()), float('nan')).tolist()

    @staticmethod
    def rolling_std(prices, window):
        import pandas as pd
        s = pd.Series(prices)
        # ddof=1 to match C++ sample std
        return s.rolling(window).std(ddof=1).where(pd.notna(s.rolling(window).std(ddof=1)), float('nan')).tolist()

    @staticmethod
    def rolling_zscore(prices, window):
        import pandas as pd, numpy as np
        s = pd.Series(prices)
        mean = s.rolling(window).mean()
        std = s.rolling(window).std(ddof=1)
        z = (s - mean) / std
        # Match C++: 0.0 where std <= 1e-10 or NaN, NaN for insufficient history
        z = z.where(std > 1e-10, 0.0)
        # First window-1 remain NaN to match C++
        return z.tolist()

    @staticmethod
    def order_book_imbalance(bid_vols, ask_vols):
        import numpy as np
        bv = np.array(bid_vols); av = np.array(ask_vols)
        denom = bv + av
        return np.where(denom > 1e-10, (bv-av)/denom, 0.0).tolist()

class _FallbackDataEngine:
    def __init__(self, db_path="data/analytics.db"):
        import duckdb
        self.con = duckdb.connect(db_path)
        self._db_path = db_path
    def load_parquet_directory(self, name, dir):
        import os
        # Validate to prevent SQL injection (mirrors C++ qc_is_safe_identifier)
        if not name.replace("_","").isalnum() or len(name)>64:
            raise ValueError(f"Unsafe view name: {name}")
        if ".." in dir or "'" in dir or '"' in dir:
            raise ValueError(f"Unsafe dir: {dir}")
        # Drop view if exists, create from parquet
        try:
            self.con.execute(f"DROP VIEW IF EXISTS {name}")
            self.con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{dir}/*.parquet')")
        except Exception as e:
            # If no parquet files, create empty view so queries don't crash
            logger.warning(f"_FallbackDataEngine load_parquet_directory failed: {e}")
    def query_sql(self, sql):
        # Only allow SELECT-like queries
        upper = sql.strip().upper()
        if not any(upper.startswith(p) for p in ("SELECT","WITH","SHOW","DESCRIBE","EXPLAIN")):
            raise ValueError("Only SELECT queries allowed")
        return self.con.execute(sql).fetchall()
    def query_sql_dict(self, sql):
        return self.con.execute(sql).fetchall()
from python.quantcore.research.prediction_suite import (
    AdvancedPredictor,
    PredictionReviewer,
    PredictionScreener,
)

class AnalyticsEngine:
    @staticmethod
    def _sanitize_for_json(obj):
        """Recursively replaces NaN/Inf with None to prevent JSON serialization crashes."""
        import math
        if isinstance(obj, dict):
            return {k: AnalyticsEngine._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [AnalyticsEngine._sanitize_for_json(x) for x in obj]
        elif isinstance(obj, (float, int)):
            try:
                if math.isnan(obj) or math.isinf(obj):
                    return None
            except TypeError:
                pass
            return obj
        return obj

    def __init__(self):
        if HAS_CPP:
            self.data_engine = core.DataEngine("data/analytics.db")
            self.feature_engine = core.FeatureEngine()
        else:
            self.data_engine = _FallbackDataEngine("data/analytics.db")
            self.feature_engine = _FallbackFeatureEngine()
            logger.info("Using Python fallback engines")
        self._live_cache = {}  # FIX: 60s TTL cache to stop hammering yfinance
        self._load_local_cache()

    def _load_local_cache(self):
        try:
            self.data_engine.load_parquet_directory("market_data", "data/raw/equities/")
        except Exception as e:
            logger.warning(f"Could not load local cache: {e}")

    def add_symbol(self, symbol: str):
        symbol = symbol.upper()
        logger.info(f"Downloading max history for {symbol}")
        df = fetch_history_max(symbol)
        if df is None or df.empty:
            raise ValueError(f"No data found for {symbol} from any configured provider.")

        df['symbol'] = symbol
        df = df.reset_index()

        # Standardize the date column name
        if 'Date' not in df.columns and 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)
        elif 'Date' not in df.columns and 'Date' in df.index.names:
            df = df.reset_index()

        # Drop any weird multi-index artifacts just in case
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        table = pa.Table.from_pandas(df)
        pq.write_table(table, f"data/raw/equities/{symbol}.parquet")
        logger.info(f"Saved {symbol} to local cache")
        self._load_local_cache()

    @staticmethod
    def _period_start(period: str) -> pd.Timestamp | None:
        """Return a UTC cutoff for a standard dashboard period."""
        now = pd.Timestamp.now(tz="UTC")
        days = {
            "1d": 1, "5d": 5, "7d": 7, "1mo": 31, "2mo": 62,
            "3mo": 93, "6mo": 186, "1y": 366, "2y": 732,
            "5y": 1830, "10y": 3660,
        }
        if period == "ytd":
            return pd.Timestamp(year=now.year, month=1, day=1, tz="UTC")
        return now - pd.Timedelta(days=days[period]) if period in days else None

    def _load_local_history(self, symbol: str, period: str) -> pd.DataFrame | None:
        """Serve the persisted daily cache when external data is unavailable.

        Dashboard availability must not depend on a live provider: the local
        parquet cache is the durable source for daily trends and predictions.
        """
        path = Path("data/raw/equities") / f"{symbol.upper()}.parquet"
        if not path.is_file():
            return None
        try:
            df = pd.read_parquet(path)
            if "Date" not in df or "Close" not in df:
                return None
            df["Date"] = pd.to_datetime(df["Date"], utc=True, errors="coerce")
            df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
            if "Volume" not in df:
                df["Volume"] = 0
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
            df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
            cutoff = self._period_start(period)
            if cutoff is not None:
                filtered = df[df["Date"] >= cutoff]
                # Retain recent cached observations even if the cache is stale;
                # an empty chart is worse than clearly stale historical data.
                if not filtered.empty:
                    df = filtered
            if df.empty:
                return None
            df.attrs["data_source"] = "local_cache"
            df.attrs["data_interval"] = "1d"
            return df.reset_index(drop=True)
        except Exception as exc:
            logger.warning("Unable to read local cache for %s: %s", symbol, exc)
            return None

    def remove_symbol(self, symbol: str):
        symbol = symbol.upper()
        path = f"data/raw/equities/{symbol}.parquet"
        if os.path.exists(path):
            os.remove(path)
            self._load_local_cache()
        else:
            raise ValueError(f"{symbol} not found in database")

    def fetch_live_data(self, symbol: str, period: str, interval: str = "1d") -> pd.DataFrame:
        """Return market history with local-cache-first availability semantics.

        The persisted parquet history is the default source because dashboards
        should remain immediately usable during provider outages or rate limits.
        Set ``QUANTCORE_PREFER_LIVE_DATA=true`` to request a live refresh first.
        """
        import time as _time
        cache_key = f"{symbol}_{period}_{interval}"
        now = _time.time()
        cached = self._live_cache.get(cache_key)
        if cached is not None and (now - cached["ts"]) < 60:
            return cached["df"].copy()
        prefer_live = os.getenv("QUANTCORE_PREFER_LIVE_DATA", "").lower() in {"1", "true", "yes"}
        if not prefer_live:
            local = self._load_local_history(symbol, period)
            if local is not None:
                self._live_cache[cache_key] = {"df": local, "ts": now}
                return local.copy()
        logger.debug(f"Fetching {symbol} | {period} | {interval}")
        try:
            df = fetch_ohlcv(symbol, period, interval)
            df.attrs["data_source"] = "live_provider"
            df.attrs["data_interval"] = interval
        except Exception as exc:
            # All providers failed: serve last good data instead of erroring
            if cached is not None:
                logger.warning(f"All providers failed for {symbol}; serving stale cache")
                return cached["df"].copy()
            df = self._load_local_history(symbol, period)
            if df is None:
                raise ValueError(
                    f"No usable data for {symbol} ({period} / {interval}); "
                    f"live providers failed and no local cache exists."
                ) from exc
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.reset_index()
        if 'Date' not in df.columns and 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)
        # FIX: drop NaN Close rows so NaN never reaches the C++ engine / JSON
        if 'Close' in df.columns:
            df = df.dropna(subset=['Close'])
        self._live_cache[cache_key] = {"df": df, "ts": now}
        return df.copy()

    def get_symbols(self) -> List[str]:
        try:
            if HAS_CPP:
                result = self.data_engine.query_sql("SELECT DISTINCT symbol FROM market_data ORDER BY symbol")
                # C++ returns list of dicts with string values
                if result and isinstance(result[0], dict):
                    return [row['symbol'] for row in result]
                else:
                    # fallback duckdb rows are tuples
                    return [row[0] for row in result]
            else:
                # Fallback: query via duckdb directly, handles empty parquet
                rows = self.data_engine.con.execute("SELECT DISTINCT symbol FROM market_data ORDER BY symbol").fetchall()
                return [r[0] for r in rows if r[0]]
        except Exception as e:
            logger.debug(f"get_symbols fallback to directory scan: {e}")
            try:
                return [f.replace('.parquet', '') for f in os.listdir("data/raw/equities") if f.endswith('.parquet')]
            except Exception:
                return []

    def get_overview(self) -> Dict[str, Any]:
        symbols = self.get_symbols()
        latest_prices = {}
        for symbol in symbols[:6]:
            try:
                df = self.fetch_live_data(symbol, "5d", "1d")
                valid_prices = df['Close'].dropna()
                if not valid_prices.empty:
                    price = float(valid_prices.iloc[-1])
                    if price > 0: latest_prices[symbol] = price
            except Exception as e:
                logger.debug("Failed to fetch overview for %s: %s", symbol, e)
        return {"total_symbols": len(symbols), "latest_prices": latest_prices, "system_status": "Active", "last_update": datetime.now().isoformat()}

    def get_trend_analysis(self, symbol: str, period: str = "1y", interval: str = "1d") -> Dict[str, Any]:
        try:
            df = self.fetch_live_data(symbol, period, interval)
            data_source = df.attrs.get("data_source", "live_provider")
            data_interval = df.attrs.get("data_interval", interval)

            dates = []
            for d in df['Date']:
                if hasattr(d, 'strftime'):
                    # Format intraday with HH:MM, daily with just YYYY-MM-DD
                    if data_interval not in ['1d', '1wk', '1mo']:
                        dates.append(d.strftime('%Y-%m-%d %H:%M'))
                    else:
                        dates.append(d.strftime('%Y-%m-%d'))
                else:
                    dates.append(str(d)[:16])

            prices = df['Close'].astype(float).tolist()
            volumes = df['Volume'].astype(float).tolist()

            # Ensure we have enough data for the 50-period SMA
            if len(prices) < 50:
                # Fallback to daily 1y data for math context if intraday period is too short
                df_math = self.fetch_live_data(symbol, "1y", "1d")
                math_prices = df_math['Close'].dropna().astype(float).tolist()
                sma_20 = self.feature_engine.rolling_mean(math_prices, 20)
                sma_50 = self.feature_engine.rolling_mean(math_prices, 50)
                zscore = self.feature_engine.rolling_zscore(math_prices, 50)

                offset = max(0, len(math_prices) - len(prices))
                sma_20 = sma_20[offset:]
                sma_50 = sma_50[offset:]
                zscore = zscore[offset:]

                # Safety padding: if math data was somehow shorter than UI data, pad with 0.0
                while len(zscore) < len(prices):
                    zscore.append(0.0)
                    sma_20.append(0.0)
                    sma_50.append(0.0)
            else:
                sma_20 = self.feature_engine.rolling_mean(prices, 20)
                sma_50 = self.feature_engine.rolling_mean(prices, 50)
                zscore = self.feature_engine.rolling_zscore(prices, 50)

            signals = []
            for i in range(min(len(prices), len(zscore))):
                if zscore[i] == 0.0 and i < 50: continue
                if zscore[i] > 2.0: signals.append({"date": dates[i], "type": "SELL", "price": prices[i]})
                elif zscore[i] < -2.0: signals.append({"date": dates[i], "type": "BUY", "price": prices[i]})

            current_price = prices[-1] if prices else 0
            current_sma20 = sma_20[-1] if sma_20 else 0
            trend = "BULLISH" if current_price > current_sma20 else "BEARISH"

            return self._sanitize_for_json({"symbol": symbol, "dates": dates, "prices": prices, "volumes": volumes, "sma_20": sma_20, "sma_50": sma_50, "zscore": zscore, "signals": signals[-10:], "current_trend": trend, "current_price": current_price, "price_change": ((prices[-1] - prices[-2]) / prices[-2] * 100) if len(prices) > 1 else 0, "data_source": data_source, "data_interval": data_interval})
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def get_predictions(self, symbol: str, period: str = "1y", interval: str = "1d") -> Dict[str, Any]:
        try:
            # Always fetch daily data for prediction math stability
            df_math = self.fetch_live_data(symbol, "1y", "1d")
            # FIX A: Drop NaN rows before passing to C++ engine
            math_prices = df_math['Close'].dropna().astype(float).tolist()

            if len(math_prices) < 20:
                return {"error": "Insufficient clean data for predictions"}

            features = {
                "zscore_20": self.feature_engine.rolling_zscore(math_prices, 20),
                "volatility": self.feature_engine.rolling_std(math_prices, 20)
            }
            current_zscore = features["zscore_20"][-1] if features["zscore_20"] else 0
            current_vol = features["volatility"][-1] if features["volatility"] else 0

            # FIX A: Guard against NaN/Inf in zscore and volatility
            import math as _math
            if not _math.isfinite(current_zscore): current_zscore = 0.0
            if not _math.isfinite(current_vol): current_vol = 0.0

            trend_data = self.get_trend_analysis(symbol, period, interval)
            predictions = []
            base_price = math_prices[-1]

            # --- FUTURE DATE INJECTION ---
            last_date_str = trend_data['dates'][-1] if trend_data.get('dates') else None
            try:
                if interval in ['1d', '1wk', '1mo']:
                    last_dt = datetime.strptime(last_date_str, '%Y-%m-%d')
                else:
                    last_dt = datetime.strptime(last_date_str, '%Y-%m-%d %H:%M')
            except Exception:
                last_dt = datetime.now()

            deltas = {'1m': timedelta(minutes=1), '5m': timedelta(minutes=5), '15m': timedelta(minutes=15),
                      '30m': timedelta(minutes=30), '1h': timedelta(hours=1), '1d': timedelta(days=1),
                      '1wk': timedelta(weeks=1), '1mo': timedelta(days=30)}
            delta = deltas.get(interval, timedelta(days=1))

            for i in range(1, 6):
                pred_price = base_price * (1 - current_zscore * 0.01 * i) if abs(current_zscore) > 1.5 else base_price * (1 + current_zscore * 0.005 * i)
                # FIX A: Clamp prediction to prevent NaN/Inf from propagating
                if not _math.isfinite(pred_price): pred_price = base_price
                future_dt = last_dt + (delta * i)
                future_str = future_dt.strftime('%Y-%m-%d') if interval in ['1d', '1wk', '1mo'] else future_dt.strftime('%Y-%m-%d %H:%M')
                predictions.append({"day": i, "date": future_str, "price": pred_price, "confidence": max(0.5, 1.0 - abs(current_zscore) * 0.1)})

            # FIX A: Sanitize the ENTIRE return value to prevent NaN JSON crashes
            return self._sanitize_for_json({
                "symbol": symbol, "current_price": base_price, "predictions": predictions,
                "zscore": current_zscore, "volatility": current_vol,
                "recommendation": "HOLD" if abs(current_zscore) < 1.0 else ("BUY" if current_zscore < -1.5 else "SELL"),
                "historical": trend_data
            })
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def get_recent_signals(self) -> List[Dict[str, Any]]:
        signals = []
        for symbol in self.get_symbols()[:5]:
            try:
                analysis = self.get_trend_analysis(symbol, "5d", "1h")
                if "signals" in analysis:
                    for sig in analysis["signals"][-3:]: signals.append({"symbol": symbol, "date": sig["date"], "type": sig["type"], "price": sig["price"]})
            except Exception as e:
                logger.debug("Signal scan failed for %s: %s", symbol, e)
        signals.sort(key=lambda x: x["date"], reverse=True)
        return signals[:20]

    def get_performance_metrics(self) -> Dict[str, Any]:
        try:
            result = self.data_engine.query_sql(
                "SELECT COUNT(*) as total_trades FROM market_data"
            )
            total_trades = int(result[0]['total_trades']) if result else 0
            return {
                "sharpe_ratio": None,
                "max_drawdown": None,
                "win_rate": None,
                "total_trades": total_trades,
                "avg_return": None,
                "volatility": None,
                "message": "Performance metrics require completed backtest data"
            }
        except Exception:
            return {"sharpe_ratio": None, "max_drawdown": None, "win_rate": None,
                    "total_trades": 0, "avg_return": None, "volatility": None}

    def get_advanced_predictions(self, symbol: str, period: str = "1y", interval: str = "1d", horizon_steps: int = 10) -> Dict[str, Any]:
        """
        Executes the extreme multi-model predictive suite combining OU mean reversion,
        momentum drift, Monte Carlo probability cones, and volume profile liquidity levels.
        """
        try:
            df = self.fetch_live_data(symbol, period, interval)
            if df is None or len(df) < 20:
                # Fallback to 1y daily if intraday history is too thin
                df = self.fetch_live_data(symbol, "1y", "1d")
                interval = "1d"

            prediction_data = AdvancedPredictor.analyze_and_predict(
                df, horizon_steps=horizon_steps, num_simulations=1000
            )

            # Extract formatted dates and price arrays for charting
            date_col = "Date" if "Date" in df.columns else ("Datetime" if "Datetime" in df.columns else df.columns[0])
            dates = []
            for d in df[date_col]:
                if hasattr(d, "strftime"):
                    dates.append(d.strftime("%Y-%m-%d %H:%M") if interval not in ("1d", "1wk", "1mo") else d.strftime("%Y-%m-%d"))
                else:
                    dates.append(str(d)[:16])

            # Future dates generation for forecast alignment
            last_date_str = dates[-1] if dates else None
            try:
                if interval in ("1d", "1wk", "1mo"):
                    last_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
                else:
                    last_dt = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M")
            except Exception:
                last_dt = datetime.now()

            deltas = {
                "1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "15m": timedelta(minutes=15),
                "30m": timedelta(minutes=30), "1h": timedelta(hours=1), "1d": timedelta(days=1),
                "1wk": timedelta(weeks=1), "1mo": timedelta(days=30),
            }
            step_delta = deltas.get(interval, timedelta(days=1))

            future_dates = []
            for i in range(1, horizon_steps + 1):
                f_dt = last_dt + (step_delta * i)
                future_dates.append(f_dt.strftime("%Y-%m-%d %H:%M") if interval not in ("1d", "1wk", "1mo") else f_dt.strftime("%Y-%m-%d"))

            # Attach future dates into forecast_steps
            for idx, step in enumerate(prediction_data["forecast_steps"]):
                if idx < len(future_dates):
                    step["date"] = future_dates[idx]

            return self._sanitize_for_json({
                "symbol": symbol.upper(),
                "period": period,
                "interval": interval,
                "historical": {
                    "dates": dates[-60:],
                    "open": df["Open"].astype(float).tolist()[-60:] if "Open" in df else df["Close"].astype(float).tolist()[-60:],
                    "high": df["High"].astype(float).tolist()[-60:] if "High" in df else df["Close"].astype(float).tolist()[-60:],
                    "low": df["Low"].astype(float).tolist()[-60:] if "Low" in df else df["Close"].astype(float).tolist()[-60:],
                    "close": df["Close"].astype(float).tolist()[-60:],
                    "volume": df["Volume"].astype(float).tolist()[-60:] if "Volume" in df else [0] * min(60, len(df)),
                },
                "future_dates": future_dates,
                "prediction": prediction_data,
            })
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def get_prediction_review(self, symbol: str, period: str = "1y", interval: str = "1d", walk_forward_bars: int = 40) -> Dict[str, Any]:
        """
        Runs an out-of-sample walk-forward prediction audit on historical data.
        Evaluates directional accuracy, MAE, RMSE, and past forecast overlays.
        """
        try:
            df = self.fetch_live_data(symbol, period, interval)
            if df is None or len(df) < 50:
                df = self.fetch_live_data(symbol, "1y", "1d")
                interval = "1d"

            audit_report = PredictionReviewer.audit_predictions(
                df, walk_forward_bars=walk_forward_bars, forecast_horizon=5
            )
            audit_report["symbol"] = symbol.upper()
            audit_report["interval"] = interval
            audit_report["period"] = period
            return self._sanitize_for_json(audit_report)
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def get_prediction_screener(self, interval: str = "1d", period: str = "1y") -> List[Dict[str, Any]]:
        """
        Scans all tracked symbols and generates a predictive conviction leaderboard.
        """
        try:
            symbols = self.get_symbols()
            if not symbols:
                symbols = ["SPY", "QQQ", "IWM", "GLD", "TLT", "BTC-USD", "ETH-USD"]
            screener_data = PredictionScreener.scan_universe(self, symbols[:15], interval=interval, period=period)
            return self._sanitize_for_json(screener_data)
        except Exception as e:
            traceback.print_exc()
            return []
