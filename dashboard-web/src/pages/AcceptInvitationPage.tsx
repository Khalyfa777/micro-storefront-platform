import {
  useEffect,
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import type {
  SellerInvitationAcceptResponse,
  SellerInvitationValidationResponse,
} from "../types/seller-invitation";


type InvitationViewState =
  | "loading"
  | "ready"
  | "invalid"
  | "expired"
  | "revoked"
  | "used"
  | "error"
  | "success";


type ApiSuccess<T> = {
  ok: true;
  data: T;
};


type ApiFailure = {
  ok: false;
  status: number;
  detail: string;
};


type ApiResult<T> =
  | ApiSuccess<T>
  | ApiFailure;


type AcceptInvitationPageProps = {
  invitationToken: string | null;
  apiBaseUrl: string;
};


const validationRequestCache = new Map<
  string,
  Promise<
    ApiResult<
      SellerInvitationValidationResponse
    >
  >
>();


function getErrorDetail(
  data: unknown,
  fallback: string,
): string {
  if (
    data &&
    typeof data === "object" &&
    "detail" in data
  ) {
    const detail = (
      data as {
        detail?: unknown;
      }
    ).detail;

    if (typeof detail === "string") {
      return detail;
    }
  }

  return fallback;
}


async function postPublicApi<T>(
  url: string,
  payload: Record<string, string>,
): Promise<ApiResult<T>> {
  const controller = new AbortController();

  const timeoutId = window.setTimeout(
    () => controller.abort(),
    12000,
  );

  try {
    const response = await fetch(
      url,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        cache: "no-store",
        body: JSON.stringify(payload),
        signal: controller.signal,
      },
    );

    const data: unknown = await response
      .json()
      .catch(() => null);

    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        detail: getErrorDetail(
          data,
          "The invitation request failed.",
        ),
      };
    }

    return {
      ok: true,
      data: data as T,
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      detail:
        error instanceof DOMException &&
        error.name === "AbortError"
          ? "The request timed out. Check your connection and try again."
          : "Could not reach StorePlug. Check your connection and try again.",
    };
  } finally {
    window.clearTimeout(timeoutId);
  }
}


function validateInvitation(
  apiBaseUrl: string,
  token: string,
) {
  const cached =
    validationRequestCache.get(token);

  if (cached) {
    return cached;
  }

  const request = postPublicApi<
    SellerInvitationValidationResponse
  >(
    `${apiBaseUrl}/seller-invitations/validate`,
    {
      token,
    },
  );

  validationRequestCache.set(
    token,
    request,
  );

  const removeCachedRequest = () => {
    if (
      validationRequestCache.get(token)
      === request
    ) {
      validationRequestCache.delete(token);
    }
  };

  void request.then(
    removeCachedRequest,
    removeCachedRequest,
  );

  return request;
}


function classifyFailure(
  status: number,
  detail: string,
): {
  state: InvitationViewState;
  title: string;
  message: string;
} {
  const normalized = detail.toLowerCase();

  if (
    status === 410 &&
    normalized.includes("expired")
  ) {
    return {
      state: "expired",
      title: "This invitation has expired",
      message:
        "Ask the StorePlug administrator to generate a new invitation link.",
    };
  }

  if (status === 410) {
    return {
      state: "revoked",
      title: "This invitation is no longer valid",
      message:
        "The link may have been replaced or cancelled. Ask the administrator for a new one.",
    };
  }

  if (
    status === 409 &&
    (
      normalized.includes("already") ||
      normalized.includes("no longer available")
    )
  ) {
    return {
      state: "used",
      title: "Account setup is already complete",
      message:
        "This invitation cannot be used again. Continue to the StorePlug sign-in page.",
    };
  }

  if (status === 404) {
    return {
      state: "invalid",
      title: "Invitation not found",
      message:
        "Check that you opened the complete invitation link or request a new one.",
    };
  }

  if (status === 429) {
    return {
      state: "error",
      title: "Too many attempts",
      message:
        "Wait a moment before trying the invitation again.",
    };
  }

  return {
    state: "error",
    title: "We could not verify this invitation",
    message: detail,
  };
}


function formatInvitationDate(
  value: string,
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return new Intl.DateTimeFormat(
    "en-GH",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}


function continueToLogin() {
  window.localStorage.removeItem("token");

  window.location.replace("/");
}


export function AcceptInvitationPage({
  invitationToken,
  apiBaseUrl,
}: AcceptInvitationPageProps) {
  const tokenIsUsable = Boolean(
    invitationToken &&
    invitationToken.length >= 20 &&
    invitationToken.length <= 512,
  );

  const [
    viewState,
    setViewState,
  ] = useState<InvitationViewState>(
    tokenIsUsable
      ? "loading"
      : "invalid",
  );

  const [
    invitation,
    setInvitation,
  ] = useState<
    SellerInvitationValidationResponse | null
  >(null);

  const [
    errorTitle,
    setErrorTitle,
  ] = useState(
    tokenIsUsable
      ? ""
      : "Invitation link is incomplete",
  );

  const [
    errorMessage,
    setErrorMessage,
  ] = useState(
    tokenIsUsable
      ? ""
      : "Open the complete invitation link sent by the StorePlug administrator.",
  );

  const [
    validationAttempt,
    setValidationAttempt,
  ] = useState(0);

  const [
    password,
    setPassword,
  ] = useState("");

  const [
    confirmPassword,
    setConfirmPassword,
  ] = useState("");

  const [
    showPassword,
    setShowPassword,
  ] = useState(false);

  const [
    showConfirmation,
    setShowConfirmation,
  ] = useState(false);

  const [
    submitting,
    setSubmitting,
  ] = useState(false);

  const [
    formError,
    setFormError,
  ] = useState("");

  const [
    acceptedResult,
    setAcceptedResult,
  ] = useState<
    SellerInvitationAcceptResponse | null
  >(null);

  useEffect(() => {
    document.title =
      "Accept invitation | StorePlug";

    return () => {
      document.title = "StorePlug";
    };
  }, []);

  useEffect(() => {
    if (viewState !== "success") {
      return;
    }

    window.scrollTo({
      top: 0,
      left: 0,
      behavior: "auto",
    });
  }, [viewState]);

  useEffect(() => {
    if (
      !tokenIsUsable ||
      !invitationToken
    ) {
      return;
    }

    let cancelled = false;

    void validateInvitation(
      apiBaseUrl,
      invitationToken,
    ).then((result) => {
      if (cancelled) {
        return;
      }

      if (result.ok) {
        setInvitation(result.data);
        setViewState("ready");
        return;
      }

      const failure = classifyFailure(
        result.status,
        result.detail,
      );

      setErrorTitle(failure.title);
      setErrorMessage(failure.message);
      setViewState(failure.state);
    });

    return () => {
      cancelled = true;
    };
  }, [
    apiBaseUrl,
    invitationToken,
    tokenIsUsable,
    validationAttempt,
  ]);

  function retryValidation() {
    if (!invitationToken) {
      return;
    }

    validationRequestCache.delete(
      invitationToken,
    );

    setErrorTitle("");
    setErrorMessage("");
    setViewState("loading");

    setValidationAttempt(
      (current) => current + 1,
    );
  }

  async function acceptInvitation(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (
      submitting ||
      !invitationToken ||
      !invitation
    ) {
      return;
    }

    setFormError("");

    if (
      password.length < 8 ||
      password.length > 128
    ) {
      setFormError(
        "Password must contain between 8 and 128 characters.",
      );
      return;
    }

    if (password !== confirmPassword) {
      setFormError(
        "The password confirmation does not match.",
      );
      return;
    }

    setSubmitting(true);

    const result = await postPublicApi<
      SellerInvitationAcceptResponse
    >(
      `${apiBaseUrl}/seller-invitations/accept`,
      {
        token: invitationToken,
        password,
      },
    );

    setSubmitting(false);

    if (result.ok) {
      validationRequestCache.delete(
        invitationToken,
      );

      setPassword("");
      setConfirmPassword("");
      setAcceptedResult(result.data);
      setViewState("success");
      return;
    }

    const failure = classifyFailure(
      result.status,
      result.detail,
    );

    if (
      failure.state !== "error"
    ) {
      setErrorTitle(failure.title);
      setErrorMessage(failure.message);
      setViewState(failure.state);
      return;
    }

    setFormError(failure.message);
  }

  if (viewState === "loading") {
    return (
      <main className="invitation-page">
        <section
          className="invitation-shell invitation-loading-card"
          aria-live="polite"
        >
          <div className="invitation-brand">
            <span>SP</span>
            <strong>StorePlug</strong>
          </div>

          <div
            className="invitation-spinner"
            aria-hidden="true"
          />

          <h1>Checking your invitation</h1>

          <p>
            Please wait while StorePlug verifies
            that this private link is still
            active.
          </p>
        </section>
      </main>
    );
  }

  if (
    viewState === "invalid" ||
    viewState === "expired" ||
    viewState === "revoked" ||
    viewState === "used" ||
    viewState === "error"
  ) {
    return (
      <main className="invitation-page">
        <section className="invitation-shell invitation-state-card">
          <div className="invitation-brand">
            <span>SP</span>
            <strong>StorePlug</strong>
          </div>

          <div
            className={`invitation-state-icon ${viewState}`}
            aria-hidden="true"
          >
            {viewState === "used" ? (
              <svg
                viewBox="0 0 24 24"
                focusable="false"
              >
                <path
                  d="M5 12.5 9.25 17 19 7"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            ) : (
              "!"
            )}
          </div>

          <p className="invitation-eyebrow">
            Seller onboarding
          </p>

          <h1>{errorTitle}</h1>

          <p>{errorMessage}</p>

          <div className="invitation-state-actions">
            {viewState === "error" && (
              <button
                type="button"
                className="invitation-secondary-button"
                onClick={retryValidation}
              >
                Try again
              </button>
            )}

            <button
              type="button"
              className="invitation-primary-button"
              onClick={continueToLogin}
            >
              Go to sign in
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (
    viewState === "success" &&
    acceptedResult &&
    invitation
  ) {
    return (
      <main className="invitation-page">
        <section className="invitation-shell invitation-success-card">
          <div className="invitation-brand">
            <span>SP</span>
            <strong>StorePlug</strong>
          </div>

          <div
            className="invitation-success-icon"
            aria-hidden="true"
          >
            <svg
              viewBox="0 0 24 24"
              focusable="false"
            >
              <path
                d="M5 12.5 9.25 17 19 7"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <p className="invitation-eyebrow">
            Setup complete
          </p>

          <h1>Your seller account is active</h1>

          <p className="invitation-success-copy">
            Your password has been created
            successfully. Sign in with{" "}
            <strong>{invitation.email}</strong>{" "}
            to continue setting up your store.
          </p>

          <div className="invitation-success-summary">
            <div>
              <span>Store</span>
              <strong>
                {invitation.store_name}
              </strong>
              <small>
                /{invitation.store_slug}
              </small>
            </div>

            <div>
              <span>Account</span>
              <strong>
                {acceptedResult.account_status}
              </strong>
              <small>Ready to sign in</small>
            </div>

            <div>
              <span>Store visibility</span>
              <strong className="invitation-status-badge">
                {acceptedResult.publication_status}
              </strong>
              <small>
                Not published yet
              </small>
            </div>
          </div>

          <button
            type="button"
            className="invitation-primary-button"
            onClick={continueToLogin}
          >
            Continue to seller sign in
          </button>
        </section>
      </main>
    );
  }

  if (!invitation) {
    return null;
  }

  return (
    <main className="invitation-page">
      <section className="invitation-shell invitation-setup-layout">
        <aside className="invitation-welcome-panel">
          <div className="invitation-brand light">
            <span>SP</span>
            <strong>StorePlug</strong>
          </div>

          <p className="invitation-eyebrow invitation-eyebrow-hero">
            You have been invited
          </p>

          <h1>
            Welcome to your new StorePlug
            workspace.
          </h1>

          <p>
            Create your private password to
            activate your seller account. Your
            storefront remains a draft until it
            is published separately.
          </p>

          <div className="invitation-store-preview">
            <span>First storefront</span>
            <strong>
              {invitation.store_name}
            </strong>
            <small>
              /{invitation.store_slug}
            </small>
          </div>

          <div className="invitation-security-list">
            <span>Single-use invitation</span>
            <span>Password is securely hashed</span>
            <span>Draft store stays private</span>
          </div>
        </aside>

        <form
          className="invitation-form-card"
          onSubmit={acceptInvitation}
        >
          <div className="invitation-form-heading">
            <p className="invitation-eyebrow invitation-eyebrow-section">
              Complete account setup
            </p>

            <h2>
              Hello, {invitation.full_name}
            </h2>

            <p className="invitation-email-copy">
              <span>
                Your StorePlug sign-in email is:
              </span>
              <strong>
                {invitation.email}
              </strong>
            </p>
          </div>

          <div className="invitation-detail-grid">
            <div>
              <span>Store</span>
              <strong>
                {invitation.store_name}
              </strong>
            </div>

            <div className="invitation-status-detail">
              <span>Visibility</span>
              <strong className="invitation-status-badge">
                {invitation.publication_status}
              </strong>
            </div>

            <div>
              <span>Invitation expires</span>
              <strong>
                {formatInvitationDate(
                  invitation.expires_at,
                )}
              </strong>
            </div>
          </div>

          <label className="invitation-password-field">
            <span>Create password</span>

            <div className="invitation-password-input">
              <input
                type={
                  showPassword
                    ? "text"
                    : "password"
                }
                value={password}
                onChange={(event) =>
                  setPassword(
                    event.target.value,
                  )
                }
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                placeholder="At least 8 characters"
                required
              />

              <button
                type="button"
                onClick={() =>
                  setShowPassword(
                    (current) => !current,
                  )
                }
                aria-label={
                  showPassword
                    ? "Hide password"
                    : "Show password"
                }
              >
                {showPassword
                  ? "Hide"
                  : "Show"}
              </button>
            </div>
          </label>

          <label className="invitation-password-field">
            <span>Confirm password</span>

            <div className="invitation-password-input">
              <input
                type={
                  showConfirmation
                    ? "text"
                    : "password"
                }
                value={confirmPassword}
                onChange={(event) =>
                  setConfirmPassword(
                    event.target.value,
                  )
                }
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                placeholder="Enter it again"
                required
              />

              <button
                type="button"
                onClick={() =>
                  setShowConfirmation(
                    (current) => !current,
                  )
                }
                aria-label={
                  showConfirmation
                    ? "Hide password confirmation"
                    : "Show password confirmation"
                }
              >
                {showConfirmation
                  ? "Hide"
                  : "Show"}
              </button>
            </div>
          </label>

          <div className="invitation-password-note">
            <strong>Password requirement</strong>
            <span>
              Use at least 8 characters. A longer,
              unique password is safer.
            </span>
          </div>

          {formError && (
            <div
              className="invitation-form-error"
              role="alert"
            >
              <strong>
                Account setup failed
              </strong>
              <span>{formError}</span>
            </div>
          )}

          <button
            type="submit"
            className="invitation-primary-button"
            disabled={submitting}
          >
            {submitting
              ? "Activating account..."
              : "Activate seller account"}
          </button>

          <p className="invitation-privacy-note">
            The invitation token is removed from
            your browser address before this page
            loads and is never saved to browser
            storage.
          </p>
        </form>
      </section>
    </main>
  );
}
