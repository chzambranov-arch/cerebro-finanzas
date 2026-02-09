
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: No GEMINI_API_KEY found in .env")
        return

    genai.configure(api_key=api_key)
    
    # Lista de modelos a probar
    models_to_try = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-1.0-pro',
        'models/gemini-1.5-flash',
        'models/gemini-1.5-flash-latest'
    ]
    
    print("Listing available models from API:")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name} ({m.display_name})")
    except Exception as e:
        print(f"Error listing models: {e}")

    print("\n--- Testing Content Generation ---")
    for model_name in models_to_try:
        print(f"\nTrying model: {model_name}...")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Hola, ¿quién eres?")
            print(f"SUCCESS with {model_name}!")
            print(f"Response: {response.text[:50]}...")
            return model_name # Retornamos el primero que funcione
        except Exception as e:
            print(f"FAILED {model_name}: {e}")
    
    return None

if __name__ == "__main__":
    working_model = test_models()
    if working_model:
        print(f"\nFINAL VERDICT: Use '{working_model}'")
    else:
        print("\nFINAL VERDICT: No model worked.")
