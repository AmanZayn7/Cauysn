import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).parent / ".env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY is missing from your .env file.")

with genai.Client(api_key=api_key) as client:
    response = client.interactions.create(
        model="gemini-3.8-flash",
        input="Reply with exactly: CAUSYN API connection successful",
    )
    print(response.output_text)