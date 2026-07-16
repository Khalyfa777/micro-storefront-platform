import {
  isLocalOrPrivateHostname,
} from "./public-store-url";

const CANONICAL_DASHBOARD_API_URL =
  "https://api.storeplughq.com/api/v1";

export function normalizeDashboardApiBaseUrl(
  value: string,
): string {
  const trimmed = value.trim();

  if (!trimmed) {
    throw new Error(
      "Dashboard API URL cannot be empty.",
    );
  }

  let parsed: URL;

  try {
    parsed = new URL(trimmed);
  }
  catch {
    throw new Error(
      "Dashboard API URL must be an absolute HTTP or HTTPS URL.",
    );
  }

  if (
    parsed.protocol !== "http:" &&
    parsed.protocol !== "https:"
  ) {
    throw new Error(
      "Dashboard API URL must use HTTP or HTTPS.",
    );
  }

  if (
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "Dashboard API URL must not contain credentials.",
    );
  }

  if (
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "Dashboard API URL must not contain a query string or fragment.",
    );
  }

  const normalizedPath =
    parsed.pathname.replace(
      /\/+$/,
      "",
    );

  if (normalizedPath !== "/api/v1") {
    throw new Error(
      "Dashboard API URL must end with /api/v1.",
    );
  }

  return `${parsed.origin}/api/v1`;
}

export function resolveDashboardApiBaseUrl():
  string {
  const configured =
    import.meta.env.VITE_API_URL
      ?.trim();

  if (!configured) {
    if (import.meta.env.DEV) {
      throw new Error(
        "VITE_API_URL is required for dashboard development.",
      );
    }

    return CANONICAL_DASHBOARD_API_URL;
  }

  const normalized =
    normalizeDashboardApiBaseUrl(
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
      : import.meta.env.DEV;

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
    return CANONICAL_DASHBOARD_API_URL;
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

export function resolveDashboardMediaUrl(
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
    resolveDashboardApiBaseUrl(),
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

export function toPortableDashboardMediaReference(
  raw?: string | null,
): string {
  const value = String(
    raw ?? "",
  ).trim();

  if (!value) {
    return "";
  }

  const relativeManagedPath =
    getManagedMediaPath(value);

  if (relativeManagedPath) {
    return relativeManagedPath;
  }

  let parsed: URL;

  try {
    parsed = new URL(value);
  }
  catch {
    return value;
  }

  const apiOrigin = new URL(
    resolveDashboardApiBaseUrl(),
  ).origin;

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
    return managedPath;
  }

  return value;
}
