import random
import time
import json
import os
from datetime import datetime
from ..logging_config import get_logger

logger = get_logger(__name__)


class SatelliteEngine:
    """Satellite Layer: orthogonal alternative-data signals.

    Produces NLP news sentiment (synthetic regime headlines + live RSS)
    and synthetic on-chain whale flows. Everything fails gracefully:
    a dead RSS endpoint must never stall or kill the feed.
    """

    # Yahoo's RSS endpoint is dead. These are live, reliable financial feeds.
    RSS_SOURCES = [
        ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ]

    def __init__(self):
        self.headlines = {
            "bullish": [
                "BlackRock reports record inflows into spot ETF products.",
                "Federal Reserve signals potential rate cuts in upcoming quarter.",
                "Major tech earnings beat expectations, driving risk-on sentiment.",
                "On-chain data shows massive accumulation by long-term holders.",
                "Institutional adoption reaches new all-time high according to survey."
            ],
            "bearish": [
                "Regulatory agency announces aggressive new enforcement actions.",
                "Macro inflation data comes in hotter than expected, spooking markets.",
                "Major exchange reports unexpected withdrawal delays.",
                "Whale wallets move record amounts to exchanges, signaling potential sell-off.",
                "Liquidity crisis fears emerge in shadow banking sector."
            ],
            "neutral": [
                "Trading volumes remain flat as market awaits macroeconomic catalyst.",
                "Consolidation phase continues as volatility compresses.",
                "Analysts divided on near-term direction amid mixed signals.",
                "Network upgrades deployed successfully with minimal market impact."
            ]
        }
        self.state_file = "data/satellite_feed.json"
        self._last_rss_fetch = 0
        self._rss_cache = []
        self._vader = None

    def _score(self, text):
        """VADER compound sentiment. Returns None if the engine is unavailable."""
        try:
            if self._vader is None:
                try:
                    from python.quantcore.nlp.vader_engine import VaderEngine
                except ImportError:
                    from quantcore.nlp.vader_engine import VaderEngine
                self._vader = VaderEngine()
            return float(self._vader.analyze(text))
        except Exception:
            return None

    def fetch_live_news(self):
        """Fetch real financial headlines via RSS with a HARD timeout.

        Cached for 60s so the 1-second UI poll never hammers the endpoint,
        and a hung network can never block the dashboard.
        """
        now = time.time()
        if self._rss_cache and (now - self._last_rss_fetch) < 60:
            return self._rss_cache

        headlines = []
        try:
            import feedparser
            import requests
            for source_name, url in self.RSS_SOURCES:
                try:
                    resp = requests.get(url, timeout=4, headers={"User-Agent": "QuantCore/1.0"})
                    if resp.status_code != 200:
                        continue
                    feed = feedparser.parse(resp.text)
                    for entry in feed.entries[:5]:
                        title = (entry.get("title") or "").strip()
                        if title:
                            headlines.append({
                                "type": "NEWS_SENTIMENT",
                                "headline": title,
                                "source": source_name,
                            })
                    if headlines:
                        break  # first live source wins
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"RSS fetch error: {e}")

        self._rss_cache = headlines
        self._last_rss_fetch = now
        return headlines

    def generate_feed(self, market_regime="neutral"):
        feed = []

        # 1. Synthetic regime headline (no network, always works)
        if market_regime == "bullish": weights = [0.6, 0.1, 0.3]
        elif market_regime == "bearish": weights = [0.1, 0.6, 0.3]
        else: weights = [0.3, 0.3, 0.4]
        regime_choice = random.choices(["bullish", "bearish", "neutral"], weights=weights, k=1)[0]
        headline = random.choice(self.headlines[regime_choice])
        score = self._score(headline)
        if score is None:
            # VADER unavailable -> fall back to regime-based synthetic score
            if regime_choice == "bullish": score = round(random.uniform(0.4, 0.95), 2)
            elif regime_choice == "bearish": score = round(random.uniform(-0.95, -0.4), 2)
            else: score = round(random.uniform(-0.2, 0.2), 2)
        feed.append({
            "type": "NEWS_SENTIMENT", "timestamp": datetime.now().isoformat(),
            "headline": headline, "sentiment_score": round(float(score), 3),
            "confidence": round(random.uniform(0.75, 0.99), 2),
            "entities": random.sample(["BTC", "ETH", "Fed", "SEC", "Macro"], 2)
        })

        # 2. Whale flow BEFORE any network call, so the on-chain radar
        #    populates even when the internet is dead.
        whale_flow_btc = round(random.gauss(0, 500), 2)
        flow_signal = "SELL_PRESSURE" if whale_flow_btc > 200 else ("ACCUMULATION" if whale_flow_btc < -200 else "NEUTRAL")
        feed.append({
            "type": "WHALE_FLOW", "timestamp": datetime.now().isoformat(),
            "asset": "BTC", "net_flow_btc": whale_flow_btc,
            "signal": flow_signal, "exchange_inflow_usd": round(abs(whale_flow_btc) * 65000, 2)
        })

        # 3. Live RSS news, scored by VADER (no more hardcoded 0.0)
        try:
            for news in self.fetch_live_news():
                s = self._score(news["headline"])
                feed.insert(0, {
                    "type": "NEWS_SENTIMENT",
                    "timestamp": datetime.now().isoformat(),
                    "headline": news["headline"],
                    "sentiment_score": round(s, 3) if s is not None else 0.0,
                    "confidence": 0.95,
                    "entities": ["MACRO", "LIVE"]
                })
        except Exception as e:
            logger.warning(f"RSS inject error: {e}")

        # 4. Persist a deduplicated rolling window
        existing = []
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        try:
            combined = feed + existing
            seen_headlines = set()
            deduped = []
            for item in combined:
                if item.get("type") == "NEWS_SENTIMENT":
                    h = item.get("headline", "")
                    if h in seen_headlines:
                        continue
                    seen_headlines.add(h)
                deduped.append(item)
            with open(self.state_file, "w") as f:
                json.dump(deduped[:50], f)
        except Exception:
            pass
        return feed
