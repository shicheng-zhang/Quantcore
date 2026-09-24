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

    def score_with_confidence(self, text: str) -> tuple[float, float]:
        """
        Returns (compound, confidence). Confidence derived from fraction of
        lexicon hits and intensity: 0.5 + 0.5*|compound| scaled by word count,
        clipped to [0.5, 0.99]. Stronger polarity and longer texts -> higher confidence.
        """
        scores = self.analyzer.polarity_scores(text)
        compound = scores['compound']
        # neu is proportion of neutral words; lower neu -> more opinionated
        neu = scores.get('neu', 1.0)
        # Word count proxy via token length
        n_words = max(1, len(text.split()))
        # Confidence: base 0.5, plus polarity strength, minus neutral dilution, plus length bonus
        conf = 0.50 + 0.35 * abs(compound) + 0.15 * (1 - neu) + min(0.10, n_words / 100)
        conf = float(max(0.50, min(0.99, conf)))
        return compound, conf

    def ingest_news(self, headline: str, entities: list):
        score, conf = self.score_with_confidence(headline)
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
            "confidence": round(conf, 3),
            "entities": entities
        })
        
        # Keep last 100 items
        feed = feed[:100]
        with open(self.feed_file, "w") as f:
            json.dump(feed, f)
