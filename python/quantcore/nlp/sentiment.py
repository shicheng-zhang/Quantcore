from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class SentimentEngine:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        
    def analyze(self, text: str) -> dict:
        scores = self.analyzer.polarity_scores(text)
        return {"sentiment": scores['compound']}
