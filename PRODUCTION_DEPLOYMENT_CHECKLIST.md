# Micro Storefront Platform — Production Deployment Checklist

## Backend required production env

DATABASE_URL=
REDIS_URL=
SECRET_KEY=
ENVIRONMENT=production
FRONTEND_URL=
BACKEND_PUBLIC_URL=
CORS_ORIGINS=
PAYSTACK_SECRET_KEY=
PAYSTACK_PUBLIC_KEY=
PAYSTACK_WEBHOOK_SECRET=
JWT_ACCESS_EXPIRE_MINUTES=30
TRIAL_DAYS=14

## Dashboard required production env

VITE_API_URL=
VITE_SUPPORT_WHATSAPP=

## Storefront required production env

NEXT_PUBLIC_API_URL=

## Production database rules

Fresh production DB:
alembic upgrade head

Existing local/dev DB:
alembic stamp head

Never rely on create_all in production.

## Production deployment rules

- Do not upload backend/.env to GitHub.
- Do not upload dashboard-web/.env.local.
- Do not upload storefront-web/.env.local.
- Use live Paystack keys only in the hosting platform secret/env settings.
- Use HTTPS URLs only for FRONTEND_URL, BACKEND_PUBLIC_URL, CORS_ORIGINS, VITE_API_URL, and NEXT_PUBLIC_API_URL.
- Upload storage is currently local disk. Use persistent volume or object storage before serious production traffic.
- Run backend behind HTTPS.
- Confirm /health returns {"status":"ok","database":"ok"}.
- Confirm Paystack callback URL points to:
  FRONTEND_URL/payment/processing
- Confirm Paystack webhook URL points to:
  BACKEND_PUBLIC_URL/api/v1/payments/webhook/paystack

## Final pre-launch checks

1. Register merchant.
2. Confirm new store gets trial_ends_at.
3. Add product.
4. Create order.
5. Manual paid order deducts inventory and shows Manual.
6. Paystack paid order deducts inventory once and shows Paystack.
7. Cancel paid order restores stock.
8. Expired/suspended store blocks public ordering.
9. Disabled online payments hides Pay Now.
10. Disabled image upload blocks upload in dashboard and backend.
11. Product limit blocks extra active products.
12. Admin can extend subscription.
13. Admin can change plan.
14. Dashboard build passes.
15. Storefront build passes.
16. Backend compile passes.