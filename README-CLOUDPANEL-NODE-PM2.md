# Flake Music Deployment Guide (CloudPanel + Node Site + PM2)

This guide documents the exact setup that worked:

- Frontend domain: `https://bot.kraftamine.in`
- Backend/API domain: `https://botapi.kraftamine.in`
- Frontend served by Node site template
- Backend (FastAPI + Discord bot) managed by PM2

---

## 0) Security First

If you shared credentials/screenshots publicly, rotate them first:

1. Change CloudPanel site user password.
2. Rotate Discord bot token/client secret.
3. Rotate database password if exposed.

---

## 1) Create Sites in CloudPanel

### 1.1 Frontend Node.js site

Create a **Node.js Site**:

- Domain: `bot.kraftamine.in`
- App Port: `5173`
- Site User: `kraftamine-bot`

Enable SSL (Let's Encrypt) and force HTTPS.

### 1.2 Backend reverse proxy site

Create a second site for API:

- Domain: `botapi.kraftamine.in`
- Reverse Proxy target: `http://127.0.0.1:8000`

Enable SSL and force HTTPS.

---

## 2) SSH Into Server and Prepare Project

```bash
sudo su - kraftamine-bot
cd /home/kraftamine-bot
```

Clone (first time) or pull updates:

```bash
git clone <YOUR_REPO_URL> flake-music
# OR if already cloned:
cd /home/kraftamine-bot/flake-music
git pull
```

---

## 3) Install PM2 (if not already)

```bash
npm install -g pm2
pm2 -v
```

---

## 4) Setup Python Environment for Backend

```bash
python3 -m venv /home/kraftamine-bot/.venvs/flake
source /home/kraftamine-bot/.venvs/flake/bin/activate
pip install -r /home/kraftamine-bot/flake-music/backend/requirements.txt
```

---

## 5) Create Backend Environment File

Create this file:

- `/home/kraftamine-bot/flake-music/.env`

Example (fill with real values):

```env
DISCORD_TOKEN=...
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=https://bot.kraftamine.in/auth/callback

SECRET_KEY=your_long_random_secret

DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST:5432/DBNAME

LAVALINK_HOST=...
LAVALINK_PORT=2333
LAVALINK_PASSWORD=...

CORS_ORIGINS=https://bot.kraftamine.in
```

---

## 6) Start Backend + Bot with PM2

Run from anywhere:

```bash
pm2 delete flake-backend-bot || true
pm2 start "/bin/bash -lc 'source /home/kraftamine-bot/.venvs/flake/bin/activate; cd /home/kraftamine-bot/flake-music; export PYTHONPATH=/home/kraftamine-bot/flake-music; uvicorn backend.main:app --host 127.0.0.1 --port 8000 --env-file /home/kraftamine-bot/flake-music/.env'" --name flake-backend-bot
```

Check:

```bash
pm2 logs flake-backend-bot --lines 100
curl http://127.0.0.1:8000/
```

---

## 7) Configure Frontend Production Env

Create file:

- `/home/kraftamine-bot/flake-music/frontend/.env.production`

```env
VITE_API_URL=https://botapi.kraftamine.in/api/v1
VITE_WS_URL=wss://botapi.kraftamine.in/ws
VITE_DISCORD_REDIRECT_URI=https://bot.kraftamine.in/auth/callback
VITE_DISCORD_CLIENT_ID=YOUR_DISCORD_CLIENT_ID
```

---

## 8) Build Frontend

```bash
cd /home/kraftamine-bot/flake-music/frontend
npm ci
npm run build
```

---

## 9) Run Frontend Dist with PM2 on Port 5173

```bash
pm2 delete flake-frontend || true
pm2 start "npx serve -s dist -l 5173" --name flake-frontend --cwd /home/kraftamine-bot/flake-music/frontend
```

Check:

```bash
pm2 logs flake-frontend --lines 100
curl http://127.0.0.1:5173/
```

---

## 10) Persist PM2 Processes

```bash
pm2 save
```

If you cannot run `pm2 startup` due to sudo restrictions, use crontab fallback:

```bash
crontab -e
```

Add:

```cron
@reboot /home/kraftamine-bot/.nvm/versions/node/v20.*/bin/pm2 resurrect
```

---

## 11) Discord Developer Portal

In OAuth2 Redirects, add:

- `https://bot.kraftamine.in/auth/callback`

---

## 12) Final Verification Checklist

1. `https://botapi.kraftamine.in/` returns API response.
2. `https://bot.kraftamine.in` loads frontend.
3. Discord login redirects back to `/auth/callback`.
4. Dashboard loads data from API.
5. `pm2 list` shows both apps online:
   - `flake-backend-bot`
   - `flake-frontend`

---

## 13) Common Issues and Fixes

### ModuleNotFoundError: No module named backend

Use this launch command format:

- Start from repo root
- Use `uvicorn backend.main:app`
- Set `PYTHONPATH=/home/kraftamine-bot/flake-music`

### Frontend cannot read .env in dist

Expected behavior. Vite injects env at build time only.

Fix: edit `frontend/.env.production`, then run `npm run build` again.

### WebSocket fails

Ensure:

- `VITE_WS_URL=wss://botapi.kraftamine.in/ws`
- Reverse proxy allows websocket upgrade
- SSL enabled on API domain

### CORS blocked

Ensure backend env has:

- `CORS_ORIGINS=https://bot.kraftamine.in`

Restart backend:

```bash
pm2 restart flake-backend-bot
```

### YouTube says “Sign in to confirm you’re not a bot”

Configure yt-dlp cookies for the backend process:

1. Export YouTube cookies in Netscape format to a file (example path below).
2. Put the file on server, e.g. `/home/kraftamine-bot/flake-music/cookies.txt`.
3. Add this in `/home/kraftamine-bot/flake-music/.env`:

```env
YTDLP_COOKIE_FILE=/home/kraftamine-bot/flake-music/cookies.txt
```

4. Restart backend:

```bash
pm2 restart flake-backend-bot
pm2 logs flake-backend-bot --lines 80
```

Notes:

- Keep cookies file private (`chmod 600`).
- Cookies expire; re-export when YouTube blocks again.
