import random
import feedparser
import time
import json
import os
from datetime import datetime

class SatelliteEngine:
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

    
import feedparser

def fetch_live_news(self):
    # Fetch real financial news from Yahoo Finance RSS
    url = "https://finance.yahoo.com/news/rssindex"
    feed = feedparser.parse(url)
    headlines = []
    for entry in feed.entries[:5]:
        headlines.append({
            "type": "NEWS_SENTIMENT",
            "headline": entry.title,
            "source": "Yahoo Finance"
        })
    return headlines

    def generate_feed(self, market_regime="neutral"):
        feed = []
        if market_regime == "bullish": weights = [0.6, 0.1, 0.3]
        elif market_regime == "bearish": weights = [0.1, 0.6, 0.3]
        else: weights = [0.3, 0.3, 0.4]

        regime_choice = random.choices(["bullish", "bearish", "neutral"], weights=weights, k=1)[0]
        headline = random.choice(self.headlines[regime_choice])

        try:
            from python.quantcore.nlp.vader_engine import VaderEngine
            vader = VaderEngine()
            score = vader.analyze(headline)
        except:
            if regime_choice == "bullish": score = round(random.uniform(0.4, 0.95), 2)
            elif regime_choice == "bearish": score = round(random.uniform(-0.95, -0.4), 2)
            else: score = round(random.uniform(-0.2, 0.2), 2)

        feed.append({
            "type": "NEWS_SENTIMENT", "timestamp": datetime.now().isoformat(),
            "headline": headline, "sentiment_score": score,
            "confidence": round(random.uniform(0.75, 0.99), 2),
            "entities": random.sample(["BTC", "ETH", "Fed", "SEC", "Macro"], 2)
        })

        
        # Inject Real RSS News
        try:
            live_news = self.fetch_live_news()
            for news in live_news:
                score = self.analyze(news['headline']) if hasattr(self, 'analyze') else 0.0
                feed.insert(0, {
                    "type": "NEWS_SENTIMENT",
                    "timestamp": datetime.now().isoformat(),
                    "headline": news['headline'],
                    "sentiment_score": round(score, 3),
                    "confidence": 0.95,
                    "entities": ["MACRO", "LIVE"]
                })
        except Exception as e:
            print(f"[SATELLITE] RSS Error: {e}")

        whale_flow_btc = round(random.gauss(0, 500), 2)
        flow_signal = "SELL_PRESSURE" if whale_flow_btc > 200 else ("ACCUMULATION" if whale_flow_btc < -200 else "NEUTRAL")

        feed.append({
            "type": "WHALE_FLOW", "timestamp": datetime.now().isoformat(),
            "asset": "BTC", "net_flow_btc": whale_flow_btc,
            "signal": flow_signal, "exchange_inflow_usd": round(abs(whale_flow_btc) * 65000, 2)
        })

        try:
            existing = []
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f: existing = json.load(f)
            existing = (feed + existing)[:50]
            with open(self.state_file, "w") as f: json.dump(existing, f)
        except: pass
        return feed
