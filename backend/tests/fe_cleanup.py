"""Cleanup: remove UI-created TEST work orders and the fe.test account (keeps fe.budi)."""
import os
import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/") + "/api"
tok = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

for q in ("TEST_FE_UI_CUST", "TEST_OPER_CHECK", "TEST_FE_CUST", "TEST_FE_OTHER"):
    items = requests.get(f"{BASE}/workorders", headers=H, params={"q": q, "page_size": 50}, timeout=30).json().get("items", [])
    for w in items:
        if str(w.get("pelanggan", "")).startswith("TEST_"):
            r = requests.delete(f"{BASE}/workorders/{w['id']}", headers=H, timeout=30)
            print("deleted WO", w["pelanggan"], w["id"], r.status_code)

fes = requests.get(f"{BASE}/users/field-engineers", headers=H, timeout=30).json()
for fe in fes:
    if fe["username"].startswith("fe.test"):
        r = requests.delete(f"{BASE}/users/{fe['id']}", headers=H, timeout=30)
        print("deleted FE", fe["username"], r.status_code)
print("remaining FE:", [f["username"] for f in requests.get(f"{BASE}/users/field-engineers", headers=H, timeout=30).json()])
