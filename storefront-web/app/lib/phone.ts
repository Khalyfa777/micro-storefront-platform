const GHANA_MOBILE_NATIONAL_NUMBER = /^[25]\d{8}$/;

export function getWhatsAppNumber(
  value?: string | null,
): string | null {
  if (!value) {
    return null;
  }

  const normalized = value.trim();

  if (
    !normalized ||
    /[/,;&]/.test(normalized) ||
    !/^[0-9+()\s.-]+$/.test(normalized) ||
    (normalized.includes("+") &&
      !normalized.startsWith("+")) ||
    (normalized.match(/\+/g)?.length ?? 0) > 1
  ) {
    return null;
  }

  const digits = normalized.replace(/\D/g, "");
  let nationalNumber = "";

  if (/^0\d{9}$/.test(digits)) {
    nationalNumber = digits.slice(1);
  } else if (/^233\d{9}$/.test(digits)) {
    nationalNumber = digits.slice(3);
  } else {
    return null;
  }

  if (
    !GHANA_MOBILE_NATIONAL_NUMBER.test(
      nationalNumber,
    )
  ) {
    return null;
  }

  return `233${nationalNumber}`;
}
