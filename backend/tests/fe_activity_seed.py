"""Helper: run FE activity clock (start/hold/resume/stop) on the UI-created TEST WO."""
import os
import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/") + "/api"


def login(u, p):
    r = requests.post(f"{BASE}/auth/login", json={"username": u, "password": p}, timeout=30)
    print("login", u, r.status_code)
    r.raise_for_status()
    return r.json()["access_token"]


def h(t):
    return {"Authorization": f"Bearer {t}"}


admin = login("admin", "admin123")
fe = login("fe.budi", "budi123")

r = requests.get(f"{BASE}/workorders", headers=h(admin), params={"q": "TEST_FE_UI_CUST", "page_size": 20}, timeout=30)
items = r.json().get("items", [])
wo = next((w for w in items if w.get("pelanggan") == "TEST_FE_UI_CUST"), None)
print("WO:", wo and (wo["id"], wo.get("field_engineer"), wo.get("jenis_pekerjaan")))
assert wo, "test WO not found"
wid = wo["id"]

for action, reason in [("start", ""), ("hold", "TEST HOLD"), ("resume", ""), ("stop", "")]:
    rr = requests.post(f"{BASE}/workorders/{wid}/activity", headers=h(fe),
                       json={"fase": "survey", "action": action, "reason": reason}, timeout=30)
    print(action, rr.status_code, rr.json().get("summary") if rr.status_code == 200 else rr.text[:200])

doc = requests.get(f"{BASE}/workorders/{wid}", headers=h(admin), timeout=30).json()
print("log:", [(e["action"], e.get("reason")) for e in doc.get("fe_activity_log", [])])
print("dates:", doc.get("activity_survey_start"), doc.get("activity_survey_end"),
      doc.get("stop_survey_start"), doc.get("stop_survey_end"))
print("WO_ID=", wid)
