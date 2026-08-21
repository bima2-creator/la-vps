"""Seed / cleanup helper for iteration 8 frontend invoice tests.

Usage:  python fe_invoice_seed.py seed | clean | legacy
"""
import os
import sys

import requests
from dotenv import dotenv_values

BASE_URL = (dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "").rstrip("/")
PELANGGAN = "PT GABUNG TEST"
PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

s = requests.Session()
r = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
r.raise_for_status()
s.headers.update({"Authorization": f"Bearer {r.json().get('access_token') or r.json()['token']}"})

mode = sys.argv[1] if len(sys.argv) > 1 else "seed"

if mode == "seed":
    specs = [
        {"si_id": "SI-GAB-01", "jenis_order": "PSB", "hasil_instalasi_status": "OK",
         "boq_jasa": 1000000, "boq_jumlah": 1000000},
        {"si_id": "SI-GAB-02", "jenis_order": "DISMANTLE", "hasil_survey_status": "OK",
         "boq_jasa": 500000, "boq_jumlah": 500000},
        {"si_id": "SI-GAB-03", "jenis_order": "MAINTENANCE", "hasil_survey_status": "OK",
         "boq_jasa": 300000, "boq_jumlah": 300000},
    ]
    for sp in specs:
        wo = s.post(f"{BASE_URL}/api/workorders", json={"pelanggan": PELANGGAN, **sp}).json()
        s.post(f"{BASE_URL}/api/workorders/{wo['id']}/attachments",
               files={"file": ("TEST.pdf", PDF, "application/pdf")}, data={"kind": "general"})
        print("seeded", wo["id"], sp["si_id"])
elif mode == "legacy":
    invs = s.get(f"{BASE_URL}/api/invoices", params={"limit": 500}).json()
    items = invs if isinstance(invs, list) else invs.get("items", [])
    for i in items:
        if (i.get("jenis_pekerjaan") or "") in ("SURVEY", "INSTALASI", "AKTIVASI", "DISMANTLE"):
            print("LEGACY", i["id"], i.get("invoice_no"), i.get("jenis_pekerjaan"))
elif mode == "clean":
    invs = s.get(f"{BASE_URL}/api/invoices", params={"limit": 500}).json()
    items = invs if isinstance(invs, list) else invs.get("items", [])
    for i in items:
        if PELANGGAN in str(i.get("pelanggans") or "") or "GAB-UI" in str(i.get("invoice_no") or ""):
            print("del inv", i.get("invoice_no"), s.delete(f"{BASE_URL}/api/invoices/{i['id']}").status_code)
    wos = s.get(f"{BASE_URL}/api/workorders", params={"q": PELANGGAN, "limit": 200}).json()
    witems = wos if isinstance(wos, list) else wos.get("items", [])
    for w in witems:
        if w.get("pelanggan") == PELANGGAN:
            print("del wo", w.get("si_id"), s.delete(f"{BASE_URL}/api/workorders/{w['id']}").status_code)
