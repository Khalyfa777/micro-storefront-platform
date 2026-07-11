# Deployment Values Template

Fill this before deploying.

## Domains

Backend API domain:

api.example.com

Merchant dashboard domain:

dashboard.example.com

Public storefront domain:

example.com

## Backend production env

DATABASE_URL=postgresql+asyncpg://storefront_user:STRONG_DB_PASSWORD@postgres:5432/storefront_prod
REDIS_URL=redis://redis:6379/0

SECRET_KEY=GENERATE_LONG_RANDOM_SECRET

ENVIRONMENT=production

FRONTEND_URL=https://example.com
BACKEND_PUBLIC_URL=https://api.example.com
CORS_ORIGINS=https://dashboard.example.com,https://example.com

PAYSTACK_SECRET_KEY=LIVE_PAYSTACK_SECRET_KEY
PAYSTACK_PUBLIC_KEY=LIVE_PAYSTACK_PUBLIC_KEY
PAYSTACK_WEBHOOK_SECRET=LIVE_PAYSTACK_SECRET_KEY

JWT_ACCESS_EXPIRE_MINUTES=30
TRIAL_DAYS=14

## Dashboard production env

VITE_API_URL=https://api.example.com/api/v1
VITE_SUPPORT_WHATSAPP=233544193559

## Storefront production env

NEXT_PUBLIC_API_URL=https://api.example.com/api/v1

## Paystack URLs

Callback URL:

https://example.com/payment/processing

Webhook URL:

https://api.example.com/api/v1/payments/webhook/paystack

## Server checklist

- Docker installed
- Docker Compose installed
- Git installed
- Domain DNS pointed to server
- HTTPS configured
- backend/.env.production created on server only
- Run alembic upgrade head
- Confirm /health returns status ok and database ok

## Final launch test

- Dashboard login works
- Public storefront loads
- Customer can create order
- Manual payment deducts stock
- Paystack payment deducts stock once
- Cancel paid order restores stock
- Subscription expiry blocks public order
- Admin extension works