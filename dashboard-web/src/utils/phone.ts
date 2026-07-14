const MULTIPLE_NUMBER_SEPARATORS = /[/,;&]/;
const ALLOWED_PHONE_CHARACTERS = /^[0-9+()\s.-]+$/;

export function normalizeGhanaWhatsAppNumber(
  value: string,
): string | null {
  const normalized = value.trim();

  if (!normalized) {
    return null;
  }

  if (
    MULTIPLE_NUMBER_SEPARATORS.test(normalized)
  ) {
    throw new Error(
      "Enter one Ghana WhatsApp number only.",
    );
  }

  if (
    !ALLOWED_PHONE_CHARACTERS.test(normalized) ||
    (normalized.includes("+") &&
      !normalized.startsWith("+")) ||
    (normalized.match(/\+/g)?.length ?? 0) > 1
  ) {
    throw new Error(
      "Enter one valid Ghana WhatsApp number, for example 0544494613.",
    );
  }

  const digits = normalized.replace(/\D/g, "");

  if (/^0\d{9}$/.test(digits)) {
    return `233${digits.slice(1)}`;
  }

  if (/^233\d{9}$/.test(digits)) {
    return digits;
  }

  throw new Error(
    "Enter one valid Ghana WhatsApp number, for example 0544494613.",
  );
}
