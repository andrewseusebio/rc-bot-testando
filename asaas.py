import requests
import os

ASAAS_URL = "https://api.asaas.com/v3"
API_KEY = os.getenv("$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjQ1ZTU2NDljLTliN2EtNDM2NS1hOTQwLWE1MjY1YmExZjgzYzo6JGFhY2hfYTVhNGJmNjItNjIzYy00ZWUyLTk1Y2YtODdiODA0OTFmMDg3")

def criar_pix(user_id, valor):
    payload = {
        "customer": "cus_000000000000",
        "billingType": "PIX",
        "value": valor,
        "description": f"Telegram {user_id}"
    }

    headers = {
        "access_token": API_KEY
    }

    r = requests.post(f"{ASAAS_URL}/payments", json=payload, headers=headers)
    data = r.json()

    return data["pixTransaction"]["qrCodeImage"], data["pixTransaction"]["payload"]
