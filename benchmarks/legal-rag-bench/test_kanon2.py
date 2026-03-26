"""Test script for Isaacus Kanon 2 Embedder API.

Model: kanon-2-embedder
Endpoint: https://api.isaacus.com/v1
Pricing: $0.35 per million tokens (pay-as-you-go, no free tier)
Dimensions: 1792 (default), 1024, 768, 512, 256
Max input: 16,384 tokens
SDK: pip install isaacus

To get an API key:
  1. Sign up at https://platform.isaacus.com
  2. Verify your account and subscribe to the usage-based API plan
  3. Generate an API key from the platform dashboard
  4. Set ISAACUS_API_KEY in your environment (or .env file)
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

ISAACUS_API_KEY = os.environ.get("ISAACUS_API_KEY")

if not ISAACUS_API_KEY:
    print("ISAACUS_API_KEY is not set.")
    print()
    print("To get an API key:")
    print("  1. Go to https://platform.isaacus.com and create an account")
    print("  2. Verify your account and subscribe to the usage-based API plan")
    print("  3. Generate an API key from the dashboard")
    print("  4. Add ISAACUS_API_KEY=<your-key> to your .env file")
    print()
    print("Pricing: $0.35 per million tokens (no free tier; contact sales for volume discounts)")
    print("Docs: https://docs.isaacus.com/api-reference/making-requests")
    sys.exit(0)

print(f"ISAACUS_API_KEY found (starts with: {ISAACUS_API_KEY[:8]}...)")
print("Testing Kanon 2 embedder...")

try:
    from isaacus import Isaacus
except ImportError:
    print("isaacus SDK not installed. Run: pip install isaacus")
    sys.exit(1)

client = Isaacus(api_key=ISAACUS_API_KEY)

test_text = "The court held that the defendant breached the duty of care owed to the claimant."

response = client.embeddings.create(
    model="kanon-2-embedder",
    texts=[test_text],
    task="retrieval/query",
)

embedding = response.embeddings[0]
print(f"Embedding dimensions: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")
print(f"Model used: kanon-2-embedder")
print("Kanon 2 embedder: OK")
