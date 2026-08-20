# 🚀 Panduan Deploy LA Tracker di VPS Linux (Ubuntu 24.04)

Setup produksi: **FastAPI + MongoDB + Frontend (Nginx) + Caddy (HTTPS otomatis)**
dalam Docker. Cocok untuk dipakai bersama Web + Mobile App.

```
Internet ──▶ Caddy (443/HTTPS) ──▶ Frontend (Nginx: React + proxy /api)
                                        └─▶ Backend (FastAPI :8001) ─▶ MongoDB
                                                                    └─▶ /data/attachments
```

---

## 0. Prasyarat
- VPS **Ubuntu Server 24.04 LTS**, min **2 vCPU / 4 GB RAM / SSD** (region ID/SG).
- **Domain** sudah diarahkan (A record) ke IP VPS, mis. `app.almar.co.id` → `123.45.67.89`.
- Port **80** dan **443** terbuka di firewall VPS.

## 1. Install Docker
```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# logout & login lagi agar grup docker aktif
```
Cek: `docker --version` dan `docker compose version`.

## 2. Ambil kode aplikasi
```bash
git clone <URL_REPO_GITHUB_ANDA> la-tracker
cd la-tracker
```
(Gunakan fitur **Save to GitHub** di Emergent untuk mendapatkan URL repo.)

## 3. Konfigurasi environment
```bash
cp prod.env.example .env
nano .env         # isi SITE_ADDRESS, PUBLIC_URL, password, JWT_SECRET
```
Buat JWT & password acak dengan: `openssl rand -hex 32`

**Mode akses (pilih salah satu di `.env`):**
- **Domain (HTTPS otomatis):** `SITE_ADDRESS=namadomain.com` & `PUBLIC_URL=https://namadomain.com`
- **IP saja (HTTP, tanpa sertifikat):** `SITE_ADDRESS=:80` & `PUBLIC_URL=http://IP_VPS_ANDA`

## 4. Jalankan (build + start)
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
- Caddy otomatis menerbitkan sertifikat **HTTPS** untuk domain Anda (butuh domain sudah mengarah ke VPS & port 80/443 terbuka).
- Tunggu ± 1–2 menit, lalu buka `https://<DOMAIN>` di browser.

Cek status & log:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
```

## 5. Login pertama
Buka `https://<DOMAIN>` → login **admin** dengan password dari `.env` (`ADMIN_PASSWORD`).
Segera ganti password dari menu Users.

---

## 🔧 Operasional Harian

**Update ke versi terbaru:**
```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

**Restart / stop:**
```bash
docker compose -f docker-compose.prod.yml restart
docker compose -f docker-compose.prod.yml down
```

**Backup Database (jalankan via cron harian):**
```bash
docker exec la-tracker-mongo sh -c 'mongodump --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin \
  --archive' > backup-$(date +%F).archive
```
> Aplikasi juga punya fitur Backup bawaan (menu Admin → Backup), tapi backup level
> DB di atas tetap disarankan & simpan salinannya ke lokasi lain (S3/Google Drive).

Contoh cron harian jam 02:00 (`crontab -e`):
```
0 2 * * * cd /home/USER/la-tracker && docker exec la-tracker-mongo sh -c 'mongodump -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --archive' > backups/db-$(date +\%F).archive
```

**File lampiran** tersimpan di `./data/attachments` (ikut di-backup dengan menyalin folder `data/`).

---

## 📱 Untuk Mobile App (nanti)
- Mobile app cukup memanggil **`https://<DOMAIN>/api/...`** dengan **JWT** (login sama seperti web).
- Dokumentasi API otomatis tersedia di **`https://<DOMAIN>/api/docs`** (Swagger).
- Saat mobile app dikembangkan, backend bisa ditambah **refresh token** & **push notification** tanpa mengubah arsitektur ini.

## ⬆️ Skala lebih besar (opsional)
- Pindah database ke **MongoDB Atlas** (managed + backup otomatis): cukup ubah `MONGO_URL` di `.env`, dan hapus service `mongo` dari compose.
- Pindah file ke **S3 / Cloudflare R2** untuk penyimpanan lampiran yang lebih tahan lama.

---

## 🌐 Cloudflare Tunnel (VM di belakang NAT, port 80/443 tertutup)

Dipakai saat VPS tidak bisa menerima koneksi masuk (seperti vm190: hanya port 22 yang diteruskan).
Tunnel membuat koneksi KELUAR dari VM ke Cloudflare, jadi tidak butuh port forwarding sama sekali,
dan HTTPS `https://app.bitech.co.id` diurus otomatis oleh Cloudflare.

### 1. Daftarkan domain ke Cloudflare (sekali saja)
1. Buat akun gratis di https://dash.cloudflare.com
2. **Add a domain** → masukkan `bitech.co.id` → pilih plan **Free**
3. Cloudflare menampilkan 2 nameserver → ganti nameserver di registrar domain
   (record DNS lama otomatis dimigrasikan; website & email utama tetap jalan)
4. Tunggu status domain menjadi **Active** (beberapa menit s/d 24 jam)

### 2. Buat Tunnel
1. Buka https://one.dash.cloudflare.com → **Networks → Tunnels → Create a tunnel**
2. Pilih **Cloudflared** → beri nama misal `la-tracker` → **Save**
3. Di halaman install, salin **token**-nya saja (teks panjang setelah `--token`)
4. Tab **Public Hostname → Add a public hostname**:
   - Subdomain: `app` — Domain: `bitech.co.id`
   - Service Type: **HTTP** — URL: `caddy:80`
5. Save

### 3. Jalankan di VPS
```bash
cd ~/la-tracker
git pull
nano .env    # pastikan: SITE_ADDRESS=:80, PUBLIC_URL=https://app.bitech.co.id, TUNNEL_TOKEN=<token langkah 2.3>
docker compose -f docker-compose.prod.yml --profile tunnel up -d
docker logs la-tracker-tunnel --tail 20   # harus muncul "Registered tunnel connection"
```

Selesai → akses **https://app.bitech.co.id**

> Catatan mode tunnel:
> - `SITE_ADDRESS` HARUS `:80` (Caddy menerima semua host; TLS diurus Cloudflare, bukan Caddy)
> - `PUBLIC_URL` HARUS `https://app.bitech.co.id` (dipakai untuk CORS backend)
> - Selalu sertakan `--profile tunnel` pada perintah `up -d` agar container tunnel ikut menyala
