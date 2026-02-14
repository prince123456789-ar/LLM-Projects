# RealEstateAI SaaS (Lead Ops + AI Routing)

This repo contains a production-oriented FastAPI backend plus a single-port web UI served directly by the backend (no Node/Next required to run locally).

## Local Run (No Docker, One Port)

1. Create backend venv and install deps:

```powershell
py -3.12 -m venv saas/backend/.venv
saas/backend/.venv/Scripts/python.exe -m pip install -r saas/backend/requirements.txt
```

2. Create env file:

```powershell
Copy-Item saas/.env.example saas/.env -Force
Copy-Item saas/.env saas/backend/.env -Force
```

3. Start the app (UI + API) and seed demo users:

```powershell
PowerShell -NoProfile -ExecutionPolicy Bypass -File saas/scripts/start-local.ps1 -SeedDemoUsers
```

Open:

- UI: `http://localhost:8000/`
- Health: `http://127.0.0.1:8000/health`
- API base: `http://127.0.0.1:8000/api/v1`

Demo users (seeded by `saas/backend/app/bootstrap.py`):

- `admin@agency.com` / `Admin@12345!secure`
- `manager@agency.com` / `Manager@12345!secure`
- `agent@agency.com` / `Agent@12345!secure`

## Notes

- The backend reads `saas/backend/.env`. Unknown env vars are ignored so the same `.env` can include provider placeholders.
- API docs are disabled by default (`ENABLE_API_DOCS=false`). Enable explicitly if needed.
