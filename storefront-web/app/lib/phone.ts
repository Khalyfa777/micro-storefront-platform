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

  if (/^0\d{9}$/.test(digits)) {
    return `233${digits.slice(1)}`;
  }

  if (/^233\d{9}$/.test(digits)) {
    return digits;
  }

  return null;
}
