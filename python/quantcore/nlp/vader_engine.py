from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import json
import os
import logging
from datetime import datetime

class VaderEngine:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.feed_file = "data/satellite_feed.json"

    def analyze(self, text: str) -> float:
        # Returns compound score from -1.0 (extremely negative) to 1.0 (extremely positive)
        return self.analyzer.polarity_scores(text)['compound']

    def ingest_news(self, headline: str, entities: list):
        score = self.analyze(headline)
        feed = []
        if os.path.exists(self.feed_file):
            try:
                with open(self.feed_file, "r") as f: feed = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
                logging.getLogger(__name__).debug("Feed file read error: %s", e)
        
        feed.insert(0, {
            "type": "NEWS_SENTIMENT",
            "timestamp": datetime.now().isoformat(),
            "headline": headline,
            "sentiment_score": round(score, 3),
            "confidence": 0.95,
            "entities": entities
        })
        
        # Keep last 100 items
        feed = feed[:100]
        with open(self.feed_file, "w") as f:
            json.dump(feed, f)
