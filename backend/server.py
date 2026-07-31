from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import io
import os
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
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Query, Header
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


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
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


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
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
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


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
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)
    role: str = Field(default="operator", pattern="^(admin|operator|viewer)$")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str


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
    cp_mitra: Optional[str] = ""
    cp_pelanggan: Optional[str] = ""

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
            "user_email": user.get("email"),
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
    await db.users.create_index("email", unique=True)
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

    # Initialize object storage (non-blocking on failure)
    if init_storage():
        log.info("Object storage initialized")

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@la-tracker.com")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_pw),
            "name": "Administrator",
            "role": "admin",
            "created_at": now_iso(),
        })
        log.info("Seeded admin user: %s", admin_email)
    elif not verify_password(admin_pw, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_pw)}},
        )
        log.info("Reset admin password for: %s", admin_email)


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
    email = payload.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "Email already registered")
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "role": payload.role,
        "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    access = create_access_token(uid, email, payload.role)
    refresh = create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return {"id": uid, "email": email, "name": payload.name, "role": payload.role, "token": access}


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    uid = str(user["_id"])
    access = create_access_token(uid, email, user["role"])
    refresh = create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return {"id": uid, "email": email, "name": user["name"], "role": user["role"], "token": access}


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
        access = create_access_token(uid, user["email"], user["role"])
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
    return [{"id": str(u["_id"]), "email": u["email"], "name": u["name"], "role": u["role"],
             "created_at": u.get("created_at")} for u in users]


@api.post("/users")
async def create_user(payload: RegisterIn, user: dict = Depends(require_roles("admin"))):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already exists")
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "role": payload.role,
        "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    return {"id": str(res.inserted_id), "email": email, "name": payload.name, "role": payload.role}


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
    the same customer/service)."""
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
        # Allow reuse if they share SA_ID or SI_ID (same customer/service).
        shares_owner = (
            (my_sa and other_sa and my_sa == other_sa)
            or (my_si and other_si and my_si == other_si)
        )
        if shares_owner:
            continue
        for oi in other_items:
            onr = (oi or {}).get("nomor_registrasi", "").strip()
            if onr and onr in seen:
                who = other_sa or other_si or str(other.get("_id"))
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
    doc["created_by"] = user["email"]
    res = await db.workorders.insert_one(doc)
    doc["_id"] = res.inserted_id
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
    await audit("workorder.update", user, workorder_id=wo_id, meta={"pelanggan": updated.get("pelanggan")})
    return workorder_to_out(updated)


@api.delete("/workorders/{wo_id}")
async def delete_workorder(wo_id: str, user: dict = Depends(require_roles("admin"))):
    res = await db.workorders.delete_one({"_id": ObjectId(wo_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found")
    await audit("workorder.delete", user, workorder_id=wo_id)
    return {"ok": True}


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


@api.get("/workorders/export/xlsx")
async def export_workorders(user: dict = Depends(get_current_user)):
    docs = await db.workorders.find({}).sort("created_at", -1).to_list(10000)
    rows = []
    for d in docs:
        rows.append({label: d.get(field, "") for field, label in EXPORT_COLUMNS})
    df = pd.DataFrame(rows, columns=[label for _, label in EXPORT_COLUMNS])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Workorders")
        wb = writer.book
        ws = writer.sheets["Workorders"]
        # Rupiah formatting for money columns
        rp_fmt = wb.add_format({"num_format": '"Rp" #,##0'})
        money_labels = {"BOQ JASA", "BOQ MATERIAL", "BOQ JUMLAH"}
        for i, label in enumerate([lbl for _, lbl in EXPORT_COLUMNS]):
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
            doc["created_by"] = user["email"]
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
            doc["created_by"] = user["email"]
            docs.append(doc)

    if not docs:
        return {"inserted": 0, "message": "No data rows found."}
    result = await db.workorders.insert_many(docs)
    return {"inserted": len(result.inserted_ids)}


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
@api.get("/dashboard/stats")
async def dashboard_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    media_jenis: Optional[str] = None,
    jenis_order: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if media_jenis:
        query["media_jenis"] = media_jenis
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

        media = (d.get("media_jenis") or "UNSPECIFIED").upper()
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
            return "TERPASANG"
        return "MAINTENANCE"
    return "TERPASANG"


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
    elems.append(Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by {user['email']}", styles["Normal"]))
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
async def export_pdf_one(wo_id: str, user: dict = Depends(get_current_user)):
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
    # Append Faktur Pajak (if uploaded) as lampiran pages.
    # -----------------------------------------------------------
    fp = inv.get("faktur_pajak_attachment") or {}
    if fp.get("storage_path") and _HAS_PYPDF:
        try:
            fp_bytes, fp_ctype = get_object(fp["storage_path"])
            fp_ext = (fp.get("ext") or "").lower()
            fp_pdf_bytes: Optional[bytes] = None
            if fp_ext == "pdf" or (fp_ctype or "").lower() == "application/pdf":
                fp_pdf_bytes = fp_bytes
            elif fp_ext in ("png", "jpg", "jpeg"):
                # Wrap image into a single-page PDF via reportlab
                img_buf = io.BytesIO()
                img_doc = SimpleDocTemplate(
                    img_buf, pagesize=A4,
                    leftMargin=10 * mm, rightMargin=10 * mm,
                    topMargin=10 * mm, bottomMargin=10 * mm,
                )
                img_reader = RLImage(io.BytesIO(fp_bytes))
                # Scale image to fit page width (~190mm)
                max_w = 190 * mm
                max_h = 260 * mm
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
                fp_pdf_bytes = img_buf.getvalue()
            if fp_pdf_bytes:
                writer = PdfWriter()
                # Append main invoice
                for page in PdfReader(io.BytesIO(buf.getvalue())).pages:
                    writer.add_page(page)
                # Append faktur pajak
                for page in PdfReader(io.BytesIO(fp_pdf_bytes)).pages:
                    writer.add_page(page)
                merged = io.BytesIO()
                writer.write(merged)
                merged.seek(0)
                return StreamingResponse(
                    merged,
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{safe_no}.pdf"'},
                )
        except Exception as e:
            logging.getLogger("la-tracker").warning(
                "faktur pajak merge failed for %s: %s", inv_id, e
            )
            # fall through to return invoice without lampiran

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
async def upload_attachment(wo_id: str, file: UploadFile = File(...), user: dict = Depends(require_roles("admin", "operator"))):
    wo = await db.workorders.find_one({"_id": ObjectId(wo_id)})
    if not wo:
        raise HTTPException(404, "Work order not found")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20MB)")
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin").lower()
    ctype = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    file_uuid = str(uuid.uuid4())
    path = f"{APP_NAME}/workorders/{wo_id}/{file_uuid}.{ext}"
    result = put_object(path, data, ctype)
    doc = {
        "workorder_id": wo_id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "uploaded_by": user["email"],
        "created_at": now_iso(),
        "is_deleted": False,
    }
    res = await db.attachments.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    await audit("attachment.upload", user, workorder_id=wo_id, meta={"filename": file.filename, "size": doc["size"]})
    return doc


@api.get("/workorders/{wo_id}/attachments")
async def list_attachments(wo_id: str, user: dict = Depends(get_current_user)):
    docs = await db.attachments.find({"workorder_id": wo_id, "is_deleted": False}).sort("created_at", -1).to_list(200)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@api.get("/attachments/{att_id}/download")
async def download_attachment(att_id: str, request: Request, auth: Optional[str] = Query(None)):
    # Support ?auth= for <img src>; fallback to normal cookie/bearer auth
    if auth and "Authorization" not in request.headers:
        request.scope["headers"] = list(request.scope["headers"]) + [(b"authorization", f"Bearer {auth}".encode())]
    user = await get_current_user(request)  # will raise 401 if not authed
    _ = user
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


class InvoiceIn(BaseModel):
    pelanggans: List[str] = []
    jenis_pekerjaan: str
    invoice_no: Optional[str] = ""
    inv_no_eproc: Optional[str] = ""
    faktur_pajak_no: Optional[str] = ""
    tanggal: Optional[str] = ""
    tgl_kirim: Optional[str] = ""
    tgl_bayar: Optional[str] = ""
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
    for d in docs:
        if not _wo_matches_activity(d, jp):
            continue
        wid = str(d["_id"])
        # Hide WOs already in another invoice — the whole point of "only show
        # pelanggan yang belum dibuatkan invoice" per user's request.
        if wid in already_billed_ids:
            continue
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
        })
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
    return docs


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
    return d


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
        "status": (payload.status or "OPEN").upper(),
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
        "created_by": user.get("email"),
    }
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
        "status": (payload.status or "OPEN").upper(),
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
FP_ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg"}


def _extract_faktur_pajak_no(pdf_bytes: bytes) -> Optional[str]:
    """Try to auto-detect the 16-digit Nomor Seri Faktur Pajak from PDF text.

    Handles both plain format "0400260028205717" and dotted/dashed format
    "040.026-00.28205717". Returns the pure 16-digit string, or None.
    """
    if not _HAS_PYPDF:
        return None
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages[:3]:  # only first pages needed
            try:
                text_parts.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(text_parts)
    except Exception:
        return None
    if not text:
        return None
    import re
    # 1. Look for labeled line first (Indonesian invoices)
    labeled = re.search(
        r"Kode\s*dan\s*Nomor\s*Seri\s*Faktur\s*Pajak\s*[:\-]?\s*([\d.\-\s]{16,25})",
        text, re.IGNORECASE,
    )
    if labeled:
        digits = re.sub(r"\D", "", labeled.group(1))
        if len(digits) == 16:
            return digits
    # 2. Dotted/dashed pattern anywhere
    dotted = re.search(r"\b(\d{3})\.(\d{3})[-.](\d{2})\.(\d{8})\b", text)
    if dotted:
        return "".join(dotted.groups())
    # 3. Bare 16-digit fallback (must not be part of longer number)
    bare = re.search(r"(?<!\d)(\d{16})(?!\d)", text)
    if bare:
        return bare.group(1)
    return None


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
    if ext not in FP_ALLOWED_EXT:
        raise HTTPException(400, "Format harus PDF, PNG, atau JPG")
    ctype = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")

    # Try auto-extract for PDFs
    detected_no: Optional[str] = None
    if ext == "pdf":
        detected_no = _extract_faktur_pajak_no(data)

    file_uuid = str(uuid.uuid4())
    path = f"{APP_NAME}/invoices/{inv_id}/faktur_pajak_{file_uuid}.{ext}"
    result = put_object(path, data, ctype)
    fp_attachment = {
        "storage_path": result["path"],
        "original_filename": fname,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "ext": ext,
        "uploaded_by": user["email"],
        "uploaded_at": now_iso(),
        "auto_detected_no": detected_no or "",
    }
    update_set: Dict[str, Any] = {
        "faktur_pajak_attachment": fp_attachment,
        "updated_at": now_iso(),
    }
    # Resolve final faktur_pajak_no with priority:
    #   1) explicit form field from client
    #   2) auto-detected from PDF
    #   3) keep existing value on the invoice
    final_no = (faktur_pajak_no or "").strip()
    if not final_no and detected_no:
        final_no = detected_no
    if final_no:
        update_set["faktur_pajak_no"] = final_no
    await db.invoices.update_one({"_id": oid}, {"$set": update_set})
    await audit(
        "invoice.faktur_pajak.upload", user, target=inv_id,
        meta={"filename": fname, "size": fp_attachment["size"], "no": final_no, "auto": bool(detected_no)},
    )
    return {
        "ok": True,
        "faktur_pajak_attachment": fp_attachment,
        "faktur_pajak_no": final_no or inv.get("faktur_pajak_no", ""),
        "auto_detected": bool(detected_no),
    }


@api.get("/invoices/{inv_id}/faktur-pajak/download")
async def download_faktur_pajak(inv_id: str, request: Request, auth: Optional[str] = Query(None)):
    # Support ?auth= for inline preview; fallback to normal auth headers
    if auth and "Authorization" not in request.headers:
        request.scope["headers"] = list(request.scope["headers"]) + [(b"authorization", f"Bearer {auth}".encode())]
    _ = await get_current_user(request)
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
    await db.invoices.update_one(
        {"_id": oid},
        {"$unset": {"faktur_pajak_attachment": ""}, "$set": {"updated_at": now_iso()}},
    )
    await audit("invoice.faktur_pajak.delete", user, target=inv_id)
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
