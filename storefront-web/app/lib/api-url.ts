const CANONICAL_STOREFRONT_API_URL =
  "https://api.storeplughq.com/api/v1";

function isPrivateIpv4(
  hostname: string,
): boolean {
  const octets = hostname
    .split(".")
    .map((part) => Number(part));

  if (
    octets.length !== 4 ||
    octets.some(
      (octet) =>
        !Number.isInteger(octet) ||
        octet < 0 ||
        octet > 255,
    )
  ) {
    return false;
  }

  const [first, second] = octets;

  return (
    first === 10 ||
    first === 127 ||
    (
      first === 169 &&
      second === 254
    ) ||
    (
      first === 172 &&
      second >= 16 &&
      second <= 31
    ) ||
    (
      first === 192 &&
      second === 168
    )
  );
}

function isLocalOrPrivateHostname(
  hostname: string,
): boolean {
  const normalized =
    hostname.trim().toLowerCase();

  return (
    normalized === "localhost" ||
    normalized === "0.0.0.0" ||
    normalized === "::1" ||
    normalized.endsWith(".local") ||
    isPrivateIpv4(normalized)
  );
}

export function normalizeStorefrontApiBaseUrl(
  value: string,
): string {
  const trimmed = value.trim();

  if (!trimmed) {
    throw new Error(
      "Storefront API URL cannot be empty.",
    );
  }

  let parsed: URL;

  try {
    parsed = new URL(trimmed);
  }
  catch {
    throw new Error(
      "Storefront API URL must be an absolute HTTP or HTTPS URL.",
    );
  }

  if (
    parsed.protocol !== "http:" &&
    parsed.protocol !== "https:"
  ) {
    throw new Error(
      "Storefront API URL must use HTTP or HTTPS.",
    );
  }

  if (
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "Storefront API URL must not contain credentials.",
    );
  }

  if (
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "Storefront API URL must not contain a query string or fragment.",
    );
  }

  const normalizedPath =
    parsed.pathname.replace(
      /\/+$/,
      "",
    );

  if (normalizedPath !== "/api/v1") {
    throw new Error(
      "Storefront API URL must end with /api/v1.",
    );
  }

  return `${parsed.origin}/api/v1`;
}

export function resolveStorefrontApiBaseUrl():
  string {
  const configured =
    process.env.NEXT_PUBLIC_API_URL
      ?.trim();

  if (!configured) {
    if (
      process.env.NODE_ENV !==
      "production"
    ) {
      throw new Error(
        "NEXT_PUBLIC_API_URL is required for storefront development.",
      );
    }

    return CANONICAL_STOREFRONT_API_URL;
  }

  const normalized =
    normalizeStorefrontApiBaseUrl(
      configured,
    );

  const runtimeHostname =
    typeof window === "undefined"
      ? ""
      : window.location.hostname;

  const runtimeIsLocal =
    runtimeHostname
      ? isLocalOrPrivateHostname(
          runtimeHostname,
        )
      : process.env.NODE_ENV !==
          "production";

  const parsed = new URL(normalized);

  if (
    !runtimeIsLocal &&
    (
      parsed.protocol !== "https:" ||
      isLocalOrPrivateHostname(
        parsed.hostname,
      )
    )
  ) {
    return CANONICAL_STOREFRONT_API_URL;
  }

  return normalized;
}

const MANAGED_MEDIA_PATH_PREFIXES = [
  "/static/uploads/",
  "/uploads/",
];

function getManagedMediaPath(
  value: string,
): string {
  const trimmed = value.trim();

  if (
    MANAGED_MEDIA_PATH_PREFIXES.some(
      (prefix) =>
        trimmed.startsWith(prefix),
    )
  ) {
    return trimmed;
  }

  return "";
}

export function resolveStorefrontMediaUrl(
  raw?: string | null,
): string {
  const value = String(
    raw ?? "",
  ).trim();

  if (
    !value ||
    value === "null" ||
    value === "undefined"
  ) {
    return "";
  }

  if (value.startsWith("data:image/")) {
    return value;
  }

  const apiOrigin = new URL(
    resolveStorefrontApiBaseUrl(),
  ).origin;

  const relativeManagedPath =
    getManagedMediaPath(value);

  if (relativeManagedPath) {
    return apiOrigin + relativeManagedPath;
  }

  let parsed: URL;

  try {
    parsed = new URL(value);
  }
  catch {
    return "";
  }

  if (
    parsed.protocol !== "http:" &&
    parsed.protocol !== "https:"
  ) {
    return "";
  }

  const managedPath =
    getManagedMediaPath(
      parsed.pathname,
    );

  if (
    managedPath &&
    (
      parsed.origin === apiOrigin ||
      isLocalOrPrivateHostname(
        parsed.hostname,
      )
    )
  ) {
    return apiOrigin + managedPath;
  }

  return parsed.toString();
}
