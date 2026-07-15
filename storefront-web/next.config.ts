import type {
  NextConfig,
} from "next";

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
      "NEXT_PUBLIC_API_URL must be an absolute HTTPS URL.",
    );
  }

  if (parsed.protocol !== "https:") {
    throw new Error(
      "NEXT_PUBLIC_API_URL must use HTTPS for production builds.",
    );
  }

  if (
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "NEXT_PUBLIC_API_URL must not contain credentials.",
    );
  }

  if (
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "NEXT_PUBLIC_API_URL must not contain a query string or fragment.",
    );
  }

  const normalizedPath =
    parsed.pathname.replace(
      /\/+$/,
      "",
    );

  if (normalizedPath !== "/api/v1") {
    throw new Error(
      "NEXT_PUBLIC_API_URL must end with /api/v1.",
    );
  }

  if (parsed.port) {
    throw new Error(
      "NEXT_PUBLIC_API_URL must not use a custom port in production.",
    );
  }

  if (
    isLocalOrPrivateHostname(
      parsed.hostname,
    )
  ) {
    throw new Error(
      "NEXT_PUBLIC_API_URL must use a publicly routable production hostname.",
    );
  }
}

if (
  process.env.NODE_ENV === "production"
) {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL
      ?.trim();

  if (!apiUrl) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is required for storefront production builds.",
    );
  }

  validateProductionApiUrl(apiUrl);
}

const nextConfig: NextConfig = {};

export default nextConfig;