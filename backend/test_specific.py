
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

try:
    print("Testing models/gemini-exp-1206...")
    model = genai.GenerativeModel('models/gemini-exp-1206')
    res = model.generate_content("hi")
    print(f"SUCCESS: {res.text}")
except Exception as e:
    print(f"FAILED: {e}")
