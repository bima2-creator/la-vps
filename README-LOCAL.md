# LA Tracker — Panduan Instalasi di PC Windows (Docker) + Database

Panduan ini menjelaskan cara menginstal dan menjalankan **LA Tracker** secara
**100% lokal di PC/laptop Windows Anda**, lengkap dengan **database MongoDB**
yang ikut terpasang otomatis. Data tersimpan di folder `.\data\` (database +
file lampiran). Aplikasi bisa diakses dari PC itu sendiri **maupun** dari PC
lain di jaringan LAN/WiFi kantor.

> **Metode:** Docker Desktop. Anda **tidak perlu** menginstal MongoDB, Python,
> atau Node.js satu per satu — semuanya sudah dibungkus otomatis oleh Docker.

---

## 1. Persyaratan Sistem

| Kebutuhan       | Keterangan                                                        |
|-----------------|-------------------------------------------------------------------|
| Sistem operasi  | Windows 10 / 11 (64-bit)                                          |
| Aplikasi wajib  | **Docker Desktop for Windows**                                    |
| RAM             | Minimum 4 GB (disarankan 8 GB)                                    |
| Ruang disk      | Minimal 2 GB kosong                                              |
| Koneksi internet| Hanya diperlukan saat instalasi/build pertama kali               |

---

## 2. Instal Docker Desktop (sekali saja)

1. Buka halaman unduhan:
   **https://www.docker.com/products/docker-desktop/**
2. Klik **Download for Windows**, lalu jalankan file `Docker Desktop Installer.exe`.
3. Ikuti proses instalasi (biarkan opsi default → **OK / Install**). Bila diminta
   mengaktifkan **WSL 2**, setujui.
4. **Restart** komputer bila diminta.
5. Buka **Docker Desktop** dari Start Menu. Tunggu hingga ikon **paus di pojok
   kanan bawah (system tray) berwarna hijau / bertuliskan "Running"**.

> Docker Desktop harus dalam keadaan **Running** setiap kali Anda ingin
> menjalankan aplikasi.

---

## 3. Menyiapkan Folder Aplikasi

1. Ekstrak folder aplikasi LA Tracker yang Anda terima, misalnya ke:
   `C:\la-tracker\`
2. Pastikan di dalam folder terdapat file: `start.bat`, `stop.bat`,
   `docker-compose.yml`, serta folder `backend\` dan `frontend\`.

---

## 4. Menjalankan Aplikasi (Pertama Kali)

1. Pastikan **Docker Desktop** sudah berjalan (ikon hijau).
2. Klik dua kali file **`start.bat`**.
3. Skrip akan otomatis:
   - memeriksa Docker Desktop,
   - membuat file `local.env` dari template (bila belum ada),
   - membuat folder database `data\mongo` dan folder lampiran `data\attachments`,
   - **membangun (build) image** — proses ini **5–10 menit** hanya pada
     pertama kali,
   - menjalankan 3 layanan: **MongoDB (database)**, **backend (API)**,
     dan **frontend (tampilan web)**,
   - membuka browser otomatis ke **http://localhost:3000**.

> Menjalankan berikutnya (`start.bat` kedua kali dst) hanya butuh **10–15 detik**
> karena image sudah dibangun.

---

## 5. Login ke Aplikasi

Login memakai **USERNAME** (bukan email). Tersedia 3 akun bawaan:

| Username   | Password   | Peran         | Hak akses                              |
|------------|------------|---------------|----------------------------------------|
| `admin`    | `admin123` | Administrator | Akses penuh, kelola user & bank data   |
| `operator` | `operator` | Operator      | Input & edit Work Order / Invoice      |
| `guest`    | `guest`    | Viewer        | Hanya melihat (read-only)              |

> Password dapat diubah di file **`local.env`** sebelum menjalankan
> `rebuild.bat`. Untuk keamanan, ganti password default setelah instalasi.

---

## 6. Database (MongoDB) — Lokasi, Backup & Restore

Database berjalan otomatis di dalam container Docker bernama `la-tracker-mongo`.
Anda **tidak perlu menginstal MongoDB secara terpisah**.

### 6.1 Di mana data disimpan?
Semua data fisik disimpan **di PC Anda** pada folder berikut (persisten, tidak
hilang saat aplikasi dimatikan):

```
la-tracker\
├── data\
│   ├── mongo\           ← isi database MongoDB (semua Work Order, Invoice, Bank Data, User)
│   └── attachments\     ← file lampiran (PDF/SPK/faktur) per Work Order
├── backups\             ← hasil dari backup.bat
└── local.env            ← konfigurasi (password akun, JWT secret)
```

> **JANGAN menghapus folder `data\`** — di situlah seluruh database Anda berada.

### 6.2 Backup database
Klik dua kali **`backup.bat`**. Skrip akan menyimpan:
- salinan database MongoDB (file `.archive.gz`), dan
- salinan folder lampiran,
ke dalam folder `backups\` dengan penanda tanggal.

Lakukan backup secara berkala (mis. tiap akhir hari kerja).

### 6.3 Pindah ke komputer lain / restore
Untuk memindahkan seluruh data ke PC baru:
1. Matikan aplikasi (`stop.bat`).
2. Salin folder **`data\`** dan file **`local.env`** ke folder aplikasi di PC baru.
3. Jalankan `start.bat` di PC baru — data langsung tersedia.

### 6.4 Melihat/akses database langsung (opsional, untuk teknisi)
Buka CMD di folder aplikasi lalu jalankan:
```
docker compose exec mongo mongosh la_tracker
```
Nama database: **`la_tracker`**.

---

## 7. Akses dari PC Lain di Jaringan (LAN/WiFi Kantor)

1. Pastikan `start.bat` sedang berjalan di PC "server".
2. Cari alamat IPv4 PC server (ditampilkan di akhir `start.bat`, atau ketik
   `ipconfig` di CMD).
3. Dari PC lain **di jaringan yang sama**, buka browser ke:
   ```
   http://<IP-PC-SERVER>:3000
   ```
   Contoh: `http://192.168.1.25:3000`
4. Bila Windows Firewall memblokir, izinkan **Docker Desktop** saat diminta,
   atau tambahkan aturan inbound untuk port `3000`.

> **Keamanan:** hanya buka port 3000 di jaringan internal. Jangan diekspos ke
> internet publik tanpa reverse proxy + HTTPS.

---

## 8. Skrip yang Tersedia

| Skrip         | Fungsi                                                              |
|---------------|--------------------------------------------------------------------|
| `start.bat`   | Menyalakan semua layanan + buka browser                            |
| `stop.bat`    | Menghentikan semua layanan (data tetap aman)                       |
| `rebuild.bat` | Membangun ulang setelah update source code / ubah `local.env`      |
| `backup.bat`  | Backup database + lampiran ke folder `backups\`                    |

Melihat log realtime — buka CMD di folder aplikasi:
```
docker compose logs -f
```

---

## 9. Update Aplikasi (versi baru)

1. Jalankan `stop.bat`.
2. Timpa folder `backend\`, `frontend\`, `docker-compose.yml`, dan file `.bat`
   dengan versi baru. **JANGAN** menghapus folder `data\` atau `local.env`.
3. Jalankan `rebuild.bat`.

---

## 10. Troubleshooting (Solusi Masalah Umum)

| Masalah                                   | Solusi                                                                                     |
|-------------------------------------------|--------------------------------------------------------------------------------------------|
| "Docker Desktop belum berjalan"           | Buka Docker Desktop, tunggu ikon hijau, lalu jalankan ulang `start.bat`.                    |
| Port 3000 dipakai aplikasi lain           | Edit `docker-compose.yml`, ubah `"3000:80"` → mis. `"8080:80"`, lalu `rebuild.bat`.        |
| Build lama saat pertama kali              | Wajar (5–10 menit). Selanjutnya `start.bat` hanya 10–15 detik.                             |
| Login gagal / API 401                     | Klik Logout dari menu profil, lalu login ulang. Pastikan username & password benar.        |
| Upload lampiran gagal                     | Docker Desktop → Settings → Resources → File Sharing → tambahkan drive `C:`.               |
| Lupa password admin                       | Edit `ADMIN_PASSWORD` di `local.env`, lalu jalankan `rebuild.bat`.                         |
| Ingin mulai dari database kosong          | `stop.bat`, hapus isi folder `data\mongo\`, lalu `start.bat` (⚠️ semua data akan hilang).  |

---

## Ringkasan Cepat (TL;DR)

1. Instal & jalankan **Docker Desktop** (tunggu ikon hijau).
2. Klik **`start.bat`**.
3. Buka **http://localhost:3000**.
4. Login: **admin / admin123**.
5. Backup rutin dengan **`backup.bat`**.

Selamat menggunakan LA Tracker versi lokal! 🇮🇩
