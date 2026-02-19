# Flake Music & Management System

A production-ready Discord Bot and Web Dashboard for music management.

## Features
- **Discord Bot**: Slash commands, Lavalink music playback, per-guild queues.
- **Web Dashboard**: React + Vite + TailwindCSS. Manage music via the web.
- **Real-time Sync**: WebSockets for instant player state updates.
- **Dockerized**: Full stack deployment with Docker Compose.

## Prerequisites
- Docker & Docker Compose
- Discord Application (Bot Token, Client ID, Client Secret)
- Node.js 20+ (for local dev)
- Python 3.11+ (for local dev)

## Setup

1. **Clone the repository**
2. **Create .env file**
   Copy `.env.example` to `.env` and fill in your credentials.
   ```bash
   cp .env.example .env
   ```
   
   *Note: Ensure your Discord App Redirect URI is set to `http://localhost:5173/auth/callback`*

3. **Run with Docker**
   ```bash
   docker-compose up --build
   ```
   
   - Frontend: http://localhost:80
   - Backend API: http://localhost:8000
   - Lavalink: http://localhost:2333

## Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Architecture
- `backend/`: FastAPI + Discord.py
- `frontend/`: React + Vite
- `lavalink/`: Lavalink Server Config
- `docker-compose.yml`: Orchestration
