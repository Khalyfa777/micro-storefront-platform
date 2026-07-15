const IDEMPOTENCY_STORAGE_PREFIX =
  "storeplug.idempotency.";

const IDEMPOTENCY_ATTEMPT_MAX_AGE_MS =
  24 * 60 * 60 * 1000;

type StoredIdempotencyAttempt = {
  idempotencyKey: string;
  createdAt: number;
};

export type PersistentIdempotencyAttempt = {
  idempotencyKey: string;
  storageKey: string | null;
};

export function createIdempotencyKey(
  prefix = "request",
): string {
  const randomUuid =
    globalThis.crypto?.randomUUID?.();

  if (randomUuid) {
    return `${prefix}-${randomUuid}`;
  }

  const randomPart = Math.random()
    .toString(36)
    .slice(2);

  return [
    prefix,
    Date.now().toString(36),
    randomPart,
  ].join("-");
}

function getPersistentStorage():
  Storage | null {
  try {
    return globalThis.localStorage ??
      null;
  }
  catch {
    return null;
  }
}

function fallbackFingerprintHash(
  value: string,
): string {
  let first = 0x811c9dc5;
  let second = 0x9e3779b9;

  for (
    let index = 0;
    index < value.length;
    index += 1
  ) {
    const code = value.charCodeAt(
      index,
    );

    first ^= code;
    first = Math.imul(
      first,
      0x01000193,
    );

    second ^= (
      code +
      index
    );
    second = Math.imul(
      second,
      0x85ebca6b,
    );
  }

  return [
    (first >>> 0)
      .toString(16)
      .padStart(8, "0"),
    (second >>> 0)
      .toString(16)
      .padStart(8, "0"),
    value.length.toString(16),
  ].join("");
}

async function fingerprintHash(
  value: string,
): Promise<string> {
  try {
    if (
      globalThis.crypto?.subtle &&
      typeof TextEncoder !== "undefined"
    ) {
      const digest =
        await globalThis.crypto
          .subtle
          .digest(
            "SHA-256",
            new TextEncoder()
              .encode(value),
          );

      return Array.from(
        new Uint8Array(digest),
      )
        .map((byte) =>
          byte
            .toString(16)
            .padStart(2, "0"),
        )
        .join("");
    }
  }
  catch {
    // Fall back to a deterministic,
    // non-sensitive storage key.
  }

  return fallbackFingerprintHash(value);
}

function parseStoredAttempt(
  value: string | null,
): StoredIdempotencyAttempt | null {
  if (!value) {
    return null;
  }

  try {
    const parsed = JSON.parse(
      value,
    ) as Partial<StoredIdempotencyAttempt>;

    if (
      typeof parsed.idempotencyKey
        !== "string" ||
      parsed.idempotencyKey.length < 16 ||
      typeof parsed.createdAt
        !== "number" ||
      !Number.isFinite(
        parsed.createdAt,
      )
    ) {
      return null;
    }

    return {
      idempotencyKey:
        parsed.idempotencyKey,
      createdAt: parsed.createdAt,
    };
  }
  catch {
    return null;
  }
}

function removeExpiredAttempts(
  storage: Storage,
  now: number,
): void {
  const keysToRemove: string[] = [];

  for (
    let index = 0;
    index < storage.length;
    index += 1
  ) {
    const key = storage.key(index);

    if (
      !key?.startsWith(
        IDEMPOTENCY_STORAGE_PREFIX,
      )
    ) {
      continue;
    }

    const attempt =
      parseStoredAttempt(
        storage.getItem(key),
      );

    if (
      !attempt ||
      now - attempt.createdAt >
        IDEMPOTENCY_ATTEMPT_MAX_AGE_MS
    ) {
      keysToRemove.push(key);
    }
  }

  keysToRemove.forEach((key) => {
    storage.removeItem(key);
  });
}

export async function
getOrCreatePersistentIdempotencyAttempt(
  scope: string,
  fingerprint: string,
  prefix = scope,
): Promise<PersistentIdempotencyAttempt> {
  const idempotencyKey =
    createIdempotencyKey(prefix);

  const storage =
    getPersistentStorage();

  if (!storage) {
    return {
      idempotencyKey,
      storageKey: null,
    };
  }

  const now = Date.now();

  try {
    removeExpiredAttempts(
      storage,
      now,
    );

    const hash =
      await fingerprintHash(
        `${scope}:${fingerprint}`,
      );

    const storageKey = [
      IDEMPOTENCY_STORAGE_PREFIX,
      scope,
      ".",
      hash,
    ].join("");

    const existing =
      parseStoredAttempt(
        storage.getItem(
          storageKey,
        ),
      );

    if (
      existing &&
      now - existing.createdAt <=
        IDEMPOTENCY_ATTEMPT_MAX_AGE_MS
    ) {
      return {
        idempotencyKey:
          existing.idempotencyKey,
        storageKey,
      };
    }

    const storedAttempt:
      StoredIdempotencyAttempt = {
        idempotencyKey,
        createdAt: now,
      };

    storage.setItem(
      storageKey,
      JSON.stringify(
        storedAttempt,
      ),
    );

    return {
      idempotencyKey,
      storageKey,
    };
  }
  catch {
    return {
      idempotencyKey,
      storageKey: null,
    };
  }
}

export function
clearPersistentIdempotencyAttempt(
  storageKey: string | null,
): void {
  if (!storageKey) {
    return;
  }

  const storage =
    getPersistentStorage();

  if (!storage) {
    return;
  }

  try {
    storage.removeItem(
      storageKey,
    );
  }
  catch {
    // Storage cleanup is best effort.
  }
}