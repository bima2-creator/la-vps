"""Tests for KPI Teknisi + Teknisi master + Media perangkat-names endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # allow tests to run from backend/.env for CI
    BASE_URL = "http://localhost:8001"

API = f"{BASE_URL}/api"

TEK_INT = ["TEST_TEK_A", "TEST_TEK_B", "TEST_TEK_C", "TEST_TEK_D"]
TEK_MIT = ["TEST_TEK_MITRA_X"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _mk_wo(pelanggan, sa_id, tim, teknisi, status_field=None, status_val="",
           media_perangkat="TEST_DEVICE_A", jenis_order="PSB"):
    body = {
        "jenis_order": jenis_order,
        "pelanggan": pelanggan,
        "sa_id": sa_id,
        "tim_pelaksana": tim,
        "teknisi_pelaksana": teknisi,
        "media_perangkat": media_perangkat,
    }
    if status_field:
        body[status_field] = status_val
    return body


@pytest.fixture(scope="module")
def created_wos(headers):
    created = []
    # 4 internal WO: 2 OK, 1 BATAL, 1 empty
    scenarios = [
        ("TEST_KPI_P1", "TESTKPI0001", "INTERNAL", TEK_INT, "hasil_aktivasi_status", "OK", "TEST_DEVICE_A"),
        ("TEST_KPI_P2", "TESTKPI0002", "INTERNAL", TEK_INT, "hasil_instalasi_status", "OK", "TEST_DEVICE_A"),
        ("TEST_KPI_P3", "TESTKPI0003", "INTERNAL", TEK_INT, "hasil_survey_status", "BATAL", "TEST_DEVICE_B"),
        ("TEST_KPI_P4", "TESTKPI0004", "INTERNAL", TEK_INT, None, "", "TEST_DEVICE_B"),
        # 2 mitra: 1 OK, 1 BATAL
        ("TEST_KPI_M1", "TESTKPI1001", "MITRA", TEK_MIT, "hasil_aktivasi_status", "OK", "TEST_DEVICE_C"),
        ("TEST_KPI_M2", "TESTKPI1002", "MITRA", TEK_MIT, "hasil_aktivasi_status", "BATAL", "TEST_DEVICE_C"),
    ]
    for p, sa, tim, tek, sf, sv, mp in scenarios:
        body = _mk_wo(p, sa, tim, tek, sf, sv, media_perangkat=mp)
        r = requests.post(f"{API}/workorders", json=body, headers=headers)
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
        created.append(r.json()["id"])
    yield created
    # cleanup
    for wid in created:
        requests.delete(f"{API}/workorders/{wid}", headers=headers)


class TestKpiTeknisi:
    def test_kpi_all(self, headers, created_wos):
        r = requests.get(f"{API}/kpi/teknisi", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "technicians" in data and "summary" in data
        s = data["summary"]
        # Internal: 4 WO, ok=2, batal=1, selesai=3, pending=1
        # But summary aggregates ALL internal WOs in DB, not only ours.
        # Check our teknisi appear:
        techs = {(t["nama"], t["tim"]): t for t in data["technicians"]}
        for nm in TEK_INT:
            assert (nm, "INTERNAL") in techs, f"missing {nm}"
            row = techs[(nm, "INTERNAL")]
            assert row["total"] == 4
            assert row["ok"] == 2
            assert row["batal"] == 1
            assert row["selesai"] == 3
            assert row["pending"] == 1
            assert row["success_rate"] == 50.0  # 2/4*100
        # mitra
        assert (TEK_MIT[0], "MITRA") in techs
        m = techs[(TEK_MIT[0], "MITRA")]
        assert m["total"] == 2 and m["ok"] == 1 and m["batal"] == 1
        assert m["selesai"] == 2 and m["pending"] == 0
        assert m["success_rate"] == 50.0

    def test_kpi_filter_tim_internal(self, headers, created_wos):
        r = requests.get(f"{API}/kpi/teknisi", params={"tim": "INTERNAL"}, headers=headers)
        assert r.status_code == 200
        data = r.json()
        for t in data["technicians"]:
            assert t["tim"] == "INTERNAL"
        assert data["summary"]["mitra"]["total"] == 0

    def test_kpi_date_filter_future_empty(self, headers, created_wos):
        r = requests.get(f"{API}/kpi/teknisi",
                         params={"date_from": "2099-01-01", "date_to": "2099-12-31"},
                         headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["all"]["total"] == 0
        assert data["technicians"] == []


class TestTeknisiMaster:
    def test_master_internal_has_our_names(self, headers, created_wos):
        r = requests.get(f"{API}/teknisi/master", params={"tim": "INTERNAL"}, headers=headers)
        assert r.status_code == 200
        names = r.json()["names"]
        for nm in TEK_INT:
            assert nm in names

    def test_master_mitra_filter(self, headers, created_wos):
        r = requests.get(f"{API}/teknisi/master", params={"tim": "MITRA"}, headers=headers)
        assert r.status_code == 200
        names = r.json()["names"]
        assert TEK_MIT[0] in names
        # internal names should not appear
        for nm in TEK_INT:
            assert nm not in names

    def test_master_q_case_insensitive(self, headers, created_wos):
        r = requests.get(f"{API}/teknisi/master",
                         params={"tim": "INTERNAL", "q": "test_tek_a"}, headers=headers)
        assert r.status_code == 200
        names = r.json()["names"]
        assert "TEST_TEK_A" in names


class TestMediaPerangkatNames:
    def test_names_include_and_distinct(self, headers, created_wos):
        r = requests.get(f"{API}/media/perangkat-names", headers=headers)
        assert r.status_code == 200
        names = r.json()["names"]
        # our seeded values present
        for v in ("TEST_DEVICE_A", "TEST_DEVICE_B", "TEST_DEVICE_C"):
            assert v in names, f"missing {v}"
        # distinct
        assert len(names) == len(set(names))

    def test_names_q_filter(self, headers, created_wos):
        r = requests.get(f"{API}/media/perangkat-names",
                         params={"q": "test_device_b"}, headers=headers)
        assert r.status_code == 200
        names = r.json()["names"]
        assert names == ["TEST_DEVICE_B"] or "TEST_DEVICE_B" in names

    def test_self_clean_after_delete(self, headers):
        """Create a WO with a unique perangkat, then delete -> value disappears."""
        unique = "TEST_UNIQ_DEV_ZZZ9"
        body = _mk_wo("TEST_SELFCLEAN_P", "TESTSC0001", "INTERNAL", TEK_INT[:1],
                      media_perangkat=unique)
        r = requests.post(f"{API}/workorders", json=body, headers=headers)
        assert r.status_code in (200, 201)
        wid = r.json()["id"]
        r2 = requests.get(f"{API}/media/perangkat-names", params={"q": unique}, headers=headers)
        assert unique in r2.json()["names"]
        d = requests.delete(f"{API}/workorders/{wid}", headers=headers)
        assert d.status_code == 200
        r3 = requests.get(f"{API}/media/perangkat-names", params={"q": unique}, headers=headers)
        assert unique not in r3.json()["names"]


@pytest.fixture(scope="module", autouse=True)
def cleanup_teknisi_master():
    """After tests, purge TEST_ names from teknisi_master via mongo."""
    yield
    try:
        from pymongo import MongoClient
        murl = os.environ.get("MONGO_URL")
        dbname = os.environ.get("DB_NAME")
        if murl and dbname:
            c = MongoClient(murl)
            c[dbname].teknisi_master.delete_many({"nama": {"$regex": "^TEST_"}})
            c.close()
    except Exception as e:
        print("cleanup teknisi_master failed:", e)
