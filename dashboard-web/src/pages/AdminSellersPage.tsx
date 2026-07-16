import { AdminSellerDetailPage } from "./AdminSellerDetailPage";
import {
  useEffect,
  useMemo,
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import {
  normalizeGhanaPhoneNumber,
} from "../utils/phone";

import type {
  AdminSellerCreateResponse,
  AdminSellerListItem,
  SellerAccountStatus,
} from "../types/admin-seller";


type SellerFilter =
  | "all"
  | SellerAccountStatus;



type AdminSubscriptionPlanItem = {
  id: string;
  name: string;
  display_name: string;
  monthly_fee: string | number;
  is_quote_only: boolean;
  product_limit?: number | null;
  can_upload_images: boolean;
  can_use_custom_domain: boolean;
  can_receive_online_payments: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};


type ApiFetch = (
  path: string,
  options?: RequestInit,
) => Promise<unknown>;


type AdminSellersPageProps = {
  adminSellers: AdminSellerListItem[];
  loadingAdminSellers: boolean;
  loadingMoreAdminSellers: boolean;
  adminSellerListError: string;
  adminSellersHasMore: boolean;

  loadAdminSellers: (
    append?: boolean,
  ) => void | Promise<void>;

  apiFetch: ApiFetch;

  onSellerCreated: (
  ) => void | Promise<void>;

  subscriptionPlans: AdminSubscriptionPlanItem[];


};


type SellerCreateForm = {
  fullName: string;
  email: string;
  phoneNumber: string;
  storeName: string;
  storeSlug: string;
  planName: string;
};


const emptyCreateForm: SellerCreateForm = {
  fullName: "",
  email: "",
  phoneNumber: "",
  storeName: "",
  storeSlug: "",
  planName: "starter",
};


type StoredSellerDraft = {
  form: SellerCreateForm;
  slugTouched: boolean;
};


type CreatedSellerConfirmation = Omit<
  AdminSellerCreateResponse,
  "invitation_url"
> & {
  invitation_url: string | null;
};


type StoredCreatedSellerConfirmation = Omit<
  AdminSellerCreateResponse,
  "invitation_url"
> & {
  stored_at: number;
};


const sellerDraftStorageKey =
  "storeplug.admin-seller-create-draft.v1";


const createdSellerStorageKey =
  "storeplug.admin-seller-created-summary.v1";


const createdSellerStorageTtlMs =
  12 * 60 * 60 * 1000;


function isStoredCreatedSeller(
  value: unknown,
): value is StoredCreatedSellerConfirmation {
  if (
    !value ||
    typeof value !== "object"
  ) {
    return false;
  }

  const candidate = value as Partial<
    StoredCreatedSellerConfirmation
  >;

  return (
    typeof candidate.seller_id ===
      "string" &&
    typeof candidate.store_id ===
      "string" &&
    typeof candidate.invitation_id ===
      "string" &&
    typeof candidate.full_name ===
      "string" &&
    typeof candidate.email ===
      "string" &&
    (
      candidate.phone_number === null ||
      typeof candidate.phone_number ===
        "string"
    ) &&
    typeof candidate.store_name ===
      "string" &&
    typeof candidate.store_slug ===
      "string" &&
    candidate.account_status ===
      "invited" &&
    candidate.publication_status ===
      "draft" &&
    typeof candidate.plan_name ===
      "string" &&
    candidate.subscription_status ===
      "trial" &&
    (
      typeof candidate.monthly_fee ===
        "string" ||
      typeof candidate.monthly_fee ===
        "number"
    ) &&
    typeof candidate.trial_ends_at ===
      "string" &&
    typeof candidate
      .invitation_expires_at ===
      "string" &&
    typeof candidate.stored_at ===
      "number"
  );
}


function readStoredCreatedSeller(
): CreatedSellerConfirmation | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw =
      window.sessionStorage.getItem(
        createdSellerStorageKey,
      );

    if (!raw) {
      return null;
    }

    const parsed: unknown =
      JSON.parse(raw);

    if (!isStoredCreatedSeller(parsed)) {
      window.sessionStorage.removeItem(
        createdSellerStorageKey,
      );

      return null;
    }

    const age =
      Date.now() - parsed.stored_at;

    if (
      age < 0 ||
      age > createdSellerStorageTtlMs
    ) {
      window.sessionStorage.removeItem(
        createdSellerStorageKey,
      );

      return null;
    }

    return {
      seller_id: parsed.seller_id,
      store_id: parsed.store_id,
      invitation_id:
        parsed.invitation_id,
      full_name: parsed.full_name,
      email: parsed.email,
      phone_number:
        parsed.phone_number,
      store_name: parsed.store_name,
      store_slug: parsed.store_slug,
      account_status:
        parsed.account_status,
      publication_status:
        parsed.publication_status,
      plan_name: parsed.plan_name,
      subscription_status:
        parsed.subscription_status,
      monthly_fee: parsed.monthly_fee,
      trial_ends_at:
        parsed.trial_ends_at,
      invitation_expires_at:
        parsed.invitation_expires_at,

      // Never restore or persist the raw token.
      invitation_url: null,
    };
  } catch {
    return null;
  }
}


function writeStoredCreatedSeller(
  seller: AdminSellerCreateResponse,
) {
  if (typeof window === "undefined") {
    return;
  }

  const safeSummary:
    StoredCreatedSellerConfirmation = {
      seller_id: seller.seller_id,
      store_id: seller.store_id,
      invitation_id:
        seller.invitation_id,
      full_name: seller.full_name,
      email: seller.email,
      phone_number:
        seller.phone_number,
      store_name: seller.store_name,
      store_slug: seller.store_slug,
      account_status:
        seller.account_status,
      publication_status:
        seller.publication_status,
      plan_name: seller.plan_name,
      subscription_status:
        seller.subscription_status,
      monthly_fee: seller.monthly_fee,
      trial_ends_at:
        seller.trial_ends_at,
      invitation_expires_at:
        seller.invitation_expires_at,
      stored_at: Date.now(),
    };

  try {
    window.sessionStorage.setItem(
      createdSellerStorageKey,
      JSON.stringify(safeSummary),
    );
  } catch {
    // Storage may be unavailable in a
    // restricted/private browser context.
  }
}


function clearStoredCreatedSeller() {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.removeItem(
      createdSellerStorageKey,
    );
  } catch {
    // Ignore unavailable browser storage.
  }
}


function readStoredSellerDraft(
): StoredSellerDraft | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.sessionStorage.getItem(
      sellerDraftStorageKey,
    );

    if (!raw) {
      return null;
    }

    const parsed: unknown = JSON.parse(raw);

    if (
      !parsed ||
      typeof parsed !== "object"
    ) {
      return null;
    }

    const candidate = parsed as {
      form?: Partial<SellerCreateForm>;
      slugTouched?: boolean;
    };

    if (
      !candidate.form ||
      typeof candidate.form !== "object"
    ) {
      return null;
    }

    return {
      form: {
        fullName:
          typeof candidate.form.fullName ===
          "string"
            ? candidate.form.fullName
            : "",
        email:
          typeof candidate.form.email ===
          "string"
            ? candidate.form.email
            : "",
        phoneNumber:
          typeof candidate.form.phoneNumber ===
          "string"
            ? candidate.form.phoneNumber
            : "",
        storeName:
          typeof candidate.form.storeName ===
          "string"
            ? candidate.form.storeName
            : "",
        storeSlug:
          typeof candidate.form.storeSlug ===
          "string"
            ? candidate.form.storeSlug
            : "",
        planName:
          typeof candidate.form.planName ===
          "string"
            ? candidate.form.planName
            : "starter",
      },
      slugTouched:
        candidate.slugTouched === true,
    };
  } catch {
    return null;
  }
}


function writeStoredSellerDraft(
  draft: StoredSellerDraft,
) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.setItem(
      sellerDraftStorageKey,
      JSON.stringify(draft),
    );
  } catch {
    // The form remains usable even when
    // browser storage is unavailable.
  }
}


function clearStoredSellerDraft() {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.removeItem(
      sellerDraftStorageKey,
    );
  } catch {
    // Nothing else is required.
  }
}


function getSellerInitials(
  name: string,
): string {
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


function formatLabel(
  value: string,
): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );
}


function formatDate(
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
      day: "numeric",
      month: "short",
      year: "numeric",
    },
  ).format(date);
}


function makeSlug(
  value: string,
): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}


function normalizeSlugDraft(
  value: string,
): string {
  return value
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-{2,}/g, "-")
    .replace(/^-+/g, "")
    .slice(0, 100);
}


function sellerSearchText(
  seller: AdminSellerListItem,
): string {
  return [
    seller.full_name,
    seller.email,
    seller.phone_number || "",
    ...seller.stores.flatMap((store) => [
      store.name,
      store.slug,
      store.plan_name,
    ]),
  ]
    .join(" ")
    .toLowerCase();
}


async function copyInvitationLink(
  value: string,
): Promise<void> {
  if (
    navigator.clipboard &&
    window.isSecureContext
  ) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textarea = document.createElement(
    "textarea",
  );

  textarea.value = value;
  textarea.setAttribute(
    "readonly",
    "",
  );

  textarea.style.position = "fixed";
  textarea.style.opacity = "0";

  document.body.appendChild(textarea);
  textarea.select();

  const copied = document.execCommand("copy");

  document.body.removeChild(textarea);

  if (!copied) {
    throw new Error(
      "Could not copy the invitation link.",
    );
  }
}


export function AdminSellersPage({
  adminSellers,
  loadingAdminSellers,
  loadingMoreAdminSellers,
  adminSellerListError,
  adminSellersHasMore,
  loadAdminSellers,
  apiFetch,
  onSellerCreated,
  subscriptionPlans,
}: AdminSellersPageProps) {
  const [initialStoredState] =
    useState(() => ({
      createdSeller:
        readStoredCreatedSeller(),
      sellerDraft:
        readStoredSellerDraft(),
    }));

  const [view, setView] = useState<
    "list" | "create" | "created" | "detail"
  >(() => {
    if (
      initialStoredState.createdSeller
    ) {
      return "created";
    }

    if (
      initialStoredState.sellerDraft
    ) {
      return "create";
    }

    return "list";
  });

  const [sellerFilter, setSellerFilter] =
    useState<SellerFilter>("all");

  const [search, setSearch] = useState("");

  const [createForm, setCreateForm] =
    useState<SellerCreateForm>(() => {
      return (
        initialStoredState
          .sellerDraft?.form ??
        emptyCreateForm
      );
    });

  const [slugTouched, setSlugTouched] =
    useState(() => {
      return (
        initialStoredState
          .sellerDraft?.slugTouched ??
        false
      );
    });

  const [creatingSeller, setCreatingSeller] =
    useState(false);

  const [createError, setCreateError] =
    useState("");

  const [createdSeller, setCreatedSeller] =
    useState<
      CreatedSellerConfirmation | null
    >(
      initialStoredState.createdSeller,
    );

  const [copied, setCopied] = useState(false);

  const [
    selectedSellerId,
    setSelectedSellerId,
  ] = useState<string | null>(null);

  useEffect(() => {
    if (view !== "create") {
      clearStoredSellerDraft();
      return;
    }

    writeStoredSellerDraft({
      form: createForm,
      slugTouched,
    });
  }, [
    createForm,
    slugTouched,
    view,
  ]);

  const filteredSellers = useMemo(() => {
    const normalizedSearch = search
      .trim()
      .toLowerCase();

    return adminSellers.filter((seller) => {
      if (
        sellerFilter !== "all" &&
        seller.account_status !== sellerFilter
      ) {
        return false;
      }

      if (
        normalizedSearch &&
        !sellerSearchText(seller).includes(
          normalizedSearch,
        )
      ) {
        return false;
      }

      return true;
    });
  }, [
    adminSellers,
    search,
    sellerFilter,
  ]);

  const activePlans = useMemo(() => {
    const planOrder: Record<string, number> = {
      starter: 0,
      business: 1,
      premium: 2,
      custom: 3,
    };

    const plans = subscriptionPlans
      .filter((plan) => plan.is_active)
      .sort(
        (left, right) =>
          (planOrder[left.name] ?? 99) -
          (planOrder[right.name] ?? 99),
      );

    if (plans.length > 0) {
      return plans;
    }

    return [
      {
        id: "starter",
        name: "starter",
        display_name: "Starter",
        monthly_fee: 30,
        is_quote_only: false,
        product_limit: 10,
        can_upload_images: true,
        can_use_custom_domain: false,
        can_receive_online_payments: true,
        is_active: true,
        created_at: "",
        updated_at: "",
      },
    ];
  }, [subscriptionPlans]);

  function updateCreateField(
    field: keyof SellerCreateForm,
    value: string,
  ) {
    setCreateForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function openSellerDetail(
    sellerId: string,
  ) {
    clearStoredCreatedSeller();
    setSelectedSellerId(sellerId);
    setView("detail");

    window.scrollTo({
      top: 0,
      left: 0,
      behavior: "auto",
    });
  }

  function closeSellerDetail() {
    setSelectedSellerId(null);
    setView("list");

    window.scrollTo({
      top: 0,
      left: 0,
      behavior: "auto",
    });
  }

  function openCreateView() {
    clearStoredCreatedSeller();
    setCreateError("");
    setCopied(false);
    setCreatedSeller(null);
    setView("create");
  }

  function returnToList() {
    clearStoredCreatedSeller();
    clearStoredSellerDraft();
    setCreateForm(emptyCreateForm);
    setSlugTouched(false);
    setCreateError("");
    setCopied(false);
    setCreatedSeller(null);
    setView("list");
  }

  function resetCreateForm() {
    clearStoredCreatedSeller();
    clearStoredSellerDraft();
    setCreateForm(emptyCreateForm);
    setSlugTouched(false);
    setCreateError("");
    setCopied(false);
    setCreatedSeller(null);
  }

  async function submitSeller(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (creatingSeller) {
      return;
    }

    const fullName =
      createForm.fullName.trim();

    const email = createForm.email
      .trim()
      .toLowerCase();

    const phoneNumber =
      createForm.phoneNumber.trim();

    const storeName =
      createForm.storeName.trim();

    const storeSlug = makeSlug(
      createForm.storeSlug,
    );

    if (
      !fullName ||
      !email ||
      !storeName ||
      !storeSlug
    ) {
      setCreateError(
        "Complete all required seller and store fields.",
      );
      return;
    }

    if (
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
        email,
      )
    ) {
      setCreateError(
        "Enter a valid seller email address.",
      );
      return;
    }

    if (storeSlug.length < 3) {
      setCreateError(
        "Store slug must contain at least 3 characters.",
      );
      return;
    }

    let normalizedPhoneNumber: string | null;

    try {
      normalizedPhoneNumber =
        normalizeGhanaPhoneNumber(phoneNumber);
    } catch (error) {
      setCreateError(
        error instanceof Error
          ? error.message
          : "Enter a valid Ghana mobile number.",
      );
      return;
    }

    setCreatingSeller(true);
    setCreateError("");
    setCopied(false);

    try {
      const response = (
        await apiFetch(
          "/admin/sellers",
          {
            method: "POST",
            body: JSON.stringify({
              full_name: fullName,
              email,
              phone_number:
                normalizedPhoneNumber,
              store_name: storeName,
              store_slug: storeSlug,
              plan_name:
                createForm.planName,
            }),
          },
        )
      ) as AdminSellerCreateResponse;

      clearStoredSellerDraft();
      writeStoredCreatedSeller(response);
      setCreatedSeller(response);
      setView("created");

      void Promise.resolve(
        onSellerCreated(),
      ).catch(() => undefined);
    } catch (error) {
      setCreateError(
        error instanceof Error
          ? error.message
          : "Could not create the seller.",
      );
    } finally {
      setCreatingSeller(false);
    }
  }

  async function copyCreatedInvitation() {
    const invitationUrl =
      createdSeller?.invitation_url;

    if (!invitationUrl) {
      return;
    }

    try {
      await copyInvitationLink(
        invitationUrl,
      );

      setCopied(true);
    } catch (error) {
      setCreateError(
        error instanceof Error
          ? error.message
          : "Could not copy the invitation link.",
      );
    }
  }

  if (
    view === "detail" &&
    selectedSellerId
  ) {
    return (
      <AdminSellerDetailPage
        sellerId={selectedSellerId}
        apiFetch={apiFetch}
        onBack={closeSellerDetail}
        onSellerChanged={() =>
          loadAdminSellers(false)
        }
      />
    );
  }

  if (
    view === "created" &&
    createdSeller
  ) {
    return (
      <section className="seller-created-page">
        <div className="seller-created-card">
          <div
            className="seller-created-icon"
            aria-hidden="true"
          >
            <svg
              viewBox="0 0 24 24"
              focusable="false"
            >
              <path
                d="M4.5 6.75h15v10.5h-15z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path
                d="m5.25 7.5 6.75 5 6.75-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="m14.9 16.15 1.65 1.65 3-3.4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <p className="seller-page-eyebrow">
            Seller invited
          </p>

          <h2>
            {createdSeller.full_name} is ready
            to complete setup
          </h2>

          <p className="seller-created-intro">
            {createdSeller.invitation_url
              ? (
                <>
                  The seller account and draft
                  store were created
                  successfully. Copy the private
                  invitation link and send it
                  directly to the seller.
                </>
              )
              : (
                <>
                  The seller account and draft
                  store were created
                  successfully. This confirmation
                  was securely restored without
                  saving the private invitation
                  token.
                </>
              )}
          </p>

          <div className="seller-created-summary">
            <div>
              <span>Seller</span>
              <strong>
                {createdSeller.full_name}
              </strong>
              <small>
                {createdSeller.email}
              </small>
            </div>

            <div>
              <span>Draft store</span>
              <strong>
                {createdSeller.store_name}
              </strong>
              <small>
                /{createdSeller.store_slug}
              </small>
            </div>

            <div>
              <span>Plan</span>
              <strong>
                {formatLabel(
                  createdSeller.plan_name,
                )}
              </strong>
              <small>
                14-day trial
              </small>
            </div>

            <div>
              <span>Invitation expires</span>
              <strong>
                {formatDate(
                  createdSeller
                    .invitation_expires_at,
                )}
              </strong>
              <small>
                Account remains invited
              </small>
            </div>
          </div>

          {createdSeller.invitation_url ? (
            <div className="invitation-link-panel">
              <label htmlFor="created-invitation-link">
                Private invitation link
              </label>

              <div className="invitation-link-row">
                <input
                  id="created-invitation-link"
                  value={
                    createdSeller.invitation_url
                  }
                  readOnly
                  onFocus={(event) =>
                    event.currentTarget.select()
                  }
                />

                <button
                  type="button"
                  className="seller-primary-button"
                  onClick={
                    copyCreatedInvitation
                  }
                >
                  {copied
                    ? "Copied"
                    : "Copy invitation link"}
                </button>
              </div>

              <p>
                This link contains a single-use
                security token. It is not saved
                in the dashboard after you leave
                this screen.
              </p>
            </div>
          ) : (
            <div
              className="invitation-link-panel invitation-link-unavailable"
              role="status"
            >
              <div
                className="invitation-link-unavailable-icon"
                aria-hidden="true"
              >
                <svg viewBox="0 0 24 24">
                  <path
                    d="M7 10V8a5 5 0 0 1 10 0v2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                  <rect
                    x="5"
                    y="10"
                    width="14"
                    height="10"
                    rx="2.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                </svg>
              </div>

              <div className="invitation-link-unavailable-copy">
                <strong>
                  Private invitation link is no
                  longer displayed
                </strong>

                <p>
                  StorePlug never saves the raw
                  security token. A link you
                  already copied remains valid
                  until it is used, revoked, or
                  expires.
                </p>

                <small>
                  Generate a replacement from
                  seller details only when
                  necessary. A replacement
                  revokes the previous active
                  invitation.
                </small>
              </div>
            </div>
          )}

          {createError && (
            <div className="seller-inline-error">
              {createError}
            </div>
          )}

          <div className="seller-created-actions">
            <button
              type="button"
              className="seller-secondary-button"
              onClick={returnToList}
            >
              Back to sellers
            </button>

            <button
              type="button"
              className="seller-secondary-button"
              onClick={() =>
                openSellerDetail(
                  createdSeller.seller_id,
                )
              }
            >
              View seller
            </button>

            <button
              type="button"
              className="seller-primary-button"
              onClick={() => {
                resetCreateForm();
                setView("create");
              }}
            >
              Add another seller
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (view === "create") {
    return (
      <section className="seller-create-page">
        <div className="seller-page-heading">
          <div>
            <p className="seller-page-eyebrow">
              Platform Admin
            </p>

            <h2>Add seller</h2>

            <p>
              Create the seller account and its
              first draft storefront. The seller
              will set their own password from
              the invitation link.
            </p>
          </div>

          <button
            type="button"
            className="seller-secondary-button"
            onClick={returnToList}
          >
            Back to sellers
          </button>
        </div>

        <form
          className="seller-create-form"
          onSubmit={submitSeller}
        >
          <section className="seller-form-section">
            <div className="seller-form-section-heading">
              <span>01</span>

              <div>
                <h3>Seller account</h3>
                <p>
                  The seller signs in with this
                  email after accepting the
                  invitation.
                </p>
              </div>
            </div>

            <div className="seller-form-grid">
              <label>
                <span>Full name</span>
                <input
                  value={createForm.fullName}
                  onChange={(event) =>
                    updateCreateField(
                      "fullName",
                      event.target.value,
                    )
                  }
                  placeholder="e.g. Ama Mensah"
                  autoComplete="name"
                  required
                />
              </label>

              <label>
                <span>Email address</span>
                <input
                  type="email"
                  value={createForm.email}
                  onChange={(event) =>
                    updateCreateField(
                      "email",
                      event.target.value,
                    )
                  }
                  placeholder="ama@example.com"
                  autoComplete="email"
                  required
                />
              </label>

              <label>
                <span>
                  Phone number
                  <small>Optional</small>
                </span>
                <input
                  value={
                    createForm.phoneNumber
                  }
                  onChange={(event) =>
                    updateCreateField(
                      "phoneNumber",
                      event.target.value,
                    )
                  }
                  placeholder="+233..."
                  autoComplete="tel"
                />
              </label>
            </div>
          </section>

          <section className="seller-form-section">
            <div className="seller-form-section-heading">
              <span>02</span>

              <div>
                <h3>First storefront</h3>
                <p>
                  The store starts as a draft and
                  remains invisible until it is
                  published separately.
                </p>
              </div>
            </div>

            <div className="seller-form-grid">
              <label>
                <span>Store name</span>
                <input
                  value={createForm.storeName}
                  onChange={(event) => {
                    const value =
                      event.target.value;

                    updateCreateField(
                      "storeName",
                      value,
                    );

                    if (!slugTouched) {
                      updateCreateField(
                        "storeSlug",
                        makeSlug(value),
                      );
                    }
                  }}
                  placeholder="e.g. Ama Styles"
                  required
                />
              </label>

              <label>
                <span>Store slug</span>

                <div className="seller-slug-input">
                  <span>/</span>

                  <input
                    value={
                      createForm.storeSlug
                    }
                    onChange={(event) => {
                      setSlugTouched(true);

                      updateCreateField(
                        "storeSlug",
                        normalizeSlugDraft(
                          event.target.value,
                        ),
                      );
                    }}
                    onBlur={() => {
                      updateCreateField(
                        "storeSlug",
                        makeSlug(
                          createForm.storeSlug,
                        ),
                      );
                    }}
                    placeholder="ama-styles"
                    inputMode="text"
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    aria-label="Store slug"
                    required
                  />
                </div>
              </label>

              <label>
                <span>Starting plan</span>
                <select
                  value={createForm.planName}
                  onChange={(event) =>
                    updateCreateField(
                      "planName",
                      event.target.value,
                    )
                  }
                >
                  {activePlans.map((plan) => (
                    <option
                      key={plan.id}
                      value={plan.name}
                    >
                      {plan.display_name}
                      {plan.is_quote_only
                        ? " - Quote only"
                        : ` - GHS ${Number(
                            plan.monthly_fee,
                          ).toFixed(2)}`}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="seller-onboarding-note">
              <strong>
                Onboarding defaults
              </strong>

              <div className="seller-onboarding-defaults">
                <span>14-day trial</span>
                <span>GHS 0 during trial</span>
                <span>Draft storefront</span>
              </div>
            </div>
          </section>

          {createError && (
            <div className="seller-inline-error">
              {createError}
            </div>
          )}

          <div className="seller-form-actions">
            <button
              type="button"
              className="seller-secondary-button"
              onClick={returnToList}
              disabled={creatingSeller}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="seller-primary-button"
              disabled={creatingSeller}
            >
              {creatingSeller
                ? "Creating seller..."
                : "Create seller and invitation"}
            </button>
          </div>
        </form>
      </section>
    );
  }

  return (
    <section className="seller-accounts-page">
      <div className="seller-accounts-hero">
        <div>
          <p className="seller-page-eyebrow">
            Seller accounts
          </p>

          <h2>
            Manage onboarding and access
          </h2>

          <p>
            Seller account state is kept
            separate from store publication,
            subscriptions, and store
            suspension.
          </p>
        </div>

        <button
          type="button"
          className="seller-primary-button"
          onClick={openCreateView}
        >
          Add seller
        </button>
      </div>

      <div className="seller-account-summary">
        {(
          [
            ["All", "all"],
            ["Invited", "invited"],
            ["Active", "active"],
            ["Suspended", "suspended"],
          ] as const
        ).map(([label, value]) => {
          const count =
            value === "all"
              ? adminSellers.length
              : adminSellers.filter(
                  (seller) =>
                    seller.account_status ===
                    value,
                ).length;

          return (
            <button
              key={value}
              type="button"
              className={
                sellerFilter === value
                  ? "active"
                  : ""
              }
              onClick={() =>
                setSellerFilter(value)
              }
            >
              <span>{label}</span>
              <strong>{count}</strong>
            </button>
          );
        })}
      </div>

      <div className="seller-list-toolbar">
        <div className="seller-search-field">
          <svg
            className="seller-search-icon"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              cx="11"
              cy="11"
              r="6.5"
            />
            <path d="m16 16 4 4" />
          </svg>

          <input
            value={search}
            onChange={(event) =>
              setSearch(event.target.value)
            }
            placeholder="Search sellers, stores, email or phone"
            aria-label="Search sellers"
          />

          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
            >
              Clear
            </button>
          )}
        </div>

        <button
          type="button"
          className="seller-secondary-button"
          onClick={() =>
            loadAdminSellers(false)
          }
          disabled={loadingAdminSellers}
        >
          {loadingAdminSellers
            ? "Refreshing..."
            : "Refresh"}
        </button>
      </div>

      {adminSellerListError && (
        <div className="seller-inline-error">
          <strong>
            Seller accounts could not be loaded.
          </strong>
          <span>{adminSellerListError}</span>

          <button
            type="button"
            onClick={() =>
              loadAdminSellers(false)
            }
          >
            Try again
          </button>
        </div>
      )}

      {loadingAdminSellers &&
      adminSellers.length === 0 ? (
        <div className="seller-list-loading">
          <span />
          <span />
          <span />
        </div>
      ) : adminSellers.length === 0 ? (
        <div className="seller-list-empty">
          <div aria-hidden="true">SP</div>

          <h3>No seller accounts yet</h3>

          <p>
            Add your first seller to create their
            account, draft store, trial, and
            private invitation.
          </p>

          <button
            type="button"
            className="seller-primary-button"
            onClick={openCreateView}
          >
            Add first seller
          </button>
        </div>
      ) : filteredSellers.length === 0 ? (
        <div className="seller-list-empty compact">
          <h3>No matching sellers</h3>

          <p>
            Change the search text or account
            filter.
          </p>

          <button
            type="button"
            className="seller-secondary-button"
            onClick={() => {
              setSearch("");
              setSellerFilter("all");
            }}
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="seller-account-list">
          {filteredSellers.map((seller) => {
            const primaryStore =
              seller.stores[0] || null;

            return (
              <article
                key={seller.seller_id}
                className="seller-account-card"
              >
                <div className="seller-account-identity">
                  <div className="seller-avatar">
                    {getSellerInitials(seller.full_name)}
                  </div>

                  <div>
                    <h3>{seller.full_name}</h3>
                    <p>{seller.email}</p>

                    {seller.phone_number && (
                      <span>
                        {seller.phone_number}
                      </span>
                    )}
                  </div>
                </div>

                <div className="seller-account-statuses">
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
                </div>

                <div className="seller-account-store">
                  <span>Primary store</span>

                  {primaryStore ? (
                    <>
                      <strong>
                        {primaryStore.name}
                      </strong>

                      <small>
                        /{primaryStore.slug}
                      </small>
                    </>
                  ) : (
                    <strong>No store</strong>
                  )}
                </div>

                <div className="seller-account-meta">
                  <div>
                    <span>Stores</span>
                    <strong>
                      {seller.store_count}
                    </strong>
                  </div>

                  <div>
                    <span>Invitation</span>
                    <strong>
                      {formatLabel(
                        seller.invitation_status,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>Added</span>
                    <strong>
                      {formatDate(
                        seller.created_at,
                      )}
                    </strong>
                  </div>
                </div>
                <div className="seller-account-card-actions">
                  <button
                    type="button"
                    className="seller-view-button"
                    onClick={() =>
                      openSellerDetail(
                        seller.seller_id,
                      )
                    }
                    aria-label={`View ${seller.full_name}`}
                  >
                    <span>View seller</span>

                    <svg
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        d="m9 5 7 7-7 7"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </div>

              </article>
            );
          })}
        </div>
      )}

      {adminSellersHasMore &&
        sellerFilter === "all" &&
        !search && (
          <div className="seller-load-more">
            <button
              type="button"
              className="seller-secondary-button"
              onClick={() =>
                loadAdminSellers(true)
              }
              disabled={
                loadingMoreAdminSellers
              }
            >
              {loadingMoreAdminSellers
                ? "Loading more..."
                : "Load more sellers"}
            </button>
          </div>
        )}
    </section>
  );
}
