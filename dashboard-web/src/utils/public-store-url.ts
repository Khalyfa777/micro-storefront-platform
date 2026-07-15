const CANONICAL_PUBLIC_STORE_URL =
  "https://storeplughq.com";

const STORE_SLUG_PATTERN =
  /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

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

export function isLocalOrPrivateHostname(
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

export function normalizePublicStoreBaseUrl(
  value: string,
): string {
  const trimmed = value.trim();

  if (!trimmed) {
    throw new Error(
      "Public-store URL cannot be empty.",
    );
  }

  let parsed: URL;

  try {
    parsed = new URL(trimmed);
  }
  catch {
    throw new Error(
      "Public-store URL must be an absolute HTTP or HTTPS URL.",
    );
  }

  if (
    parsed.protocol !== "http:" &&
    parsed.protocol !== "https:"
  ) {
    throw new Error(
      "Public-store URL must use HTTP or HTTPS.",
    );
  }

  if (
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "Public-store URL must not contain credentials.",
    );
  }

  if (
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "Public-store URL must not contain a query string or fragment.",
    );
  }

  if (
    parsed.pathname !== "/" &&
    parsed.pathname !== ""
  ) {
    throw new Error(
      "Public-store URL must point to the storefront domain root.",
    );
  }

  return parsed.origin;
}

export function resolvePublicStoreBaseUrl():
  string {
  const configured =
    import.meta.env.VITE_PUBLIC_STORE_URL
      ?.trim();

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

  if (configured) {
    const normalized =
      normalizePublicStoreBaseUrl(
        configured,
      );

    const configuredUrl =
      new URL(normalized);

    if (
      !runtimeIsLocal &&
      (
        configuredUrl.protocol !==
          "https:" ||
        isLocalOrPrivateHostname(
          configuredUrl.hostname,
        )
      )
    ) {
      return CANONICAL_PUBLIC_STORE_URL;
    }

    return normalized;
  }

  if (
    import.meta.env.DEV &&
    typeof window !== "undefined"
  ) {
    return normalizePublicStoreBaseUrl(
      `${window.location.protocol}//${window.location.hostname}:3000`,
    );
  }

  return CANONICAL_PUBLIC_STORE_URL;
}

export function buildPublicStoreUrl(
  baseUrl: string,
  storeSlug: string,
): string {
  const normalizedBase =
    normalizePublicStoreBaseUrl(baseUrl);

  const normalizedSlug = storeSlug
    .trim()
    .replace(/^\/+|\/+$/g, "")
    .toLowerCase();

  if (
    !STORE_SLUG_PATTERN.test(
      normalizedSlug,
    )
  ) {
    throw new Error(
      "Cannot open a public store with an invalid slug.",
    );
  }

  return new URL(
    encodeURIComponent(normalizedSlug),
    `${normalizedBase}/`,
  ).toString();
}