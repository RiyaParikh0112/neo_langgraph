import os

# Project configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
REGION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

# Vertex AI settings
MODEL_NAME = "gemini-2.5-pro"
MODEL_PARAMS = {
    "temperature": 0.7,
    "max_output_tokens": 8192,
    "top_p": 0.95,
    "top_k": 40
}

# Storage settings
BUCKET_NAME = f"{PROJECT_ID}-blogger-assets"