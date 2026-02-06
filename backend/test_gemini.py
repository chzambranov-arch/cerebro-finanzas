
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print(f"Testing key: {api_key[:8]}...")
genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Hola, di 'test' si funcionas.")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"FAIL: {e}")
