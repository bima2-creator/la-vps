"""Field Engineer (role field_engineer) — FE user mgmt, WO assignment, field-data whitelist, activity clock."""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE = base_url.rstrip("/") + "/api"

CREDS = {
    "admin": ("admin", "admin123"),
    "operator": ("operator", "operator"),
    "guest": ("guest", "guest"),
    "fe": ("fe.budi", "budi123"),
}


def _login(username, password):
    r = requests.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("access_token")
    assert tok
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(*v) for k, v in CREDS.items()}


@pytest.fixture(scope="module")
def state():
    return {}


# ---------- FE user management ----------
class TestFEUsers:
    def test_list_fe_admin(self, tokens):
        r = requests.get(f"{BASE}/users/field-engineers", headers=_h(tokens["admin"]), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(u["username"] == "fe.budi" for u in data), data
        for u in data:
            assert "_id" not in u and "password_hash" not in u

    def test_list_fe_operator_allowed(self, tokens):
        r = requests.get(f"{BASE}/users/field-engineers", headers=_h(tokens["operator"]), timeout=30)
        assert r.status_code == 200

    def test_list_fe_guest_forbidden(self, tokens):
        r = requests.get(f"{BASE}/users/field-engineers", headers=_h(tokens["guest"]), timeout=30)
        assert r.status_code == 403

    def test_create_toggle_reset_delete(self, tokens, state):
        uname = f"fe.test{uuid.uuid4().hex[:4]}"
        r = requests.post(f"{BASE}/users/field-engineers", headers=_h(tokens["admin"]),
                          json={"username": uname, "name": "TEST_FE", "password": "test1234"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        fe = r.json()
        assert fe["username"] == uname and fe["active"] is True and fe["name"] == "TEST_FE"
        fid = fe["id"]

        # duplicate username -> 400
        dup = requests.post(f"{BASE}/users/field-engineers", headers=_h(tokens["admin"]),
                            json={"username": uname, "name": "X", "password": "test1234"}, timeout=30)
        assert dup.status_code == 400

        # operator cannot create
        opc = requests.post(f"{BASE}/users/field-engineers", headers=_h(tokens["operator"]),
                            json={"username": uname + "z", "name": "X", "password": "test1234"}, timeout=30)
        assert opc.status_code == 403

        # deactivate
        r = requests.patch(f"{BASE}/users/field-engineers/{fid}", headers=_h(tokens["admin"]),
                           json={"active": False}, timeout=30)
        assert r.status_code == 200 and r.json()["active"] is False
        # login blocked while inactive
        bad = requests.post(f"{BASE}/auth/login", json={"username": uname, "password": "test1234"}, timeout=30)
        assert bad.status_code in (401, 403), bad.status_code
        # reactivate + reset password
        r = requests.patch(f"{BASE}/users/field-engineers/{fid}", headers=_h(tokens["admin"]),
                           json={"active": True}, timeout=30)
        assert r.status_code == 200 and r.json()["active"] is True
        r = requests.patch(f"{BASE}/users/field-engineers/{fid}", headers=_h(tokens["admin"]),
                           json={"password": "newpass1"}, timeout=30)
        assert r.status_code == 200
        assert _login(uname, "newpass1")
        # short password rejected
        r = requests.patch(f"{BASE}/users/field-engineers/{fid}", headers=_h(tokens["admin"]),
                           json={"password": "ab"}, timeout=30)
        assert r.status_code == 400
        # empty payload rejected
        r = requests.patch(f"{BASE}/users/field-engineers/{fid}", headers=_h(tokens["admin"]),
                           json={}, timeout=30)
        assert r.status_code == 400
        # delete
        r = requests.delete(f"{BASE}/users/{fid}", headers=_h(tokens["admin"]), timeout=30)
        assert r.status_code in (200, 204), r.text[:200]
        lst = requests.get(f"{BASE}/users/field-engineers", headers=_h(tokens["admin"]), timeout=30).json()
        assert not any(u["username"] == uname for u in lst)

    def test_fe_not_in_main_users_list_role(self, tokens):
        r = requests.get(f"{BASE}/users", headers=_h(tokens["admin"]), timeout=30)
        assert r.status_code == 200
        roles = {u["username"]: u["role"] for u in r.json()}
        assert roles.get("fe.budi") == "field_engineer"
        for base_u in ("admin", "operator", "guest"):
            assert base_u in roles


# ---------- WO assignment + FE scoping ----------
class TestFEWorkorder:
    def test_create_wo_assigned_and_unassigned(self, tokens, state):
        payload = {"jenis_order": "PSB", "pelanggan": "TEST_FE_CUST", "si_id": f"TESTSI{uuid.uuid4().hex[:6]}",
                   "field_engineer": "fe.budi"}
        r = requests.post(f"{BASE}/workorders", headers=_h(tokens["admin"]), json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        wo = r.json()
        state["wo_id"] = wo["id"]
        assert wo["field_engineer"] == "fe.budi"

        other = {"jenis_order": "PSB", "pelanggan": "TEST_FE_OTHER", "si_id": f"TESTSI{uuid.uuid4().hex[:6]}"}
        r2 = requests.post(f"{BASE}/workorders", headers=_h(tokens["admin"]), json=other, timeout=30)
        assert r2.status_code in (200, 201), r2.text[:400]
        state["other_wo_id"] = r2.json()["id"]

    def test_fe_list_only_assigned(self, tokens, state):
        r = requests.get(f"{BASE}/workorders", headers=_h(tokens["fe"]), params={"page_size": 200}, timeout=30)
        assert r.status_code == 200
        items = r.json().get("items", r.json() if isinstance(r.json(), list) else [])
        ids = [w["id"] for w in items]
        assert state["wo_id"] in ids
        assert state["other_wo_id"] not in ids
        for w in items:
            assert w.get("field_engineer") == "fe.budi"

    def test_fe_get_other_wo_forbidden(self, tokens, state):
        r = requests.get(f"{BASE}/workorders/{state['other_wo_id']}", headers=_h(tokens["fe"]), timeout=30)
        assert r.status_code == 403, r.status_code

    def test_fe_field_data_other_wo_forbidden(self, tokens, state):
        r = requests.patch(f"{BASE}/workorders/{state['other_wo_id']}/field-data", headers=_h(tokens["fe"]),
                           json={"data": {"info_kondisi": "x"}}, timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"

    def test_fe_field_data_whitelist(self, tokens, state):
        r = requests.patch(f"{BASE}/workorders/{state['wo_id']}/field-data", headers=_h(tokens["fe"]),
                           json={"data": {"info_kondisi": "TEST_KONDISI", "pelanggan": "HACKED"}}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "pelanggan" in body["rejected_fields"]
        assert body["workorder"]["info_kondisi"] == "TEST_KONDISI"
        assert body["workorder"]["pelanggan"] == "TEST_FE_CUST"
        # persistence
        g = requests.get(f"{BASE}/workorders/{state['wo_id']}", headers=_h(tokens["admin"]), timeout=30).json()
        assert g["info_kondisi"] == "TEST_KONDISI"
        assert g["pelanggan"] == "TEST_FE_CUST"

    def test_fe_field_data_all_rejected(self, tokens, state):
        r = requests.patch(f"{BASE}/workorders/{state['wo_id']}/field-data", headers=_h(tokens["fe"]),
                           json={"data": {"pelanggan": "X"}}, timeout=30)
        assert r.status_code == 400

    def test_activity_clock_flow(self, tokens, state):
        wid = state["wo_id"]
        h = _h(tokens["fe"])
        # hold before start -> 400
        r = requests.post(f"{BASE}/workorders/{wid}/activity", headers=h,
                          json={"fase": "survey", "action": "hold", "reason": "x"}, timeout=30)
        assert r.status_code == 400
        r = requests.post(f"{BASE}/workorders/{wid}/activity", headers=h,
                          json={"fase": "survey", "action": "start"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["summary"]["status"] == "running"
        # double start -> 400
        assert requests.post(f"{BASE}/workorders/{wid}/activity", headers=h,
                             json={"fase": "survey", "action": "start"}, timeout=30).status_code == 400
        # hold without reason -> 400
        assert requests.post(f"{BASE}/workorders/{wid}/activity", headers=h,
                             json={"fase": "survey", "action": "hold"}, timeout=30).status_code == 400
        r = requests.post(f"{BASE}/workorders/{wid}/activity", headers=h,
                          json={"fase": "survey", "action": "hold", "reason": "TEST HOLD"}, timeout=30)
        assert r.status_code == 200 and r.json()["summary"]["status"] == "hold"
        r = requests.post(f"{BASE}/workorders/{wid}/activity", headers=h,
                          json={"fase": "survey", "action": "resume"}, timeout=30)
        assert r.status_code == 200 and r.json()["summary"]["status"] == "running"
        r = requests.post(f"{BASE}/workorders/{wid}/activity", headers=h,
                          json={"fase": "survey", "action": "stop"}, timeout=30)
        assert r.status_code == 200
        summ = r.json()["summary"]
        assert summ["status"] == "done"
        assert isinstance(summ["net_minutes"], (int, float))

        # verify persisted log + date sync
        doc = requests.get(f"{BASE}/workorders/{wid}", headers=_h(tokens["admin"]), timeout=30).json()
        log = doc.get("fe_activity_log") or []
        assert [e["action"] for e in log] == ["start", "hold", "resume", "stop"]
        assert any(e.get("reason") == "TEST HOLD" for e in log)
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        assert doc["activity_survey_start"] == today
        assert doc["activity_survey_end"] == today
        assert doc["stop_survey_start"] == today
        assert doc["stop_survey_end"] == today

    def test_activity_invalid_fase(self, tokens, state):
        r = requests.post(f"{BASE}/workorders/{state['wo_id']}/activity", headers=_h(tokens["fe"]),
                          json={"fase": "bogus", "action": "start"}, timeout=30)
        assert r.status_code == 422

    def test_activity_other_wo_forbidden(self, tokens, state):
        r = requests.post(f"{BASE}/workorders/{state['other_wo_id']}/activity", headers=_h(tokens["fe"]),
                          json={"fase": "survey", "action": "start"}, timeout=30)
        assert r.status_code == 403

    def test_fe_cannot_use_admin_endpoints(self, tokens):
        r = requests.get(f"{BASE}/users/field-engineers", headers=_h(tokens["fe"]), timeout=30)
        assert r.status_code == 403
        r = requests.get(f"{BASE}/users", headers=_h(tokens["fe"]), timeout=30)
        assert r.status_code == 403


@pytest.fixture(scope="module", autouse=True)
def cleanup(tokens, state):
    yield
    for key in ("wo_id", "other_wo_id"):
        wid = state.get(key)
        if wid:
            requests.delete(f"{BASE}/workorders/{wid}", headers=_h(tokens["admin"]), timeout=30)
