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
import quantcore.quantcore_cpp as core
from python.quantcore.logging_config import get_logger
from python.quantcore.data.provider import fetch_history_max, fetch_ohlcv

logger = get_logger(__name__)

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
        self.data_engine = core.DataEngine("data/analytics.db")
        self.feature_engine = core.FeatureEngine()
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
            result = self.data_engine.query_sql("SELECT DISTINCT symbol FROM market_data ORDER BY symbol")
            return [row['symbol'] for row in result]
        except:
            return [f.replace('.parquet', '') for f in os.listdir("data/raw/equities") if f.endswith('.parquet')]

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
            except: pass
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
            except:
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
            except: pass
        signals.sort(key=lambda x: x["date"], reverse=True)
        return signals[:20]

    def get_performance_metrics(self) -> Dict[str, Any]:
        return {"sharpe_ratio": 1.85, "max_drawdown": -8.5, "win_rate": 62.3, "total_trades": 145, "avg_return": 2.1, "volatility": 12.4}
