from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import io
import os
import json
import uuid
import csv
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import bcrypt
import jwt
import pandas as pd
from bson import ObjectId
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Query, Header, Form
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image as RLImage
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# For merging faktur pajak PDF into the invoice output
try:
    from pypdf import PdfReader, PdfWriter
    _HAS_PYPDF = True
except Exception:
    _HAS_PYPDF = False

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Object storage
# STORAGE_MODE=local -> save files on disk under LOCAL_STORAGE_DIR (for local Docker/offline install)
# STORAGE_MODE=cloud (default) -> Emergent object storage
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_MODE = os.environ.get("STORAGE_MODE", "cloud").lower()
LOCAL_STORAGE_DIR = os.environ.get("LOCAL_STORAGE_DIR", "/data/attachments")
APP_NAME = "la-tracker"
_storage_key: Optional[str] = None

import mimetypes
from pathlib import Path as _Path


def init_storage() -> Optional[str]:
    global _storage_key
    if STORAGE_MODE == "local":
        _Path(LOCAL_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
        return "local"
    if _storage_key:
        return _storage_key
    if not EMERGENT_KEY:
        return None
    try:
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        return _storage_key
    except Exception as e:
        logging.getLogger("la-tracker").error("storage init failed: %s", e)
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(500, "Object storage not initialized")
    if STORAGE_MODE == "local":
        target = _Path(LOCAL_STORAGE_DIR) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"path": path, "size": len(data), "content_type": content_type}
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    if not key:
        raise HTTPException(500, "Object storage not initialized")
    if STORAGE_MODE == "local":
        target = _Path(LOCAL_STORAGE_DIR) / path
        if not target.exists():
            raise HTTPException(404, "Attachment not found on disk")
        ctype, _ = mimetypes.guess_type(str(target))
        return target.read_bytes(), (ctype or "application/octet-stream")
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="LA Tracker API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("la-tracker")


# ------------------------------------------------------------------
# Password / JWT helpers
# ------------------------------------------------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=28800, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


async def _resolve_user_from_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(401, "User not found")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        user.setdefault("username", user.get("email", ""))
        user.setdefault("email", "")
        # `actor` is the stable identity string used for created_by / audit trails
        user["actor"] = user.get("username") or user.get("email") or "system"
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    return await _resolve_user_from_token(token)


def require_roles(*roles: str):
    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(403, "Forbidden: insufficient role")
        return user
    return _dep


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------
class RegisterIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=4)
    name: str = Field(min_length=1)
    role: str = Field(default="operator", pattern="^(admin|operator|viewer)$")
    email: Optional[str] = ""


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    name: str
    role: str
    email: Optional[str] = ""


# ---- Work Order sub-schemas ----
class PhaseTriple(BaseModel):
    survey: Optional[Any] = None
    instalasi: Optional[Any] = None
    aktivasi: Optional[Any] = None


class WorkOrderBase(BaseModel):
    # Top-level identifiers
    pelanggan: Optional[str] = ""
    alamat: Optional[str] = ""
    jenis_order: Optional[str] = ""
    wo_jenis_pekerjaan: Optional[str] = ""  # SURVEY | INSTALASI | AKTIVASI (only for PSB/MUTASI/MIGRASI)
    maintenance_type: Optional[str] = ""    # CM | PM (only for MAINTENANCE)
    case_no: Optional[str] = ""             # only for MAINTENANCE
    task_no: Optional[str] = ""             # only for MAINTENANCE
    sa_id: Optional[str] = ""
    si_id: Optional[str] = ""
    lat: Optional[str] = ""
    lng: Optional[str] = ""
    bw: Optional[str] = ""

    # RFS
    rfs_la: Optional[str] = ""
    rfs_pelanggan: Optional[str] = ""

    # SPK Survey / Instalasi / Aktivasi
    spk_survey_nomor: Optional[str] = ""
    spk_survey_tgl_doc: Optional[str] = ""
    spk_survey_tgl_terima: Optional[str] = ""
    spk_instalasi_nomor: Optional[str] = ""
    spk_instalasi_tgl_doc: Optional[str] = ""
    spk_instalasi_tgl_terima: Optional[str] = ""
    spk_aktivasi_nomor: Optional[str] = ""
    spk_aktivasi_tgl_doc: Optional[str] = ""
    spk_aktivasi_tgl_terima: Optional[str] = ""

    # Activity
    activity_survey_start: Optional[str] = ""
    activity_survey_end: Optional[str] = ""
    activity_instalasi_start: Optional[str] = ""
    activity_instalasi_end: Optional[str] = ""
    activity_aktivasi_start: Optional[str] = ""
    activity_aktivasi_end: Optional[str] = ""

    # Stop Clock
    stop_survey_start: Optional[str] = ""
    stop_survey_end: Optional[str] = ""
    stop_instalasi_start: Optional[str] = ""
    stop_instalasi_end: Optional[str] = ""
    stop_aktivasi_start: Optional[str] = ""
    stop_aktivasi_end: Optional[str] = ""

    # SDT (durasi & target)
    sdt_survey_durasi: Optional[str] = ""
    sdt_survey_target: Optional[str] = ""
    sdt_instalasi_durasi: Optional[str] = ""
    sdt_instalasi_target: Optional[str] = ""
    sdt_aktivasi_durasi: Optional[str] = ""
    sdt_aktivasi_target: Optional[str] = ""

    # Media Akses
    media_jenis: Optional[str] = ""
    media_perangkat: Optional[str] = ""

    # Contact Persons
    cp_la: Optional[str] = ""
    cp_mitra: Optional[str] = ""  # label diubah jadi "CP Pelaksana" di UI
    cp_pelanggan: Optional[str] = ""

    # Tim Pelaksana (dasar penilaian KPI & target)
    tim_pelaksana: Optional[str] = ""            # "INTERNAL" | "MITRA"
    teknisi_pelaksana: Optional[List[Any]] = []  # daftar nama teknisi (4 utk INTERNAL, 1 utk MITRA)

    # Hasil Pekerjaan
    hasil_survey_status: Optional[str] = ""
    hasil_survey_datek: Optional[str] = ""
    hasil_survey_npae: Optional[str] = ""
    hasil_instalasi_status: Optional[str] = ""
    hasil_instalasi_datek: Optional[str] = ""
    hasil_instalasi_npae: Optional[str] = ""
    hasil_aktivasi_status: Optional[str] = ""
    hasil_aktivasi_datek: Optional[str] = ""
    hasil_aktivasi_npae: Optional[str] = ""

    # Info Pelanggan
    info_kondisi: Optional[str] = ""
    info_perizinan: Optional[str] = ""
    info_biaya: Optional[str] = ""
    info_masalah: Optional[str] = ""
    info_tindak_lanjut: Optional[str] = ""

    # Perangkat & BoQ
    perangkat_terpasang: Optional[str] = ""  # legacy free-text; use perangkat_items going forward
    perangkat_items: Optional[List[Any]] = []  # [{nama, nomor_registrasi}]
    boq_items: Optional[List[Any]] = []  # multi-paket rows; see /frontend/BoqItemsEditor
    boq_paket: Optional[str] = ""
    boq_paket_code: Optional[str] = ""  # e.g. "P003" (dari master paket)
    boq_mode: Optional[str] = "both"    # "jasa" | "material" | "both"
    boq_jasa: Optional[float] = 0
    boq_material: Optional[float] = 0
    boq_jumlah: Optional[float] = 0

    # Invoice
    inv_no: Optional[str] = ""
    inv_jenis_pekerjaan: Optional[str] = ""  # SURVEY | INSTALASI | AKTIVASI | DISMANTLE | MAINTENANCE
    inv_tgl: Optional[str] = ""
    inv_tgl_kirim: Optional[str] = ""
    inv_tgl_bayar: Optional[str] = ""
    inv_status: Optional[str] = ""

    keterangan: Optional[str] = ""


class WorkOrderIn(WorkOrderBase):
    pass


class WorkOrderOut(WorkOrderBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None


def workorder_to_out(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def audit(action: str, user: dict, workorder_id: Optional[str] = None, target: Optional[str] = None, meta: Optional[dict] = None) -> None:
    try:
        await db.audit_logs.insert_one({
            "action": action,
            "user_id": user.get("id"),
            "user_email": user.get("actor") or user.get("email"),
            "user_role": user.get("role"),
            "workorder_id": workorder_id,
            "target": target,
            "meta": meta or {},
            "created_at": now_iso(),
        })
    except Exception as e:
        log.warning("audit failed: %s", e)


# ------------------------------------------------------------------
# Startup
# ------------------------------------------------------------------
@app.on_event("startup")
async def on_startup() -> None:
    await seed_fixed_users()
    await db.workorders.create_index("pelanggan")
    await db.workorders.create_index("sa_id")
    await db.workorders.create_index("inv_status")
    await db.workorders.create_index("media_jenis")
    try:
        await db.workorders.create_index("perangkat_items.nomor_registrasi", sparse=True)
    except Exception:
        pass
    await db.audit_logs.create_index([("created_at", -1)])
    await db.audit_logs.create_index("workorder_id")
    await db.attachments.create_index("workorder_id")
    await db.invoices.create_index([("created_at", -1)])
    await db.invoices.create_index("pelanggan")
    await db.invoices.create_index("invoice_no", unique=True, sparse=True)

    try:
        await db.perangkat_bank.create_index([("prefix", 1), ("plen", 1)])
    except Exception:
        pass
    try:
        await db.teknisi_master.create_index([("nama", 1), ("tim", 1)], unique=True)
    except Exception:
        pass
    await _seed_perangkat_bank()

    # Initialize object storage (non-blocking on failure)
    if init_storage():
        log.info("Object storage initialized")


# The application supports exactly three fixed login accounts.
# Passwords are read from env when provided, otherwise fall back to the defaults.
FIXED_USERS = [
    {
        "username": "admin",
        "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
        "name": "Administrator",
        "role": "admin",
        # Admin notification/alert address (SLA, Invoice, dll.)
        "email": os.environ.get("ADMIN_EMAIL", "support@almar.co.id"),
    },
    {
        "username": "operator",
        "password": os.environ.get("OPERATOR_PASSWORD", "operator"),
        "name": "Operator",
        "role": "operator",
        "email": "",
    },
    {
        "username": "guest",
        "password": os.environ.get("GUEST_PASSWORD", "guest"),
        "name": "Guest",
        "role": "viewer",
        "email": "",
    },
]


async def seed_fixed_users() -> None:
    """Ensure exactly the three fixed accounts exist (admin/operator/guest).
    Idempotent: creates missing accounts, keeps passwords/roles in sync, and
    removes any other accounts so only these three can log in."""
    usernames = [u["username"] for u in FIXED_USERS]

    # Clean up the legacy unique index on `email` (operator/guest have no email).
    try:
        await db.users.drop_index("email_1")
    except Exception:
        pass

    # Remove any accounts that are not part of the fixed set.
    try:
        await db.users.delete_many({"username": {"$nin": usernames}})
    except Exception:
        pass

    for u in FIXED_USERS:
        doc_set = {
            "username": u["username"],
            "name": u["name"],
            "role": u["role"],
            "email": u.get("email", ""),
        }
        existing = await db.users.find_one({"username": u["username"]})
        if existing is None:
            await db.users.insert_one({
                **doc_set,
                "password_hash": hash_password(u["password"]),
                "created_at": now_iso(),
            })
            log.info("Seeded user: %s (%s)", u["username"], u["role"])
        else:
            update = {"$set": doc_set}
            # Keep password in sync with the configured value.
            if not verify_password(u["password"], existing.get("password_hash", "")):
                update["$set"]["password_hash"] = hash_password(u["password"])
            await db.users.update_one({"_id": existing["_id"]}, update)

    # Unique index on username (safe now that data is clean).
    try:
        await db.users.create_index("username", unique=True)
    except Exception as e:
        log.warning("Could not create username index: %s", e)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    client.close()


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------
@api.get("/")
async def health_root():
    return {"status": "ok", "app": APP_NAME}


# ------------------------------------------------------------------
# Auth routes
# ------------------------------------------------------------------
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    username = payload.username.strip().lower()
    existing = await db.users.find_one({"username": username})
    if existing:
        raise HTTPException(400, "Username already registered")
    doc = {
        "username": username,
        "email": (payload.email or "").strip().lower(),
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "role": payload.role,
        "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    access = create_access_token(uid, username, payload.role)
    refresh = create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return {"id": uid, "username": username, "email": doc["email"], "name": payload.name, "role": payload.role, "token": access}


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    username = payload.username.strip().lower()
    user = await db.users.find_one({"username": username})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    uid = str(user["_id"])
    access = create_access_token(uid, username, user["role"])
    refresh = create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return {"id": uid, "username": username, "email": user.get("email", ""), "name": user["name"], "role": user["role"], "token": access}


@api.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Missing refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token")
        uid = payload["sub"]
        user = await db.users.find_one({"_id": ObjectId(uid)})
        if not user:
            raise HTTPException(401, "User not found")
        access = create_access_token(uid, user.get("username", ""), user["role"])
        response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=28800, path="/")
        return {"token": access}
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid refresh token")


# ------------------------------------------------------------------
# Users management (admin only)
# ------------------------------------------------------------------
@api.get("/users")
async def list_users(user: dict = Depends(require_roles("admin"))):
    users = await db.users.find({}, {"password_hash": 0}).to_list(500)
    return [{"id": str(u["_id"]), "username": u.get("username", ""), "email": u.get("email", ""),
             "name": u["name"], "role": u["role"], "created_at": u.get("created_at")} for u in users]


@api.post("/users")
async def create_user(payload: RegisterIn, user: dict = Depends(require_roles("admin"))):
    username = payload.username.strip().lower()
    if await db.users.find_one({"username": username}):
        raise HTTPException(400, "Username already exists")
    doc = {
        "username": username,
        "email": (payload.email or "").strip().lower(),
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "role": payload.role,
        "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    return {"id": str(res.inserted_id), "username": username, "email": doc["email"], "name": payload.name, "role": payload.role}


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_roles("admin"))):
    if user_id == user["id"]:
        raise HTTPException(400, "Cannot delete yourself")
    res = await db.users.delete_one({"_id": ObjectId(user_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "User not found")
    return {"ok": True}


# ------------------------------------------------------------------
# Work Order CRUD
# ------------------------------------------------------------------
@api.get("/workorders")
async def list_workorders(
    q: Optional[str] = None,
    inv_status: Optional[str] = None,
    media_jenis: Optional[str] = None,
    media_perangkat: Optional[str] = None,
    jenis_order: Optional[str] = None,
    jenis_pekerjaan: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if q:
        query["$or"] = [
            {"pelanggan": {"$regex": q, "$options": "i"}},
            {"alamat": {"$regex": q, "$options": "i"}},
            {"sa_id": {"$regex": q, "$options": "i"}},
            {"si_id": {"$regex": q, "$options": "i"}},
            {"spk_survey_nomor": {"$regex": q, "$options": "i"}},
            {"spk_instalasi_nomor": {"$regex": q, "$options": "i"}},
            {"spk_aktivasi_nomor": {"$regex": q, "$options": "i"}},
            {"inv_no": {"$regex": q, "$options": "i"}},
        ]
    if inv_status:
        query["inv_status"] = inv_status
    if media_jenis:
        query["media_jenis"] = media_jenis
    if media_perangkat:
        query["media_perangkat"] = media_perangkat
    if jenis_order:
        query["jenis_order"] = jenis_order

    # Derived "jenis pekerjaan" filter — different meanings per value:
    #   SURVEY/INSTALASI/AKTIVASI → matches wo_jenis_pekerjaan (only PSB/MUTASI/MIGRASI carry this)
    #   DISMANTLE                 → matches jenis_order = DISMANTLE
    #   MAINTENANCE               → matches jenis_order = MAINTENANCE
    #   CM / PM                   → matches maintenance_type (implicitly MAINTENANCE)
    if jenis_pekerjaan:
        jp = jenis_pekerjaan.strip().upper()
        if jp in ("SURVEY", "INSTALASI", "AKTIVASI"):
            query["wo_jenis_pekerjaan"] = jp
        elif jp == "DISMANTLE":
            query["jenis_order"] = "DISMANTLE"
        elif jp == "MAINTENANCE":
            query["jenis_order"] = "MAINTENANCE"
        elif jp in ("CM", "PM"):
            query["jenis_order"] = "MAINTENANCE"
            query["maintenance_type"] = jp

    # Derived status filter (mirrors _wo_status logic used by dashboard/reports).
    if status:
        s = status.strip().lower()
        completed_regex = {"$regex": r"^(done|ok|selesai|completed)$", "$options": "i"}
        completed_or = [
            {"hasil_aktivasi_status": completed_regex},
            {"hasil_instalasi_status": completed_regex},
            {"hasil_survey_status": completed_regex},
        ]
        progress_or = [
            {"hasil_aktivasi_status": {"$nin": ["", None]}},
            {"hasil_instalasi_status": {"$nin": ["", None]}},
            {"hasil_survey_status": {"$nin": ["", None]}},
            {"activity_aktivasi_start": {"$nin": ["", None]}},
            {"activity_instalasi_start": {"$nin": ["", None]}},
            {"activity_survey_start": {"$nin": ["", None]}},
        ]
        if s == "completed":
            existing = query.pop("$or", None)
            and_clauses: List[Dict[str, Any]] = [{"$or": completed_or}]
            if existing:
                and_clauses.append({"$or": existing})
            query["$and"] = and_clauses
        elif s == "in_progress":
            existing = query.pop("$or", None)
            and_clauses = [
                {"$nor": [{"$or": completed_or}]},
                {"$or": progress_or},
            ]
            if existing:
                and_clauses.append({"$or": existing})
            query["$and"] = and_clauses
        elif s == "pending":
            existing = query.pop("$or", None)
            and_clauses = [{"$nor": [{"$or": progress_or}]}]
            if existing:
                and_clauses.append({"$or": existing})
            query["$and"] = and_clauses

    total = await db.workorders.count_documents(query)
    cursor = db.workorders.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = [workorder_to_out(d) for d in await cursor.to_list(page_size)]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@api.get("/workorders/{wo_id}")
async def get_workorder(wo_id: str, user: dict = Depends(get_current_user)):
    doc = await db.workorders.find_one({"_id": ObjectId(wo_id)})
    if not doc:
        raise HTTPException(404, "Not found")
    return workorder_to_out(doc)


async def _validate_perangkat_uniqueness(doc: dict, exclude_wo_id: Optional[str] = None) -> None:
    """Ensure each perangkat_items[].nomor_registrasi is unique per SA/SI owner.
    Rule: 1 perangkat (nomor registrasi) hanya boleh milik 1 SA ID atau SI ID.
    The same nomor_registrasi may appear in multiple work orders as long as
    they share the same SA_ID or SI_ID (e.g. PSB then later MAINTENANCE for
    the same customer/service).

    Exceptions:
    - Perangkat pada WO DISMANTLE dianggap "lepas"/tersedia sehingga boleh
      dipakai kembali di WO lain, termasuk untuk SA/SI yang berbeda.
    - Perangkat ber-role "dicabut" (Dicabut/Rusak) pada WO MAINTENANCE dianggap
      pensiun permanen dan tidak boleh dipakai di WO manapun."""
    items = doc.get("perangkat_items") or []
    seen: Dict[str, int] = {}
    for i, it in enumerate(items):
        nr = (it or {}).get("nomor_registrasi", "")
        nr = (nr or "").strip()
        if not nr:
            continue
        if nr in seen:
            raise HTTPException(
                400,
                f"Nomor registrasi duplikat di baris ini: {nr}",
            )
        seen[nr] = i
    if not seen:
        return
    my_sa = (doc.get("sa_id") or "").strip()
    my_si = (doc.get("si_id") or "").strip()
    query: Dict[str, Any] = {"perangkat_items.nomor_registrasi": {"$in": list(seen.keys())}}
    if exclude_wo_id:
        try:
            query["_id"] = {"$ne": ObjectId(exclude_wo_id)}
        except Exception:
            pass
    async for other in db.workorders.find(query):
        other_items = other.get("perangkat_items") or []
        other_sa = (other.get("sa_id") or "").strip()
        other_si = (other.get("si_id") or "").strip()
        other_jenis = (other.get("jenis_order") or "").strip().upper()
        # Allow reuse if they share SA_ID or SI_ID (same customer/service).
        shares_owner = (
            (my_sa and other_sa and my_sa == other_sa)
            or (my_si and other_si and my_si == other_si)
        )
        for oi in other_items:
            onr = (oi or {}).get("nomor_registrasi", "").strip()
            if not (onr and onr in seen):
                continue
            orole = ((oi or {}).get("role") or "").strip().lower()
            who = other_sa or other_si or str(other.get("_id"))
            # Rule: a device marked DICABUT/RUSAK on a MAINTENANCE work order is
            # permanently retired and may NOT be reused on ANY work order.
            if orole == "dicabut":
                raise HTTPException(
                    400,
                    f"Perangkat '{onr}' berstatus DICABUT/RUSAK pada WO maintenance (SA/SI: {who}) sehingga tidak dapat dipakai di pekerjaan manapun.",
                )
            # Rule: a device on a DISMANTLE work order is released (dismantled) and
            # may be reused on other work orders, even for a different SA/SI.
            if other_jenis == "DISMANTLE":
                continue
            # Default rule: 1 perangkat hanya boleh milik 1 SA/SI (kecuali berbagi owner).
            if shares_owner:
                continue
            raise HTTPException(
                400,
                f"Nomor registrasi '{onr}' sudah terdaftar di WO lain (SA/SI: {who}). 1 perangkat hanya boleh milik 1 SA/SI.",
            )


def _validate_sa_or_si_required(doc: dict) -> None:
    """Every work order MUST have Pelanggan filled and at least SA ID or SI ID filled."""
    pel = (doc.get("pelanggan") or "").strip()
    if not pel:
        raise HTTPException(400, "Nama Pelanggan wajib diisi")
    sa = (doc.get("sa_id") or "").strip()
    si = (doc.get("si_id") or "").strip()
    if not sa and not si:
        raise HTTPException(
            400,
            "SA ID atau SI ID wajib diisi minimal salah satu untuk setiap Work Order.",
        )


@api.post("/workorders")
async def create_workorder(payload: WorkOrderIn, user: dict = Depends(require_roles("admin", "operator"))):
    doc = payload.model_dump()
    _validate_sa_or_si_required(doc)
    await _validate_perangkat_uniqueness(doc)
    doc["created_at"] = now_iso()
    doc["updated_at"] = now_iso()
    doc["created_by"] = user["actor"]
    res = await db.workorders.insert_one(doc)
    doc["_id"] = res.inserted_id
    await _learn_perangkat(doc.get("perangkat_items"))
    await _learn_teknisi(doc.get("tim_pelaksana"), doc.get("teknisi_pelaksana"))
    await audit("workorder.create", user, workorder_id=str(res.inserted_id), meta={"pelanggan": doc.get("pelanggan")})
    return workorder_to_out(doc)


@api.put("/workorders/{wo_id}")
async def update_workorder(wo_id: str, payload: WorkOrderIn, user: dict = Depends(require_roles("admin", "operator"))):
    doc = payload.model_dump()
    _validate_sa_or_si_required(doc)
    await _validate_perangkat_uniqueness(doc, exclude_wo_id=wo_id)
    doc["updated_at"] = now_iso()
    res = await db.workorders.update_one({"_id": ObjectId(wo_id)}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    updated = await db.workorders.find_one({"_id": ObjectId(wo_id)})
    await _learn_perangkat(doc.get("perangkat_items"))
    await _learn_teknisi(doc.get("tim_pelaksana"), doc.get("teknisi_pelaksana"))
    await audit("workorder.update", user, workorder_id=wo_id, meta={"pelanggan": updated.get("pelanggan")})
    return workorder_to_out(updated)


@api.delete("/workorders/{wo_id}")
async def delete_workorder(wo_id: str, user: dict = Depends(require_roles("admin"))):
    doc = await db.workorders.find_one({"_id": ObjectId(wo_id)})
    if not doc:
        raise HTTPException(404, "Not found")
    await db.workorders.delete_one({"_id": ObjectId(wo_id)})
    await audit("workorder.delete", user, workorder_id=wo_id, meta={"pelanggan": doc.get("pelanggan")})
    # Return the deleted document so the client can offer an "Undo" (restore).
    return {"ok": True, "deleted": workorder_to_out(doc)}


class BulkDeleteIn(BaseModel):
    ids: List[str] = Field(default_factory=list)


class RestoreIn(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)


@api.post("/workorders/bulk-delete")
async def bulk_delete_workorders(payload: BulkDeleteIn, user: dict = Depends(require_roles("admin"))):
    ids = [i for i in (payload.ids or []) if i]
    if not ids:
        raise HTTPException(400, "No ids provided")
    try:
        oids = [ObjectId(i) for i in ids]
    except Exception:
        raise HTTPException(400, "Invalid id in list")
    docs = await db.workorders.find({"_id": {"$in": oids}}).to_list(length=len(oids))
    if not docs:
        raise HTTPException(404, "No matching work orders")
    res = await db.workorders.delete_many({"_id": {"$in": oids}})
    for d in docs:
        await audit("workorder.delete", user, workorder_id=str(d["_id"]), meta={"pelanggan": d.get("pelanggan"), "bulk": True})
    return {"ok": True, "deleted_count": res.deleted_count, "deleted": [workorder_to_out(d) for d in docs]}


@api.post("/workorders/restore")
async def restore_workorders(payload: RestoreIn, user: dict = Depends(require_roles("admin"))):
    items = payload.items or []
    if not items:
        raise HTTPException(400, "No items to restore")
    restored = 0
    for it in items:
        doc = dict(it)
        raw_id = doc.pop("id", None)
        if not raw_id:
            continue
        try:
            doc["_id"] = ObjectId(raw_id)
        except Exception:
            continue
        # Skip if it already exists (idempotent restore).
        exists = await db.workorders.find_one({"_id": doc["_id"]})
        if exists:
            continue
        doc["updated_at"] = now_iso()
        await db.workorders.insert_one(doc)
        await audit("workorder.restore", user, workorder_id=raw_id, meta={"pelanggan": doc.get("pelanggan")})
        restored += 1
    return {"ok": True, "restored": restored}


# ------------------------------------------------------------------
# Tim Pelaksana: master teknisi (autocomplete) + KPI per teknisi/tim
# ------------------------------------------------------------------
async def _learn_teknisi(tim, names) -> None:
    """Kumpulkan nama teknisi ke master (untuk autocomplete konsisten)."""
    tim_norm = (tim or "").strip().upper()
    if tim_norm not in ("INTERNAL", "MITRA"):
        return
    for n in names or []:
        nama = str(n or "").strip()
        if not nama:
            continue
        await db.teknisi_master.update_one(
            {"nama": nama, "tim": tim_norm},
            {"$inc": {"count": 1}, "$set": {"updated_at": now_iso()}},
            upsert=True,
        )


def _wo_effective_status(wo: dict) -> str:
    """Status akhir WO: ambil status fase paling maju yang sudah terisi."""
    for k in ("hasil_aktivasi_status", "hasil_instalasi_status", "hasil_survey_status"):
        v = (wo.get(k) or "").strip().upper()
        if v:
            return v
    return ""


@api.get("/teknisi/master")
async def teknisi_master(tim: Optional[str] = None, q: Optional[str] = None,
                         user: dict = Depends(get_current_user)):
    query: Dict[str, Any] = {}
    if tim and tim.strip().upper() in ("INTERNAL", "MITRA"):
        query["tim"] = tim.strip().upper()
    if q and q.strip():
        query["nama"] = {"$regex": q.strip(), "$options": "i"}
    names = await db.teknisi_master.distinct("nama", query)
    names = sorted([n for n in names if n], key=lambda s: s.lower())
    return {"names": names}


@api.get("/media/perangkat-names")
async def media_perangkat_names(q: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Nilai media_perangkat unik yang pernah diinput (untuk autocomplete)."""
    query: Dict[str, Any] = {"media_perangkat": {"$nin": ["", None]}}
    if q and q.strip():
        query["media_perangkat"] = {"$regex": q.strip(), "$options": "i"}
    names = await db.workorders.distinct("media_perangkat", query)
    names = sorted([str(n).strip() for n in names if str(n).strip()], key=lambda s: s.lower())
    return {"names": names}


@api.get("/kpi/teknisi")
async def kpi_teknisi(date_from: Optional[str] = None, date_to: Optional[str] = None,
                      tim: Optional[str] = None, user: dict = Depends(get_current_user)):
    """KPI per teknisi & ringkasan Internal vs Mitra.
    Selesai = status OK atau BATAL."""
    return await _compute_kpi_teknisi(date_from, date_to, tim)


def _kpi_query(date_from, date_to, tim) -> Dict[str, Any]:
    query: Dict[str, Any] = {"tim_pelaksana": {"$in": ["INTERNAL", "MITRA"]}}
    if tim and tim.strip().upper() in ("INTERNAL", "MITRA"):
        query["tim_pelaksana"] = tim.strip().upper()
    if date_from:
        query.setdefault("created_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("created_at", {})["$lte"] = date_to + "T23:59:59"
    return query


async def _compute_kpi_teknisi(date_from, date_to, tim) -> dict:
    query = _kpi_query(date_from, date_to, tim)
    docs = await db.workorders.find(query).to_list(100000)

    per: Dict[tuple, dict] = {}
    summary = {
        "INTERNAL": {"teknisi": set(), "total": 0, "selesai": 0, "ok": 0, "batal": 0},
        "MITRA": {"teknisi": set(), "total": 0, "selesai": 0, "ok": 0, "batal": 0},
    }
    for wo in docs:
        tim_wo = (wo.get("tim_pelaksana") or "").strip().upper()
        if tim_wo not in ("INTERNAL", "MITRA"):
            continue
        st = _wo_effective_status(wo)
        is_ok = st == "OK"
        is_batal = st == "BATAL"
        is_selesai = is_ok or is_batal
        names = [str(n).strip() for n in (wo.get("teknisi_pelaksana") or []) if str(n).strip()]
        summary[tim_wo]["total"] += 1
        summary[tim_wo]["ok"] += 1 if is_ok else 0
        summary[tim_wo]["batal"] += 1 if is_batal else 0
        summary[tim_wo]["selesai"] += 1 if is_selesai else 0
        for nm in names:
            summary[tim_wo]["teknisi"].add(nm)
            key = (nm, tim_wo)
            row = per.setdefault(key, {"nama": nm, "tim": tim_wo, "total": 0,
                                       "selesai": 0, "ok": 0, "batal": 0, "pending": 0})
            row["total"] += 1
            row["ok"] += 1 if is_ok else 0
            row["batal"] += 1 if is_batal else 0
            row["selesai"] += 1 if is_selesai else 0
            row["pending"] += 0 if is_selesai else 1

    technicians = []
    for row in per.values():
        row["success_rate"] = round((row["ok"] / row["total"] * 100), 1) if row["total"] else 0
        technicians.append(row)
    technicians.sort(key=lambda r: (-r["total"], r["nama"].lower()))

    def sumout(s):
        return {
            "teknisi_count": len(s["teknisi"]),
            "total": s["total"], "selesai": s["selesai"], "ok": s["ok"], "batal": s["batal"],
            "success_rate": round((s["ok"] / s["total"] * 100), 1) if s["total"] else 0,
        }

    all_total = summary["INTERNAL"]["total"] + summary["MITRA"]["total"]
    all_ok = summary["INTERNAL"]["ok"] + summary["MITRA"]["ok"]
    all_batal = summary["INTERNAL"]["batal"] + summary["MITRA"]["batal"]
    all_selesai = summary["INTERNAL"]["selesai"] + summary["MITRA"]["selesai"]
    all_teknisi = summary["INTERNAL"]["teknisi"] | summary["MITRA"]["teknisi"]

    return {
        "technicians": technicians,
        "summary": {
            "internal": sumout(summary["INTERNAL"]),
            "mitra": sumout(summary["MITRA"]),
            "all": {
                "teknisi_count": len(all_teknisi), "total": all_total, "selesai": all_selesai,
                "ok": all_ok, "batal": all_batal,
                "success_rate": round((all_ok / all_total * 100), 1) if all_total else 0,
            },
        },
    }


@api.get("/kpi/teknisi/workorders")
async def kpi_teknisi_workorders(nama: str, tim: Optional[str] = None,
                                 date_from: Optional[str] = None, date_to: Optional[str] = None,
                                 user: dict = Depends(get_current_user)):
    """Daftar Work Order yang ditangani seorang teknisi (untuk detail per teknisi)."""
    query = _kpi_query(date_from, date_to, tim)
    query["teknisi_pelaksana"] = nama.strip()
    docs = await db.workorders.find(query).sort("created_at", -1).to_list(100000)
    items = []
    for wo in docs:
        items.append({
            "id": str(wo["_id"]),
            "pelanggan": wo.get("pelanggan", ""),
            "sa_id": wo.get("sa_id", ""),
            "jenis_order": wo.get("jenis_order", ""),
            "media_jenis": wo.get("media_jenis", ""),
            "tim_pelaksana": wo.get("tim_pelaksana", ""),
            "status": _wo_effective_status(wo) or "-",
            "created_at": wo.get("created_at", ""),
        })
    return {"nama": nama, "items": items, "total": len(items)}


@api.get("/kpi/teknisi/export/xlsx")
async def kpi_teknisi_export(date_from: Optional[str] = None, date_to: Optional[str] = None,
                             tim: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Unduh rekap KPI per teknisi ke Excel (untuk laporan bulanan)."""
    data = await _compute_kpi_teknisi(date_from, date_to, tim)
    rows = [{
        "NAMA TEKNISI": t["nama"],
        "TIM": t["tim"],
        "TOTAL WO": t["total"],
        "SELESAI - OK": t["ok"],
        "SELESAI - BATAL": t["batal"],
        "PENDING": t["pending"],
    } for t in data["technicians"]]
    df = pd.DataFrame(rows, columns=["NAMA TEKNISI", "TIM", "TOTAL WO", "SELESAI - OK", "SELESAI - BATAL", "PENDING"])

    s = data["summary"]
    srows = [
        {"TIM": "INTERNAL", "JUMLAH TEKNISI": s["internal"]["teknisi_count"], "TOTAL WO": s["internal"]["total"],
         "SELESAI - OK": s["internal"]["ok"], "SELESAI - BATAL": s["internal"]["batal"]},
        {"TIM": "MITRA", "JUMLAH TEKNISI": s["mitra"]["teknisi_count"], "TOTAL WO": s["mitra"]["total"],
         "SELESAI - OK": s["mitra"]["ok"], "SELESAI - BATAL": s["mitra"]["batal"]},
        {"TIM": "SEMUA", "JUMLAH TEKNISI": s["all"]["teknisi_count"], "TOTAL WO": s["all"]["total"],
         "SELESAI - OK": s["all"]["ok"], "SELESAI - BATAL": s["all"]["batal"]},
    ]
    df_sum = pd.DataFrame(srows, columns=["TIM", "JUMLAH TEKNISI", "TOTAL WO", "SELESAI - OK", "SELESAI - BATAL"])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df_sum.to_excel(writer, index=False, sheet_name="Ringkasan")
        df.to_excel(writer, index=False, sheet_name="Per Teknisi")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=kpi-teknisi.xlsx"},
    )


# ------------------------------------------------------------------
# Perangkat "Bank Data": prefix -> nama learning + lookup
# Setiap perangkat yang ditambahkan menjadi bank data. Nomor registrasi
# dikenali lewat prefix 13 karakter.
# ------------------------------------------------------------------
PREFIX_LEN = 13
PREFIX_LENGTHS = (PREFIX_LEN,)


def _clean_nomor(nomor: Optional[str]) -> str:
    return (nomor or "").strip().upper()


async def _learn_perangkat(items) -> None:
    """Persist prefix->nama mappings so future entries auto-detect the device."""
    for it in items or []:
        if not isinstance(it, dict):
            continue
        nama = (it.get("nama_perangkat") or "").strip()
        nomor = _clean_nomor(it.get("nomor_registrasi"))
        if not nama or len(nomor) < PREFIX_LEN:
            continue
        for L in PREFIX_LENGTHS:
            if len(nomor) < L:
                continue
            await db.perangkat_bank.update_one(
                {"prefix": nomor[:L], "plen": L, "nama": nama},
                {"$inc": {"count": 1}, "$set": {"updated_at": now_iso()}},
                upsert=True,
            )


async def _seed_perangkat_bank() -> None:
    if await db.perangkat_bank.estimated_document_count() > 0:
        return
    try:
        with open(ROOT_DIR / "perangkat_bank_seed.json", "r", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception as e:
        log.warning(f"perangkat bank seed skipped: {e}")
        return
    items = [{"nama_perangkat": r[0], "nomor_registrasi": r[1]} for r in rows if len(r) == 2]
    await _learn_perangkat(items)
    log.info(f"Seeded perangkat bank from {len(items)} rows")


@api.get("/perangkat/bank/lookup")
async def perangkat_bank_lookup(nomor: str, user: dict = Depends(get_current_user)):
    """Return device name(s) matching a registration number by longest prefix."""
    n = _clean_nomor(nomor)
    if len(n) < PREFIX_LEN:
        return {"matched": False, "options": []}
    for L in PREFIX_LENGTHS:
        if len(n) < L:
            continue
        prefix = n[:L]
        agg: Dict[str, int] = {}
        async for d in db.perangkat_bank.find({"prefix": prefix, "plen": L}):
            agg[d["nama"]] = agg.get(d["nama"], 0) + int(d.get("count", 1))
        if agg:
            options = sorted(
                [{"nama": k, "count": v} for k, v in agg.items()],
                key=lambda x: (-x["count"], x["nama"]),
            )
            return {
                "matched": True,
                "prefix": prefix,
                "length": L,
                "ambiguous": len(options) > 1,
                "suggested": options[0]["nama"],
                "options": options,
            }
    return {"matched": False, "options": []}


def _derive_perangkat_status(occurrences: List[Dict[str, Any]]) -> str:
    """Derive a device's current status from its occurrences across work orders.
    Rules (retired wins; otherwise the latest occurrence decides):
      - "retired"   : pernah role=dicabut (Dicabut/Rusak) -> pensiun permanen
      - "available" : occurrence terbaru = DISMANTLE -> lepas, boleh dipakai kembali
      - "in_use"    : occurrence terbaru non-dismantle -> terpasang aktif
      - "new"       : belum pernah tercatat
    """
    if not occurrences:
        return "new"
    if any((o.get("role") or "").strip().lower() == "dicabut" for o in occurrences):
        return "retired"
    latest = max(occurrences, key=lambda o: o.get("created_at") or "")
    if (latest.get("jenis_order") or "").strip().upper() == "DISMANTLE":
        return "available"
    return "in_use"


@api.get("/perangkat/history")
async def perangkat_history(nomor: str, exclude_wo_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Trace a registration number across all work orders and derive its status.

    status:
      - "retired"   : pernah Dicabut/Rusak -> tak boleh dipakai di WO manapun
      - "available" : occurrence terbaru = DISMANTLE -> lepas, boleh dipakai kembali
      - "in_use"    : occurrence terbaru non-dismantle -> terpasang aktif
      - "new"       : belum pernah tercatat
    """
    nr = (nomor or "").strip()
    if not nr:
        return {"nomor_registrasi": "", "status": "new", "occurrences": []}
    query: Dict[str, Any] = {"perangkat_items.nomor_registrasi": nr}
    if exclude_wo_id:
        try:
            query["_id"] = {"$ne": ObjectId(exclude_wo_id)}
        except Exception:
            pass
    occurrences: List[Dict[str, Any]] = []
    async for wo in db.workorders.find(query):
        jenis = (wo.get("jenis_order") or "").strip().upper()
        for it in (wo.get("perangkat_items") or []):
            if (it or {}).get("nomor_registrasi", "").strip() != nr:
                continue
            occurrences.append({
                "workorder_id": str(wo.get("_id")),
                "pelanggan": wo.get("pelanggan") or "",
                "sa_id": wo.get("sa_id") or "",
                "si_id": wo.get("si_id") or "",
                "jenis_order": jenis,
                "role": ((it or {}).get("role") or "").strip().lower(),
                "nama_perangkat": (it or {}).get("nama_perangkat") or "",
                "created_at": wo.get("created_at") or "",
            })
    status = _derive_perangkat_status(occurrences)
    occurrences.sort(key=lambda o: o.get("created_at") or "", reverse=True)
    return {"nomor_registrasi": nr, "status": status, "occurrences": occurrences}


@api.get("/perangkat/names")
async def perangkat_names(q: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Semua nama perangkat yang pernah tercatat (dipelajari dari work order / bank).
    Daftar ini bertambah otomatis begitu perangkat baru direkam, sehingga
    autocomplete pada 'Tambah Perangkat' selalu memuat perangkat yang baru terdaftar."""
    names = [n for n in await db.perangkat_bank.distinct("nama") if n]
    if q:
        ql = q.strip().lower()
        names = [n for n in names if ql in n.lower()]
    names.sort()
    return {"names": names[:1000]}


@api.get("/perangkat/stats")
async def perangkat_stats(user: dict = Depends(get_current_user)):
    """Ringkasan jumlah perangkat unik menurut status (untuk dashboard)."""
    by_nomor: Dict[str, List[Dict[str, Any]]] = {}
    cursor = db.workorders.find({}, {"perangkat_items": 1, "jenis_order": 1, "created_at": 1})
    async for wo in cursor:
        jenis = (wo.get("jenis_order") or "").strip().upper()
        created = wo.get("created_at") or ""
        for it in (wo.get("perangkat_items") or []):
            nr = ((it or {}).get("nomor_registrasi") or "").strip()
            if not nr:
                continue
            by_nomor.setdefault(nr, []).append({
                "jenis_order": jenis,
                "role": ((it or {}).get("role") or "").strip().lower(),
                "created_at": created,
            })
    counts = {"total": len(by_nomor), "tersedia": 0, "terpasang": 0, "dicabut": 0}
    for occ in by_nomor.values():
        st = _derive_perangkat_status(occ)
        if st == "available":
            counts["tersedia"] += 1
        elif st == "in_use":
            counts["terpasang"] += 1
        elif st == "retired":
            counts["dicabut"] += 1
    return counts


class NameMergeIn(BaseModel):
    from_names: List[str] = Field(default_factory=list)
    into: str


class NameDeleteIn(BaseModel):
    names: List[str] = Field(default_factory=list)


@api.get("/perangkat/names/summary")
async def perangkat_names_summary(q: Optional[str] = None, user: dict = Depends(require_roles("admin"))):
    """Daftar nama perangkat unik + total pemakaian (count) untuk halaman kelola."""
    pipeline = [
        {"$group": {"_id": "$nama", "count": {"$sum": "$count"}, "entries": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    rows = await db.perangkat_bank.aggregate(pipeline).to_list(100000)
    items = [
        {"nama": r["_id"], "count": int(r.get("count", 0)), "entries": int(r.get("entries", 0))}
        for r in rows
        if r.get("_id")
    ]
    if q:
        ql = q.strip().lower()
        items = [i for i in items if ql in i["nama"].lower()]
    return {"total": len(items), "items": items}


@api.post("/perangkat/names/merge")
async def perangkat_names_merge(payload: NameMergeIn, user: dict = Depends(require_roles("admin"))):
    """Gabungkan / ganti nama: pindahkan semua entri bank & item WO dari
    `from_names` ke nama `into`. Berlaku juga sebagai rename (1 sumber)."""
    into = (payload.into or "").strip().upper()
    sources = [(s or "").strip().upper() for s in (payload.from_names or []) if (s or "").strip()]
    sources = [s for s in dict.fromkeys(sources) if s and s != into]  # unik, buang target
    if not into or not sources:
        raise HTTPException(400, "from_names dan into wajib diisi")
    bank_moved = 0
    for src in sources:
        async for d in db.perangkat_bank.find({"nama": src}):
            await db.perangkat_bank.update_one(
                {"prefix": d["prefix"], "plen": d["plen"], "nama": into},
                {"$inc": {"count": int(d.get("count", 1))}, "$set": {"updated_at": now_iso()}},
                upsert=True,
            )
            await db.perangkat_bank.delete_one({"_id": d["_id"]})
            bank_moved += 1
    wo_updated = 0
    async for wo in db.workorders.find({"perangkat_items.nama_perangkat": {"$in": sources}}):
        items = wo.get("perangkat_items") or []
        changed = False
        for it in items:
            if isinstance(it, dict) and ((it.get("nama_perangkat") or "").strip().upper() in sources):
                it["nama_perangkat"] = into
                changed = True
        if changed:
            await db.workorders.update_one(
                {"_id": wo["_id"]},
                {"$set": {"perangkat_items": items, "updated_at": now_iso()}},
            )
            wo_updated += 1
    await audit("perangkat.names.merge", user, meta={"into": into, "from": sources})
    return {"ok": True, "into": into, "bank_moved": bank_moved, "workorders_updated": wo_updated}


@api.post("/perangkat/names/delete")
async def perangkat_names_delete(payload: NameDeleteIn, user: dict = Depends(require_roles("admin"))):
    """Hapus nama perangkat dari registry (bank). Tidak mengubah data WO."""
    names = [(n or "").strip().upper() for n in (payload.names or []) if (n or "").strip()]
    names = list(dict.fromkeys(names))
    if not names:
        raise HTTPException(400, "names wajib diisi")
    res = await db.perangkat_bank.delete_many({"nama": {"$in": names}})
    await audit("perangkat.names.delete", user, meta={"names": names})
    return {"ok": True, "deleted_entries": res.deleted_count}


# --- Bank Data management (admin) ---------------------------------
class BankEntryIn(BaseModel):
    prefix: str
    nama: str


class BankEntryUpdate(BaseModel):
    prefix: Optional[str] = None
    nama: Optional[str] = None


def _bank_out(d: dict) -> dict:
    return {
        "id": str(d["_id"]),
        "prefix": d.get("prefix"),
        "plen": d.get("plen"),
        "nama": d.get("nama"),
        "count": int(d.get("count", 1)),
        "updated_at": d.get("updated_at", ""),
    }


@api.get("/perangkat/bank")
async def perangkat_bank_list(
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    user: dict = Depends(require_roles("admin")),
):
    query: Dict[str, Any] = {}
    if q and q.strip():
        s = q.strip()
        query = {"$or": [
            {"prefix": {"$regex": s.upper()}},
            {"nama": {"$regex": s, "$options": "i"}},
        ]}
    total = await db.perangkat_bank.count_documents(query)
    cur = (
        db.perangkat_bank.find(query)
        .sort([("nama", 1), ("prefix", 1), ("plen", 1)])
        .skip(max(0, (page - 1) * page_size))
        .limit(page_size)
    )
    items = [_bank_out(d) async for d in cur]
    total_prefixes = len(await db.perangkat_bank.distinct("prefix"))
    total_namas = len(await db.perangkat_bank.distinct("nama"))
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "kpi": {
            "total_entries": await db.perangkat_bank.estimated_document_count(),
            "total_prefixes": total_prefixes,
            "total_namas": total_namas,
        },
    }


@api.get("/perangkat/bank/export/xlsx")
async def perangkat_bank_export(user: dict = Depends(require_roles("admin"))):
    docs = await db.perangkat_bank.find({}).sort([("nama", 1), ("prefix", 1)]).to_list(100000)
    rows = [
        {
            "PREFIX": d.get("prefix"),
            "PANJANG": d.get("plen"),
            "NAMA PERANGKAT": d.get("nama"),
            "JUMLAH DATA": int(d.get("count", 1)),
            "DIPERBARUI": d.get("updated_at", ""),
        }
        for d in docs
    ]
    df = pd.DataFrame(rows, columns=["PREFIX", "PANJANG", "NAMA PERANGKAT", "JUMLAH DATA", "DIPERBARUI"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Bank Data Perangkat")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bank-data-perangkat.xlsx"},
    )


@api.post("/perangkat/bank")
async def perangkat_bank_create(payload: BankEntryIn, user: dict = Depends(require_roles("admin"))):
    prefix = _clean_nomor(payload.prefix)
    nama = (payload.nama or "").strip()
    if not nama:
        raise HTTPException(400, "Nama perangkat wajib diisi.")
    if len(prefix) != PREFIX_LEN:
        raise HTTPException(400, f"Prefix harus {PREFIX_LEN} karakter.")
    plen = len(prefix)
    existing = await db.perangkat_bank.find_one({"prefix": prefix, "plen": plen, "nama": nama})
    if existing:
        return _bank_out(existing)
    doc = {"prefix": prefix, "plen": plen, "nama": nama, "count": 1, "updated_at": now_iso()}
    res = await db.perangkat_bank.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _bank_out(doc)


@api.put("/perangkat/bank/{entry_id}")
async def perangkat_bank_update(entry_id: str, payload: BankEntryUpdate, user: dict = Depends(require_roles("admin"))):
    doc = await db.perangkat_bank.find_one({"_id": ObjectId(entry_id)})
    if not doc:
        raise HTTPException(404, "Not found")
    new_prefix = _clean_nomor(payload.prefix) if payload.prefix is not None else doc["prefix"]
    new_nama = payload.nama.strip() if payload.nama is not None else doc["nama"]
    if not new_nama:
        raise HTTPException(400, "Nama perangkat wajib diisi.")
    if len(new_prefix) != PREFIX_LEN:
        raise HTTPException(400, f"Prefix harus {PREFIX_LEN} karakter.")
    new_plen = len(new_prefix)
    dup = await db.perangkat_bank.find_one(
        {"prefix": new_prefix, "plen": new_plen, "nama": new_nama, "_id": {"$ne": ObjectId(entry_id)}}
    )
    if dup:
        await db.perangkat_bank.update_one(
            {"_id": dup["_id"]},
            {"$inc": {"count": int(doc.get("count", 1))}, "$set": {"updated_at": now_iso()}},
        )
        await db.perangkat_bank.delete_one({"_id": ObjectId(entry_id)})
        merged = await db.perangkat_bank.find_one({"_id": dup["_id"]})
        return {**_bank_out(merged), "merged": True}
    await db.perangkat_bank.update_one(
        {"_id": ObjectId(entry_id)},
        {"$set": {"prefix": new_prefix, "plen": new_plen, "nama": new_nama, "updated_at": now_iso()}},
    )
    updated = await db.perangkat_bank.find_one({"_id": ObjectId(entry_id)})
    return _bank_out(updated)


@api.delete("/perangkat/bank/{entry_id}")
async def perangkat_bank_delete(entry_id: str, user: dict = Depends(require_roles("admin"))):
    res = await db.perangkat_bank.delete_one({"_id": ObjectId(entry_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@api.post("/perangkat/bank/import/xlsx")
async def perangkat_bank_import(file: UploadFile = File(...), user: dict = Depends(require_roles("admin"))):
    """Import many prefix->nama pairs from Excel.

    Two accepted layouts (auto-detected by headers):
      1. PREFIX + NAMA PERANGKAT  -> direct import (prefix must be 11-13 chars).
      2. NOMOR/KODE REGISTRASI + NAMA PERANGKAT -> derive prefixes via learning.
    """
    raw = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(raw), sheet_name=0)
    except Exception as e:
        raise HTTPException(400, f"Gagal membaca file Excel: {e}")

    cols = {str(c).strip().upper(): c for c in df.columns}

    def find(*keys):
        for norm, orig in cols.items():
            if any(k in norm for k in keys):
                return orig
        return None

    prefix_col = cols.get("PREFIX")
    nama_col = find("NAMA")
    nomor_col = find("REGISTRASI", "NOMOR", "KODE")

    if not nama_col:
        raise HTTPException(400, "Kolom nama perangkat tidak ditemukan. Gunakan template (kolom 'Prefix' + 'Nama Perangkat').")

    def clean_cell(v) -> str:
        s = str(v).strip()
        return "" if s.lower() == "nan" else s

    imported = 0
    skipped = 0
    errors: List[str] = []

    if prefix_col is not None:
        mode = "prefix"
        for idx, row in df.iterrows():
            prefix = _clean_nomor(clean_cell(row.get(prefix_col, "")))
            nama = clean_cell(row.get(nama_col, ""))
            if not prefix or not nama:
                skipped += 1
                continue
            if len(prefix) != PREFIX_LEN:
                skipped += 1
                if len(errors) < 20:
                    errors.append(f"Baris {idx + 2}: prefix '{prefix}' bukan {PREFIX_LEN} karakter")
                continue
            plen = len(prefix)
            existing = await db.perangkat_bank.find_one({"prefix": prefix, "plen": plen, "nama": nama})
            if existing:
                skipped += 1
                continue
            await db.perangkat_bank.insert_one(
                {"prefix": prefix, "plen": plen, "nama": nama, "count": 1, "updated_at": now_iso()}
            )
            imported += 1
    elif nomor_col is not None:
        mode = "registrasi"
        items = []
        for idx, row in df.iterrows():
            nama = clean_cell(row.get(nama_col, ""))
            nomor = _clean_nomor(clean_cell(row.get(nomor_col, "")))
            if not nama or len(nomor) < PREFIX_LEN:
                skipped += 1
                continue
            items.append({"nama_perangkat": nama, "nomor_registrasi": nomor})
        await _learn_perangkat(items)
        imported = len(items)
    else:
        raise HTTPException(400, "Format tidak dikenali. Sertakan kolom 'Prefix' atau 'Nomor Registrasi'.")

    return {"ok": True, "mode": mode, "imported": imported, "skipped": skipped, "errors": errors}


@api.get("/perangkat/bank/import/template.xlsx")
async def perangkat_bank_import_template(user: dict = Depends(require_roles("admin"))):
    """Downloadable template showing the expected import columns."""
    rows = [
        {"Prefix": "B2WS01000103", "Nama Perangkat": "CANISTER 1.8 DIAMETER 4 INCHI"},
        {"Prefix": "B2WS02A70201", "Nama Perangkat": "EVOLUTION X3 SATELLITE ROUTER"},
        {"Prefix": "B2WS0100010I", "Nama Perangkat": "LNB,C-BAND LS EXTD BAND"},
    ]
    df = pd.DataFrame(rows, columns=["Prefix", "Nama Perangkat"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Template Bank Data")
        ws = writer.sheets["Template Bank Data"]
        ws.set_column(0, 0, 20)
        ws.set_column(1, 1, 48)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template-bank-data.xlsx"},
    )





# ------------------------------------------------------------------
# Excel Import / Export
# ------------------------------------------------------------------
EXPORT_COLUMNS: List[tuple] = [
    ("pelanggan", "PELANGGAN"),
    ("alamat", "ALAMAT"),
    ("jenis_order", "JENIS ORDER"),
    ("sa_id", "SA ID"),
    ("si_id", "SI ID"),
    ("lat", "LATITUDE"),
    ("lng", "LONGITUDE"),
    ("bw", "BW"),
    ("rfs_la", "RFS LA"),
    ("rfs_pelanggan", "RFS PELANGGAN"),
    ("spk_survey_nomor", "SPK SURVEY NOMOR"),
    ("spk_survey_tgl_doc", "SPK SURVEY TGL DOC"),
    ("spk_survey_tgl_terima", "SPK SURVEY TGL TERIMA"),
    ("spk_instalasi_nomor", "SPK INSTALASI NOMOR"),
    ("spk_instalasi_tgl_doc", "SPK INSTALASI TGL DOC"),
    ("spk_instalasi_tgl_terima", "SPK INSTALASI TGL TERIMA"),
    ("spk_aktivasi_nomor", "SPK AKTIVASI NOMOR"),
    ("spk_aktivasi_tgl_doc", "SPK AKTIVASI TGL DOC"),
    ("spk_aktivasi_tgl_terima", "SPK AKTIVASI TGL TERIMA"),
    ("activity_survey_start", "ACTIVITY SURVEY START"),
    ("activity_survey_end", "ACTIVITY SURVEY END"),
    ("activity_instalasi_start", "ACTIVITY INSTALASI START"),
    ("activity_instalasi_end", "ACTIVITY INSTALASI END"),
    ("activity_aktivasi_start", "ACTIVITY AKTIVASI START"),
    ("activity_aktivasi_end", "ACTIVITY AKTIVASI END"),
    ("stop_survey_start", "STOP CLOCK SURVEY START"),
    ("stop_survey_end", "STOP CLOCK SURVEY END"),
    ("stop_instalasi_start", "STOP CLOCK INSTALASI START"),
    ("stop_instalasi_end", "STOP CLOCK INSTALASI END"),
    ("stop_aktivasi_start", "STOP CLOCK AKTIVASI START"),
    ("stop_aktivasi_end", "STOP CLOCK AKTIVASI END"),
    ("sdt_survey_durasi", "SDT SURVEY DURASI"),
    ("sdt_survey_target", "SDT SURVEY TARGET"),
    ("sdt_instalasi_durasi", "SDT INSTALASI DURASI"),
    ("sdt_instalasi_target", "SDT INSTALASI TARGET"),
    ("sdt_aktivasi_durasi", "SDT AKTIVASI DURASI"),
    ("sdt_aktivasi_target", "SDT AKTIVASI TARGET"),
    ("media_jenis", "MEDIA AKSES JENIS"),
    ("media_perangkat", "MEDIA AKSES PERANGKAT"),
    ("cp_la", "CP LA"),
    ("cp_mitra", "CP MITRA"),
    ("cp_pelanggan", "CP PELANGGAN"),
    ("hasil_survey_status", "HASIL SURVEY STATUS"),
    ("hasil_survey_datek", "HASIL SURVEY DATEK"),
    ("hasil_survey_npae", "HASIL SURVEY NPAE"),
    ("hasil_instalasi_status", "HASIL INSTALASI STATUS"),
    ("hasil_instalasi_datek", "HASIL INSTALASI DATEK"),
    ("hasil_instalasi_npae", "HASIL INSTALASI NPAE"),
    ("hasil_aktivasi_status", "HASIL AKTIVASI STATUS"),
    ("hasil_aktivasi_datek", "HASIL AKTIVASI DATEK"),
    ("hasil_aktivasi_npae", "HASIL AKTIVASI NPAE"),
    ("info_kondisi", "INFO KONDISI PELANGGAN"),
    ("info_perizinan", "INFO PERIZINAN"),
    ("info_biaya", "INFO BIAYA"),
    ("info_masalah", "INFO MASALAH"),
    ("info_tindak_lanjut", "INFO TINDAK LANJUT"),
    ("perangkat_terpasang", "PERANGKAT TERPASANG"),
    ("boq_paket", "BOQ PAKET"),
    ("boq_jasa", "BOQ JASA"),
    ("boq_material", "BOQ MATERIAL"),
    ("boq_jumlah", "BOQ JUMLAH"),
    ("inv_no", "NO INV"),
    ("inv_tgl", "TGL INV"),
    ("inv_tgl_kirim", "TGL KIRIM"),
    ("inv_tgl_bayar", "TGL BAYAR"),
    ("inv_status", "INV STATUS"),
    ("keterangan", "KETERANGAN"),
]


def _val(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    return str(v).strip()


_WO_KEY_FIELDS = [
    "pelanggan", "sa_id", "si_id", "jenis_order",
    "spk_survey_nomor", "spk_instalasi_nomor", "spk_aktivasi_nomor",
]


def _wo_key_query(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Natural key untuk deduplikasi import: cocokkan pada field pengenal yang
    terisi. None bila tidak ada pengenal (tidak bisa didedup -> insert biasa)."""
    q: Dict[str, Any] = {}
    for f in _WO_KEY_FIELDS:
        v = (str(doc.get(f) or "")).strip()
        if v:
            q[f] = doc.get(f)
    return q or None


def _format_perangkat_items(items) -> str:
    """Ringkas perangkat_items menjadi satu teks untuk kolom export."""
    out = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        nama = (it.get("nama_perangkat") or "").strip()
        nr = (it.get("nomor_registrasi") or "").strip()
        role = (it.get("role") or "").strip()
        part = nama
        if nr:
            part += f" [NR: {nr}]"
        if role:
            part += f" ({role})"
        part = part.strip()
        if part:
            out.append(part)
    return " ; ".join(out)


@api.get("/workorders/export/xlsx")
async def export_workorders(user: dict = Depends(get_current_user)):
    docs = await db.workorders.find({}).sort("created_at", -1).to_list(10000)
    rows = []
    perangkat_rows = []
    for d in docs:
        row = {label: d.get(field, "") for field, label in EXPORT_COLUMNS}
        row["PERANGKAT (DETAIL)"] = _format_perangkat_items(d.get("perangkat_items"))
        rows.append(row)
        for it in (d.get("perangkat_items") or []):
            if not isinstance(it, dict):
                continue
            perangkat_rows.append({
                "PELANGGAN": d.get("pelanggan", ""),
                "SA ID": d.get("sa_id", ""),
                "SI ID": d.get("si_id", ""),
                "JENIS ORDER": d.get("jenis_order", ""),
                "NAMA PERANGKAT": it.get("nama_perangkat", ""),
                "NOMOR REGISTRASI": it.get("nomor_registrasi", ""),
                "KATEGORI": it.get("role", ""),
            })
    export_labels = [label for _, label in EXPORT_COLUMNS] + ["PERANGKAT (DETAIL)"]
    df = pd.DataFrame(rows, columns=export_labels)
    perangkat_cols = ["PELANGGAN", "SA ID", "SI ID", "JENIS ORDER", "NAMA PERANGKAT", "NOMOR REGISTRASI", "KATEGORI"]
    df_perangkat = pd.DataFrame(perangkat_rows, columns=perangkat_cols)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Workorders")
        df_perangkat.to_excel(writer, index=False, sheet_name="Perangkat")
        wb = writer.book
        ws = writer.sheets["Workorders"]
        # Rupiah formatting for money columns
        rp_fmt = wb.add_format({"num_format": '"Rp" #,##0'})
        money_labels = {"BOQ JASA", "BOQ MATERIAL", "BOQ JUMLAH"}
        for i, label in enumerate(export_labels):
            if label in money_labels:
                ws.set_column(i, i, 18, rp_fmt)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=workorders.xlsx"},
    )


@api.post("/workorders/import/xlsx")
async def import_workorders(file: UploadFile = File(...), user: dict = Depends(require_roles("admin", "operator"))):
    raw = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=None)
    except Exception as e:
        raise HTTPException(400, f"Cannot read Excel: {e}")

    # Original dump has a 3-row header (group, phase, subheader). Detect it heuristically:
    # if any of the top 3 rows contains "SA ID" and row0 contains "PELANGGAN" we assume original layout.
    row0 = [_val(x).upper() for x in df.iloc[0].tolist()] if len(df) > 0 else []
    row1 = [_val(x).upper() for x in df.iloc[1].tolist()] if len(df) > 1 else []
    row2 = [_val(x).upper() for x in df.iloc[2].tolist()] if len(df) > 2 else []
    data_start = 0

    def _idx_original() -> Optional[Dict[str, int]]:
        try:
            has_sa = "SA ID" in row1 or "SA ID" in row2
            has_pel = "PELANGGAN" in " ".join(row0)
            if not (has_sa and has_pel):
                return None
        except Exception:
            return None
        # The original file has fixed positions. Build fixed mapping:
        mapping = {
            "pelanggan": 3, "alamat": 4, "jenis_order": 5,
            "lat": 6, "lng": 7, "bw": 8,
            "sa_id": 1, "si_id": 2,
            "rfs_la": 9, "rfs_pelanggan": 10,
            "spk_survey_nomor": 11, "spk_survey_tgl_doc": 12, "spk_survey_tgl_terima": 13,
            "spk_instalasi_nomor": 14, "spk_instalasi_tgl_doc": 15, "spk_instalasi_tgl_terima": 16,
            "spk_aktivasi_nomor": 17, "spk_aktivasi_tgl_doc": 18, "spk_aktivasi_tgl_terima": 19,
            "activity_survey_start": 20, "activity_survey_end": 21,
            "activity_instalasi_start": 22, "activity_instalasi_end": 23,
            "activity_aktivasi_start": 24, "activity_aktivasi_end": 25,
            "stop_survey_start": 26, "stop_survey_end": 27,
            "stop_instalasi_start": 28, "stop_instalasi_end": 29,
            "stop_aktivasi_start": 30, "stop_aktivasi_end": 31,
            "sdt_survey_durasi": 32, "sdt_survey_target": 33,
            "sdt_instalasi_durasi": 34, "sdt_instalasi_target": 35,
            "sdt_aktivasi_durasi": 36, "sdt_aktivasi_target": 37,
            "media_jenis": 38, "media_perangkat": 39,
            "cp_la": 40, "cp_mitra": 41, "cp_pelanggan": 42,
            "hasil_survey_status": 43, "hasil_survey_datek": 44, "hasil_survey_npae": 45,
            "hasil_instalasi_status": 46, "hasil_instalasi_datek": 47, "hasil_instalasi_npae": 48,
            "hasil_aktivasi_status": 49, "hasil_aktivasi_datek": 50, "hasil_aktivasi_npae": 51,
            "info_kondisi": 52, "info_perizinan": 53, "info_biaya": 54,
            "info_masalah": 55, "info_tindak_lanjut": 56,
            "perangkat_terpasang": 57,
            "boq_paket": 58, "boq_jasa": 59, "boq_material": 60, "boq_jumlah": 61,
            "inv_no": 62, "inv_tgl": 63, "inv_tgl_kirim": 64, "inv_tgl_bayar": 65, "inv_status": 66,
            "keterangan": 67,
        }
        return mapping

    mapping = _idx_original()
    if mapping:
        # Determine how many header rows to skip: find the last row where any subheader token is present.
        data_start = 3 if "SA ID" in row2 else 2
        docs = []
        for _, row in df.iloc[data_start:].iterrows():
            doc: Dict[str, Any] = {}
            has_any = False
            for field, col_idx in mapping.items():
                if col_idx < len(row):
                    v = _val(row.iloc[col_idx])
                    if v:
                        has_any = True
                    doc[field] = v
            if not has_any:
                continue
            # numeric coercion
            for k in ("boq_jasa", "boq_material", "boq_jumlah"):
                try:
                    doc[k] = float(str(doc.get(k, "0")).replace(",", "").replace(" ", "") or 0)
                except Exception:
                    doc[k] = 0
            doc["created_at"] = now_iso()
            doc["updated_at"] = now_iso()
            doc["created_by"] = user["actor"]
            docs.append(doc)
    else:
        # Fallback: expect flat headers in row 0 matching EXPORT_COLUMNS labels
        header = [_val(x).upper() for x in df.iloc[0].tolist()]
        idx_by_field = {}
        for field, label in EXPORT_COLUMNS:
            if label.upper() in header:
                idx_by_field[field] = header.index(label.upper())
        if not idx_by_field:
            raise HTTPException(400, "Unrecognized Excel format. Please use the LA dump layout or the app export template.")
        docs = []
        for _, row in df.iloc[1:].iterrows():
            doc: Dict[str, Any] = {}
            has_any = False
            for field, i in idx_by_field.items():
                v = _val(row.iloc[i]) if i < len(row) else ""
                if v:
                    has_any = True
                doc[field] = v
            if not has_any:
                continue
            for k in ("boq_jasa", "boq_material", "boq_jumlah"):
                try:
                    doc[k] = float(str(doc.get(k, "0")).replace(",", "").replace(" ", "") or 0)
                except Exception:
                    doc[k] = 0
            doc["created_at"] = now_iso()
            doc["updated_at"] = now_iso()
            doc["created_by"] = user["actor"]
            docs.append(doc)

    if not docs:
        return {"inserted": 0, "message": "No data rows found."}
    result = await db.workorders.insert_many(docs)
    return {"inserted": len(result.inserted_ids)}


@api.get("/workorders/import/template.xlsx")
async def import_template(user: dict = Depends(require_roles("admin", "operator"))):
    """Return a ready-to-fill Excel template whose header row matches exactly what
    the flat-format importer expects, plus one illustrative example row."""
    labels = [label for _, label in EXPORT_COLUMNS]
    example = {
        "PELANGGAN": "PT Contoh Sejahtera",
        "ALAMAT": "Jl. Contoh No. 1, Jakarta",
        "JENIS ORDER": "PSB",
        "SA ID": "SA-0001",
        "SI ID": "SI-0001",
        "BW": "100 Mbps",
        "MEDIA AKSES JENIS": "FIBER",
        "HASIL INSTALASI STATUS": "DONE",
        "BOQ JASA": 1000000,
        "BOQ MATERIAL": 500000,
        "BOQ JUMLAH": 1500000,
        "INV STATUS": "OPEN",
        "KETERANGAN": "Baris contoh — hapus sebelum import",
    }
    row = {label: example.get(label, "") for label in labels}
    df = pd.DataFrame([row], columns=labels)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Workorders")
        wb = writer.book
        ws = writer.sheets["Workorders"]
        header_fmt = wb.add_format({"bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1})
        for i, label in enumerate(labels):
            ws.write(0, i, label, header_fmt)
            ws.set_column(i, i, max(14, min(len(label) + 4, 40)))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=workorders_import_template.xlsx"},
    )


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
@api.get("/dashboard/stats")
async def dashboard_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    media_jenis: Optional[str] = None,
    media_perangkat: Optional[str] = None,
    jenis_order: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if media_jenis:
        query["media_jenis"] = media_jenis
    if media_perangkat:
        query["media_perangkat"] = media_perangkat
    if jenis_order:
        query["jenis_order"] = jenis_order
    if date_from or date_to:
        rng: Dict[str, Any] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59"
        # Match either invoice date OR created_at within range
        query["$or"] = [{"inv_tgl": rng}, {"created_at": rng}]

    total = await db.workorders.count_documents(query)

    def status_of(d: dict) -> str:
        for phase in ("aktivasi", "instalasi", "survey"):
            s = (d.get(f"hasil_{phase}_status") or "").strip().lower()
            if s in ("done", "selesai", "completed", "ok"):
                return "completed"
            if s and s not in ("", "-"):
                return "in_progress"
        # If any activity has start but no completion
        for phase in ("aktivasi", "instalasi", "survey"):
            if d.get(f"activity_{phase}_start") and not d.get(f"activity_{phase}_end"):
                return "in_progress"
        return "pending"

    docs = await db.workorders.find(query).to_list(10000)

    by_status = {"completed": 0, "in_progress": 0, "pending": 0}
    by_media: Dict[str, int] = {}
    by_jenis: Dict[str, int] = {}
    by_inv: Dict[str, int] = {}
    revenue_paid = 0.0
    revenue_open = 0.0
    sla_hit = 0
    sla_miss = 0

    for d in docs:
        st = status_of(d)
        by_status[st] = by_status.get(st, 0) + 1

        media = (d.get("media_perangkat") or "UNSPECIFIED").upper()
        by_media[media] = by_media.get(media, 0) + 1

        jo = (d.get("jenis_order") or "UNSPECIFIED").upper()
        by_jenis[jo] = by_jenis.get(jo, 0) + 1

        inv = (d.get("inv_status") or "OPEN").upper() or "OPEN"
        by_inv[inv] = by_inv.get(inv, 0) + 1

        try:
            j = float(d.get("boq_jumlah") or 0)
        except Exception:
            j = 0
        if inv in ("PAID", "LUNAS", "BAYAR"):
            revenue_paid += j
        else:
            revenue_open += j

        # very rough SLA: durasi <= target (numeric extract)
        def _num(s: str) -> Optional[float]:
            if not s:
                return None
            try:
                return float("".join(ch for ch in str(s) if ch.isdigit() or ch == "."))
            except Exception:
                return None

        for phase in ("survey", "instalasi", "aktivasi"):
            dur = _num(d.get(f"sdt_{phase}_durasi", ""))
            tgt = _num(d.get(f"sdt_{phase}_target", ""))
            if dur is not None and tgt is not None and tgt > 0:
                if dur <= tgt:
                    sla_hit += 1
                else:
                    sla_miss += 1

    sla_total = sla_hit + sla_miss
    sla_pct = round((sla_hit / sla_total) * 100, 1) if sla_total else 0.0

    return {
        "total": total,
        "by_status": by_status,
        "by_media": [{"name": k, "value": v} for k, v in sorted(by_media.items(), key=lambda x: -x[1])],
        "by_jenis_order": [{"name": k, "value": v} for k, v in sorted(by_jenis.items(), key=lambda x: -x[1])],
        "by_inv_status": [{"name": k, "value": v} for k, v in sorted(by_inv.items(), key=lambda x: -x[1])],
        "revenue_paid": revenue_paid,
        "revenue_open": revenue_open,
        "sla_pct": sla_pct,
        "sla_hit": sla_hit,
        "sla_miss": sla_miss,
    }


# ------------------------------------------------------------------
# Reports segmented per Jenis Order (PSB / MUTASI / MIGRASI / DISMANTLE / MAINTENANCE)
# ------------------------------------------------------------------
JENIS_ORDER_ALL = ["PSB", "MUTASI", "MIGRASI", "DISMANTLE", "MAINTENANCE"]


def _wo_status(d: dict) -> str:
    """Return one of: completed | in_progress | pending."""
    for phase in ("aktivasi", "instalasi", "survey"):
        s = (d.get(f"hasil_{phase}_status") or "").strip().lower()
        if s in ("done", "selesai", "completed", "ok"):
            return "completed"
        if s and s not in ("", "-"):
            return "in_progress"
    for phase in ("aktivasi", "instalasi", "survey"):
        if d.get(f"activity_{phase}_start") and not d.get(f"activity_{phase}_end"):
            return "in_progress"
    return "pending"


def _wo_sla_score(d: dict) -> tuple:
    """Return (hit_count, miss_count) for a single WO across its phases."""
    def _num(s):
        if not s:
            return None
        try:
            return float("".join(ch for ch in str(s) if ch.isdigit() or ch == "."))
        except Exception:
            return None

    hit = 0
    miss = 0
    for phase in ("survey", "instalasi", "aktivasi"):
        dur = _num(d.get(f"sdt_{phase}_durasi", ""))
        tgt = _num(d.get(f"sdt_{phase}_target", ""))
        if dur is not None and tgt is not None and tgt > 0:
            if dur <= tgt:
                hit += 1
            else:
                miss += 1
    return hit, miss


def _empty_segment(jenis: str) -> dict:
    return {
        "jenis": jenis,
        "count": 0,
        "by_status": {"completed": 0, "in_progress": 0, "pending": 0},
        "by_media": {},
        "revenue_total": 0.0,
        "revenue_paid": 0.0,
        "revenue_open": 0.0,
        "sla_hit": 0,
        "sla_miss": 0,
        "sla_pct": 0.0,
        # MAINTENANCE-only sub-breakdown; kept zero for other jenis
        "cm_count": 0,
        "pm_count": 0,
    }


@api.get("/reports/by-jenis")
async def reports_by_jenis(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    media_jenis: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Segmented report per jenis_order with volume, revenue, and SLA metrics."""
    query: Dict[str, Any] = {}
    if media_jenis:
        query["media_jenis"] = media_jenis
    if date_from or date_to:
        rng: Dict[str, Any] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59"
        query["$or"] = [{"inv_tgl": rng}, {"created_at": rng}]

    docs = await db.workorders.find(query).to_list(20000)

    segments = {j: _empty_segment(j) for j in JENIS_ORDER_ALL}
    other = _empty_segment("OTHER")

    for d in docs:
        jo = (d.get("jenis_order") or "").strip().upper()
        seg = segments.get(jo, other)
        seg["count"] += 1

        st = _wo_status(d)
        seg["by_status"][st] = seg["by_status"].get(st, 0) + 1

        media = (d.get("media_jenis") or "UNSPECIFIED").upper()
        seg["by_media"][media] = seg["by_media"].get(media, 0) + 1

        try:
            j = float(d.get("boq_jumlah") or 0)
        except Exception:
            j = 0.0
        seg["revenue_total"] += j
        inv = (d.get("inv_status") or "").upper()
        if inv in ("PAID", "LUNAS", "BAYAR"):
            seg["revenue_paid"] += j
        else:
            seg["revenue_open"] += j

        hit, miss = _wo_sla_score(d)
        seg["sla_hit"] += hit
        seg["sla_miss"] += miss

        if jo == "MAINTENANCE":
            mt = (d.get("maintenance_type") or "").strip().upper()
            if mt == "CM":
                seg["cm_count"] += 1
            elif mt == "PM":
                seg["pm_count"] += 1

    # Finalize sla_pct + turn by_media into sorted array; build totals
    totals = _empty_segment("ALL")
    result_segments: List[Dict[str, Any]] = []
    for jenis in JENIS_ORDER_ALL:
        seg = segments[jenis]
        tot = seg["sla_hit"] + seg["sla_miss"]
        seg["sla_pct"] = round((seg["sla_hit"] / tot) * 100, 1) if tot else 0.0
        seg["by_media"] = [
            {"name": k, "value": v}
            for k, v in sorted(seg["by_media"].items(), key=lambda x: -x[1])
        ]
        # Accumulate totals (excluding "OTHER")
        totals["count"] += seg["count"]
        for k, v in seg["by_status"].items():
            totals["by_status"][k] = totals["by_status"].get(k, 0) + v
        totals["revenue_total"] += seg["revenue_total"]
        totals["revenue_paid"] += seg["revenue_paid"]
        totals["revenue_open"] += seg["revenue_open"]
        totals["sla_hit"] += seg["sla_hit"]
        totals["sla_miss"] += seg["sla_miss"]
        totals["cm_count"] += seg["cm_count"]
        totals["pm_count"] += seg["pm_count"]
        result_segments.append(seg)

    tot = totals["sla_hit"] + totals["sla_miss"]
    totals["sla_pct"] = round((totals["sla_hit"] / tot) * 100, 1) if tot else 0.0
    totals["by_media"] = []  # not needed for totals card
    totals.pop("jenis", None)

    return {
        "segments": result_segments,
        "totals": totals,
        "filters": {
            "date_from": date_from,
            "date_to": date_to,
            "media_jenis": media_jenis,
        },
    }


# ------------------------------------------------------------------
# Master Perangkat / Asset registry (aggregated from workorders.perangkat_items)
# ------------------------------------------------------------------
def _device_current_status(wo_history: List[dict]) -> str:
    """Derive device current status from most-recent WO in history.

    For MAINTENANCE work orders, the perangkat-item-level `role` refines the
    status: dicabut → DISMANTLED, pengganti/existing → TERPASANG, unspecified
    → MAINTENANCE (device is currently being worked on)."""
    if not wo_history:
        return "UNKNOWN"
    latest = wo_history[0]
    jo = (latest.get("jenis_order") or "").upper()
    role = (latest.get("role") or "").strip().lower()
    if jo == "DISMANTLE":
        return "DISMANTLED"
    if jo == "MAINTENANCE":
        if role == "dicabut":
            return "DISMANTLED"
        if role in ("pengganti", "existing"):
            return "TERPASANG_MAINT"
        return "MAINTENANCE"
    return "TERPASANG_INSTAL"


@api.get("/perangkat/registry")
async def perangkat_registry(
    q: Optional[str] = None,
    jenis_wo: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    user: dict = Depends(get_current_user),
):
    """Aggregate all perangkat_items across workorders. Grouped by nomor_registrasi.

    Query params:
      q          – text search (nomor_registrasi / nama / pelanggan)
      jenis_wo   – filter devices whose LATEST WO has this jenis_order
      status     – filter by current status (TERPASANG / DISMANTLED / MAINTENANCE)
    """
    all_wos = await db.workorders.find(
        {"perangkat_items.0": {"$exists": True}},
        {
            "perangkat_items": 1,
            "pelanggan": 1,
            "sa_id": 1,
            "si_id": 1,
            "jenis_order": 1,
            "wo_jenis_pekerjaan": 1,
            "maintenance_type": 1,
            "media_jenis": 1,
            "hasil_survey_status": 1,
            "hasil_instalasi_status": 1,
            "hasil_aktivasi_status": 1,
            "created_at": 1,
            "updated_at": 1,
        },
    ).to_list(20000)

    # Map nomor_registrasi -> device record
    devices: Dict[str, Dict[str, Any]] = {}
    for wo in all_wos:
        wo_id = str(wo.get("_id"))
        for item in wo.get("perangkat_items") or []:
            nr = (item.get("nomor_registrasi") or "").strip()
            if not nr:
                continue
            nama = (item.get("nama") or "").strip()
            hist_entry = {
                "wo_id": wo_id,
                "pelanggan": wo.get("pelanggan") or "",
                "sa_id": wo.get("sa_id") or "",
                "si_id": wo.get("si_id") or "",
                "jenis_order": wo.get("jenis_order") or "",
                "wo_jenis_pekerjaan": wo.get("wo_jenis_pekerjaan") or "",
                "maintenance_type": wo.get("maintenance_type") or "",
                "media_jenis": wo.get("media_jenis") or "",
                "role": (item.get("role") or "").strip(),
                "created_at": wo.get("created_at") or "",
                "updated_at": wo.get("updated_at") or "",
            }
            if nr not in devices:
                devices[nr] = {
                    "nomor_registrasi": nr,
                    "nama": nama,
                    "wo_history": [hist_entry],
                }
            else:
                devices[nr]["wo_history"].append(hist_entry)
                if nama and not devices[nr]["nama"]:
                    devices[nr]["nama"] = nama

    # Sort each device's history desc by updated_at then created_at
    for dev in devices.values():
        dev["wo_history"].sort(
            key=lambda h: (h.get("updated_at") or "", h.get("created_at") or ""),
            reverse=True,
        )
        latest = dev["wo_history"][0]
        dev["wo_count"] = len(dev["wo_history"])
        dev["current_status"] = _device_current_status(dev["wo_history"])
        dev["current_wo"] = latest
        dev["latest_pelanggan"] = latest.get("pelanggan") or ""
        dev["latest_jenis_order"] = latest.get("jenis_order") or ""
        dev["latest_media"] = latest.get("media_jenis") or ""

    items = list(devices.values())

    # Filters
    if q:
        s = q.lower()
        items = [
            d
            for d in items
            if s in d["nomor_registrasi"].lower()
            or s in (d.get("nama") or "").lower()
            or s in (d.get("latest_pelanggan") or "").lower()
        ]
    if jenis_wo:
        items = [d for d in items if (d.get("latest_jenis_order") or "").upper() == jenis_wo.upper()]
    if status:
        items = [d for d in items if (d.get("current_status") or "").upper() == status.upper()]

    total = len(items)

    # Aggregate KPIs (over the filtered set)
    total_devices = total
    total_wo_links = sum(d["wo_count"] for d in items)
    by_status_kpi: Dict[str, int] = {}
    by_jenis_kpi: Dict[str, int] = {}
    by_media_kpi: Dict[str, int] = {}
    for d in items:
        by_status_kpi[d["current_status"]] = by_status_kpi.get(d["current_status"], 0) + 1
        jo = (d.get("latest_jenis_order") or "UNSPECIFIED").upper()
        by_jenis_kpi[jo] = by_jenis_kpi.get(jo, 0) + 1
        media = (d.get("latest_media") or "UNSPECIFIED").upper()
        by_media_kpi[media] = by_media_kpi.get(media, 0) + 1

    # Sort by wo_count desc, then nomor_registrasi
    items.sort(key=lambda d: (-d["wo_count"], d["nomor_registrasi"]))

    # Pagination
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    page_items = items[start:end]

    return {
        "kpi": {
            "total_devices": total_devices,
            "total_wo_links": total_wo_links,
            "by_status": by_status_kpi,
            "by_jenis_order": [{"name": k, "value": v} for k, v in sorted(by_jenis_kpi.items(), key=lambda x: -x[1])],
            "by_media": [{"name": k, "value": v} for k, v in sorted(by_media_kpi.items(), key=lambda x: -x[1])],
        },
        "items": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@api.get("/perangkat/export/csv")
async def perangkat_export_csv(
    q: Optional[str] = None,
    jenis_wo: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """CSV export of perangkat registry with same filters as /perangkat/registry."""
    data = await perangkat_registry(q=q, jenis_wo=jenis_wo, status=status, page=1, page_size=100000, user=user)
    items = data["items"]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Nomor Registrasi",
        "Nama Perangkat",
        "Status",
        "Jumlah WO",
        "Pelanggan Terakhir",
        "Jenis Order Terakhir",
        "Media Terakhir",
        "SA ID",
        "SI ID",
        "Update Terakhir",
    ])
    for d in items:
        cw = d.get("current_wo") or {}
        writer.writerow([
            d.get("nomor_registrasi") or "",
            d.get("nama") or "",
            d.get("current_status") or "",
            d.get("wo_count") or 0,
            d.get("latest_pelanggan") or "",
            d.get("latest_jenis_order") or "",
            d.get("latest_media") or "",
            cw.get("sa_id") or "",
            cw.get("si_id") or "",
            cw.get("updated_at") or cw.get("created_at") or "",
        ])
    content = buf.getvalue()
    filename = f"perangkat-registry-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ------------------------------------------------------------------
# PDF Export
# ------------------------------------------------------------------
def _brand_paragraph(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def _fmt_rp(n) -> str:
    """Rupiah formatter used in PDF/Excel exports (thousand separator = '.')."""
    try:
        v = float(n or 0)
    except Exception:
        v = 0.0
    return "Rp " + f"{v:,.0f}".replace(",", ".")


@api.get("/workorders/export/pdf")
async def export_pdf_list(
    q: Optional[str] = None,
    inv_status: Optional[str] = None,
    media_jenis: Optional[str] = None,
    jenis_order: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if q:
        query["$or"] = [
            {"pelanggan": {"$regex": q, "$options": "i"}},
            {"sa_id": {"$regex": q, "$options": "i"}},
        ]
    if inv_status:
        query["inv_status"] = inv_status
    if media_jenis:
        query["media_jenis"] = media_jenis
    if jenis_order:
        query["jenis_order"] = jenis_order
    docs = await db.workorders.find(query).sort("created_at", -1).to_list(2000)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#3B82F6")
    styles["Title"].fontSize = 20
    styles["Normal"].fontSize = 8

    elems: List[Any] = []
    elems.append(Paragraph("LA TRACKER · Work Order Report", styles["Title"]))
    elems.append(Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by {user['actor']}", styles["Normal"]))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph(f"Total records: <b>{len(docs)}</b>", styles["Normal"]))
    elems.append(Spacer(1, 10))

    headers = ["Pelanggan", "SA ID", "Jenis", "BW", "Media", "Aktivasi", "Invoice", "No Inv", "Jumlah"]
    data = [headers]
    total_val = 0.0
    for d in docs:
        try:
            j = float(d.get("boq_jumlah") or 0)
        except Exception:
            j = 0
        total_val += j
        data.append([
            (d.get("pelanggan") or "-")[:40],
            d.get("sa_id") or "-",
            d.get("jenis_order") or "-",
            d.get("bw") or "-",
            d.get("media_jenis") or "-",
            d.get("hasil_aktivasi_status") or "-",
            d.get("inv_status") or "-",
            d.get("inv_no") or "-",
            _fmt_rp(j),
        ])
    data.append(["", "", "", "", "", "", "", "TOTAL", _fmt_rp(total_val)])

    table = Table(data, repeatRows=1, colWidths=[65 * mm, 22 * mm, 15 * mm, 20 * mm, 22 * mm, 22 * mm, 22 * mm, 30 * mm, 25 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A0A0C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#3B82F6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#27272A")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F5F5F7")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E0F2FE")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    elems.append(table)
    doc.build(elems)
    buf.seek(0)
    await audit("workorder.export.pdf", user, meta={"count": len(docs)})
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=workorders.pdf"})


@api.get("/workorders/{wo_id}/pdf")
async def export_pdf_one(wo_id: str, request: Request, auth: Optional[str] = Query(None)):
    user = (await _resolve_user_from_token(auth)) if auth else (await get_current_user(request))
    d = await db.workorders.find_one({"_id": ObjectId(wo_id)})
    if not d:
        raise HTTPException(404, "Not found")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#3B82F6")
    styles["Heading2"].textColor = colors.HexColor("#0A0A0C")
    elems: List[Any] = [
        Paragraph("LA TRACKER · Work Order Detail", styles["Title"]),
        Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]),
        Spacer(1, 10),
        Paragraph(f"<b>{d.get('pelanggan') or '-'}</b>", styles["Heading2"]),
        Paragraph(d.get("alamat") or "-", styles["Normal"]),
        Spacer(1, 8),
    ]

    groups = [
        ("Identifikasi", [("Jenis Order", "jenis_order"), ("SA ID", "sa_id"), ("SI ID", "si_id"), ("BW", "bw"), ("Koordinat", None)]),
        ("SPK", [("Survey", "spk_survey_nomor"), ("Instalasi", "spk_instalasi_nomor"), ("Aktivasi", "spk_aktivasi_nomor")]),
        ("Media Akses", [("Jenis", "media_jenis"), ("Perangkat", "media_perangkat")]),
        ("SLA Durasi / Target", [
            ("Survey", None), ("Instalasi", None), ("Aktivasi", None),
        ]),
        ("Invoice", [("No", "inv_no"), ("Tanggal", "inv_tgl"), ("Kirim", "inv_tgl_kirim"), ("Bayar", "inv_tgl_bayar"), ("Status", "inv_status"), ("Jumlah", "boq_jumlah")]),
    ]
    for title, fields in groups:
        rows = [[title, ""]]
        for label, key in fields:
            if title == "Identifikasi" and label == "Koordinat":
                val = f"{d.get('lat') or '-'} , {d.get('lng') or '-'}"
            elif title == "SLA Durasi / Target":
                phase = label.lower()
                val = f"{d.get(f'sdt_{phase}_durasi') or '-'}  /  {d.get(f'sdt_{phase}_target') or '-'}"
            elif key == "boq_jumlah":
                val = _fmt_rp(d.get(key) or 0)
            else:
                val = str(d.get(key) or "-")
            rows.append([label, val])
        t = Table(rows, colWidths=[45 * mm, 130 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3B82F6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("SPAN", (0, 0), (-1, 0)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 8))

    doc.build(elems)
    buf.seek(0)
    await audit("workorder.export.pdf_detail", user, workorder_id=wo_id)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=workorder_{wo_id}.pdf"})


# ------------------------------------------------------------------
# Invoice PDF (formal layout matching PT ALMAR sample)
# ------------------------------------------------------------------
ALMAR_COMPANY = {
    "name": "PT. ALMAR MITRA NIAGA",
    "address_lines": [
        "Jl. Pahlawan Revolusi No.10, RT.2/RW.2,",
        "Pd. Bambu, Kec. Duren Sawit, Kota Jakarta Timur,",
        "Daerah Khusus Ibukota Jakarta 13430",
    ],
}
LINTASARTA_BILL = {
    "name": "PT. APLIKANUSA LINTASARTA",
    "address_lines": [
        "Gedung Menara Thamrin",
        "Jl. MH Thamrin kav. 3 Jakarta Pusat",
        "DKI Jakarta 10250",
    ],
}
BANK_INFO = {
    "acc_no": "736081066",
    "bank_name": "BANK BSI SYARIAH CAB. DUREN SAWIT",
    "recipient": "PT. ALMAR MITRA NIAGA",
}
SIGNATORY = {"name": "Chairuz Zamany", "title": "Direktur"}


def _fmt_rp(n: float) -> str:
    try:
        return "Rp " + f"{int(round(float(n or 0))):,}".replace(",", ".")
    except Exception:
        return "Rp 0"


@api.get("/invoices/{inv_id}/pdf")
async def invoice_pdf(inv_id: str, user: dict = Depends(get_current_user)):
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    inv = await db.invoices.find_one({"_id": oid})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan")

    # Build line items from WO snapshots.
    wo_ids = inv.get("work_order_ids", []) or []
    wos = []
    for wid in wo_ids:
        try:
            w = await db.workorders.find_one({"_id": ObjectId(wid)})
        except Exception:
            w = None
        if w:
            wos.append(w)

    jp = (inv.get("jenis_pekerjaan") or "").upper()

    def _spk_no_for(w: dict) -> str:
        if jp == "SURVEY":
            return w.get("spk_survey_nomor") or ""
        if jp == "INSTALASI":
            return w.get("spk_instalasi_nomor") or ""
        if jp == "AKTIVASI":
            return w.get("spk_aktivasi_nomor") or ""
        if jp in ("DISMANTLE", "MAINTENANCE"):
            return w.get("spk_survey_nomor") or ""
        return ""

    def _desc_for(w: dict) -> str:
        parts = []
        sa = (w.get("sa_id") or "").strip()
        si = (w.get("si_id") or "").strip()
        if sa and si:
            parts.append(f"{sa}/{si}")
        elif sa:
            parts.append(sa)
        elif si:
            parts.append(si)
        pel = (w.get("pelanggan") or "").strip()
        if pel:
            parts.append(pel)
        spk = _spk_no_for(w).strip()
        if spk:
            parts.append(spk)
        return " - ".join(parts) if parts else "-"

    # Aggregate totals.
    subtotal = 0.0
    rows_data = []
    for i, w in enumerate(wos, start=1):
        amount = float(w.get("boq_jumlah") or 0)
        subtotal += amount
        rows_data.append([
            str(i),
            _desc_for(w),
            jp or "-",
            "1",
            _fmt_rp(amount),
            _fmt_rp(amount),
        ])
    ppn = round(subtotal * 0.12)
    grand_total = subtotal + ppn

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    # Compact paragraph styles for dense multi-customer invoices
    from reportlab.lib.styles import ParagraphStyle
    small_style = ParagraphStyle(
        "small", parent=styles["Normal"], fontName="Helvetica",
        fontSize=6.5, leading=8,
    )
    small_bold = ParagraphStyle(
        "small_bold", parent=small_style, fontName="Helvetica-Bold",
    )
    story: list = []

    # Brand color from sample invoice
    BRAND_BLUE = colors.HexColor("#1F4E79")
    BRAND_BLUE_LIGHT = colors.HexColor("#4472C4")

    # -----------------------------------------------------------
    # Header row: Logo (left) | "INVOICE" title (right)
    # -----------------------------------------------------------
    logo_path = os.path.join(os.path.dirname(__file__), "static", "almar_logo.png")
    if os.path.exists(logo_path):
        logo_flow = RLImage(logo_path, width=44 * mm, height=15 * mm)
    else:
        logo_flow = Paragraph("<b>almar networks</b>", small_bold)

    invoice_title = Paragraph(
        '<para align="right"><font size="20" color="#1F4E79"><b>INVOICE</b></font></para>',
        styles["Normal"],
    )
    hdr = Table(
        [[logo_flow, invoice_title]],
        colWidths=[110 * mm, 70 * mm],
    )
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 2.5 * mm))

    # Company block (below logo)
    company_html = '<font color="#1F4E79" size="9"><b>{}</b></font><br/><font size="6.5">{}</font>'.format(
        ALMAR_COMPANY["name"],
        "<br/>".join(ALMAR_COMPANY["address_lines"]),
    )
    story.append(Paragraph(company_html, small_style))
    story.append(Spacer(1, 3 * mm))

    # -----------------------------------------------------------
    # Blue banner row: BILL TO | INVOICE # | DATE
    # -----------------------------------------------------------
    tanggal = inv.get("tanggal") or ""
    inv_no = inv.get("invoice_no") or "-"
    eproc = inv.get("inv_no_eproc") or ""

    banner_style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2.5),
        ("TOPPADDING", (0, 1), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]

    bill_lines = "<b>{}</b><br/>{}".format(
        LINTASARTA_BILL["name"],
        "<br/>".join(LINTASARTA_BILL["address_lines"]),
    )
    # Meta top: BILL TO + INVOICE # / DATE, optionally with EPROC # inline
    # so it sits directly under the INVOICE # value (no big vertical gap).
    if eproc:
        meta_rows = [
            ["BILL TO", "INVOICE #", "DATE"],
            [
                Paragraph(bill_lines, small_style),
                Paragraph(f'<para align="center"><b>{inv_no}</b></para>', small_style),
                Paragraph(f'<para align="center">{tanggal}</para>', small_style),
            ],
            ["", "INVOICE EPROC #", ""],
            [
                "",
                Paragraph(f'<para align="center"><b>{eproc}</b></para>', small_style),
                "",
            ],
        ]
        meta_top = Table(meta_rows, colWidths=[90 * mm, 45 * mm, 45 * mm], hAlign="LEFT")
        meta_style = list(banner_style) + [
            # Blue banner on EPROC header
            ("BACKGROUND", (1, 2), (1, 2), BRAND_BLUE_LIGHT),
            ("TEXTCOLOR", (1, 2), (1, 2), colors.white),
            ("FONTNAME", (1, 2), (1, 2), "Helvetica-Bold"),
            ("FONTSIZE", (1, 2), (1, 2), 7),
            ("ALIGN", (1, 2), (1, 2), "CENTER"),
            # BILL TO cell spans across all 4 rows (address stays visible top)
            ("SPAN", (0, 1), (0, 3)),
            # DATE cell spans across the extra 2 EPROC rows to keep border clean
            ("SPAN", (2, 1), (2, 3)),
        ]
        meta_top.setStyle(TableStyle(meta_style))
        story.append(meta_top)
    else:
        meta_top = Table(
            [
                ["BILL TO", "INVOICE #", "DATE"],
                [
                    Paragraph(bill_lines, small_style),
                    Paragraph(f'<para align="center"><b>{inv_no}</b></para>', small_style),
                    Paragraph(f'<para align="center">{tanggal}</para>', small_style),
                ],
            ],
            colWidths=[90 * mm, 45 * mm, 45 * mm],
            hAlign="LEFT",
        )
        meta_top.setStyle(TableStyle(banner_style))
        story.append(meta_top)

    story.append(Spacer(1, 3 * mm))

    # Line items table
    table_data = [["No", "Description", "SPK", "QTY", "Unit Price (Rp)", "Total Amount (Rp)"]] + (
        rows_data or [["-", "(Tidak ada work order)", "-", "-", "-", "-"]]
    )
    tbl = Table(
        table_data,
        colWidths=[8 * mm, 80 * mm, 22 * mm, 10 * mm, 28 * mm, 32 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 6.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (3, -1), "CENTER"),
        ("ALIGN", (4, 1), (5, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 3 * mm))

    # Totals block — mirror parent items table column widths so amounts
    # line up exactly under the "Total Amount (Rp)" column.
    totals_tbl = Table(
        [
            ["", "", "Subtotal (DPP)", "", "", _fmt_rp(subtotal)],
            ["", "", "PPN 12%", "", "", _fmt_rp(ppn)],
            ["", "", "Grand Total", "", "", _fmt_rp(grand_total)],
        ],
        colWidths=[8 * mm, 80 * mm, 22 * mm, 10 * mm, 28 * mm, 32 * mm],
        hAlign="LEFT",
    )
    totals_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("SPAN", (2, 0), (4, 0)),
        ("SPAN", (2, 1), (4, 1)),
        ("SPAN", (2, 2), (4, 2)),
        ("ALIGN", (2, 0), (5, -1), "RIGHT"),
        ("FONTNAME", (2, 2), (5, 2), "Helvetica-Bold"),
        ("BACKGROUND", (2, 2), (5, 2), colors.HexColor("#e5e7eb")),
        ("LINEABOVE", (2, 2), (5, 2), 0.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(totals_tbl)
    story.append(Spacer(1, 8 * mm))

    # -----------------------------------------------------------
    # Footer: Thank-you note + Bank Details table (left) | Signature (right)
    # -----------------------------------------------------------
    thanks_flow = Paragraph(
        '<para align="left"><b>Thank you for your business!</b></para>', small_style,
    )

    # Bank Details as a bordered table with blue header
    bank_tbl = Table(
        [
            ["BANK DETAILS", ""],
            ["Bank Acc No", BANK_INFO['acc_no']],
            ["Bank Name", BANK_INFO['bank_name']],
            ["Recipient", BANK_INFO['recipient']],
        ],
        colWidths=[15 * mm, 40 * mm],
    )
    bank_tbl.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 6),
        ("FONTSIZE", (0, 1), (-1, -1), 5.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    # Signature (right column) pushed down a couple lines so it sits beside
    # / just below the bank details table.
    sig_para = Paragraph(
        '<para align="right">'
        "<br/><br/><br/><br/><br/><br/><br/><br/>"
        f'<b>{SIGNATORY["name"]}</b><br/>{SIGNATORY["title"]}'
        '</para>',
        small_style,
    )

    # Left column stacks: thank-you + spacer + bank table
    left_col = Table(
        [[thanks_flow], [Spacer(1, 2 * mm)], [bank_tbl]],
        colWidths=[55 * mm],
    )
    left_col.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    footer = Table(
        [[left_col, sig_para]],
        colWidths=[110 * mm, 65 * mm],
    )
    footer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(footer)

    doc.build(story)
    buf.seek(0)
    safe_no = (inv_no or "invoice").replace("/", "-").replace(" ", "_")

    # -----------------------------------------------------------
    # Build lampiran list: Faktur Pajak + all attachments from every
    # work order that belongs to this invoice. Each item is converted
    # to PDF bytes (images wrapped into an A4 page) and merged
    # sequentially after the main invoice.
    # -----------------------------------------------------------
    def _to_pdf_bytes(raw: bytes, ext: str, ctype: str) -> Optional[bytes]:
        ext = (ext or "").lower()
        ctype = (ctype or "").lower()
        if ext == "pdf" or ctype == "application/pdf":
            return raw
        if ext in ("png", "jpg", "jpeg") or ctype.startswith("image/"):
            try:
                img_buf = io.BytesIO()
                img_doc = SimpleDocTemplate(
                    img_buf, pagesize=A4,
                    leftMargin=10 * mm, rightMargin=10 * mm,
                    topMargin=10 * mm, bottomMargin=10 * mm,
                )
                img_reader = RLImage(io.BytesIO(raw))
                max_w, max_h = 190 * mm, 260 * mm
                try:
                    iw = img_reader.imageWidth
                    ih = img_reader.imageHeight
                    ratio = min(max_w / iw, max_h / ih)
                    img_reader.drawWidth = iw * ratio
                    img_reader.drawHeight = ih * ratio
                except Exception:
                    img_reader.drawWidth = max_w
                    img_reader.drawHeight = max_h
                img_doc.build([img_reader])
                return img_buf.getvalue()
            except Exception:
                return None
        return None

    lampiran_pdfs: List[bytes] = []
    log = logging.getLogger("la-tracker")

    def _first_last_pdf(pdf_bytes: bytes) -> bytes:
        """Ambil halaman PERTAMA (Surat Perintah Kerja) & TERAKHIR (Berita Acara) dari SPK."""
        if not _HAS_PYPDF:
            return pdf_bytes
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            n = len(reader.pages)
            if n <= 2:
                return pdf_bytes
            writer = PdfWriter()
            writer.add_page(reader.pages[0])
            writer.add_page(reader.pages[n - 1])
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        except Exception as e:
            log.warning("first/last SPK extract failed: %s", e)
            return pdf_bytes

    def _first_pdf(pdf_bytes: bytes) -> bytes:
        """Ambil HANYA halaman pertama (untuk SPK Maintenance)."""
        if not _HAS_PYPDF:
            return pdf_bytes
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            if len(reader.pages) <= 1:
                return pdf_bytes
            writer = PdfWriter()
            writer.add_page(reader.pages[0])
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        except Exception as e:
            log.warning("first-page SPK extract failed: %s", e)
            return pdf_bytes

    # 1) Faktur Pajak
    fp = inv.get("faktur_pajak_attachment") or {}
    if fp.get("storage_path"):
        try:
            raw, ctype_fp = get_object(fp["storage_path"])
            pdf_bytes = _to_pdf_bytes(raw, fp.get("ext") or "", ctype_fp or fp.get("content_type") or "")
            if pdf_bytes:
                lampiran_pdfs.append(pdf_bytes)
        except Exception as e:
            log.warning("faktur pajak fetch failed for %s: %s", inv_id, e)

    # 2) Bukti Potong
    bp = inv.get("bukti_potong_attachment") or {}
    if bp.get("storage_path"):
        try:
            raw, ctype_bp = get_object(bp["storage_path"])
            pdf_bytes = _to_pdf_bytes(raw, bp.get("ext") or "", ctype_bp or bp.get("content_type") or "")
            if pdf_bytes:
                lampiran_pdfs.append(pdf_bytes)
        except Exception as e:
            log.warning("bukti potong fetch failed for %s: %s", inv_id, e)

    # 3) Attachments from all work orders bound to this invoice
    wo_ids = inv.get("work_order_ids") or []
    if wo_ids:
        try:
            # Peta jenis order per WO (Maintenance -> lampiran SPK cukup 1 halaman)
            wo_jenis: Dict[str, str] = {}
            async for w in db.workorders.find(
                {"_id": {"$in": [ObjectId(x) for x in wo_ids if ObjectId.is_valid(str(x))]}}
            ):
                wo_jenis[str(w["_id"])] = (w.get("jenis_order") or "").strip().upper()
            atts = await db.attachments.find(
                {"workorder_id": {"$in": [str(w) for w in wo_ids]}, "is_deleted": False}
            ).sort("created_at", 1).to_list(500)
            for att in atts:
                try:
                    raw, ctype_a = get_object(att["storage_path"])
                    fname_a = att.get("original_filename") or ""
                    ext_a = (fname_a.rsplit(".", 1)[-1] if "." in fname_a else "").lower()
                    pdf_bytes = _to_pdf_bytes(
                        raw, ext_a, ctype_a or att.get("content_type") or "",
                    )
                    if pdf_bytes:
                        if (att.get("kind") or "").lower() == "spk":
                            jenis = wo_jenis.get(str(att.get("workorder_id")), "")
                            if jenis == "MAINTENANCE":
                                # Maintenance: cukup halaman pertama sesuai file SPK
                                pdf_bytes = _first_pdf(pdf_bytes)
                            else:
                                # Lainnya: halaman pertama (SPK) & terakhir (Berita Acara)
                                pdf_bytes = _first_last_pdf(pdf_bytes)
                        lampiran_pdfs.append(pdf_bytes)
                except Exception as e:
                    log.warning(
                        "wo attachment merge skipped (id=%s): %s",
                        att.get("_id"), e,
                    )
        except Exception as e:
            log.warning("wo attachments query failed for %s: %s", inv_id, e)

    # 4) Merge everything if we have pypdf and any lampiran
    if lampiran_pdfs and _HAS_PYPDF:
        try:
            writer = PdfWriter()
            for page in PdfReader(io.BytesIO(buf.getvalue())).pages:
                writer.add_page(page)
            for pdf_b in lampiran_pdfs:
                try:
                    for page in PdfReader(io.BytesIO(pdf_b)).pages:
                        writer.add_page(page)
                except Exception as e:
                    log.warning("skip lampiran page: %s", e)
            merged = io.BytesIO()
            writer.write(merged)
            merged.seek(0)
            return StreamingResponse(
                merged,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{safe_no}.pdf"'},
            )
        except Exception as e:
            log.warning("invoice pdf merge failed for %s: %s", inv_id, e)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_no}.pdf"'},
    )


# ------------------------------------------------------------------
# Attachments (Object Storage)
# ------------------------------------------------------------------
MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf",
    "csv": "text/csv", "txt": "text/plain", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@api.post("/workorders/{wo_id}/attachments")
async def upload_attachment(wo_id: str, file: UploadFile = File(...), kind: str = Form("general"), user: dict = Depends(require_roles("admin", "operator"))):
    wo = await db.workorders.find_one({"_id": ObjectId(wo_id)})
    if not wo:
        raise HTTPException(404, "Work order not found")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20MB)")
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin").lower()
    # Only PDF attachments are allowed on work orders
    if ext != "pdf" and (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(400, "Hanya file PDF yang diperbolehkan")
    ctype = "application/pdf"
    kind = (kind or "general").strip().lower()
    if kind not in ("general", "spk"):
        kind = "general"
    # Only a single SPK document is allowed per work order.
    if kind == "spk":
        existing_spk = await db.attachments.count_documents(
            {"workorder_id": wo_id, "kind": "spk", "is_deleted": False}
        )
        if existing_spk >= 1:
            raise HTTPException(400, "SPK sudah ada. Hapus file SPK yang lama sebelum upload baru.")
    file_uuid = str(uuid.uuid4())
    path = f"{APP_NAME}/workorders/{wo_id}/{file_uuid}.{ext}"
    result = put_object(path, data, ctype)
    doc = {
        "workorder_id": wo_id,
        "kind": kind,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "uploaded_by": user["actor"],
        "created_at": now_iso(),
        "is_deleted": False,
    }
    res = await db.attachments.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    await audit("attachment.upload", user, workorder_id=wo_id, meta={"filename": file.filename, "size": doc["size"], "kind": kind})
    return doc


@api.get("/workorders/{wo_id}/attachments")
async def list_attachments(wo_id: str, user: dict = Depends(get_current_user)):
    docs = await db.attachments.find({"workorder_id": wo_id, "is_deleted": False}).sort("created_at", -1).to_list(200)
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d.setdefault("kind", "general")
    return docs


@api.get("/attachments/{att_id}/download")
async def download_attachment(att_id: str, request: Request, auth: Optional[str] = Query(None)):
    # Support ?auth= for <img src>; fallback to normal cookie/bearer auth
    _ = (await _resolve_user_from_token(auth)) if auth else (await get_current_user(request))
    att = await db.attachments.find_one({"_id": ObjectId(att_id), "is_deleted": False})
    if not att:
        raise HTTPException(404, "Attachment not found")
    data, ctype = get_object(att["storage_path"])
    return Response(content=data, media_type=att.get("content_type") or ctype,
                    headers={"Content-Disposition": f'inline; filename="{att.get("original_filename", "file")}"'})


@api.delete("/attachments/{att_id}")
async def delete_attachment(att_id: str, user: dict = Depends(require_roles("admin", "operator"))):
    att = await db.attachments.find_one({"_id": ObjectId(att_id)})
    if not att:
        raise HTTPException(404, "Not found")
    await db.attachments.update_one({"_id": ObjectId(att_id)}, {"$set": {"is_deleted": True, "deleted_at": now_iso()}})
    await audit("attachment.delete", user, workorder_id=att.get("workorder_id"), meta={"filename": att.get("original_filename")})
    return {"ok": True}


# ------------------------------------------------------------------
# Invoices (Consolidated per Pelanggan + Jenis Pekerjaan)
# ------------------------------------------------------------------
INV_ACTIVITY_TYPES = {"SURVEY", "INSTALASI", "AKTIVASI", "DISMANTLE", "MAINTENANCE", "NON_MAINTENANCE"}


BILLABLE_STATUS = {"OK", "BATAL", "DONE", "SELESAI", "COMPLETED"}


def _wo_status_for_activity(wo: dict, jp: str) -> str:
    """Return the relevant hasil_*_status string for the given activity/jenis."""
    jp = (jp or "").upper()
    if jp in ("DISMANTLE", "MAINTENANCE"):
        return (wo.get("hasil_survey_status") or "").strip().upper()
    if jp == "SURVEY":
        return (wo.get("hasil_survey_status") or "").strip().upper()
    if jp == "INSTALASI":
        return (wo.get("hasil_instalasi_status") or "").strip().upper()
    if jp == "AKTIVASI":
        return (wo.get("hasil_aktivasi_status") or "").strip().upper()
    if jp == "NON_MAINTENANCE":
        # For the aggregated bucket, pick the "most advanced" phase status that is
        # billable, else the aktivasi/instalasi/survey in that priority.
        for f in ("hasil_aktivasi_status", "hasil_instalasi_status", "hasil_survey_status"):
            s = (wo.get(f) or "").strip().upper()
            if s in BILLABLE_STATUS:
                return s
        # No billable status — return whatever is present (or "" if none)
        for f in ("hasil_aktivasi_status", "hasil_instalasi_status", "hasil_survey_status"):
            s = (wo.get(f) or "").strip().upper()
            if s:
                return s
        return ""
    return ""


def _wo_ready_for_billing(wo: dict, jp: str) -> bool:
    """A WO is eligible for BoQ/invoice only when its relevant hasil_*_status is OK or BATAL."""
    jp = (jp or "").upper()
    if jp == "NON_MAINTENANCE":
        # ANY phase's status being billable qualifies the WO for the aggregated invoice.
        for f in ("hasil_survey_status", "hasil_instalasi_status", "hasil_aktivasi_status"):
            s = (wo.get(f) or "").strip().upper()
            if s in BILLABLE_STATUS:
                return True
        return False
    return _wo_status_for_activity(wo, jp) in BILLABLE_STATUS


def _wo_matches_activity(wo: dict, jenis_pekerjaan: str) -> bool:
    """Return True if the work order applies to and is ready-for-billing on the given activity."""
    jp = (jenis_pekerjaan or "").upper()
    if jp == "NON_MAINTENANCE":
        if (wo.get("jenis_order") or "").upper() not in ("PSB", "MUTASI", "MIGRASI", "DISMANTLE"):
            return False
        return _wo_ready_for_billing(wo, jp)
    # 1. Activity/jenis applicability
    if jp == "DISMANTLE":
        if (wo.get("jenis_order") or "").upper() != "DISMANTLE":
            return False
    elif jp == "MAINTENANCE":
        if (wo.get("jenis_order") or "").upper() != "MAINTENANCE":
            return False
    elif jp in ("SURVEY", "INSTALASI", "AKTIVASI"):
        # PSB / MUTASI / MIGRASI only — MAINTENANCE/DISMANTLE never invoiced via SURVEY/INSTALASI/AKTIVASI channels
        if (wo.get("jenis_order") or "").upper() in ("DISMANTLE", "MAINTENANCE"):
            return False
    # 2. Must be ready for billing (status OK or BATAL)
    return _wo_ready_for_billing(wo, jp)


def compute_invoice_status(inv: dict) -> str:
    """Automatically derive invoice status from its data.
    Fields used:
      - tgl_bayar   = Tanggal Jatuh Tempo (due date, YYYY-MM-DD)
      - tgl_dibayar = Tanggal Dibayar (actual payment date; empty = belum dibayar)
      - tgl_kirim   = Tanggal Kirim/Submit
      - faktur_pajak_attachment / bukti_potong_attachment / inv_no_eproc = kelengkapan dokumen
    Rules:
      PAID    -> sudah dibayar (tgl_dibayar terisi) dan <= jatuh tempo
      OVERDUE -> dibayar melewati jatuh tempo, ATAU belum dibayar tapi sudah lewat jatuh tempo
      OPEN    -> Faktur / Bukti Potong / No eProc belum lengkap
      SENT    -> dokumen lengkap dan sudah ada Tanggal Kirim
    """
    due = (inv.get("tgl_bayar") or "").strip()
    paid = (inv.get("tgl_dibayar") or "").strip()
    sent = (inv.get("tgl_kirim") or "").strip()
    today = datetime.now(timezone.utc).date().isoformat()

    if paid:
        # ISO date strings compare lexicographically
        if due and paid > due:
            return "OVERDUE"
        return "PAID"
    # belum dibayar
    if due and today > due:
        return "OVERDUE"
    has_faktur = bool(inv.get("faktur_pajak_attachment"))
    has_bupot = bool(inv.get("bukti_potong_attachment"))
    has_eproc = bool((inv.get("inv_no_eproc") or "").strip())
    if not (has_faktur and has_bupot and has_eproc):
        return "OPEN"
    if sent:
        return "SENT"
    return "OPEN"


class InvoiceIn(BaseModel):
    pelanggans: List[str] = []
    jenis_pekerjaan: str
    invoice_no: Optional[str] = ""
    inv_no_eproc: Optional[str] = ""
    faktur_pajak_no: Optional[str] = ""
    tanggal: Optional[str] = ""
    tgl_kirim: Optional[str] = ""
    tgl_bayar: Optional[str] = ""
    tgl_dibayar: Optional[str] = ""
    status: Optional[str] = "OPEN"
    keterangan: Optional[str] = ""
    work_order_ids: List[str] = []


def _invoice_totals(work_orders: List[dict]) -> Dict[str, float]:
    tj = sum(float(w.get("boq_jasa") or 0) for w in work_orders)
    tm = sum(float(w.get("boq_material") or 0) for w in work_orders)
    return {"total_jasa": tj, "total_material": tm, "grand_total": tj + tm}


async def _load_selected_wos(ids: List[str]) -> List[dict]:
    out: List[dict] = []
    for wid in ids:
        try:
            d = await db.workorders.find_one({"_id": ObjectId(wid)})
            if d:
                d["id"] = str(d.pop("_id"))
                out.append(d)
        except Exception:
            continue
    return out


@api.get("/invoices/customers")
async def invoice_customers(
    jenis_pekerjaan: Optional[str] = None,
    exclude_invoice_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Return unique pelanggan (with SA IDs & WO count) for the invoice picker.
    Only WOs that are NOT yet in any invoice are counted.
    A `diagnostic` field explains why some WOs are excluded."""
    if jenis_pekerjaan:
        jp = jenis_pekerjaan.upper()
        if jp not in INV_ACTIVITY_TYPES:
            raise HTTPException(400, "Jenis pekerjaan tidak valid")
        # Collect all WO ids already in any invoice (except the one being edited).
        inv_query: Dict[str, Any] = {}
        if exclude_invoice_id:
            try:
                inv_query["_id"] = {"$ne": ObjectId(exclude_invoice_id)}
            except Exception:
                pass
        already_billed: set = set()
        async for iv in db.invoices.find(inv_query, {"work_order_ids": 1}):
            for wid in iv.get("work_order_ids", []):
                already_billed.add(str(wid))

        docs = await db.workorders.find(
            {},
            {"pelanggan": 1, "sa_id": 1, "jenis_order": 1,
             "hasil_survey_status": 1, "hasil_instalasi_status": 1, "hasil_aktivasi_status": 1},
        ).to_list(10000)
        by_pel: Dict[str, Dict[str, Any]] = {}
        # Diagnostics for empty-state UX
        missing_pelanggan = 0
        not_ready_status = 0
        already_billed_count = 0
        for d in docs:
            # Applicability check (jenis_order matches picker category)
            jo = (d.get("jenis_order") or "").upper()
            if jp == "NON_MAINTENANCE":
                if jo not in ("PSB", "MUTASI", "MIGRASI", "DISMANTLE"):
                    continue
            elif jp == "MAINTENANCE":
                if jo != "MAINTENANCE":
                    continue
            elif jp == "DISMANTLE":
                if jo != "DISMANTLE":
                    continue
            elif jp in ("SURVEY", "INSTALASI", "AKTIVASI"):
                if jo in ("DISMANTLE", "MAINTENANCE"):
                    continue
            # Ready-for-billing gate
            if not _wo_ready_for_billing(d, jp):
                not_ready_status += 1
                continue
            # Skip WOs that are already in an invoice
            if str(d["_id"]) in already_billed:
                already_billed_count += 1
                continue
            p = (d.get("pelanggan") or "").strip()
            if not p:
                missing_pelanggan += 1
                continue
            entry = by_pel.setdefault(p, {"pelanggan": p, "wo_count": 0, "sa_ids": set()})
            entry["wo_count"] += 1
            sa = (d.get("sa_id") or "").strip()
            if sa:
                entry["sa_ids"].add(sa)
        items = [
            {"pelanggan": r["pelanggan"], "wo_count": r["wo_count"], "sa_ids": sorted(r["sa_ids"])}
            for r in sorted(by_pel.values(), key=lambda x: x["pelanggan"].lower())
        ]
        return {
            "items": items,
            "diagnostic": {
                "missing_pelanggan": missing_pelanggan,
                "not_ready_status": not_ready_status,
                "already_billed": already_billed_count,
            },
        }

    # No jenis filter: keep legacy behaviour (all pelanggan, plain list — for CSV, etc.)
    pipeline = [
        {"$match": {"pelanggan": {"$exists": True, "$ne": ""}}},
        {"$group": {
            "_id": "$pelanggan",
            "wo_count": {"$sum": 1},
            "sa_ids": {"$addToSet": "$sa_id"},
        }},
        {"$sort": {"_id": 1}},
    ]
    rows = await db.workorders.aggregate(pipeline).to_list(2000)
    return [
        {"pelanggan": r["_id"], "wo_count": r["wo_count"], "sa_ids": [x for x in r.get("sa_ids", []) if x]}
        for r in rows
    ]


@api.get("/invoices/candidates")
async def invoice_candidates(
    jenis_pekerjaan: str,
    pelanggans: Optional[str] = None,  # comma-separated list; if empty, no filter (all pelanggan)
    pelanggan: Optional[str] = None,   # backward compat: single pelanggan
    exclude_invoice_id: Optional[str] = None,  # when editing, don't exclude own WOs
    user: dict = Depends(get_current_user),
):
    """List work orders eligible to be included in a new invoice for the given jenis pekerjaan.
    Optionally filter to a subset of pelanggan via ?pelanggans=A,B,C.
    Work orders that are already included in another invoice are excluded."""
    jp = jenis_pekerjaan.upper()
    if jp not in INV_ACTIVITY_TYPES:
        raise HTTPException(400, "Jenis pekerjaan tidak valid")

    query: Dict[str, Any] = {}
    p_list: List[str] = []
    if pelanggans:
        p_list = [p.strip() for p in pelanggans.split(",") if p.strip()]
    elif pelanggan:
        p_list = [pelanggan]
    if p_list:
        query["pelanggan"] = {"$in": p_list}

    docs = await db.workorders.find(query).sort("created_at", -1).to_list(2000)

    # Collect ALL WO ids already in any invoice (except the one being edited).
    inv_query: Dict[str, Any] = {}
    if exclude_invoice_id:
        try:
            inv_query["_id"] = {"$ne": ObjectId(exclude_invoice_id)}
        except Exception:
            pass
    already_billed_ids: set = set()
    async for iv in db.invoices.find(inv_query, {"work_order_ids": 1}):
        for wid in iv.get("work_order_ids", []):
            already_billed_ids.add(str(wid))

    out = []
    eligible_ids: List[str] = []
    for d in docs:
        if not _wo_matches_activity(d, jp):
            continue
        wid = str(d["_id"])
        # Hide WOs already in another invoice — the whole point of "only show
        # pelanggan yang belum dibuatkan invoice" per user's request.
        if wid in already_billed_ids:
            continue
        eligible_ids.append(wid)
        out.append({
            "id": wid,
            "pelanggan": d.get("pelanggan", ""),
            "sa_id": d.get("sa_id", ""),
            "si_id": d.get("si_id", ""),
            "jenis_order": d.get("jenis_order", ""),
            "bw": d.get("bw", ""),
            "media_jenis": d.get("media_jenis", ""),
            "boq_jasa": d.get("boq_jasa", 0),
            "boq_material": d.get("boq_material", 0),
            "boq_jumlah": d.get("boq_jumlah", 0),
            "activity_end": d.get(f"activity_{jp.lower()}_end") if jp in ("SURVEY", "INSTALASI", "AKTIVASI") else d.get("activity_instalasi_end"),
            "has_attachment": False,
        })
    if eligible_ids:
        counts = await db.attachments.aggregate([
            {"$match": {"workorder_id": {"$in": eligible_ids}, "is_deleted": False}},
            {"$group": {"_id": "$workorder_id", "n": {"$sum": 1}}},
        ]).to_list(len(eligible_ids))
        have = {c["_id"] for c in counts if c.get("n", 0) > 0}
        for row in out:
            row["has_attachment"] = row["id"] in have
    return out


@api.get("/invoices")
async def list_invoices(
    pelanggan: Optional[str] = None,
    jenis_pekerjaan: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(500, ge=1, le=2000),
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if pelanggan:
        # Search either legacy `pelanggan` field or the new `pelanggans` array
        query["$or"] = [
            {"pelanggan": {"$regex": pelanggan, "$options": "i"}},
            {"pelanggans": {"$regex": pelanggan, "$options": "i"}},
        ]
    if jenis_pekerjaan:
        query["jenis_pekerjaan"] = jenis_pekerjaan.upper()
    if status:
        query["status"] = status.upper()
    docs = await db.invoices.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
        # Backward compat: expose `pelanggans` list even for legacy single-pelanggan invoices
        if not d.get("pelanggans"):
            d["pelanggans"] = [d.get("pelanggan")] if d.get("pelanggan") else []
        # Status is always auto-derived (recompute to reflect time-based OVERDUE)
        d["status"] = compute_invoice_status(d)
    return docs


INVOICE_EXPORT_COLUMNS: List[tuple] = [
    ("invoice_no", "NO INVOICE"),
    ("inv_no_eproc", "NO EPROC"),
    ("faktur_pajak_no", "NO FAKTUR PAJAK"),
    ("pelanggan_display", "PELANGGAN"),
    ("jenis_pekerjaan", "JENIS PEKERJAAN"),
    ("tanggal", "TANGGAL"),
    ("tgl_kirim", "TGL KIRIM"),
    ("tgl_bayar", "TGL BAYAR"),
    ("status", "STATUS"),
    ("wo_count", "JUMLAH WO"),
    ("total_jasa", "TOTAL JASA"),
    ("total_material", "TOTAL MATERIAL"),
    ("grand_total", "GRAND TOTAL"),
    ("keterangan", "KETERANGAN"),
    ("created_at", "DIBUAT"),
]


@api.get("/invoices/export/xlsx")
async def export_invoices(
    pelanggan: Optional[str] = None,
    jenis_pekerjaan: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Export invoices (honoring the same filters as the list view) to Excel."""
    query: Dict[str, Any] = {}
    if pelanggan:
        query["$or"] = [
            {"pelanggan": {"$regex": pelanggan, "$options": "i"}},
            {"pelanggans": {"$regex": pelanggan, "$options": "i"}},
        ]
    if jenis_pekerjaan:
        query["jenis_pekerjaan"] = jenis_pekerjaan.upper()
    if status:
        query["status"] = status.upper()

    docs = await db.invoices.find(query).sort("created_at", -1).to_list(5000)
    rows = []
    for d in docs:
        pelanggans = d.get("pelanggans") or ([d.get("pelanggan")] if d.get("pelanggan") else [])
        row = {
            "invoice_no": d.get("invoice_no", ""),
            "inv_no_eproc": d.get("inv_no_eproc", ""),
            "faktur_pajak_no": d.get("faktur_pajak_no", ""),
            "pelanggan_display": ", ".join([p for p in pelanggans if p]),
            "jenis_pekerjaan": d.get("jenis_pekerjaan", ""),
            "tanggal": d.get("tanggal", ""),
            "tgl_kirim": d.get("tgl_kirim", ""),
            "tgl_bayar": d.get("tgl_bayar", ""),
            "status": d.get("status", ""),
            "wo_count": len(d.get("work_order_ids", []) or []),
            "total_jasa": float(d.get("total_jasa") or 0),
            "total_material": float(d.get("total_material") or 0),
            "grand_total": float(d.get("grand_total") or 0),
            "keterangan": d.get("keterangan", ""),
            "created_at": (d.get("created_at") or "")[:10],
        }
        rows.append({label: row.get(field, "") for field, label in INVOICE_EXPORT_COLUMNS})

    labels = [label for _, label in INVOICE_EXPORT_COLUMNS]
    df = pd.DataFrame(rows, columns=labels)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Invoices")
        wb = writer.book
        ws = writer.sheets["Invoices"]
        header_fmt = wb.add_format({"bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1})
        rp_fmt = wb.add_format({"num_format": '"Rp" #,##0'})
        money_labels = {"TOTAL JASA", "TOTAL MATERIAL", "GRAND TOTAL"}
        for i, label in enumerate(labels):
            ws.write(0, i, label, header_fmt)
            if label in money_labels:
                ws.set_column(i, i, 18, rp_fmt)
            else:
                ws.set_column(i, i, max(14, min(len(label) + 4, 40)))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=invoices.xlsx"},
    )


@api.get("/invoices/{inv_id}")
async def get_invoice(inv_id: str, user: dict = Depends(get_current_user)):
    try:
        d = await db.invoices.find_one({"_id": ObjectId(inv_id)})
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not d:
        raise HTTPException(404, "Not found")
    d["id"] = str(d.pop("_id"))
    if not d.get("pelanggans"):
        d["pelanggans"] = [d.get("pelanggan")] if d.get("pelanggan") else []
    d["status"] = compute_invoice_status(d)
    return d


async def _ensure_wos_have_attachments(wos: List[dict]):
    """Setiap work order pada invoice wajib punya minimal 1 attachment PDF.

    Attachment ini nantinya akan digabung otomatis sebagai lampiran PDF
    invoice. Kalau ada WO yang belum punya attachment, batalkan operasi
    dengan pesan yang menyebutkan WO mana saja yang perlu upload dokumen.
    """
    if not wos:
        return
    wo_ids = [str(w["id"]) for w in wos if w.get("id")]
    if not wo_ids:
        return
    counts = await db.attachments.aggregate([
        {"$match": {"workorder_id": {"$in": wo_ids}, "is_deleted": False}},
        {"$group": {"_id": "$workorder_id", "n": {"$sum": 1}}},
    ]).to_list(1000)
    have = {c["_id"] for c in counts if c.get("n", 0) > 0}
    missing = []
    for w in wos:
        wid = str(w.get("id") or "")
        if wid and wid not in have:
            label = w.get("sa_id") or w.get("pelanggan") or wid
            missing.append(label)
    if missing:
        preview = ", ".join(missing[:5])
        more = "" if len(missing) <= 5 else f" (+{len(missing) - 5} lainnya)"
        raise HTTPException(
            400,
            f"Setiap pekerjaan wajib upload attachment PDF sebagai lampiran invoice. "
            f"Belum ada attachment untuk: {preview}{more}",
        )


@api.post("/invoices")
async def create_invoice(
    payload: InvoiceIn,
    user: dict = Depends(require_roles("admin", "operator")),
):
    jp = payload.jenis_pekerjaan.upper()
    if jp not in INV_ACTIVITY_TYPES:
        raise HTTPException(400, "Jenis pekerjaan tidak valid")
    if not payload.pelanggans:
        raise HTTPException(400, "Pilih minimal 1 pelanggan")
    wos = await _load_selected_wos(payload.work_order_ids)
    # Wajib: setiap work order pada invoice harus punya minimal 1 attachment PDF
    await _ensure_wos_have_attachments(wos)
    totals = _invoice_totals(wos)
    pelanggans = [p for p in payload.pelanggans if p]
    invoice_no = (payload.invoice_no or "").strip()
    if not invoice_no:
        raise HTTPException(400, "No Invoice wajib diisi")
    # Nilai invoice tidak boleh 0 atau kosong
    grand = float(totals.get("grand_total") or 0)
    if grand <= 0:
        raise HTTPException(400, "Nilai invoice tidak boleh 0 atau kosong — pastikan WO yang dipilih memiliki nilai BoQ")
    doc = {
        "pelanggans": pelanggans,
        # Legacy display field: comma-joined when multi, single when 1
        "pelanggan": pelanggans[0] if len(pelanggans) == 1 else f"Multiple ({len(pelanggans)}): {', '.join(pelanggans)[:80]}",
        "jenis_pekerjaan": jp,
        "invoice_no": invoice_no,
        "inv_no_eproc": (payload.inv_no_eproc or "").strip(),
        "faktur_pajak_no": (payload.faktur_pajak_no or "").strip(),
        "tanggal": payload.tanggal or "",
        "tgl_kirim": payload.tgl_kirim or "",
        "tgl_bayar": payload.tgl_bayar or "",
        "tgl_dibayar": payload.tgl_dibayar or "",
        "keterangan": payload.keterangan or "",
        "work_order_ids": [w["id"] for w in wos],
        "work_orders_snapshot": [
            {
                "id": w["id"],
                "pelanggan": w.get("pelanggan", ""),
                "sa_id": w.get("sa_id", ""),
                "jenis_order": w.get("jenis_order", ""),
                "boq_jasa": w.get("boq_jasa", 0),
                "boq_material": w.get("boq_material", 0),
                "boq_jumlah": w.get("boq_jumlah", 0),
            }
            for w in wos
        ],
        **totals,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "created_by": user.get("actor"),
    }
    doc["status"] = compute_invoice_status(doc)
    res = await db.invoices.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    await audit("invoice.create", user, target=doc["id"], meta={"pelanggans": pelanggans, "jp": jp})
    return doc


@api.put("/invoices/{inv_id}")
async def update_invoice(
    inv_id: str,
    payload: InvoiceIn,
    user: dict = Depends(require_roles("admin", "operator")),
):
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    existing = await db.invoices.find_one({"_id": oid})
    if not existing:
        raise HTTPException(404, "Not found")
    jp = payload.jenis_pekerjaan.upper()
    if jp not in INV_ACTIVITY_TYPES:
        raise HTTPException(400, "Jenis pekerjaan tidak valid")
    if not payload.pelanggans:
        raise HTTPException(400, "Pilih minimal 1 pelanggan")
    wos = await _load_selected_wos(payload.work_order_ids)
    # Wajib: setiap work order pada invoice harus punya minimal 1 attachment PDF
    await _ensure_wos_have_attachments(wos)
    totals = _invoice_totals(wos)
    pelanggans = [p for p in payload.pelanggans if p]
    invoice_no = (payload.invoice_no or "").strip()
    if not invoice_no:
        raise HTTPException(400, "No Invoice wajib diisi")
    grand = float(totals.get("grand_total") or 0)
    if grand <= 0:
        raise HTTPException(400, "Nilai invoice tidak boleh 0 atau kosong — pastikan WO yang dipilih memiliki nilai BoQ")
    upd = {
        "pelanggans": pelanggans,
        "pelanggan": pelanggans[0] if len(pelanggans) == 1 else f"Multiple ({len(pelanggans)}): {', '.join(pelanggans)[:80]}",
        "jenis_pekerjaan": jp,
        "invoice_no": invoice_no,
        "inv_no_eproc": (payload.inv_no_eproc or "").strip(),
        "faktur_pajak_no": (payload.faktur_pajak_no or "").strip(),
        "tanggal": payload.tanggal or "",
        "tgl_kirim": payload.tgl_kirim or "",
        "tgl_bayar": payload.tgl_bayar or "",
        "tgl_dibayar": payload.tgl_dibayar or "",
        "keterangan": payload.keterangan or "",
        "work_order_ids": [w["id"] for w in wos],
        "work_orders_snapshot": [
            {
                "id": w["id"],
                "pelanggan": w.get("pelanggan", ""),
                "sa_id": w.get("sa_id", ""),
                "jenis_order": w.get("jenis_order", ""),
                "boq_jasa": w.get("boq_jasa", 0),
                "boq_material": w.get("boq_material", 0),
                "boq_jumlah": w.get("boq_jumlah", 0),
            }
            for w in wos
        ],
        **totals,
        "updated_at": now_iso(),
    }
    # Auto-compute status from the merged data (keep existing faktur/bupot attachments).
    upd["status"] = compute_invoice_status({**existing, **upd})
    await db.invoices.update_one({"_id": oid}, {"$set": upd})
    await audit("invoice.update", user, target=inv_id, meta={"pelanggans": pelanggans, "jp": jp})
    upd["id"] = inv_id
    return upd


@api.delete("/invoices/{inv_id}")
async def delete_invoice(
    inv_id: str,
    user: dict = Depends(require_roles("admin")),
):
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    res = await db.invoices.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found")
    await audit("invoice.delete", user, target=inv_id)
    return {"ok": True}


# ------------------------------------------------------------------
# Invoice - Faktur Pajak (upload PDF/image + store nomor)
# ------------------------------------------------------------------
FP_ALLOWED_EXT = {"pdf"}


@api.post("/invoices/{inv_id}/faktur-pajak")
async def upload_faktur_pajak(
    inv_id: str,
    file: UploadFile = File(...),
    faktur_pajak_no: Optional[str] = None,
    user: dict = Depends(require_roles("admin", "operator")),
):
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    inv = await db.invoices.find_one({"_id": oid})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File terlalu besar (maks 20MB)")
    fname = file.filename or "faktur_pajak"
    ext = (fname.rsplit(".", 1)[-1] if "." in fname else "bin").lower()
    if ext not in FP_ALLOWED_EXT and (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(400, "Hanya file PDF yang diperbolehkan")
    ctype = "application/pdf"
    file_uuid = str(uuid.uuid4())
    path = f"{APP_NAME}/invoices/{inv_id}/faktur_pajak_{file_uuid}.pdf"
    result = put_object(path, data, ctype)
    fp_attachment = {
        "storage_path": result["path"],
        "original_filename": fname,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "ext": "pdf",
        "uploaded_by": user["actor"],
        "uploaded_at": now_iso(),
    }
    update_set: Dict[str, Any] = {
        "faktur_pajak_attachment": fp_attachment,
        "updated_at": now_iso(),
    }
    if faktur_pajak_no is not None:
        update_set["faktur_pajak_no"] = (faktur_pajak_no or "").strip()
    update_set["status"] = compute_invoice_status({**inv, **update_set})
    await db.invoices.update_one({"_id": oid}, {"$set": update_set})
    await audit(
        "invoice.faktur_pajak.upload", user, target=inv_id,
        meta={"filename": fname, "size": fp_attachment["size"], "no": update_set.get("faktur_pajak_no")},
    )
    return {
        "ok": True,
        "faktur_pajak_attachment": fp_attachment,
        "faktur_pajak_no": update_set.get("faktur_pajak_no", inv.get("faktur_pajak_no", "")),
    }


@api.get("/invoices/{inv_id}/faktur-pajak/download")
async def download_faktur_pajak(inv_id: str, request: Request, auth: Optional[str] = Query(None)):
    # Support ?auth= for inline preview; fallback to normal auth headers
    _ = (await _resolve_user_from_token(auth)) if auth else (await get_current_user(request))
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    inv = await db.invoices.find_one({"_id": oid})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan")
    fp = inv.get("faktur_pajak_attachment") or {}
    if not fp.get("storage_path"):
        raise HTTPException(404, "Faktur pajak belum diupload")
    data, ctype = get_object(fp["storage_path"])
    return Response(
        content=data,
        media_type=fp.get("content_type") or ctype,
        headers={"Content-Disposition": f'inline; filename="{fp.get("original_filename", "faktur_pajak")}"'},
    )


@api.delete("/invoices/{inv_id}/faktur-pajak")
async def delete_faktur_pajak(
    inv_id: str,
    user: dict = Depends(require_roles("admin", "operator")),
):
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    inv = await db.invoices.find_one({"_id": oid})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan")
    merged = {k: v for k, v in inv.items() if k != "faktur_pajak_attachment"}
    await db.invoices.update_one(
        {"_id": oid},
        {"$unset": {"faktur_pajak_attachment": ""}, "$set": {"updated_at": now_iso(), "status": compute_invoice_status(merged)}},
    )
    await audit("invoice.faktur_pajak.delete", user, target=inv_id)
    return {"ok": True}


# ------------------------------------------------------------------
# Invoice - Bukti Potong (upload PDF/image lampiran)
# ------------------------------------------------------------------
BP_ALLOWED_EXT = {"pdf"}


@api.post("/invoices/{inv_id}/bukti-potong")
async def upload_bukti_potong(
    inv_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("admin", "operator")),
):
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    inv = await db.invoices.find_one({"_id": oid})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File terlalu besar (maks 20MB)")
    fname = file.filename or "bukti_potong"
    ext = (fname.rsplit(".", 1)[-1] if "." in fname else "bin").lower()
    if ext not in BP_ALLOWED_EXT and (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(400, "Hanya file PDF yang diperbolehkan")
    ctype = "application/pdf"
    file_uuid = str(uuid.uuid4())
    path = f"{APP_NAME}/invoices/{inv_id}/bukti_potong_{file_uuid}.pdf"
    result = put_object(path, data, ctype)
    bp_attachment = {
        "storage_path": result["path"],
        "original_filename": fname,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "ext": "pdf",
        "uploaded_by": user["actor"],
        "uploaded_at": now_iso(),
    }
    await db.invoices.update_one(
        {"_id": oid},
        {"$set": {"bukti_potong_attachment": bp_attachment, "updated_at": now_iso(), "status": compute_invoice_status({**inv, "bukti_potong_attachment": bp_attachment})}},
    )
    await audit(
        "invoice.bukti_potong.upload", user, target=inv_id,
        meta={"filename": fname, "size": bp_attachment["size"]},
    )
    return {"ok": True, "bukti_potong_attachment": bp_attachment}


@api.get("/invoices/{inv_id}/bukti-potong/download")
async def download_bukti_potong(inv_id: str, request: Request, auth: Optional[str] = Query(None)):
    _ = (await _resolve_user_from_token(auth)) if auth else (await get_current_user(request))
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    inv = await db.invoices.find_one({"_id": oid})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan")
    bp = inv.get("bukti_potong_attachment") or {}
    if not bp.get("storage_path"):
        raise HTTPException(404, "Bukti potong belum diupload")
    data, ctype = get_object(bp["storage_path"])
    return Response(
        content=data,
        media_type=bp.get("content_type") or ctype,
        headers={"Content-Disposition": f'inline; filename="{bp.get("original_filename", "bukti_potong")}"'},
    )


@api.delete("/invoices/{inv_id}/bukti-potong")
async def delete_bukti_potong(
    inv_id: str,
    user: dict = Depends(require_roles("admin", "operator")),
):
    try:
        oid = ObjectId(inv_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    inv = await db.invoices.find_one({"_id": oid})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan")
    merged = {k: v for k, v in inv.items() if k != "bukti_potong_attachment"}
    await db.invoices.update_one(
        {"_id": oid},
        {"$unset": {"bukti_potong_attachment": ""}, "$set": {"updated_at": now_iso(), "status": compute_invoice_status(merged)}},
    )
    await audit("invoice.bukti_potong.delete", user, target=inv_id)
    return {"ok": True}


# ------------------------------------------------------------------
# Audit Log
# ------------------------------------------------------------------
@api.get("/audit-logs")
async def list_audit_logs(
    action: Optional[str] = None,
    user_email: Optional[str] = None,
    workorder_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    user: dict = Depends(require_roles("admin")),
):
    query: Dict[str, Any] = {}
    if action:
        query["action"] = {"$regex": action, "$options": "i"}
    if user_email:
        query["user_email"] = {"$regex": user_email, "$options": "i"}
    if workorder_id:
        query["workorder_id"] = workorder_id
    docs = await db.audit_logs.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    return [{
        "id": str(d.pop("_id")),
        **d,
    } for d in docs]


class AccessDeniedIn(BaseModel):
    path: str = ""
    required_roles: Optional[List[str]] = None


@api.post("/audit/access-denied")
async def log_access_denied(payload: AccessDeniedIn, user: dict = Depends(get_current_user)):
    """Record an attempt by an authenticated user to open a page their role
    is not allowed to access. Visible in the Audit Log for admin monitoring."""
    await audit(
        "access.denied",
        user,
        target=payload.path or "",
        meta={"path": payload.path or "", "required_roles": payload.required_roles or []},
    )
    return {"ok": True}


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------
@api.get("/")
async def root():
    return {"service": "LA Tracker", "status": "ok"}


# Register router & CORS
app.include_router(api)

allow_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", FRONTEND_URL).split(",") if o.strip()]
if FRONTEND_URL not in allow_origins:
    allow_origins.append(FRONTEND_URL)
# Local install: allow any LAN origin via wildcard regex when CORS_ORIGINS="*"
_use_wildcard = "*" in allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if _use_wildcard else allow_origins,
    allow_origin_regex=".*" if _use_wildcard else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
