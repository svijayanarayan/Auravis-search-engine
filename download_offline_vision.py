"""One-time AURAVIS Offline Vision setup. Run this once while connected to internet."""
import os
from transformers import pipeline
model = os.getenv("AURAVIS_OFFLINE_VISION_MODEL", "Salesforce/blip-image-captioning-base")
print("Downloading/caching AURAVIS Offline Vision model:", model)
print("This can take several minutes the first time. Keep internet connected.")
pipe = pipeline("image-to-text", model=model)
print("OFFLINE VISION READY")
print("The model is now cached. AURAVIS image search can use it without OpenAI credits or internet.")
