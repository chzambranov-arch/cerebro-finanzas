
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

load_dotenv()

def test_vision_payload():
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-flash-latest')

    # Crear una imagen negra de 1x1 base64
    # Simplificado: Usar una cadena de bytes que parezca una imagen
    dummy_image = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    
    prompt = "Analiza esta boleta y dime qué ves. Responde en JSON asfixiable."
    
    content = [
        prompt,
        {'mime_type': 'image/png', 'data': dummy_image}
    ]
    
    print("Enviando petición de visión...")
    try:
        response = model.generate_content(content)
        print("Respuesta recibida!")
        print(response.text)
        return True
    except Exception as e:
        print(f"ERROR EN VISION: {e}")
        return False

if __name__ == "__main__":
    test_vision_payload()
