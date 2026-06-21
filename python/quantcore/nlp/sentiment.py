from llama_cpp import Llama
from pathlib import Path
import json

class SentimentEngine:
    def __init__(self, model_path: str = "data/models/llama-3-8b-instruct.Q4_K_M.gguf", n_gpu_layers: int = -1):
        if not Path(model_path).exists(): raise FileNotFoundError(f"Model not found at {model_path}")
        self.llm = Llama(model_path=model_path, n_gpu_layers=n_gpu_layers, n_ctx=4096, verbose=False)
        self.prompt = "Analyze financial text and return JSON: {{\"sentiment\": float(-1 to 1)}}\nText: {text}\nJSON:"

    def analyze(self, text: str) -> dict:
        response = self.llm.create_completion(prompt=self.prompt.format(text=text), max_tokens=64, temperature=0.1)
        try: return json.loads(response['choices'][0]['text'].strip())
        except: return {"sentiment": 0.0}
