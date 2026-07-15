import type {
  Dispatch,
  FormEvent,
  SetStateAction,
} from "react";
import {
  resolveDashboardMediaUrl,
} from "../utils/api-url";

type StoreForm = {
  name: string;
  slug: string;
  bio: string;
  whatsapp_number: string;
  logo_url: string;
  banner_url: string;
  category: string;
};

type StoreSummary = {
  plan_name?: string | null;
  subscription_status?: string | null;
  monthly_fee?: string | number | null;
  trial_ends_at?: string | null;
  subscription_ends_at?: string | null;
  is_suspended?: boolean | null;
};

type StoreSubscriptionUsage = {
  plan_name: string;
  display_name: string;
  monthly_fee: string | number;
  is_quote_only: boolean;
  product_limit?: number | null;
  active_products: number;
  remaining_products?: number | null;
  is_unlimited: boolean;
  can_upload_images: boolean;
  can_use_custom_domain: boolean;
  can_receive_online_payments: boolean;
  plan_is_active: boolean;
};

type StoreProfilePageProps = {
  selectedStore: StoreSummary | null;
  storeForm: StoreForm;
  setStoreForm:
    Dispatch<SetStateAction<StoreForm>>;
  subscriptionUsage:
    StoreSubscriptionUsage | null;
  loadingSubscriptionUsage: boolean;
  saveStoreSettings:
    (
      event: FormEvent<HTMLFormElement>
    ) => void | Promise<void>;
  makeSlug: (value: string) => string;
  uploadStoreImage:
    (
      file: File,
      type: "logo" | "banner",
    ) => void | Promise<void>;
  formatPlanName:
    (value?: string | null) => string;
  getComputedSubscriptionStatus: (
    status?: string | null,
    trialEndsAt?: string | null,
    subscriptionEndsAt?: string | null,
    isSuspended?: boolean | null,
  ) => string;
  formatMonthlyFee:
    (
      value?: string | number | null
    ) => string;
  formatSubscriptionDate:
    (value?: string | null) => string;
  formatProductUsageLabel:
    (
      usage?: StoreSubscriptionUsage | null
    ) => string;
  getProductUsageClass:
    (
      usage?: StoreSubscriptionUsage | null
    ) => string;
  getProductUsagePercent:
    (
      usage?: StoreSubscriptionUsage | null
    ) => number;
  formatRemainingProducts:
    (
      usage?: StoreSubscriptionUsage | null
    ) => string;
};

export function StoreProfilePage({
  selectedStore,
  storeForm,
  setStoreForm,
  subscriptionUsage,
  loadingSubscriptionUsage,
  saveStoreSettings,
  makeSlug,
  uploadStoreImage,
  formatPlanName,
  getComputedSubscriptionStatus,
  formatMonthlyFee,
  formatSubscriptionDate,
  formatProductUsageLabel,
  getProductUsageClass,
  getProductUsagePercent,
  formatRemainingProducts,
}: StoreProfilePageProps) {
  const computedSubscriptionStatus =
    selectedStore
      ? getComputedSubscriptionStatus(
          selectedStore.subscription_status,
          selectedStore.trial_ends_at,
          selectedStore.subscription_ends_at,
          selectedStore.is_suspended,
        )
      : "";

  const isTrialSubscription =
    selectedStore?.subscription_status === "trial";

  const isExpiredTrial =
    isTrialSubscription &&
    computedSubscriptionStatus === "expired";

  const isQuoteOnly =
    subscriptionUsage?.is_quote_only
    ?? selectedStore?.plan_name === "custom";

  const standardMonthlyFee =
    subscriptionUsage?.monthly_fee
    ?? selectedStore?.monthly_fee
    ?? 0;

  const standardPriceLabel = isQuoteOnly
    ? "Custom quote"
    : `${formatMonthlyFee(standardMonthlyFee)}/month`;

  const currentMonthlyFee =
    selectedStore?.monthly_fee
    ?? standardMonthlyFee;

  const logoPreviewUrl =
    resolveDashboardMediaUrl(
      storeForm.logo_url,
    );

  const bannerPreviewUrl =
    resolveDashboardMediaUrl(
      storeForm.banner_url,
    );

  const subscriptionExpiry =
    isTrialSubscription
      ? selectedStore?.trial_ends_at
      : selectedStore?.subscription_ends_at;

  return (
    <div className="settings-layout store-profile-page">
      <form className="settings-card" onSubmit={saveStoreSettings}>
        <h2>Store profile</h2>

        {selectedStore && (
          <div className="subscription-summary-card">
            <div>
              <span>Current plan</span>
              <strong>{formatPlanName(selectedStore.plan_name)}</strong>
            </div>

            <div>
              <span>Status</span>
              <strong
                className={`subscription-status ${computedSubscriptionStatus}`}
              >
                {formatPlanName(
                  computedSubscriptionStatus,
                )}
              </strong>
            </div>

            <div className="subscription-charge-summary">
              <span>
                {isTrialSubscription
                  ? "Trial charge"
                  : "Monthly fee"}
              </span>
              <strong>
                {isTrialSubscription
                  ? isExpiredTrial
                    ? "Trial ended"
                    : "GHS 0 during trial"
                  : formatMonthlyFee(
                      currentMonthlyFee,
                    )}
              </strong>
              {isTrialSubscription && (
                <small>
                  {loadingSubscriptionUsage
                    ? "Loading standard price..."
                    : subscriptionUsage
                      ? (
                          <>
                            Standard price:{" "}
                            {standardPriceLabel}
                          </>
                        )
                      : "Standard price unavailable"}
                </small>
              )}
            </div>

            <div>
              <span>Expires</span>
              <strong>{formatSubscriptionDate(subscriptionExpiry)}</strong>
            </div>
          </div>
        )}

        {selectedStore && (
          <div className="product-usage-card">
            <div className="product-usage-head">
              <div>
                <span>Product usage</span>
                <h3>{subscriptionUsage?.display_name || formatPlanName(selectedStore.plan_name)}</h3>
              </div>

              <strong>
                {loadingSubscriptionUsage ? "Loading..." : formatProductUsageLabel(subscriptionUsage)}
              </strong>
            </div>

            <div className="product-usage-progress">
              <div
                className={`product-usage-progress-fill ${getProductUsageClass(subscriptionUsage)}`}
                style={{ width: `${getProductUsagePercent(subscriptionUsage)}%` }}
              />
            </div>

            <div className="product-usage-meta">
              <span>{formatRemainingProducts(subscriptionUsage)}</span>
              <span>
                {isTrialSubscription
                  ? "Standard plan: "
                  : "Monthly fee: "}
                {isTrialSubscription
                  ? standardPriceLabel
                  : formatMonthlyFee(
                      currentMonthlyFee,
                    )}
              </span>
            </div>

            {subscriptionUsage && (
              <div className="plan-feature-chips">
                <span className={`plan-feature-chip ${subscriptionUsage.can_upload_images ? "enabled" : "disabled"}`}>
                  Images: {subscriptionUsage.can_upload_images ? "Enabled" : "Disabled"}
                </span>

                <span className={`plan-feature-chip ${subscriptionUsage.can_receive_online_payments ? "enabled" : "disabled"}`}>
                  Online payments: {subscriptionUsage.can_receive_online_payments ? "Enabled" : "Disabled"}
                </span>

                <span className={`plan-feature-chip ${subscriptionUsage.can_use_custom_domain ? "enabled" : "disabled"}`}>
                  Custom domain: {subscriptionUsage.can_use_custom_domain ? "Enabled" : "Disabled"}
                </span>

                <span className={`plan-feature-chip ${subscriptionUsage.plan_is_active ? "enabled" : "disabled"}`}>
                  Plan: {subscriptionUsage.plan_is_active ? "Active" : "Inactive"}
                </span>
              </div>
            )}
          </div>
        )}

        <label>
          Store name
          <input
            value={storeForm.name}
            onChange={(e) => setStoreForm((prev: StoreForm) => ({ ...prev, name: e.target.value }))}
            placeholder="e.g. Accra Style Hub"
            required
          />
        </label>

        <label>
          Store slug
          <input
            value={storeForm.slug}
            onChange={(e) =>
              setStoreForm((prev: StoreForm) => ({
                ...prev,
                slug: makeSlug(e.target.value),
              }))
            }
            placeholder="e.g. accra-style-hub"
            required
          />
        </label>

        <label>
          Bio
          <textarea
            value={storeForm.bio}
            onChange={(e) => setStoreForm((prev: StoreForm) => ({ ...prev, bio: e.target.value }))}
            placeholder="e.g. Fashion, accessories, and everyday essentials."
          />
        </label>

        <label>
          WhatsApp number
          <input
            value={storeForm.whatsapp_number}
            onChange={(e) =>
              setStoreForm((prev: StoreForm) => ({
                ...prev,
                whatsapp_number: e.target.value,
              }))
            }
            placeholder="e.g. 0544494613"
            inputMode="tel"
            autoComplete="tel"
            maxLength={20}
          />
          <small className="field-help-text">
            Use one Ghana number only. Local format
            (0544494613) is accepted and saved as
            233544494613.
          </small>
        </label>

        {subscriptionUsage?.can_upload_images === false && (
          <p className="plan-restriction-note">
            Logo and banner uploads are disabled on your current plan. Upgrade to enable store branding images.
          </p>
        )}

        <label
          className={
            "upload-dropzone store-brand-upload "
            + (
              loadingSubscriptionUsage
              || subscriptionUsage
                ?.can_upload_images === false
                ? "disabled"
                : ""
            )
          }
        >
          <input
            className="upload-file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            aria-label="Choose a store logo"
            disabled={loadingSubscriptionUsage || subscriptionUsage?.can_upload_images === false}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadStoreImage(file, "logo");
            }}
          />

          <span className="upload-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <rect x="5" y="5" width="14" height="14" rx="3" />
              <circle cx="10" cy="10" r="1.5" />
              <path d="m7.5 17 3.5-3.5 2.2 2.2 1.6-1.6 2.7 2.9" />
            </svg>
          </span>
          <span>
            <strong>Upload store logo</strong>
            <small>
              Square JPEG, PNG, or WEBP
            </small>
          </span>
        </label>

        {logoPreviewUrl && (
          <div className="uploaded-image-preview">
            <img
              src={logoPreviewUrl}
              alt="Store logo preview"
            />
            <p>Logo uploaded successfully</p>
          </div>
        )}

        <label
          className={
            "upload-dropzone store-brand-upload "
            + (
              loadingSubscriptionUsage
              || subscriptionUsage
                ?.can_upload_images === false
                ? "disabled"
                : ""
            )
          }
        >
          <input
            className="upload-file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            aria-label="Choose a store banner"
            disabled={loadingSubscriptionUsage || subscriptionUsage?.can_upload_images === false}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadStoreImage(file, "banner");
            }}
          />

          <span className="upload-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <rect x="3.5" y="6.5" width="17" height="11" rx="2.5" />
              <circle cx="9" cy="10.5" r="1.25" />
              <path d="m6 15 3.3-3 2.6 2.1 2.1-1.8 4 2.7" />
            </svg>
          </span>
          <span>
            <strong>Upload store banner</strong>
            <small>
              Wide JPEG, PNG, or WEBP
            </small>
          </span>
        </label>

        {bannerPreviewUrl && (
          <div className="uploaded-image-preview">
            <img
              src={bannerPreviewUrl}
              alt="Store banner preview"
            />
            <p>Banner uploaded successfully</p>
          </div>
        )}

        <label>
          Category
          <input
            value={storeForm.category}
            onChange={(e) => setStoreForm((prev: StoreForm) => ({ ...prev, category: e.target.value }))}
            placeholder="Fashion"
          />
        </label>

        <button type="submit">Save store settings</button>
      </form>

      <aside className="settings-preview">
        <h2>Preview</h2>

        {storeForm.banner_url && (
          <img className="banner-preview" src={storeForm.banner_url} alt="Store banner" />
        )}

        {storeForm.logo_url && (
          <img className="logo-preview" src={storeForm.logo_url} alt="Store logo" />
        )}

        <h3>{storeForm.name || "Store name"}</h3>
        <p className="muted">/{storeForm.slug || "store-slug"}</p>
        <p>{storeForm.bio || "Store bio will appear here."}</p>
        <p>WhatsApp: {storeForm.whatsapp_number || "Not added"}</p>
        <p>Category: {storeForm.category || "Not added"}</p>
      </aside>
    </div>
  );
}
