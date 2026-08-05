# 📘 Panduan Instalasi LA Tracker di PC Windows

Dokumen ini menjelaskan cara menjalankan aplikasi **LA Tracker** di komputer
Windows (Windows 10 / 11), baik untuk dipakai sendiri di satu PC maupun diakses
bersama dalam satu jaringan kantor (LAN).

> Catatan: LA Tracker adalah **aplikasi web**. Setelah dijalankan, aplikasi
> dibuka lewat browser (Chrome / Edge) di alamat `http://localhost:3000`.
> Tidak ada file `.exe` yang di-install seperti aplikasi desktop biasa —
> yang dijalankan adalah "server" aplikasinya.

---

## 1. Software yang Harus Di-install Dulu (Prasyarat)

Install ketiga software di bawah ini (gratis semua). Klik **Next → Next → Finish**
dengan pengaturan default kecuali disebutkan lain.

| No | Software | Link Download | Catatan Penting |
|----|----------|---------------|-----------------|
| 1 | **MongoDB Community Server** | https://www.mongodb.com/try/download/community | Pilih versi Windows (.msi). Saat install pilih **"Install MongoDB as a Service"** agar database jalan otomatis. |
| 2 | **Python 3.11** | https://www.python.org/downloads/release/python-3119/ | ⚠️ **WAJIB centang "Add Python to PATH"** di layar pertama installer. |
| 3 | **Node.js LTS (v20)** | https://nodejs.org/en/download | Pilih **Windows Installer (.msi)** versi LTS. |

Setelah Node.js terpasang, install **Yarn** (pengelola paket frontend). Buka
**Command Prompt** (tekan tombol Windows → ketik `cmd` → Enter), lalu jalankan:

```bat
npm install -g yarn
```

### Cara memastikan semua sudah terpasang
Di Command Prompt jalankan satu per satu. Jika muncul nomor versi, berarti sukses:

```bat
python --version
node --version
yarn --version
mongod --version
```

---

## 2. Menyiapkan Kode Aplikasi

1. Dapatkan kode aplikasi (gunakan fitur **"Save to GitHub"** di Emergent, lalu
   `git clone`, atau unduh sebagai file ZIP lalu ekstrak).
2. Misalkan hasil ekstrak ada di folder: `C:\la-tracker\`
   Di dalamnya harus ada 2 folder: `backend` dan `frontend`.

---

## 3. Konfigurasi (File `.env`)

### 3a. Backend — buat file `C:\la-tracker\backend\.env`
Buka Notepad, isi seperti di bawah, lalu **Save As** dengan nama `.env`
(pilih "Save as type: All Files" agar tidak menjadi `.env.txt`).

```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="la_tracker"
JWT_SECRET="ganti-dengan-teks-acak-panjang-minimal-32-karakter"
CORS_ORIGINS="*"
FRONTEND_URL="http://localhost:3000"
STORAGE_MODE="local"
LOCAL_STORAGE_DIR="C:\\la-tracker-data\\attachments"
ADMIN_PASSWORD="admin123"
OPERATOR_PASSWORD="operator"
GUEST_PASSWORD="guest"
ADMIN_EMAIL="support@almar.co.id"
```

Keterangan:
- `STORAGE_MODE="local"` → file lampiran SPK/foto disimpan di folder lokal
  `LOCAL_STORAGE_DIR` (di contoh: `C:\la-tracker-data\attachments`). Tidak butuh internet.
- `CORS_ORIGINS="*"` → mengizinkan akses dari PC lain di jaringan kantor.
- Ganti nilai `ADMIN_PASSWORD` dll. bila ingin password sendiri.

### 3b. Frontend — buat file `C:\la-tracker\frontend\.env`

```env
REACT_APP_BACKEND_URL=http://localhost:8001
WDS_SOCKET_PORT=0
```

---

## 4. Menjalankan Backend (Server API)

Buka **Command Prompt**, jalankan baris demi baris:

```bat
cd C:\la-tracker\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
uvicorn server:app --host 0.0.0.0 --port 8001
```

Jika berhasil, akan muncul tulisan `Uvicorn running on http://0.0.0.0:8001`.
**Biarkan jendela ini tetap terbuka** (ini adalah servernya).

> Uji cepat: buka browser ke `http://localhost:8001/docs` → harus muncul halaman dokumentasi API.

---

## 5. Menjalankan Frontend (Tampilan Aplikasi)

Buka **jendela Command Prompt BARU** (jangan tutup yang backend), jalankan:

```bat
cd C:\la-tracker\frontend
yarn install
yarn start
```

Setelah selesai, browser biasanya terbuka otomatis ke `http://localhost:3000`.
Jika tidak, buka manual di Chrome/Edge: **http://localhost:3000**

---

## 6. Login Pertama Kali

| Peran | Username | Password |
|-------|----------|----------|
| Admin | `admin` | `admin123` |
| Operator | `operator` | `operator` |
| Viewer (hanya lihat) | `guest` | `guest` |

Akun ini dibuat otomatis saat backend pertama kali dijalankan.
Segera ganti password Admin dari menu **Users** setelah login.

---

## 7. (Opsional) Diakses dari PC Lain di Kantor (LAN)

Agar rekan kerja bisa membuka aplikasi dari PC mereka:

1. Cari alamat IP PC server. Di Command Prompt ketik `ipconfig`, catat
   **IPv4 Address**, misalnya `192.168.1.50`.
2. Ubah `C:\la-tracker\frontend\.env` menjadi:
   ```env
   REACT_APP_BACKEND_URL=http://192.168.1.50:8001
   WDS_SOCKET_PORT=0
   ```
3. Pastikan `CORS_ORIGINS="*"` di backend `.env` (sudah sesuai contoh di atas).
4. Izinkan port di **Windows Defender Firewall**: buka firewall → *Advanced
   Settings* → *Inbound Rules* → *New Rule* → *Port* → TCP → ketik `3000,8001`
   → *Allow*.
5. Restart backend & frontend (tutup lalu jalankan lagi langkah 4 & 5).
6. Dari PC lain, buka browser ke `http://192.168.1.50:3000`.

---

## 8. Menjalankan Ulang Setelah PC Restart

Setiap kali PC dinyalakan ulang, cukup jalankan **2 jendela Command Prompt**:

**Jendela 1 — Backend:**
```bat
cd C:\la-tracker\backend
venv\Scripts\activate
uvicorn server:app --host 0.0.0.0 --port 8001
```

**Jendela 2 — Frontend:**
```bat
cd C:\la-tracker\frontend
yarn start
```

(MongoDB berjalan otomatis sebagai *Windows Service* jika saat install memilih
opsi "Install as a Service".)

> 💡 Tip: Anda bisa membuat dua file `.bat` (mis. `start-backend.bat` dan
> `start-frontend.bat`) berisi perintah di atas, lalu cukup klik dua kali
> untuk menjalankan.

---

## 9. Masalah Umum & Solusi

| Masalah | Penyebab / Solusi |
|---------|-------------------|
| `python` tidak dikenali | Python belum ditambahkan ke PATH. Install ulang & centang "Add Python to PATH". |
| Backend error "connection refused" ke MongoDB | Service MongoDB belum jalan. Buka *Services* Windows → cari **MongoDB** → Start. |
| Halaman aplikasi kosong / gagal login | Pastikan backend (jendela 1) masih terbuka & `REACT_APP_BACKEND_URL` benar. |
| `pip install` gagal untuk emergentintegrations | Jalankan perintah dengan `--extra-index-url` seperti pada langkah 4. |
| Port 3000 / 8001 sudah dipakai | Tutup aplikasi lain yang memakai port tsb, atau restart PC. |

---

## 10. Alternatif: Pakai Versi Online (Tanpa Install)

Jika tidak ingin repot instalasi, aplikasi juga bisa **di-deploy online** sehingga
punya link tetap yang bisa dibuka dari PC/HP mana pun lewat browser — tanpa
install apa pun. Hubungi admin/pengembang untuk link versi online-nya.

---
*Dokumen ini dibuat untuk LA Tracker — Portal Project Management & Delivery (Almar).*
