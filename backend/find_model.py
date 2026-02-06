
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models = genai.list_models()
print(f"Found {len(list(models))} total models. Testing candidates...")

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        try:
            name = m.name
            print(f"Testing {name}...", end=" ")
            model = genai.GenerativeModel(name)
            res = model.generate_content("hi")
            print("SUCCESS!!")
            with open("found_model.txt", "w") as f:
                f.write(name)
            exit(0)
        except Exception as e:
            print(f"FAILED: {str(e)[:100]}...")
