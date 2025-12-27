from __future__ import annotations

import os
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, BertModel


BASE_MODEL_NAME = os.getenv("SENTIMENT_BASE_MODEL", "dbmdz/bert-base-german-cased")
MODEL_PATH = os.getenv("MODEL_PATH", "/app/model.pth")

LABELS = {0: "Negative", 1: "Neutral", 2: "Positive"}


class SentimentClassifier(nn.Module):
    def __init__(self, n_classes: int = 3):
        super().__init__()
        self.bert = BertModel.from_pretrained(BASE_MODEL_NAME)
        self.drop = nn.Dropout(p=0.3)
        self.out = nn.Linear(self.bert.config.hidden_size, n_classes)

    def forward(self, input_ids, attention_mask, token_type_ids=None):
        bert_output = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = bert_output.pooler_output
        output = self.drop(pooled_output)
        return self.out(output)


@dataclass
class SentimentRuntime:
    model: SentimentClassifier
    tokenizer: any
    device: torch.device


def load_runtime(
    *,
    model_path: str | None = None,
    device: torch.device | None = None,
) -> SentimentRuntime:
    """
    Lädt Tokenizer + Modell (state_dict) und gibt ein Runtime-Objekt zurück.
    """
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    path = model_path or MODEL_PATH

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)

    model = SentimentClassifier(n_classes=3)
    state = torch.load(path, map_location=device)
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    return SentimentRuntime(model=model, tokenizer=tokenizer, device=device)


def predict(runtime: SentimentRuntime, text: str) -> str:
    """
    Macht eine Vorhersage für einen Text und gibt das Label zurück.
    """
    inputs = runtime.tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=512
    )
    inputs = {k: v.to(runtime.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = runtime.model(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
        )
        probabilities = F.softmax(outputs, dim=-1)
        pred = torch.argmax(probabilities, dim=-1).item()

    return LABELS[pred]
