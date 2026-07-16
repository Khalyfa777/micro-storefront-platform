const MULTIPLE_NUMBER_SEPARATORS = /[/,;&]/;
const ALLOWED_PHONE_CHARACTERS = /^[0-9+()\s.-]+$/;
const GHANA_MOBILE_NATIONAL_NUMBER = /^[25]\d{8}$/;

function normalizeGhanaMobileNumber(
  value: string,
  fieldLabel: string,
): string | null {
  const normalized = value.trim();

  if (!normalized) {
    return null;
  }

  if (
    MULTIPLE_NUMBER_SEPARATORS.test(normalized)
  ) {
    throw new Error(
      `Enter one ${fieldLabel} only.`,
    );
  }

  if (
    !ALLOWED_PHONE_CHARACTERS.test(normalized) ||
    (normalized.includes("+") &&
      !normalized.startsWith("+")) ||
    (normalized.match(/\+/g)?.length ?? 0) > 1
  ) {
    throw new Error(
      `Enter one valid ${fieldLabel}, for example 0544494613.`,
    );
  }

  const digits = normalized.replace(/\D/g, "");
  let nationalNumber: string;

  if (/^0\d{9}$/.test(digits)) {
    nationalNumber = digits.slice(1);
  } else if (/^233\d{9}$/.test(digits)) {
    nationalNumber = digits.slice(3);
  } else {
    throw new Error(
      `Enter one valid ${fieldLabel}, for example 0544494613.`,
    );
  }

  if (
    !GHANA_MOBILE_NATIONAL_NUMBER.test(
      nationalNumber,
    )
  ) {
    throw new Error(
      `Enter one valid ${fieldLabel}, for example 0544494613.`,
    );
  }

  return `233${nationalNumber}`;
}

export function normalizeGhanaPhoneNumber(
  value: string,
): string | null {
  return normalizeGhanaMobileNumber(
    value,
    "Ghana mobile number",
  );
}

export function normalizeGhanaWhatsAppNumber(
  value: string,
): string | null {
  return normalizeGhanaMobileNumber(
    value,
    "Ghana WhatsApp number",
  );
}
