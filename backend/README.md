# Micro Storefront Backend - Phase 1

## Run locally

```bash
cd storefront_platform
cp backend/.env.example backend/.env
docker compose up -d postgres redis
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## First test flow

1. `POST /api/v1/auth/register`
2. Copy access token.
3. Authorize in Swagger with `Bearer <token>`.
4. `POST /api/v1/stores/`
5. `POST /api/v1/stores/{store_id}/products/`
6. Visit `GET /api/v1/public/stores/{slug}`
