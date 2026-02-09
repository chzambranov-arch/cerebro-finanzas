
import os
import google.generativeai as genai
from dotenv import load_dotenv
import time

load_dotenv()

def test_specific_model(model_name):
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    print(f"Testing model: {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hola Lúcio, responde 'OK' si me escuchas.")
        print(f"SUCCESS! Response: {response.text}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

if __name__ == "__main__":
    # Esperamos un poco para resetear cuota por si acaso
    time.sleep(5)
    test_specific_model('gemini-flash-latest')
