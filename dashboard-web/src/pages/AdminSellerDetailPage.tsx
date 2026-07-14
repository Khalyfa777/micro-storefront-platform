import {
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  AdminSellerAccountActionResponse,
  AdminSellerDetailResponse,
  AdminSellerInvitationRegenerateResponse,
  AdminSellerStoreSummary,
  AdminSellerOnboardingCancelResponse,
} from "../types/admin-seller";


type ApiFetch = (
  path: string,
  options?: RequestInit,
) => Promise<unknown>;


type ConfirmAction =
  | "suspend"
  | "reactivate"
  | "cancel"
  | null;


type BusyAction =
  | "suspend"
  | "reactivate"
  | "regenerate"
  | "cancel"
  | "publish"
  | "unpublish"
  | "subscription"
  | null;


type AdminSellerDetailPageProps = {
  sellerId: string;
  apiFetch: ApiFetch;
  onBack: () => void;
  onSellerChanged:
    () => void | Promise<void>;
};


type AdminSubscriptionPlanOption = {
  name: string;
  display_name: string;
  monthly_fee: string | number;
  is_active: boolean;
  is_quote_only?: boolean;
};


type SubscriptionFormState = {
  storeId: string;
  planName: string;
  amountPaid: string;
  extendDays: string;
  paymentMethod:
    | "manual"
    | "momo"
    | "bank"
    | "cash"
    | "paystack";
  paymentReference: string;
  note: string;
};


function formatLabel(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase(),
    );
}


function formatDateTime(
  value?: string | null,
): string {
  if (!value) {
    return "Not set";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not set";
  }

  return new Intl.DateTimeFormat(
    "en-GH",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}


function formatMoney(
  value: string | number,
): string {
  const numeric = Number(value);

  if (!Number.isFinite(numeric)) {
    return `GHS ${value}`;
  }

  return new Intl.NumberFormat(
    "en-GH",
    {
      style: "currency",
      currency: "GHS",
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    },
  ).format(numeric);
}


function getInitials(name: string): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (parts.length === 0) {
    return "SP";
  }

  if (parts.length === 1) {
    return parts[0][0].toUpperCase();
  }

  return (
    parts[0][0] +
    parts[parts.length - 1][0]
  ).toUpperCase();
}


async function copyPrivateValue(
  value: string,
): Promise<void> {
  if (
    navigator.clipboard &&
    window.isSecureContext
  ) {
    await navigator.clipboard.writeText(
      value,
    );
    return;
  }

  const textarea =
    document.createElement("textarea");

  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";

  document.body.appendChild(textarea);
  textarea.select();

  const copied =
    document.execCommand("copy");

  document.body.removeChild(textarea);

  if (!copied) {
    throw new Error(
      "Could not copy the invitation link.",
    );
  }
}


export function AdminSellerDetailPage({
  sellerId,
  apiFetch,
  onBack,
  onSellerChanged,
}: AdminSellerDetailPageProps) {
  const requestRef = useRef(apiFetch);

  const [
    seller,
    setSeller,
  ] = useState<
    AdminSellerDetailResponse | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    refreshing,
    setRefreshing,
  ] = useState(false);

  const [
    reloadKey,
    setReloadKey,
  ] = useState(0);

  const [
    loadError,
    setLoadError,
  ] = useState("");

  const [
    actionError,
    setActionError,
  ] = useState("");

  const [
    actionMessage,
    setActionMessage,
  ] = useState("");

  const [
    confirmation,
    setConfirmation,
  ] = useState<ConfirmAction>(null);

  const [
    busyAction,
    setBusyAction,
  ] = useState<BusyAction>(null);

  const [
    publicationStoreId,
    setPublicationStoreId,
  ] = useState<string | null>(null);

  const [
    actionReason,
    setActionReason,
  ] = useState("");

  const [
    generatedInvitation,
    setGeneratedInvitation,
  ] = useState<
    AdminSellerInvitationRegenerateResponse
    | null
  >(null);

  const [
    copied,
    setCopied,
  ] = useState(false);

  const [
    subscriptionPlans,
    setSubscriptionPlans,
  ] = useState<
    AdminSubscriptionPlanOption[]
  >([]);

  const [
    loadingSubscriptionPlans,
    setLoadingSubscriptionPlans,
  ] = useState(false);

  const [
    subscriptionPlanError,
    setSubscriptionPlanError,
  ] = useState("");

  const [
    subscriptionForm,
    setSubscriptionForm,
  ] = useState<SubscriptionFormState | null>(
    null,
  );

  useEffect(() => {
    requestRef.current = apiFetch;
  }, [apiFetch]);

  useEffect(() => {
    let cancelled = false;

    async function loadSubscriptionPlans() {
      setLoadingSubscriptionPlans(true);
      setSubscriptionPlanError("");

      try {
        const response =
          await requestRef.current(
            "/admin/subscription-plans",
          ) as AdminSubscriptionPlanOption[];

        if (!cancelled) {
          setSubscriptionPlans(
            response.filter(
              (plan) => plan.is_active,
            ),
          );
        }
      } catch (error) {
        if (!cancelled) {
          setSubscriptionPlanError(
            error instanceof Error
              ? error.message
              : "Could not load subscription plans.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingSubscriptionPlans(false);
        }
      }
    }

    void loadSubscriptionPlans();

    return () => {
      cancelled = true;
    };
  }, [sellerId]);

  useEffect(() => {
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: "auto",
    });
  }, [sellerId]);

  useEffect(() => {
    let cancelled = false;

    async function loadDetail() {
      if (reloadKey === 0) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }

      setLoadError("");

      try {
        const response =
          await requestRef.current(
            `/admin/sellers/${sellerId}`,
          ) as AdminSellerDetailResponse;

        if (!cancelled) {
          setSeller(response);
        }
      } catch (error) {
        if (!cancelled) {
          setLoadError(
            error instanceof Error
              ? error.message
              : "Could not load the seller.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [sellerId, reloadKey]);

  function refreshDetail() {
    setActionError("");
    setActionMessage("");

    setReloadKey(
      (current) => current + 1,
    );
  }

  function syncSellerList() {
    void Promise.resolve(
      onSellerChanged(),
    ).catch(() => undefined);
  }

  async function performAccountAction(
    action: "suspend" | "reactivate",
  ) {
    if (!seller || busyAction) {
      return;
    }

    setBusyAction(action);
    setActionError("");
    setActionMessage("");

    try {
      const response =
        await requestRef.current(
          `/admin/sellers/${sellerId}/${action}`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              expected_updated_at:
                seller.updated_at,
              reason:
                actionReason.trim() || null,
            }),
          },
        ) as AdminSellerAccountActionResponse;

      setActionMessage(
        response.account_status ===
        "suspended"
          ? "Seller account suspended. Store publication and subscriptions were not changed."
          : "Seller account reactivated. Existing stores were not changed.",
      );

      setConfirmation(null);
      setActionReason("");

      setReloadKey(
        (current) => current + 1,
      );

      syncSellerList();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "The account action failed.",
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function performPublicationAction(
    store: AdminSellerStoreSummary,
    action: "publish" | "unpublish",
  ) {
    if (!seller || busyAction) {
      return;
    }

    if (
      action === "publish" &&
      seller.setup_status !== "completed"
    ) {
      setActionError(
        "The seller must accept the invitation and complete account setup before the store can be published.",
      );
      return;
    }

    const confirmed = window.confirm(
      action === "publish"
        ? `Publish ${store.name}? The storefront will become public and customers can place orders immediately.`
        : `Unpublish ${store.name}? The public storefront and all new order creation will be blocked immediately.`,
    );

    if (!confirmed) {
      return;
    }

    setBusyAction(action);
    setPublicationStoreId(store.id);
    setActionError("");
    setActionMessage("");

    try {
      const response =
        await requestRef.current(
          `/admin/stores/${store.id}/${action}`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              expected_updated_at:
                store.updated_at,
            }),
          },
        ) as AdminSellerStoreSummary;

      setSeller((current) => {
        if (!current) {
          return current;
        }

        return {
          ...current,
          stores: current.stores.map(
            (currentStore) =>
              currentStore.id === store.id
                ? {
                    ...currentStore,
                    publication_status:
                      response
                        .publication_status,
                    updated_at:
                      response.updated_at,
                  }
                : currentStore,
          ),
        };
      });

      setActionMessage(
        response.publication_status ===
        "published"
          ? `${store.name} is now live. Customers can visit /${store.slug} and place orders.`
          : `${store.name} has been unpublished. Its products and settings were retained.`,
      );

      syncSellerList();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : `Could not ${action} the store.`,
      );
    } finally {
      setBusyAction(null);
      setPublicationStoreId(null);
    }
  }


  function getSubscriptionPlan(
    planName: string,
  ) {
    return subscriptionPlans.find(
      (plan) => plan.name === planName,
    );
  }


  function openSubscriptionManager(
    store: AdminSellerStoreSummary,
  ) {
    const plan = getSubscriptionPlan(
      store.plan_name,
    );

    setActionError("");
    setActionMessage("");

    setSubscriptionForm({
      storeId: store.id,
      planName: store.plan_name,
      amountPaid: String(
        plan?.monthly_fee
        ?? store.monthly_fee
        ?? "",
      ),
      extendDays: "30",
      paymentMethod: "momo",
      paymentReference: "",
      note: store.subscription_status === "active"
        ? "Subscription renewal"
        : "Paid subscription activation",
    });
  }


  async function submitSubscription(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!subscriptionForm || busyAction) {
      return;
    }

    const amountPaid = Number(
      subscriptionForm.amountPaid,
    );

    const extendDays = Number(
      subscriptionForm.extendDays,
    );

    if (
      !Number.isFinite(amountPaid) ||
      amountPaid <= 0
    ) {
      setActionError(
        "Enter the amount received for this paid subscription.",
      );
      return;
    }

    if (
      !Number.isInteger(extendDays) ||
      extendDays < 1 ||
      extendDays > 366
    ) {
      setActionError(
        "Subscription duration must be between 1 and 366 days.",
      );
      return;
    }

    setBusyAction("subscription");
    setActionError("");
    setActionMessage("");

    try {
      await requestRef.current(
        `/admin/stores/${subscriptionForm.storeId}/subscription/extend`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            plan_name:
              subscriptionForm.planName,
            amount_paid: amountPaid,
            extend_days: extendDays,
            payment_method:
              subscriptionForm.paymentMethod,
            payment_reference:
              subscriptionForm.paymentReference
                .trim() || null,
            note:
              subscriptionForm.note.trim() ||
              null,
            mark_active: true,
          }),
        },
      );

      setActionMessage(
        "Paid subscription activated and payment recorded.",
      );
      setSubscriptionForm(null);

      setReloadKey(
        (current) => current + 1,
      );

      syncSellerList();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Could not activate the paid subscription.",
      );
    } finally {
      setBusyAction(null);
    }
  }


  async function regenerateInvitation() {
    if (
      !seller ||
      busyAction ||
      seller.setup_status !== "pending"
    ) {
      return;
    }

    setBusyAction("regenerate");
    setActionError("");
    setActionMessage("");
    setCopied(false);

    const currentInvitationId =
      seller.latest_invitation &&
      (
        seller.latest_invitation.status ===
          "active" ||
        seller.latest_invitation.status ===
          "expired"
      )
        ? seller.latest_invitation.id
        : null;

    try {
      const response =
        await requestRef.current(
          `/admin/sellers/${sellerId}/invitation/regenerate`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              current_invitation_id:
                currentInvitationId,
            }),
          },
        ) as AdminSellerInvitationRegenerateResponse;

      setGeneratedInvitation(response);

      setActionMessage(
        "A new single-use invitation was generated. Copy it before leaving this page.",
      );

      setReloadKey(
        (current) => current + 1,
      );

      syncSellerList();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Could not generate a new invitation.",
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function cancelOnboarding() {
    if (
      !seller ||
      busyAction ||
      !seller.latest_invitation
    ) {
      return;
    }

    setBusyAction("cancel");
    setActionError("");
    setActionMessage("");

    try {
      const response =
        await requestRef.current(
          `/admin/sellers/${sellerId}/cancel-onboarding`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              current_invitation_id:
                seller.latest_invitation.id,
            }),
          },
        ) as AdminSellerOnboardingCancelResponse;

      setActionMessage(
        response.onboarding_status ===
        "cancelled"
          ? "Seller onboarding cancelled. The account and draft store were retained."
          : "Seller onboarding was updated.",
      );

      setGeneratedInvitation(null);
      setConfirmation(null);

      setReloadKey(
        (current) => current + 1,
      );

      syncSellerList();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Could not cancel onboarding.",
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function copyGeneratedInvitation() {
    if (!generatedInvitation) {
      return;
    }

    setActionError("");

    try {
      await copyPrivateValue(
        generatedInvitation.invitation_url,
      );

      setCopied(true);
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Could not copy the invitation.",
      );
    }
  }

  if (loading) {
    return (
      <section className="seller-detail-page">
        <button
          type="button"
          className="seller-detail-back"
          onClick={onBack}
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              d="m15 5-7 7 7 7"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          Back to sellers
        </button>

        <div
          className="seller-detail-loading"
          aria-live="polite"
        >
          <div
            className="seller-detail-spinner"
            aria-hidden="true"
          />

          <h2>Loading seller account</h2>

          <p>
            Fetching account, onboarding,
            stores, and security history.
          </p>
        </div>
      </section>
    );
  }

  if (!seller || loadError) {
    return (
      <section className="seller-detail-page">
        <button
          type="button"
          className="seller-detail-back"
          onClick={onBack}
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              d="m15 5-7 7 7 7"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          Back to sellers
        </button>

        <div className="seller-detail-error-state">
          <strong>
            Seller details could not be loaded
          </strong>

          <p>
            {loadError ||
              "The seller was not found."}
          </p>

          <button
            type="button"
            className="seller-primary-button"
            onClick={refreshDetail}
          >
            Try again
          </button>
        </div>
      </section>
    );
  }

  const latestInvitation =
    seller.latest_invitation;

  const canManageInvitation =
    seller.account_status === "invited" &&
    seller.setup_status === "pending";

  const canCancelOnboarding =
    canManageInvitation &&
    latestInvitation !== null &&
    (
      latestInvitation.status ===
        "active" ||
      latestInvitation.status ===
        "expired"
    );

  return (
    <section className="seller-detail-page">
      <div className="seller-detail-toolbar">
        <button
          type="button"
          className="seller-detail-back"
          onClick={onBack}
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              d="m15 5-7 7 7 7"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          Back to sellers
        </button>

        <button
          type="button"
          className="seller-detail-refresh"
          onClick={refreshDetail}
          disabled={refreshing}
        >
          {refreshing
            ? "Refreshing..."
            : "Refresh account"}
        </button>
      </div>

      <header className="seller-detail-hero">
        <div className="seller-detail-identity">
          <div className="seller-detail-avatar">
            {getInitials(seller.full_name)}
          </div>

          <div>
            <p className="seller-page-eyebrow">
              Seller account
            </p>

            <h2>{seller.full_name}</h2>

            <p className="seller-detail-email">
              {seller.email}
            </p>

            {seller.phone_number && (
              <span>{seller.phone_number}</span>
            )}
          </div>
        </div>

        <div className="seller-detail-status-row">
          <span
            className={`seller-status-pill account-${seller.account_status}`}
          >
            {formatLabel(
              seller.account_status,
            )}
          </span>

          <span
            className={`seller-status-pill setup-${seller.setup_status}`}
          >
            Setup:{" "}
            {formatLabel(
              seller.setup_status,
            )}
          </span>

          <span
            className={`seller-status-pill invitation-${seller.invitation_status}`}
          >
            Invitation:{" "}
            {formatLabel(
              seller.invitation_status,
            )}
          </span>
        </div>

        <div className="seller-detail-primary-actions">
          {seller.account_status ===
            "active" && (
            <button
              type="button"
              className="seller-danger-button"
              onClick={() => {
                setActionError("");
                setConfirmation("suspend");
              }}
            >
              Suspend account
            </button>
          )}

          {seller.account_status ===
            "suspended" && (
            <button
              type="button"
              className="seller-primary-button"
              onClick={() => {
                setActionError("");
                setConfirmation(
                  "reactivate",
                );
              }}
            >
              Reactivate account
            </button>
          )}
        </div>
      </header>

      {actionError && (
        <div
          className="seller-detail-alert error"
          role="alert"
        >
          <strong>Action failed</strong>
          <span>{actionError}</span>
        </div>
      )}

      {actionMessage && (
        <div
          className="seller-detail-alert success"
          role="status"
        >
          <strong>Update complete</strong>
          <span>{actionMessage}</span>
        </div>
      )}

      {confirmation && (
        <section className="seller-action-confirmation">
          <div>
            <p className="seller-page-eyebrow">
              Confirmation required
            </p>

            <h3>
              {confirmation === "suspend"
                ? "Suspend seller account?"
                : confirmation ===
                    "reactivate"
                  ? "Reactivate seller account?"
                  : "Cancel seller onboarding?"}
            </h3>

            <p>
              {confirmation === "suspend"
                ? "The seller will lose dashboard access. Store publication, plans, subscriptions, and store suspension remain unchanged."
                : confirmation ===
                    "reactivate"
                  ? "Dashboard access will be restored. Store state remains unchanged."
                  : "The current invitation will be revoked. The seller account and draft store will remain in the system."}
            </p>
          </div>

          {confirmation !== "cancel" && (
            <label>
              <span>
                Reason
                <small>Optional</small>
              </span>

              <textarea
                value={actionReason}
                onChange={(event) =>
                  setActionReason(
                    event.target.value,
                  )
                }
                maxLength={500}
                placeholder="Add an internal reason for the account history"
              />
            </label>
          )}

          <div className="seller-confirmation-actions">
            <button
              type="button"
              className="seller-secondary-button"
              onClick={() => {
                setConfirmation(null);
                setActionReason("");
              }}
              disabled={busyAction !== null}
            >
              Keep current state
            </button>

            <button
              type="button"
              className={
                confirmation ===
                  "reactivate"
                  ? "seller-primary-button"
                  : "seller-danger-button"
              }
              onClick={() => {
                if (
                  confirmation === "suspend" ||
                  confirmation ===
                    "reactivate"
                ) {
                  void performAccountAction(
                    confirmation,
                  );
                } else {
                  void cancelOnboarding();
                }
              }}
              disabled={busyAction !== null}
            >
              {busyAction
                ? "Applying change..."
                : confirmation === "suspend"
                  ? "Confirm suspension"
                  : confirmation ===
                      "reactivate"
                    ? "Confirm reactivation"
                    : "Cancel onboarding"}
            </button>
          </div>
        </section>
      )}

      {generatedInvitation && (
        <section className="seller-generated-invitation">
          <div>
            <p className="seller-page-eyebrow">
              New private invitation
            </p>

            <h3>
              Copy this link before leaving
            </h3>

            <p>
              The raw security token is only
              returned during generation and is
              not stored in this dashboard.
            </p>
          </div>

          <div className="seller-generated-link-row">
            <input
              value={
                generatedInvitation
                  .invitation_url
              }
              readOnly
              aria-label="New private invitation link"
              onFocus={(event) =>
                event.currentTarget.select()
              }
            />

            <button
              type="button"
              className="seller-primary-button"
              onClick={
                copyGeneratedInvitation
              }
            >
              {copied
                ? "Copied"
                : "Copy invitation link"}
            </button>
          </div>

          <small>
            Expires{" "}
            {formatDateTime(
              generatedInvitation
                .invitation_expires_at,
            )}
          </small>
        </section>
      )}

      <div className="seller-detail-grid">
        <section className="seller-detail-panel">
          <div className="seller-detail-panel-heading">
            <div>
              <p className="seller-page-eyebrow">
                Account
              </p>

              <h3>Account overview</h3>
            </div>
          </div>

          <div className="seller-detail-facts seller-account-facts">
            <div>
              <span>Email address</span>
              <strong>{seller.email}</strong>
            </div>

            <div>
              <span>Phone number</span>
              <strong>
                {seller.phone_number ||
                  "Not provided"}
              </strong>
            </div>

            <div>
              <span>Password created</span>
              <strong>
                {seller.has_password
                  ? "Yes"
                  : "No"}
              </strong>
            </div>

            <div>
              <span>Email verified</span>
              <strong>
                {seller.is_verified
                  ? "Yes"
                  : "No"}
              </strong>
            </div>

            <div>
              <span>Added</span>
              <strong>
                {formatDateTime(
                  seller.created_at,
                )}
              </strong>
            </div>

            <div>
              <span>Last account change</span>
              <strong>
                {formatDateTime(
                  seller.updated_at,
                )}
              </strong>
            </div>
          </div>
        </section>

        <section className="seller-detail-panel">
          <div className="seller-detail-panel-heading">
            <div>
              <p className="seller-page-eyebrow">
                Onboarding
              </p>

              <h3>
                Invitation and setup
              </h3>
            </div>
          </div>

          <div className="seller-detail-facts seller-onboarding-facts">
            <div>
              <span>Setup status</span>
              <strong>
                {formatLabel(
                  seller.setup_status,
                )}
              </strong>
            </div>

            <div>
              <span>Invitation status</span>
              <strong>
                {formatLabel(
                  seller.invitation_status,
                )}
              </strong>
            </div>

            <div>
              <span>Invitations issued</span>
              <strong>
                {seller.invitation_count}
              </strong>
            </div>

            <div>
              <span>Latest expiry</span>
              <strong>
                {formatDateTime(
                  latestInvitation
                    ?.expires_at,
                )}
              </strong>
            </div>
          </div>

          {canManageInvitation && (
            <div className="seller-invitation-controls">
              <button
                type="button"
                className="seller-primary-button"
                onClick={() =>
                  void regenerateInvitation()
                }
                disabled={busyAction !== null}
              >
                {busyAction === "regenerate"
                  ? "Generating..."
                  : latestInvitation
                    ? "Generate new link"
                    : "Generate invitation"}
              </button>

              {canCancelOnboarding && (
                <button
                  type="button"
                  className="seller-danger-button"
                  onClick={() => {
                    setActionError("");
                    setConfirmation("cancel");
                  }}
                  disabled={
                    busyAction !== null
                  }
                >
                  Cancel onboarding
                </button>
              )}
            </div>
          )}

          {seller.setup_status ===
            "cancelled" && (
            <p className="seller-detail-note">
              Onboarding has been cancelled.
              Generate a new invitation only
              after the workflow is explicitly
              reopened.
            </p>
          )}
        </section>

        <section className="seller-detail-panel seller-detail-panel-full">
          <div className="seller-detail-panel-heading">
            <div>
              <p className="seller-page-eyebrow">
                Stores
              </p>

              <h3>
                Owned storefronts
              </h3>

              <p>
                Store publication, suspension,
                and subscription state are
                managed separately from this
                seller account.
              </p>
            </div>

            <span className="seller-detail-count">
              {seller.store_count}
            </span>
          </div>

          {seller.stores.length === 0 ? (
            <div className="seller-detail-empty">
              No storefronts belong to this
              seller.
            </div>
          ) : (
            <div className="seller-detail-store-grid">
              {seller.stores.map((store) => (
                <article
                  key={store.id}
                  className="seller-detail-store-card"
                >
                  <div className="seller-detail-store-head">
                    <div>
                      <h4>{store.name}</h4>
                      <p>/{store.slug}</p>
                    </div>

                    <span
                      className={`seller-store-state publication-${store.publication_status}`}
                    >
                      {formatLabel(
                        store.publication_status,
                      )}
                    </span>
                  </div>

                  <div className="seller-detail-store-facts">
                    <div>
                      <span>Plan</span>
                      <strong>
                        {formatLabel(
                          store.plan_name,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Subscription</span>
                      <strong>
                        {formatLabel(
                          store.subscription_status,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Monthly fee</span>
                      <strong>
                        {formatMoney(
                          store.monthly_fee,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Store access</span>
                      <strong>
                        {store.is_suspended
                          ? "Suspended"
                          : store.is_active
                            ? "Active"
                            : "Inactive"}
                      </strong>
                    </div>

                    {store.subscription_status ===
                    "trial" ? (
                      <div>
                        <span>Trial ends</span>
                        <strong>
                          {formatDateTime(
                            store.trial_ends_at,
                          )}
                        </strong>
                      </div>
                    ) : (
                      <div>
                        <span>Last payment</span>
                        <strong>
                          {formatDateTime(
                            store.last_payment_at,
                          )}
                        </strong>
                      </div>
                    )}

                    <div>
                      <span>
                        {store.subscription_status ===
                        "trial"
                          ? "Paid subscription"
                          : "Subscription ends"}
                      </span>
                      <strong>
                        {store.subscription_status ===
                        "trial"
                          ? "Not activated"
                          : formatDateTime(
                              store
                                .subscription_ends_at,
                            )}
                      </strong>
                    </div>
                  </div>

                  <div className="seller-store-subscription">
                    <div>
                      <p className="seller-page-eyebrow">
                        Billing
                      </p>
                      <strong>
                        {store.subscription_status ===
                        "active"
                          ? "Paid subscription active"
                          : "Convert to a paid plan"}
                      </strong>
                      <p>
                        Record the payment, choose the
                        plan, and grant paid access in
                        one action. Remaining trial or
                        paid time is preserved.
                      </p>
                    </div>

                    <button
                      type="button"
                      className="seller-primary-button"
                      onClick={() =>
                        openSubscriptionManager(store)
                      }
                      disabled={
                        busyAction !== null ||
                        loadingSubscriptionPlans
                      }
                    >
                      {store.subscription_status ===
                      "active"
                        ? "Renew or change plan"
                        : "Activate paid plan"}
                    </button>
                  </div>

                  {subscriptionPlanError && (
                    <p className="seller-inline-error">
                      {subscriptionPlanError}
                    </p>
                  )}

                  {subscriptionForm?.storeId ===
                    store.id && (
                    <form
                      className="seller-subscription-form"
                      onSubmit={(event) =>
                        void submitSubscription(event)
                      }
                    >
                      <div className="seller-subscription-form-heading">
                        <div>
                          <p className="seller-page-eyebrow">
                            Payment confirmation
                          </p>
                          <h5>
                            Activate or renew subscription
                          </h5>
                        </div>

                        <button
                          type="button"
                          className="seller-text-button"
                          onClick={() =>
                            setSubscriptionForm(null)
                          }
                          disabled={
                            busyAction === "subscription"
                          }
                        >
                          Close
                        </button>
                      </div>

                      <div className="seller-subscription-fields">
                        <label>
                          <span>Plan</span>
                          <select
                            value={
                              subscriptionForm.planName
                            }
                            onChange={(event) => {
                              const planName =
                                event.target.value;
                              const plan =
                                getSubscriptionPlan(
                                  planName,
                                );

                              setSubscriptionForm(
                                (current) =>
                                  current
                                    ? {
                                        ...current,
                                        planName,
                                        amountPaid:
                                          String(
                                            plan
                                              ?.monthly_fee
                                            ?? current
                                              .amountPaid,
                                          ),
                                      }
                                    : current,
                              );
                            }}
                            required
                          >
                            {subscriptionPlans.map(
                              (plan) => (
                                <option
                                  key={plan.name}
                                  value={plan.name}
                                >
                                  {plan.display_name} - {formatMoney(plan.monthly_fee)}
                                </option>
                              ),
                            )}
                          </select>
                        </label>

                        <label>
                          <span>Amount received (GHS)</span>
                          <input
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={
                              subscriptionForm.amountPaid
                            }
                            onChange={(event) =>
                              setSubscriptionForm(
                                (current) =>
                                  current
                                    ? {
                                        ...current,
                                        amountPaid:
                                          event.target.value,
                                      }
                                    : current,
                              )
                            }
                            required
                          />
                        </label>

                        <label>
                          <span>Access days</span>
                          <input
                            type="number"
                            min="1"
                            max="366"
                            step="1"
                            value={
                              subscriptionForm.extendDays
                            }
                            onChange={(event) =>
                              setSubscriptionForm(
                                (current) =>
                                  current
                                    ? {
                                        ...current,
                                        extendDays:
                                          event.target.value,
                                      }
                                    : current,
                              )
                            }
                            required
                          />
                        </label>

                        <label>
                          <span>Payment method</span>
                          <select
                            value={
                              subscriptionForm
                                .paymentMethod
                            }
                            onChange={(event) =>
                              setSubscriptionForm(
                                (current) =>
                                  current
                                    ? {
                                        ...current,
                                        paymentMethod:
                                          event.target.value as SubscriptionFormState["paymentMethod"],
                                      }
                                    : current,
                              )
                            }
                          >
                            <option value="momo">Mobile money</option>
                            <option value="cash">Cash</option>
                            <option value="bank">Bank transfer</option>
                            <option value="manual">Manual</option>
                            <option value="paystack">Paystack</option>
                          </select>
                        </label>

                        <label>
                          <span>Payment reference</span>
                          <input
                            maxLength={100}
                            value={
                              subscriptionForm
                                .paymentReference
                            }
                            onChange={(event) =>
                              setSubscriptionForm(
                                (current) =>
                                  current
                                    ? {
                                        ...current,
                                        paymentReference:
                                          event.target.value,
                                      }
                                    : current,
                              )
                            }
                            placeholder="MoMo transaction or receipt ID"
                          />
                        </label>

                        <label className="seller-subscription-note">
                          <span>Internal note</span>
                          <textarea
                            maxLength={500}
                            value={
                              subscriptionForm.note
                            }
                            onChange={(event) =>
                              setSubscriptionForm(
                                (current) =>
                                  current
                                    ? {
                                        ...current,
                                        note:
                                          event.target.value,
                                      }
                                    : current,
                              )
                            }
                          />
                        </label>
                      </div>

                      <div className="seller-subscription-actions">
                        <p>
                          Paid access will start after any
                          remaining valid trial or paid
                          period.
                        </p>
                        <button
                          type="submit"
                          className="seller-primary-button"
                          disabled={
                            busyAction !== null
                          }
                        >
                          {busyAction === "subscription"
                            ? "Recording payment..."
                            : "Confirm paid subscription"}
                        </button>
                      </div>
                    </form>
                  )}

                  <div className="seller-store-publication">
                    <div>
                      <strong>
                        {store.publication_status ===
                        "published"
                          ? "Store is live"
                          : "Store is not public"}
                      </strong>

                      <p>
                        {store.publication_status ===
                        "published"
                          ? "Customers can view this storefront and create new orders."
                          : seller.setup_status !==
                              "completed"
                            ? "The seller must complete invitation setup before publishing."
                            : "Publishing requires a valid trial or subscription and at least one active product."}
                      </p>
                    </div>

                    <button
                      type="button"
                      className={
                        store.publication_status ===
                        "published"
                          ? "seller-secondary-button"
                          : "seller-primary-button"
                      }
                      onClick={() =>
                        void performPublicationAction(
                          store,
                          store.publication_status ===
                          "published"
                            ? "unpublish"
                            : "publish",
                        )
                      }
                      disabled={
                        busyAction !== null ||
                        (
                          store.publication_status !==
                            "published" &&
                          seller.setup_status !==
                            "completed"
                        )
                      }
                    >
                      {publicationStoreId ===
                        store.id &&
                      busyAction === "publish"
                        ? "Publishing..."
                        : publicationStoreId ===
                              store.id &&
                            busyAction ===
                              "unpublish"
                          ? "Unpublishing..."
                          : store.publication_status ===
                              "published"
                            ? "Unpublish store"
                            : "Publish store"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="seller-detail-panel seller-detail-panel-full">
          <div className="seller-detail-panel-heading">
            <div>
              <p className="seller-page-eyebrow">
                Billing history
              </p>
              <h3>Subscription payments</h3>
              <p>
                Confirmed payments recorded by a
                platform administrator.
              </p>
            </div>
            <span className="seller-detail-count">
              {seller.subscription_payment_count}
            </span>
          </div>

          {seller.subscription_payments.length ===
          0 ? (
            <div className="seller-detail-empty">
              No paid subscriptions have been
              recorded yet.
            </div>
          ) : (
            <div className="seller-payment-history">
              {seller.subscription_payments.map(
                (payment) => (
                  <article key={payment.id}>
                    <div className="seller-payment-main">
                      <div>
                        <span>
                          {formatLabel(
                            payment.plan_name,
                          )}
                        </span>
                        <strong>
                          {formatMoney(
                            payment.amount,
                          )}
                        </strong>
                      </div>
                      <span className="seller-payment-method">
                        {formatLabel(
                          payment.payment_method,
                        )}
                      </span>
                    </div>
                    <dl>
                      <div>
                        <dt>Paid</dt>
                        <dd>
                          {formatDateTime(
                            payment.paid_at,
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Access</dt>
                        <dd>
                          {payment.covered_days} days
                        </dd>
                      </div>
                      <div>
                        <dt>Reference</dt>
                        <dd>
                          {payment.payment_reference ||
                            "Not provided"}
                        </dd>
                      </div>
                      <div>
                        <dt>Recorded by</dt>
                        <dd>
                          {payment.approved_by_email ||
                            "Platform admin"}
                        </dd>
                      </div>
                    </dl>
                    {payment.note && (
                      <p>{payment.note}</p>
                    )}
                  </article>
                ),
              )}
            </div>
          )}
        </section>

        <section className="seller-detail-panel">
          <div className="seller-detail-panel-heading">
            <div>
              <p className="seller-page-eyebrow">
                Security history
              </p>

              <h3>
                Account events
              </h3>
            </div>

            <span className="seller-detail-count">
              {seller.account_event_count}
            </span>
          </div>

          {seller.account_events.length === 0 ? (
            <div className="seller-detail-empty">
              No account suspension or
              reactivation events yet.
            </div>
          ) : (
            <div className="seller-detail-timeline">
              {seller.account_events.map(
                (event) => (
                  <article key={event.id}>
                    <span
                      className={`seller-event-dot ${event.action}`}
                      aria-hidden="true"
                    />

                    <div>
                      <strong>
                        {formatLabel(
                          event.action,
                        )}
                      </strong>

                      <p>
                        {formatLabel(
                          event
                            .previous_account_status,
                        )}
                        {" to "}
                        {formatLabel(
                          event
                            .new_account_status,
                        )}
                      </p>

                      {event.reason && (
                        <blockquote>
                          {event.reason}
                        </blockquote>
                      )}

                      <small>
                        {event.actor_email ||
                          "System administrator"}
                        {" - "}
                        {formatDateTime(
                          event.created_at,
                        )}
                      </small>
                    </div>
                  </article>
                ),
              )}
            </div>
          )}
        </section>

        <section className="seller-detail-panel">
          <div className="seller-detail-panel-heading">
            <div>
              <p className="seller-page-eyebrow">
                Invitation history
              </p>

              <h3>
                Issued invitations
              </h3>
            </div>

            <span className="seller-detail-count">
              {seller.invitation_count}
            </span>
          </div>

          {seller.invitations.length === 0 ? (
            <div className="seller-detail-empty">
              No invitation history is
              available.
            </div>
          ) : (
            <div className="seller-invitation-history">
              {seller.invitations.map(
                (invitation) => (
                  <article
                    key={invitation.id}
                  >
                    <div>
                      <span
                        className={`seller-status-pill invitation-${invitation.status}`}
                      >
                        {formatLabel(
                          invitation.status,
                        )}
                      </span>

                      <strong>
                        Issued{" "}
                        {formatDateTime(
                          invitation.created_at,
                        )}
                      </strong>
                    </div>

                    <dl>
                      <div>
                        <dt>Expires</dt>
                        <dd>
                          {formatDateTime(
                            invitation
                              .expires_at,
                          )}
                        </dd>
                      </div>

                      <div>
                        <dt>Accepted</dt>
                        <dd>
                          {formatDateTime(
                            invitation
                              .accepted_at,
                          )}
                        </dd>
                      </div>

                      <div>
                        <dt>Revoked</dt>
                        <dd>
                          {formatDateTime(
                            invitation
                              .revoked_at,
                          )}
                        </dd>
                      </div>
                    </dl>
                  </article>
                ),
              )}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
