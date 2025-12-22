import torch
import torch.nn as nn
import torch.nn.functional as F
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, BertModel

app = FastAPI(title="Sentiment Analysis Service")

# --- CONFIGURATION ---
# This must match the model used inside SentimentClassifier
BASE_MODEL_NAME = "dbmdz/bert-base-german-cased" 
MODEL_PATH = "/app/model.pth"  # Ensure this points to your NEW clean file
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# --- MODEL DEFINITION ---
class SentimentClassifier(nn.Module):
    """
    BERT-based sentiment classifier for German-language text.
    """
    def __init__(self, n_classes):
        super(SentimentClassifier, self).__init__()
        self.bert = BertModel.from_pretrained(BASE_MODEL_NAME)
        self.drop = nn.Dropout(p=0.3)
        self.out = nn.Linear(self.bert.config.hidden_size, n_classes)

    def forward(self, input_ids, attention_mask, token_type_ids=None):
        bert_output = self.bert(
            input_ids=input_ids, 
            attention_mask=attention_mask
        )
        pooled_output = bert_output.pooler_output
        output = self.drop(pooled_output)
        return self.out(output)

# Global variables
model = None
tokenizer = None
labels = {0: 'Negative', 1: 'Neutral', 2: 'Positive'} 

@app.on_event("startup")
async def load_model():
    global model, tokenizer
    print("Loading BERT model...")
    
    # 1. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    
    # 2. Load the Clean Model (Weights Only)
    try:
        # A. Initialize the architecture first
        model = SentimentClassifier(n_classes=3)
        
        # B. Load the weights (state_dict) safely
        # Note: we use weights_only=True by default in newer torch, which is safe!
        state_dict = torch.load(MODEL_PATH, map_location=device)
        
        # C. Apply weights to the architecture
        model.load_state_dict(state_dict)
        
        model.to(device)
        model.eval()
        print("Model loaded successfully (Safe Mode)!")
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e

class SentimentRequest(BaseModel):
    text: str

@app.post("/predict")
async def predict_sentiment(request: SentimentRequest):
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
        
    inputs = tokenizer(
        request.text, 
        return_tensors="pt", 
        truncation=True, 
        padding=True, 
        max_length=512
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        # Pass inputs to model
        outputs = model(
            input_ids=inputs['input_ids'], 
            attention_mask=inputs['attention_mask']
        )
        
        # CRITICAL FIX: Your class returns a Tensor, not an object with .logits
        # Old code: F.softmax(outputs.logits, ...) -> Wrong
        # New code: F.softmax(outputs, ...)        -> Correct
        probabilities = F.softmax(outputs, dim=-1)
        prediction = torch.argmax(probabilities, dim=-1).item()

    return {"sentiment": labels[prediction]}
