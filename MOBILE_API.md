# LA Tracker — Panduan API untuk Aplikasi Mobile (Expo / React Native)

Backend FastAPI yang sama melayani web dan mobile. Bangun UI mobile lewat **Mobile Agent**
Emergent (task terpisah) dan hubungkan ke API di bawah.

## Base URL
- Semua endpoint di-prefix `/api`.
- Preview/prod URL diambil dari environment (jangan hardcode). Contoh dev:
  `https://<host>/api`

## Autentikasi (JWT — access + refresh token)

Login pakai **username** (bukan email). Akun tetap: admin / operator / guest
(lihat `memory/test_credentials.md`).

### 1) Login
```
POST /api/auth/login
Content-Type: application/json
{ "username": "admin", "password": "admin123" }
```
Response:
```json
{
  "id": "...", "username": "admin", "role": "admin", "name": "...",
  "access_token": "<jwt 8 jam>",
  "refresh_token": "<jwt 7 hari>",
  "token": "<alias access_token>",
  "token_type": "bearer"
}
```
Simpan `access_token` & `refresh_token` di secure storage (mis. `expo-secure-store`).

### 2) Panggil endpoint terproteksi
Kirim header:
```
Authorization: Bearer <access_token>
```

### 3) Refresh saat access token kadaluarsa (dapat 401)
```
POST /api/auth/refresh
Content-Type: application/json
{ "refresh_token": "<refresh_token>" }
```
(atau kirim `Authorization: Bearer <refresh_token>`)

Response mengembalikan `access_token` + `refresh_token` **baru** (dirotasi). Simpan ulang keduanya,
lalu ulangi request yang gagal.

### 4) Ambil profil
```
GET /api/auth/me           (Authorization: Bearer <access_token>)
```

### 5) Logout
```
POST /api/auth/logout      (Authorization: Bearer <access_token>)
```

## Contoh pola Axios (Expo)
```js
import axios from "axios";
import * as SecureStore from "expo-secure-store";

const api = axios.create({ baseURL: `${BACKEND_URL}/api` });

api.interceptors.request.use(async (cfg) => {
  const t = await SecureStore.getItemAsync("access_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const orig = err.config;
    if (err.response?.status === 401 && !orig._retried) {
      orig._retried = true;
      const refresh = await SecureStore.getItemAsync("refresh_token");
      const { data } = await axios.post(`${BACKEND_URL}/api/auth/refresh`, { refresh_token: refresh });
      await SecureStore.setItemAsync("access_token", data.access_token);
      await SecureStore.setItemAsync("refresh_token", data.refresh_token);
      orig.headers.Authorization = `Bearer ${data.access_token}`;
      return api(orig);
    }
    return Promise.reject(err);
  }
);
```

## Endpoint utama (untuk fitur mobile)
- `GET /api/workorders?page=&page_size=&q=&invoiced=belum|sudah` — daftar WO (paginated)
- `GET /api/workorders/{id}` — detail WO
- `POST /api/workorders` / `PUT /api/workorders/{id}` — buat/ubah (role admin/operator)
- `GET /api/workorders/lookup-by-si?si_id=` — prefill dari riwayat SI ID
- `GET /api/dashboard/stats` — ringkasan dashboard
- `GET /api/dashboard/m2m-expiry?within=30` — peringatan masa aktif M2M
- `GET /api/kpi/teknisi` — KPI per teknisi
- `GET /api/invoices` — daftar invoice
- `GET /api/perangkat/bank/lookup?nomor=` — deteksi nama perangkat dari nomor registrasi

Role: `admin` (full), `operator` (buat/ubah WO), `viewer/guest` (read-only).

---

## Field Engineer (FE) — Endpoint untuk Mobile

Role baru `field_engineer`. Akun dibuat admin di web (Administration → Field Engineer).
FE login lewat `POST /api/auth/login` yang sama (`{"username","password"}`).

- `GET /api/workorders` — untuk role FE otomatis terfilter hanya WO yang ditugaskan padanya (`field_engineer == username`). Query params filter/pagination tetap berlaku.
- `GET /api/workorders/{id}` — 403 jika WO bukan miliknya.
- `PATCH /api/workorders/{id}/field-data` — body `{"data": {field: value, ...}}`. Hanya field berikut yang diterima (lainnya diabaikan & dilaporkan di `rejected_fields`):
  - `lat`, `lng` (titik lokasi real, format DMS sama dengan web)
  - `media_jenis`, `media_perangkat`, `m2m_sim_card`, `m2m_jenis_kartu`, `m2m_kuota_gb`, `m2m_masa_aktif`
  - `cp_pelanggan`
  - `tim_pelaksana`, `teknisi_pelaksana` (FE lain yang ikut mengerjakan → masuk KPI)
  - `hasil_{survey|instalasi|aktivasi}_{status|datek|npae}`
  - `info_kondisi`, `info_perizinan`, `info_biaya`, `info_masalah`, `info_tindak_lanjut`
  - `perangkat_items`
  - `activity_*_start/end`, `stop_*_start/end`
- `POST /api/workorders/{id}/activity` — clock kerja lapangan. Body: `{"fase":"survey|instalasi|aktivasi","action":"start|hold|resume|stop","reason":"wajib saat hold"}`.
  Respons berisi `summary` `{status: idle|running|hold|done, net_minutes, hold_count}` (durasi bersih di luar masa hold).
  Aksi otomatis menyinkronkan tanggal ke field `activity_*`/`stop_*` WO (tampil di web).
- Riwayat lengkap tersimpan di field WO `fe_activity_log` `[{fase, action, time, reason, by}]`.
- `PUT /api/workorders/{id}` — kini juga bisa dipakai role FE. Perilaku untuk FE: hanya WO miliknya (403 jika bukan), hanya field whitelist yang diterapkan, dan **hanya field yang dikirim** (kirim subset saja, mis. `{"cp_pelanggan":"..."}` — field lain tidak tertimpa). Field terlarang diabaikan; jika tidak ada field valid → 400.
