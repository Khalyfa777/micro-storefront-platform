import {
  useEffect,
  useRef,
  useState,
} from "react";
import type {
  FormEvent,
} from "react";


type ChangePasswordPayload = {
  current_password: string;
  new_password: string;
};

type ChangePasswordResponse = {
  detail?: string;
};

type SecurityPageProps = {
  changePassword: (
    payload: ChangePasswordPayload,
  ) => Promise<ChangePasswordResponse>;
  onPasswordChanged: () => void;
};


export function SecurityPage({
  changePassword,
  onPasswordChanged,
}: SecurityPageProps) {
  const [currentPassword, setCurrentPassword] =
    useState("");
  const [newPassword, setNewPassword] =
    useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");
  const [
    showCurrentPassword,
    setShowCurrentPassword,
  ] = useState(false);
  const [
    showNewPassword,
    setShowNewPassword,
  ] = useState(false);
  const [
    showConfirmPassword,
    setShowConfirmPassword,
  ] = useState(false);
  const [submitting, setSubmitting] =
    useState(false);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] =
    useState("");
  const logoutTimer = useRef<number | null>(
    null,
  );

  useEffect(() => {
    return () => {
      if (logoutTimer.current !== null) {
        window.clearTimeout(
          logoutTimer.current,
        );
      }
    };
  }, []);

  async function submitPasswordChange(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (submitting) {
      return;
    }

    setError("");
    setStatusMessage("");

    if (!currentPassword) {
      setError(
        "Enter your current password.",
      );
      return;
    }

    if (newPassword.length < 8) {
      setError(
        "New password must be at least 8 characters.",
      );
      return;
    }

    if (newPassword === currentPassword) {
      setError(
        "Choose a new password that is different from your current password.",
      );
      return;
    }

    if (newPassword !== confirmPassword) {
      setError(
        "New password confirmation does not match.",
      );
      return;
    }

    setSubmitting(true);

    try {
      const response = await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowCurrentPassword(false);
      setShowNewPassword(false);
      setShowConfirmPassword(false);
      setStatusMessage(
        response.detail ||
          "Password updated. Signing you out securely.",
      );

      logoutTimer.current =
        window.setTimeout(
          onPasswordChanged,
          1100,
        );
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Password could not be updated.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className="security-page"
      aria-labelledby="security-page-title"
    >
      <article className="security-card">
        <header className="security-card-header">
          <div className="security-title-row">
            <div
              className="security-shield"
              aria-hidden="true"
            >
              <svg
                viewBox="0 0 24 24"
                focusable="false"
              >
                <path
                  d="M12 3 19 6v5c0 4.8-2.9 8.1-7 10-4.1-1.9-7-5.2-7-10V6l7-3Z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
                <path
                  d="m9.2 12.1 1.8 1.8 3.9-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            <div className="security-heading-copy">
              <h2 id="security-page-title">
                Change password
              </h2>

              <p className="security-card-description">
                Use a unique password you do not
                use for another account.
              </p>
            </div>
          </div>

          <div
            className="security-session-notice"
            role="note"
          >
            <svg
              className="security-session-icon"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                d="M12 8v4l2.6 1.6"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
              <circle
                cx="12"
                cy="12"
                r="8"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
              />
            </svg>

            <p>
              <strong>
                All sessions will end.
              </strong>{" "}
              Sign in again after updating.
            </p>
          </div>
        </header>

        <form
          className="security-form"
          onSubmit={submitPasswordChange}
        >
          <div className="security-field">
            <label htmlFor="current-password">
              Current password
            </label>

            <div className="security-password-field">
              <input
                id="current-password"
                name="current_password"
                type={
                  showCurrentPassword
                    ? "text"
                    : "password"
                }
                value={currentPassword}
                onChange={(event) =>
                  setCurrentPassword(
                    event.target.value,
                  )
                }
                autoComplete="current-password"
                autoCapitalize="none"
                spellCheck={false}
                maxLength={128}
                disabled={submitting}
                required
              />

              <button
                type="button"
                className="security-password-toggle"
                onClick={() =>
                  setShowCurrentPassword(
                    (current) => !current,
                  )
                }
                aria-label={
                  showCurrentPassword
                    ? "Hide current password"
                    : "Show current password"
                }
                aria-pressed={
                  showCurrentPassword
                }
                disabled={submitting}
              >
                {showCurrentPassword
                  ? "Hide"
                  : "Show"}
              </button>
            </div>
          </div>

          <div className="security-field">
            <label htmlFor="new-password">
              New password
            </label>

            <div className="security-password-field">
              <input
                id="new-password"
                name="new_password"
                type={
                  showNewPassword
                    ? "text"
                    : "password"
                }
                value={newPassword}
                onChange={(event) =>
                  setNewPassword(
                    event.target.value,
                  )
                }
                autoComplete="new-password"
                autoCapitalize="none"
                spellCheck={false}
                minLength={8}
                maxLength={128}
                disabled={submitting}
                aria-describedby="new-password-help"
                required
              />

              <button
                type="button"
                className="security-password-toggle"
                onClick={() =>
                  setShowNewPassword(
                    (current) => !current,
                  )
                }
                aria-label={
                  showNewPassword
                    ? "Hide new password"
                    : "Show new password"
                }
                aria-pressed={
                  showNewPassword
                }
                disabled={submitting}
              >
                {showNewPassword
                  ? "Hide"
                  : "Show"}
              </button>
            </div>
          </div>

          <div className="security-field">
            <label htmlFor="confirm-password">
              Confirm new password
            </label>

            <div className="security-password-field">
              <input
                id="confirm-password"
                name="confirm_password"
                type={
                  showConfirmPassword
                    ? "text"
                    : "password"
                }
                value={confirmPassword}
                onChange={(event) =>
                  setConfirmPassword(
                    event.target.value,
                  )
                }
                autoComplete="new-password"
                autoCapitalize="none"
                spellCheck={false}
                minLength={8}
                maxLength={128}
                disabled={submitting}
                aria-describedby="new-password-help"
                required
              />

              <button
                type="button"
                className="security-password-toggle"
                onClick={() =>
                  setShowConfirmPassword(
                    (current) => !current,
                  )
                }
                aria-label={
                  showConfirmPassword
                    ? "Hide password confirmation"
                    : "Show password confirmation"
                }
                aria-pressed={
                  showConfirmPassword
                }
                disabled={submitting}
              >
                {showConfirmPassword
                  ? "Hide"
                  : "Show"}
              </button>
            </div>
          </div>

          <p
            id="new-password-help"
            className="security-form-help"
          >
            At least 8 characters. A longer
            passphrase is easier to remember and
            harder to guess.
          </p>

          <div
            className="security-form-feedback"
            aria-live="polite"
            aria-atomic="true"
          >
            {error && (
              <div
                className="security-error"
                role="alert"
              >
                {error}
              </div>
            )}

            {statusMessage && (
              <div
                className="security-success"
                role="status"
              >
                {statusMessage}
              </div>
            )}
          </div>

          <div className="security-form-actions">
            <button
              type="submit"
              className="security-submit"
              disabled={submitting}
            >
              {submitting
                ? "Updating password..."
                : "Update password"}
            </button>
          </div>
        </form>
      </article>
    </section>
  );
}
