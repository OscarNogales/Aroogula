"""FinBERT classifier wrapper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch
from safetensors.torch import load_file
from torch import nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


class MultiTaskFinBert(nn.Module):
    """FinBERT base model with sentiment and tradeability heads."""

    def __init__(self):
        super().__init__()
        self.bert = AutoModelForSequenceClassification.from_pretrained("ProsusAI/Finbert")
        hidden_size = self.bert.config.hidden_size
        self.sentiment = nn.Linear(hidden_size, 3)
        self.tradeable = nn.Linear(hidden_size, 2)

    def forward(self, input_ids: Any, attention_mask: Any, **kwargs: Any):
        outputs = self.bert.base_model(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output
        sentiment_logits = self.sentiment(pooled_output)
        tradeable_logits = self.tradeable(pooled_output)
        return sentiment_logits, tradeable_logits


class FinBERTClassifier:
    """Loads the fine-tuned FinBERT model and returns structured predictions."""

    def __init__(self, model_path: str | Path, device: str = "cpu"):
        if device not in {"cuda", "cpu"}:
            raise ValueError("FinBERT device must be 'cuda' or 'cpu'.")

        self.model_path = Path(model_path)
        self.device = device
        self.tokenizer: AutoTokenizer | None = None
        self.model: MultiTaskFinBert | None = None
        self._load()

    def _load(self) -> None:
        logger.info("Loading FinBERT on %s.", self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
        self.model = MultiTaskFinBert()

        state_dict = load_file(str(self.model_path / "model.safetensors"))
        corrected_state_dict = {}
        for key, value in state_dict.items():
            if key.startswith("bert.") and not key.startswith("bert.bert."):
                corrected_state_dict[key.replace("bert.", "bert.bert.", 1)] = value
            else:
                corrected_state_dict[key] = value

        self.model.load_state_dict(corrected_state_dict, strict=False)
        self.model.eval()
        self.model.to(self.device)
        logger.info("FinBERT loaded successfully.")

    def predict(self, text: str) -> dict:
        """Return sentiment/tradeability labels and probabilities."""
        if self.tokenizer is None or self.model is None:
            raise RuntimeError("FinBERTClassifier was not loaded correctly.")

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=256,
        ).to(self.device)

        with torch.no_grad():
            logits_sent, logits_trad = self.model(**inputs)

        probs_sent = torch.softmax(logits_sent, dim=-1)
        probs_trad = torch.softmax(logits_trad, dim=-1)

        idx_s = int(torch.argmax(probs_sent, dim=-1).item())
        idx_t = int(torch.argmax(probs_trad, dim=-1).item())

        sent_labels = ["positive", "negative", "neutral"]
        trad_labels = [False, True]

        return {
            "sentiment": sent_labels[idx_s],
            "tradeable": trad_labels[idx_t],
            "sentiment_score": float(probs_sent[0][idx_s].item()),
            "tradeable_score": float(probs_trad[0][idx_t].item()),
        }
