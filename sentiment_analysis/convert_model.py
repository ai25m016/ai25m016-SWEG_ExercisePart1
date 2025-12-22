# sentiment_analysis/convert_model.py
import torch
import __main__
from transformers import BertModel
import torch.nn as nn

# 1. Define the class exactly as it is in the pickle
class SentimentClassifier(nn.Module):
    def __init__(self, n_classes=3):
        super(SentimentClassifier, self).__init__()
        self.bert = BertModel.from_pretrained("bert-base-german-cased")
        self.drop = nn.Dropout(p=0.3)
        self.out = nn.Linear(self.bert.config.hidden_size, n_classes)
  
    def forward(self, input_ids, attention_mask, token_type_ids=None):
        _, pooled_output = self.bert(
          input_ids=input_ids,
          attention_mask=attention_mask,
          return_dict=False
        )
        output = self.drop(pooled_output)
        return self.out(output)

# 2. Monkey-patch the environment so pickle finds the class
setattr(__main__, "SentimentClassifier", SentimentClassifier)

# 3. Load the problematic full model
print("⏳ Loading full model (legacy mode)...")
# We use a safe loading trick if strict loading fails
model = torch.load("models/bert.pth", map_location="cpu", weights_only=False)

# 4. Extract ONLY the weights
print("💾 Extracting weights (state_dict)...")
state_dict = model.state_dict()

# 5. Save as a clean .pth file
torch.save(state_dict, "models/bert_clean.pth")
print("✅ Success! 'bert_clean.pth' saved. Use this one from now on!")
