# StorePlug Deployment

## Persistent media storage

The backend serves managed seller media from:

```text
/app/static/uploads
```

Production must mount that path on durable persistent storage. Container-local
ephemeral storage is not acceptable because a rebuild or replacement would
remove seller logos, banners, and product images.

Back up the media volume independently from PostgreSQL. A database restore and
media restore must use compatible restore points so stored image URLs do not
reference missing files.

## Upload request limits

The application enforces a hard request-body limit with
`MAX_REQUEST_BODY_BYTES`. The reverse proxy must enforce the same limit or a
slightly smaller one before forwarding traffic.

For Nginx, use a value equivalent to:

```nginx
client_max_body_size 5m;
```

Do not configure the proxy with a materially larger upload limit than the API.

The image-specific settings are:

```text
IMAGE_UPLOAD_MAX_BYTES
IMAGE_UPLOAD_STORE_QUOTA_BYTES
IMAGE_UPLOAD_ORPHAN_TTL_SECONDS
IMAGE_UPLOAD_RATE_LIMIT_ATTEMPTS
IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS
```

Redis must be available in production for distributed upload throttling. The
bounded in-process limiter is a resilience fallback, not the primary production
rate limiter.

## Release checks

Before deploying an upload change:

1. Run the focused image-upload safety tests.
2. Run the full backend test suite.
3. Build and lint the dashboard.
4. Confirm no base64 upload payload remains in dashboard or backend source.
5. Confirm the production media volume is mounted and writable.
6. Confirm the reverse-proxy request limit matches the application limit.
