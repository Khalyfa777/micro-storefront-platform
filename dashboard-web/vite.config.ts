import {
  defineConfig,
  loadEnv,
} from "vite";
import react from "@vitejs/plugin-react";

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

function validateProductionApiUrl(
  value: string,
): void {
  let parsed: URL;

  try {
    parsed = new URL(value);
  }
  catch {
    throw new Error(
      "VITE_API_URL must be an absolute HTTPS URL.",
    );
  }

  if (parsed.protocol !== "https:") {
    throw new Error(
      "VITE_API_URL must use HTTPS for production builds.",
    );
  }

  if (
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "VITE_API_URL must not contain credentials.",
    );
  }

  if (
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "VITE_API_URL must not contain a query string or fragment.",
    );
  }

  const normalizedPath =
    parsed.pathname.replace(
      /\/+$/,
      "",
    );

  if (normalizedPath !== "/api/v1") {
    throw new Error(
      "VITE_API_URL must end with /api/v1.",
    );
  }

  if (parsed.port) {
    throw new Error(
      "VITE_API_URL must not use a custom port in production.",
    );
  }

  if (
    isLocalOrPrivateHostname(
      parsed.hostname,
    )
  ) {
    throw new Error(
      "VITE_API_URL must use a publicly routable production hostname.",
    );
  }
}

function validateProductionPublicStoreUrl(
  value: string,
): void {
  let parsed: URL;

  try {
    parsed = new URL(value);
  }
  catch {
    throw new Error(
      "VITE_PUBLIC_STORE_URL must be an absolute HTTPS URL.",
    );
  }

  if (parsed.protocol !== "https:") {
    throw new Error(
      "VITE_PUBLIC_STORE_URL must use HTTPS for production builds.",
    );
  }

  if (
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "VITE_PUBLIC_STORE_URL must not contain credentials.",
    );
  }

  if (
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "VITE_PUBLIC_STORE_URL must not contain a query string or fragment.",
    );
  }

  if (
    parsed.pathname !== "/" &&
    parsed.pathname !== ""
  ) {
    throw new Error(
      "VITE_PUBLIC_STORE_URL must point to the storefront domain root.",
    );
  }

  if (parsed.port) {
    throw new Error(
      "VITE_PUBLIC_STORE_URL must not use a custom port in production.",
    );
  }

  if (
    isLocalOrPrivateHostname(
      parsed.hostname,
    )
  ) {
    throw new Error(
      "VITE_PUBLIC_STORE_URL must use a publicly routable production hostname.",
    );
  }
}

export default defineConfig(
  ({ mode }) => {
    const environment = loadEnv(
      mode,
      process.cwd(),
      "",
    );

    if (mode === "production") {
      const apiUrl =
        process.env.VITE_API_URL ??
        environment.VITE_API_URL;

      if (!apiUrl?.trim()) {
        throw new Error(
          "VITE_API_URL is required for dashboard production builds.",
        );
      }

      validateProductionApiUrl(
        apiUrl.trim(),
      );

      const publicStoreUrl =
        process.env.VITE_PUBLIC_STORE_URL ??
        environment.VITE_PUBLIC_STORE_URL;

      if (!publicStoreUrl?.trim()) {
        throw new Error(
          "VITE_PUBLIC_STORE_URL is required for dashboard production builds.",
        );
      }

      validateProductionPublicStoreUrl(
        publicStoreUrl.trim(),
      );
    }

    return {
      plugins: [react()],
    };
  },
);