<div align="center">

# 🎵 Flake Music & Management System
**A powerful, production-ready Discord Bot and Web Dashboard for music and server management.**

[![Star on GitHub](https://img.shields.io/github/stars/sumanulto/Flake-Music?style=social)](https://github.com/sumanulto/Flake-Music)

⭐ **If you like this bot, please consider giving it a star on GitHub! It helps a lot!** ⭐

💖 **Donate**: If you want to support the ongoing development of Flake Music, you can donate at:  
[Insert Donation Link Here - Patreon / Ko-Fi / PayPal]

</div>

---

## 📑 Table of Contents
1. [Requirements](#-requirements)
2. [File Structure](#-file-structure)
3. [Setup Required (Local Dev)](#-setup-required-local-development)
4. [API Routes Overview](#-api-routes-overview)
5. [How to Setup Lavalink](#-how-to-exactly-setup-lavalink)
6. [Hosting the Backend](#-hosting-the-backend)
7. [Hosting the Frontend](#-hosting-the-frontend)
8. [CloudPanel + Node + PM2 Setup](#️-cloudpanel--node--pm2-setup-recommended)
9. [Database Sync & Migration](#️-database-sync--migration)
10. [Custom Emojis Configuration](#-custom-emojis-configuration)
11. [Common Issues](#️-common-issues)
---

## 🛠 Requirements
To host or develop Flake Music, you will need:
- **Node.js**: v20+ (for Frontend & Dashboard)
- **Python**: 3.11+ (for Backend API & Discord Bot)
- **Database**: PostgreSQL (NeonDB) and optionally MySQL.
- **Lavalink**: Java 17+ (If running Lavalink standalone without Docker)
- **Docker & Docker Compose**: (Optional, but recommended for simple deployment)
- **Process Manager**: PM2 (If running without Docker)
- **Discord Developer App**: Bot Token, Client ID, Client Secret, Redirect URI.

---

## 📁 File Structure
```text
flake-music/
├── backend/                  # FastAPI Backend & Discord Bot logic
│   ├── api/                  # REST API logic (FastAPI endpoints)
│   │   ├── routes/           # Auth, Music, Playlist, Guilds, etc.
│   │   └── dependencies.py   # FastAPI specific dependencies
│   ├── bot/                  # Discord.py bot logic, cogs, listeners
│   │   ├── cogs/             # Command modules (Music, Filters, Admin)
│   │   ├── core/             # Bot core event handling
│   │   └── wavelink_nodes.py # Lavalink integration wrapper
│   ├── database/             # SQLAlchemy Models and connection logic
│   ├── main.py               # Backend Entry Point (FastAPI + Bot)
│   └── requirements.txt      # Python dependencies
├── frontend/                 # Vite + React + Tailwind CSS Web Dashboard
│   ├── src/                  # React Components, Pages, State
│   │   ├── pages/            # Login, Dashboard, Settings, etc.
│   │   ├── components/       # Player components, Modals, UI Buttons
│   │   └── types/            # TypeScript interfaces
│   ├── package.json          # Node dependencies
│   └── vite.config.ts        # Vite build configuration
├── lavalink/                 # Lavalink Server specific configuration
│   └── application.yml       # Password, Port, and Node configs
├── .env                      # Global Environment Variables
├── docker-compose.yml        # Docker Deployment Configuration
└── README.md                 # Project Documentation
```

---

## 🚀 Setup Required (Local Development)

### 1. Environment Setup
Create a `.env` file in the root directory and copy the contents from `.env.example`. You **must** configure the following core variables for the bot to run:

**Discord Bot Setup**
- `DISCORD_TOKEN`: Your Discord bot token from the Developer Portal.
- `DISCORD_CLIENT_ID`: Your Application ID.
- `DISCORD_CLIENT_SECRET`: Your Application Secret.

**Database Setup**
- `DATABASE_URL`: If using PostgreSQL (e.g., NeonDB). Make sure `USE_NEON_DB=true`.
- `MYSQL_DATABASE_URL`: If using MySQL locally. Make sure `USE_MYSQL_DB=true`.
- *Note:* Do not leave both set to `true` permanently.

**Lavalink Setup**
- `LAVALINK_HOST`, `LAVALINK_PORT`, `LAVALINK_PASSWORD` must match your `lavalink/application.yml`.

**Dashboard Setup**
- `SECRET_KEY`: A secure random string for JWT sessions.
- `ADMIN_USER_ID`: Your Discord User ID (gives you access to the Superadmin Settings panel).
- `MOTHER_GUILD_ID`: The primary Discord server ID for your bot.

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
# The dashboard will be running at http://localhost:5173
```

---

## 🌐 API Routes Overview
The FastAPI backend acts as the bridge connecting the Web UI, Database, and Discord Bot.

- **`/auth/`**: `login`, `callback`, `logout` (Handles Discord OAuth2 and sessions).
- **`/users/@me`**: Fetches the currently authenticated user's info.
- **`/guilds/`**: Retrieves lists of Discord servers the user is in.
- **`/bot/`**: Routes mapping Bot state (e.g., active players, bot stats, allowing/disallowing guilds).
- **`/music/`**: Endpoints for queueing, pausing, skipping, volume control, and applying filters from the Web UI.
- **`/playlist/`**: Create, edit, list, delete, and add songs to custom bot playlists in the DB.
- **`/ws`**: Real-time websocket endpoint streaming player updates to the UI.

---

## 🎧 How to exactly Setup Lavalink

Lavalink handles all music processing and playback. Flake Music relies on specific Lavalink plugins to bypass YouTube restrictions and add Spotify support.

### Required Folder Structure
Whether using Docker or Standalone, ensure your `lavalink` directory looks like this:
```text
lavalink/
├── application.yml       # Primary configuration with your credentials
├── Lavalink.jar          # The executable (if standalone)
└── plugins/              # Automatically generated on first run
    ├── lavasrc-plugin-4.8.1.jar
    └── youtube-plugin-1.18.0.jar
```

### 🔑 Configuring Credentials (`application.yml`)
Before starting Lavalink, you **must** edit `lavalink/application.yml` and provide your API keys to prevent playback blocking.

#### 1. Spotify (Optional but Recommended)
For Spotify link support:
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Create an app to obtain a `Client ID` and `Client Secret`.
3. In `application.yml`, find the `spotify:` section and replace the placeholders:
   ```yaml
         spotify:
             clientId: "YOUR_SPOTIFY_CLIENT_ID"
             clientSecret: "YOUR_SPOTIFY_CLIENT_SECRET"
             countryCode: IN
   ```

#### 2. YouTube Authentication (Crucial)
YouTube actively blocks bot IPs from streaming. You need an OAuth token and a PoToken to bypass this.

**A. Generating an OAuth Refresh Token**
1. In `application.yml`, set `refreshToken: ""` under `youtube: oauth:`.
2. Start Lavalink (`java -jar Lavalink.jar` or via Docker).
3. Check the startup logs. It will provide a link (`https://www.google.com/device`) and a code.
4. **IMPORTANT:** Authorize the login using a **burner** Google account to prevent suspension risks.
5. Lavalink will print your permanent `refreshToken` (e.g. `1//0g...`). Paste it into `application.yml`.
   ```yaml
           oauth:
               enabled: true
               refreshToken: "1//0gxrX...paste_here"
   ```

**B. Generating a PoToken**
1. Install Node.js on your computer or server.
2. Run the token generator tool:
   ```bash
   npx -y youtube-po-token-generator
   ```
3. It will generate a `poToken` and `visitorData`. Paste them into the `pot:` section of `application.yml`:
   ```yaml
           pot:
               token: "YOUR_GENERATED_POTOKEN"
               visitorData: "YOUR_GENERATED_VISITORDATA"
   ```

### 🚀 Running Lavalink

#### Method 1: Using Docker (Recommended)
You can simply run:
```bash
docker-compose up -d lavalink
```
This automatically spins up Lavalink on your configured port (default `25566`) using `application.yml`.

#### Method 2: Standalone Installation
1. Ensure **Java 17+** is installed on your system.
2. Download the newest `Lavalink.jar` (v4+) from the [official releases](https://github.com/lavalink-devs/Lavalink/releases).
3. Place `Lavalink.jar` in your `lavalink/` directory.
4. Ensure your Discord bot's `.env` variables match the Lavalink connection details.
5. Run the server:
   ```bash
   java -jar Lavalink.jar
   ```

---

## ⚙️ Hosting the Backend

For production, run the backend API and Discord Bot utilizing a process manager like **PM2**.

1. Navigate to the project directory and setup Python Venv:
   ```bash
   python3 -m venv .venvs/flake
   source .venvs/flake/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Start the process using PM2 from the root directory ensuring `PYTHONPATH` points to the application root.
   ```bash
   pm2 start "/bin/bash -lc 'source .venvs/flake/bin/activate; export PYTHONPATH=$(pwd); uvicorn backend.main:app --host 127.0.0.1 --port 8000 --env-file .env'" --name flake-backend
   pm2 save
   ```

---

## 💻 Hosting the Frontend

1. Ensure your `.env.production` inside the `frontend` directory has the correct production URLs:
   ```env
   VITE_API_URL=https://botapi.yourdomain.com/api/v1
   VITE_WS_URL=wss://botapi.yourdomain.com/ws
   VITE_DISCORD_REDIRECT_URI=https://bot.yourdomain.com/auth/callback
   VITE_DISCORD_CLIENT_ID=YOUR_CLIENT_ID
   ```
2. Build the project:
   ```bash
   cd frontend
   npm install --include=dev
   npm run build
   ```
3. Serve the `dist` folder:
   ```bash
   # Run Node HTTP server locally with PM2
   pm2 start "npx serve -s dist -l 5173" --name flake-frontend
   pm2 save
   ```
   *Then point your reverse proxy to port `5173`.*

---

## ☁️ CloudPanel + Node + PM2 Setup (Recommended)

This specific setup works flawlessly using **CloudPanel** with separated Front-End Node App and Reverse Proxy setups.

### 1. CloudPanel configuration
- Create a **Node.js Site** on CloudPanel for the Frontend:
  - App Port: `5173`
  - Domain: `bot.yourdomain.com`
  - Site User: `kraftamine-bot`
- Create a **Reverse Proxy Site** for the Backend:
  - Target: `http://127.0.0.1:8000`
  - Domain: `botapi.yourdomain.com`
- Enable SSL on both domains.

### 2. Prepare Code on the Server
SSH into the server as your Node Site User (e.g. `kraftamine-bot`):
```bash
sudo su - kraftamine-bot
cd /home/kraftamine-bot/
git clone <YOUR_REPO> flake-music
cd flake-music
```

### 3. Setup Python Backend
```bash
python3 -m venv /home/kraftamine-bot/.venvs/flake
source /home/kraftamine-bot/.venvs/flake/bin/activate
pip install -r backend/requirements.txt
```
Populate `/home/kraftamine-bot/flake-music/.env` with your production runtime variables. Then launch it with PM2:
```bash
pm2 start "/bin/bash -lc 'source /home/kraftamine-bot/.venvs/flake/bin/activate; export PYTHONPATH=/home/kraftamine-bot/flake-music; cd /home/kraftamine-bot/flake-music; uvicorn backend.main:app --host 127.0.0.1 --port 8000 --env-file /home/kraftamine-bot/flake-music/.env'" --name flake-backend-bot
pm2 save
```

### 4. Build and Run Frontend
```bash
cd /home/kraftamine-bot/flake-music/frontend
# Edit .env.production with your botapi domains and correct redirect URIs
npm install
npm run build
```
Run the frontend via PM2:
```bash
pm2 start "npx serve -s dist -l 5173" --name flake-frontend --cwd /home/kraftamine-bot/flake-music/frontend
pm2 save
```

Once both PM2 apps are running `(flake-backend-bot & flake-frontend)`, your bot is fully deployed!

---

## 🗄️ Database Sync & Migration

Flake Music supports connecting to both a NeonDB (PostgreSQL) and a local MySQL database. However, **do not run the bot with both databases enabled permanently** as it can create data redundancy and bot lag.

**If you need to migrate/sync data between them:**
1. Keep the destination database completely **empty** before syncing, or else data will get merged.
2. In your `.env`, set both to true temporarily:
   ```env
   USE_NEON_DB=true
   USE_MYSQL_DB=true
   ```
3. Start the bot. The backend will initialize both schemas and sync tables/data.
4. Once synced, shut down the bot.
5. In your `.env`, set the database you want to use to `true` and the other to `false`.
6. Reboot the bot to run using your single selected database.

---

## ✨ Custom Emojis Configuration

Flake Music supports using custom emojis for player controller buttons (Play, Pause, Skip, etc.), the new "💖 Like" button, and queue source icons (YouTube, Spotify) to personalize your bot's look.

### How to Add Custom Emojis
1. **Upload Emojis to Your Server:** Upload your desired custom emojis to a Discord server where your bot is present (e.g., your designated support or host server).
2. **Get the Emoji IDs:** Type `\:emoji_name:` in Discord chat (e.g., `\:spotify:` or `\:favourite:`) and press enter. Discord will output a raw string that looks like `<:spotify:1476099462463230116>`.
3. **Copy the String:** Copy that entire `<:name:id>` string.

### Updating `.env`
Open your `.env` file and locate the **Custom Emojis** section.
- To enable custom player buttons, set `USE_CUSTOM_EMOJIS_PLAYER=true`.
- To enable custom queue source icons, set `USE_CUSTOM_EMOJIS_ICON=true`.
- Paste your copied strings into their respective variables.

```env
# Custom Emojis Configuration
USE_CUSTOM_EMOJIS_PLAYER=true
EMOJI_PLAY=<:playbutton:1234567890>
EMOJI_PAUSE=<:pausebutton:1234567890>
EMOJI_STOP=<:stopbutton:1234567890>
EMOJI_NEXT=<:fastforwardbutton:1234567890>
EMOJI_PREV=<:fastbackward:1234567890>
EMOJI_VOL_UP=<:volumeup:1234567890>
EMOJI_VOL_DOWN=<:volumedown:1234567890>
EMOJI_LOOP_OFF=<:repeatnone:1234567890>
EMOJI_LOOP_ALL=<:repeatall:1234567890>
EMOJI_LOOP_ONE=<:repeatone:1234567890>
EMOJI_SHUFFLE=<:shuffle:1234567890>
EMOJI_LIKE=<:favourite:1234567890>

USE_CUSTOM_EMOJIS_ICON=true
EMOJI_YOUTUBE=<:youtube:1234567890>
EMOJI_SPOTIFY=<:spotify:1234567890>
```
*Note: The bot account **must** be a member of the server where these emojis were uploaded to be able to use them.*

---

## ⚠️ Common Issues

- **Always Check Lavalink Logs First**: Most bot playback issues arise from Lavalink blockages. If a track isn't playing, check your Lavalink terminal/logs.
- **Public Lavalink Hosts**: Using public Lavalink hosts might not work, as many do not configure YouTube bypasses clearly. Hence, most problems you will face will be with YouTube-related links. Flake Music tries to eliminate these issues in many ways, but still, many things are unsuccessful due to aggressive YouTube policies.
- **Database Redundancy/Lag**: Ensure you only have `USE_NEON_DB=true` or `USE_MYSQL_DB=true` set, not both at the same time for normal operation.
- **YouTube "Sign in to confirm you’re not a bot"**: You are being blocked by YouTube. Please use the OAuth and PoToken setup described in the Lavalink section to bypass this.
- **WebSocket Fails on Frontend**: Ensure `VITE_WS_URL` is set correctly and `wss://` is used in production.
- **ModuleNotFoundError: No module named backend**: Make sure you are running the backend using `uvicorn backend.main:app` from the *root* folder, with `PYTHONPATH` set to the root directory.

---

## 🚨 Security Warnings & Disclaimer

- **Keep Your `.env` Secret**: Ensure your `.env` variables are never shared or committed publicly. If these tokens are exposed, malicious users can hijack your bot and server!
- **Do Not Tamper**: Try not to tamper with the bot's security or token management if you are not experienced.
- **Proper Lavalink Setup**: Please make sure to follow the Lavalink configuration guide perfectly so that external access is secure.
- **Disclaimer**: **Kraftamine is not responsible in any terms** for server hacks, data breaches, or bot hijacking resulting from exposed `.env` files or improperly secured setups. Host at your own risk!
