"""
Test directo de conexión a Google Sheets usando las credenciales configuradas
"""
import os
import json
import base64

# Simular el entorno de Cloud Run
credentials_b64 = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "eyJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsICJwcm9qZWN0X2lkIjogImFjdGl2aWRhZGVzLWRpYXJpYXMtNDgyMjIxIiwgInByaXZhdGVfa2V5X2lkIjogIjhjNTc4MjMyYmY3ZDQ0OGU5MThiNzRlNDMxZjU4YjRkNjVhMGI4ZmMiLCAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tXG5NSUlFdmdJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLZ3dnZ1NrQWdFQUFvSUJBUUNxUmQrUm5IYnlIeHVwXG54OS9DZEhCMjJxUExNSkpWZ0N1UjBwU3ovWmVKV3FHNkRDZ1IrSHpLQXdwRzE0RnF6c1JuS1VldVBDK1E1Szl6XG5CM1g1RVRlVzhiYkdrK1pjN0ZVcWRmWnNCUWxJYU5PL3N2dEd0VVc5NE0vczZuQnpBcDVvR2d2OW8xSzdTZ2dLXG42S2ZaZUVHNThtMHNvVHNYeHF5V29NeDl0YXhkNHJzUWtGNUZCejVuTWlxM2dlaENNMXV3WDVselZHcXNxY0xFXG56UGExSDNkZ05CeVdjZDk4YmtRM3g5T2d2N0l0YjRUMDdNTnBnRXJDdjhNSHBac2hjY0ZWcWFiWWtweUFPQ0dRXG4yV2hqV1RneTVNYXVJZGJqUWtpQVNHaDd2RWw5aU96OWlHVk9wNmtXNURmaDhsanVlUFI3a0FyVEUvSittWnJEXG5aRkVPYWxtWEFnTUJBQUVDZ2dFQUFWZ1dobCs3SmZqT09jT0tKZmw2cWNyYXRYcVNBbnJGM1VZbThRVEtIWERKXG50Z2p0TXJjZUdtVEx2L2krTWg3NlkwREFLc1ZFTURDZDhlL1h6bytFTzN6TStlUlEvVFYxdHFWdEVlS05vRFN6XG5vZC9DZkFjU1N6TEFjVzVTLzVWckNySC9SanZ6MEpGVkNaWlhQTnJtS2V4RlVGbzFkOS9wbk53ZGE4dElxN1VMXG5KZ0JlQ09zazRhUHdaOEVRVExXOEVxNWQxeEppeTBMRFZ5SWI3MzJrNmd2ZDJ1VERxV2V5Um1FVnlHUm5OZXJiXG5lcUl1ODRkR0JSc3JyK3hLQjJRYURiQnVYcXpxamozU1BybDlhYXlTMmV3dGFkTWdqWmh5anBPL1o4YnpQbHU3XG51aUo4ODFDL0pVTnFsbUVyOW9kdGZUdDRJRDhDS09yS3ZsWkExWjRrQVFLQmdRRHdrZC96enp2T3VXYzVPT3Z1XG5vejZmTm15cFYrY0s1RStYcmFzMTFCVjQvZzdpREUvMUIrcjVjbTl1V0xWRmQrSjlFOXZUdnpYNWJqNEp3QWczXG4xWlQ4UnZlWEZIVXRwOUR4VTBBTTRRcmRMcFk2V1NmVmRYWHZ0N3R4VkdEa2RwL244THlVcnloT1JHNG9UN2lWXG5zVk1mSERLbUZtZko4RC9MalFNT1pGMFd0d0tCZ1FDMU1idWRTYW8zTlUzanltVWZxODRVcnRoSnlZQStvMHNHXG5oZXR6alIrUkFyK3JVV25qY1lnUnFVcDF0SHdiRU9ZU1c1LzhySDBEOGtTaFVOMFU4R3FTQnQ0OUV2dlZoN2pEXG5Hc0xiUTAxdmpnWk1xU21uVnQ2KzM5S1ZGR0IvYmxnbkdEeHV2YXNBd1Z1K01Ba1pLUDdsaW0vYSt4OFhjREJwXG5DNmp0blZ6MElRS0JnUUN4NmZCS2k3U2JpaHFCQTB2WlRQbC9IZXoyd0grcVduZFNvYW5CUVh3djR4UjJzTXhoXG5WdDI4WlpscmJrZUJmTXdQM0tQeTBiTEZLWGJRRnlqOHdnUlJIdHIwN0xoTWI1UGpKY0owdytvWThkOUFmN2NwXG44cGlxRktPWGlPT3ZrdHRuMlc1ZU43d0RSakNCdDVPM2dWRUw3UHE0UWxHMzB1b2JTOG82MXBiUnVRS0JnUUNBXG5LZEZmREFBT1ZQSG5NZjRkVE5UVDVHaXdxSXJCdzVjSjRpZ003OEZvUE4xK1BIUDlvUXh5RWFETmFRQnYxS0FvXG5WQTd5RnIvR3p0S2ttQ0lJOFpVdi9ST3RkNFFTSVpJYXp3OE5NS25SUWxCS1lVMUpSRFVDSmljNXM5UWR6dHNqXG5yQXp5OTgzQkZ3UGhudkNRajJMYzBmTVVuWlA4YkNxUjR1RjJVVnl5Z1FLQmdISEZOUU9QT0F1TzJQVi9BRzdCXG51cTd0TGF3c2pWZE5ya1EwZ1AwQTVsaE9RTlVhOWxVWWxGMXZkSHh3Ukljc1Y4YnJqT29yelNkYjZ4R0dKSDJwXG4yai9qYm1QWWI3SVpzNlkwRTRVTFA2TXEwbGtxdDZBRVcxcEVWQ0d3Q2J3dEdhSW0wMVJvMjhwL0t3Vy9jMnRIXG4wLzdXcnpPdDJ6QWZaYVE3eGhFVkV6dXpcbi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS1cbiIsICJjbGllbnRfZW1haWwiOiAiY2VyZWJyby1wYXRpb0BhY3RpdmlkYWRlcy1kaWFyaWFzLTQ4MjIyMS5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsICJjbGllbnRfaWQiOiAiMTE3NzQ4NzMwNzY2MDUxNTYzMjQ1IiwgImF1dGhfdXJpIjogImh0dHBzOi8vYWNjb3VudHMuZ29vZ2xlLmNvbS9vL29hdXRoMi9hdXRoIiwgInRva2VuX3VyaSI6ICJodHRwczovL29hdXRoMi5nb29nbGVhcGlzLmNvbS90b2tlbiIsICJhdXRoX3Byb3ZpZGVyX3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vb2F1dGgyL3YxL2NlcnRzIiwgImNsaWVudF94NTA5X2NlcnRfdXJsIjogImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL3JvYm90L3YxL21ldGFkYXRhL3g1MDkvY2VyZWJyby1wYXRpbyU0MGFjdGl2aWRhZGVzLWRpYXJpYXMtNDgyMjIx

LmlhbS5nc2VydmljZWFjY291bnQuY29tIiwgInVuaXZlcnNlX2RvbWFpbiI6ICJnb29nbGVhcGlzLmNvbSJ9")
sheet_id = os.getenv("GOOGLE_SHEET_ID", "19eXI3AV-S5uzXfwxC9HoGa6FExZ4ZlvmCvK79fbwMts")

print(f"Sheet ID: {sheet_id}")
print(f"Credentials (primeros 50 chars): {credentials_b64[:50]}...")

# Probar decode
try:
    # Check si es base64
    if not credentials_b64.strip().startswith('{'):
        decoded = base64.b64decode(credentials_b64).decode('utf-8')
        creds_dict = json.loads(decoded)
    else:
        creds_dict = json.loads(credentials_b64)
        
    print(f"\n✅ Credentials JSON parseado correctamente")
    print(f"Project ID: {creds_dict.get('project_id')}")
    print(f"Client Email: {creds_dict.get('client_email')}")
    
    # Probar conexión a sheets
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    print(f"\n✅ Autenticación exitosa con Google")
    
    # Intentar abrir el sheet
    sheet = client.open_by_key(sheet_id)
    print(f"\n✅ Sheet abierto: {sheet.title}")
    print(f"Hojas disponibles:")
    for ws in sheet.worksheets():
        print(f"  - {ws.title}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
