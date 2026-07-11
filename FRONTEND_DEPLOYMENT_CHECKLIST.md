# Frontend Deployment Checklist

## Dashboard

App folder:

dashboard-web

Required production env:

VITE_API_URL=https://your-api-domain.com/api/v1
VITE_SUPPORT_WHATSAPP=233544193559

Build command:

npm ci
npm run build

Output folder:

dist

Important checks:

- VITE_API_URL must point to the backend API `/api/v1`.
- Do not use localhost in production.
- Do not commit dashboard-web/.env.local or dashboard-web/.env.production.
- Dashboard domain must be included in backend CORS_ORIGINS.

Example:

VITE_API_URL=https://api.yourdomain.com/api/v1

## Storefront

App folder:

storefront-web

Required production env:

NEXT_PUBLIC_API_URL=https://your-api-domain.com/api/v1

Build command:

npm ci
npm run build

Important checks:

- NEXT_PUBLIC_API_URL must point to the backend API `/api/v1`.
- Do not use localhost in production.
- Do not commit storefront-web/.env.local or storefront-web/.env.production.
- Storefront domain must be included in backend CORS_ORIGINS.
- Paystack callback should land on:
  https://your-storefront-domain.com/payment/processing

Example:

NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1

## Backend CORS example

CORS_ORIGINS=https://dashboard.yourdomain.com,https://your-storefront-domain.com

## Recommended domain structure

Backend API:

api.yourdomain.com

Merchant dashboard:

dashboard.yourdomain.com

Public storefront:

yourdomain.com

## Pre-launch frontend tests

1. Dashboard login works.
2. Dashboard loads stores.
3. Dashboard loads products.
4. Dashboard image upload works if plan allows it.
5. Dashboard blocks image upload if plan disables it.
6. Dashboard order buttons only show valid next actions.
7. Dashboard shows Manual or Paystack badge on paid orders.
8. Storefront public page loads.
9. Storefront product order page loads.
10. Storefront hides Pay Now if online payments are disabled.
11. Payment processing page links back to the correct store slug.
12. Tracking page works.