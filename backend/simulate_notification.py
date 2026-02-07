import requests
import json
import time

# Configuración
BASE_URL = "http://localhost:8002/api/v1"
TEST_ACCOUNT = "christian.zv@cerebro.com"

def simulate_gmail_notification():
    """
    Simula la llegada de un correo bancario enviando un POST al webhook.
    """
    url = f"{BASE_URL}/webhooks/gmail-push"
    
    payload = {
        "amount": 25990,
        "concept": "COMPRA FARMACIAS AHUMADA",
        "payment_method": "Tarjeta Crédito",
        "email_id": f"test_msg_{int(time.time())}",
        "user_email": TEST_ACCOUNT
    }
    
    print(f"--- Simulando notificación de Gmail para {TEST_ACCOUNT} ---")
    try:
        response = requests.post(url, json=payload)
        if response.ok:
            print("✅ Webhook recibido con éxito.")
            print("Response:", response.json())
            print("\nPróximos pasos:")
            print("1. Revisa tu navegador en http://localhost:8002")
            print("2. Deberías recibir una notificación Push (si diste permiso).")
            print("3. Al recargar o abrir el chat, Lúcio debería preguntarte por este gasto.")
        else:
            print(f"❌ Error en el webhook: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"⚠️ Error de conexión: {e}")

if __name__ == "__main__":
    simulate_gmail_notification()
