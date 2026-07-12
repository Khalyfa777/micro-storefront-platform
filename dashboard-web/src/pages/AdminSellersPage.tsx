import {
  useEffect,
  useMemo,
  useState,
} from "react";

import type {
  Dispatch,
  FormEvent,
  SetStateAction,
} from "react";

import type {
  AdminSellerCreateResponse,
  AdminSellerListItem,
  SellerAccountStatus,
} from "../types/admin-seller";


type SellerFilter =
  | "all"
  | SellerAccountStatus;


type AdminStoreFilter =
  | "all"
  | "active"
  | "trial"
  | "expired"
  | "suspended"
  | "expiring";


type AdminStoreItem = {
  id: string;
  owner_id: string;
  owner_email: string;
  owner_name: string;
  slug: string;
  name: string;
  plan_name: string;
  subscription_status: string;
  monthly_fee: string | number;
  subscription_ends_at?: string | null;
  last_payment_at?: string | null;
  is_active: boolean;
  is_suspended: boolean;
};


type AdminSubscriptionPlanItem = {
  id: string;
  name: string;
  display_name: string;
  monthly_fee: string | number;
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

  /*
   * Legacy store-operation props stay wired
   * temporarily. Their UI has been removed from
   * the seller list and will move into seller detail.
   */
  adminStores: AdminStoreItem[];
  filteredAdminStores: AdminStoreItem[];
  adminStoreSearch: string;
  setAdminStoreSearch: (value: string) => void;
  adminStoreFilter: AdminStoreFilter;
  setAdminStoreFilter: Dispatch<
    SetStateAction<AdminStoreFilter>
  >;
  adminPlanDrafts: Record<string, string>;
  setAdminPlanDrafts: Dispatch<
    SetStateAction<Record<string, string>>
  >;
  loadingSubscriptionPlans: boolean;
  loadAdminStores: () => void | Promise<void>;
  loadingAdminStores: boolean;
  exportAdminStoresCsv: () => void;
  formatPlanName: (
    value?: string | null
  ) => string;
  formatMonthlyFee: (
    value?: string | number | null
  ) => string;
  formatSubscriptionDate: (
    value?: string | null
  ) => string;
  getComputedSubscriptionStatus: (
    status?: string | null,
    endsAt?: string | null,
    isSuspended?: boolean,
  ) => string;
  getSubscriptionTimeClass: (
    status?: string | null,
    endsAt?: string | null,
    isSuspended?: boolean,
  ) => string;
  getSubscriptionTimeLabel: (
    status?: string | null,
    endsAt?: string | null,
    isSuspended?: boolean,
  ) => string;
  extendSelectedStoreSubscription: (
  ) => void | Promise<void>;
  extendAdminStoreSubscription: (
    storeId: string
  ) => void | Promise<void>;
  adminChangeStorePlan: (
    store: AdminStoreItem
  ) => void | Promise<void>;
  adminSetStoreSuspension: (
    store: AdminStoreItem,
    suspended: boolean,
  ) => void | Promise<void>;
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


const sellerDraftStorageKey =
  "storeplug.admin-seller-create-draft.v1";


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
  const [view, setView] = useState<
    "list" | "create" | "created"
  >(() =>
    readStoredSellerDraft()
      ? "create"
      : "list"
  );

  const [sellerFilter, setSellerFilter] =
    useState<SellerFilter>("all");

  const [search, setSearch] = useState("");

  const [createForm, setCreateForm] =
    useState<SellerCreateForm>(() => {
      return (
        readStoredSellerDraft()?.form ??
        emptyCreateForm
      );
    });

  const [slugTouched, setSlugTouched] =
    useState(() => {
      return (
        readStoredSellerDraft()
          ?.slugTouched ?? false
      );
    });

  const [creatingSeller, setCreatingSeller] =
    useState(false);

  const [createError, setCreateError] =
    useState("");

  const [createdSeller, setCreatedSeller] =
    useState<
      AdminSellerCreateResponse | null
    >(null);

  const [copied, setCopied] = useState(false);

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

  function openCreateView() {
    setCreateError("");
    setCopied(false);
    setCreatedSeller(null);
    setView("create");
  }

  function returnToList() {
    clearStoredSellerDraft();
    setCreateForm(emptyCreateForm);
    setSlugTouched(false);
    setCreateError("");
    setCopied(false);
    setCreatedSeller(null);
    setView("list");
  }

  function resetCreateForm() {
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
                phoneNumber || null,
              store_name: storeName,
              store_slug: storeSlug,
              plan_name:
                createForm.planName,
            }),
          },
        )
      ) as AdminSellerCreateResponse;

      clearStoredSellerDraft();
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
    if (!createdSeller) {
      return;
    }

    try {
      await copyInvitationLink(
        createdSeller.invitation_url,
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
            ?
          </div>

          <p className="seller-page-eyebrow">
            Seller invited
          </p>

          <h2>
            {createdSeller.full_name} is ready
            to complete setup
          </h2>

          <p className="seller-created-intro">
            The seller account and draft store
            were created successfully. Copy the
            private invitation link and send it
            directly to the seller.
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
              security token. It is not saved in
              the dashboard after you leave this
              screen.
            </p>
          </div>

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
                      {plan.name === "custom"
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
            placeholder="Search seller, email, phone, store, or slug"
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
                    {seller.full_name
                      .split(/\s+/)
                      .slice(0, 2)
                      .map((part) => part[0])
                      .join("")
                      .toUpperCase()}
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
