import type { FormEvent } from "react";

type StoreForm = {
  name: string;
  slug: string;
  bio: string;
  whatsapp_number: string;
  logo_url: string;
  banner_url: string;
  category: string;
};

type StoreProfilePageProps = {
  selectedStore: any;
  storeForm: StoreForm;
  setStoreForm: any;
  subscriptionUsage: any;
  loadingSubscriptionUsage: boolean;
  saveStoreSettings: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  makeSlug: (value: string) => string;
  uploadStoreImage: (file: File, type: "logo" | "banner") => void | Promise<void>;
  formatPlanName: (value?: string | null) => string;
  getComputedSubscriptionStatus: (
    status?: string | null,
    endsAt?: string | null,
    isSuspended?: boolean
  ) => string;
  formatMonthlyFee: (value?: string | number | null) => string;
  formatSubscriptionDate: (value?: string | null) => string;
  formatProductUsageLabel: (usage?: any) => string;
  getProductUsageClass: (usage?: any) => string;
  getProductUsagePercent: (usage?: any) => number;
  formatRemainingProducts: (usage?: any) => string;
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
                className={`subscription-status ${getComputedSubscriptionStatus(
                  selectedStore.subscription_status,
                  selectedStore.subscription_ends_at,
                  selectedStore.is_suspended
                )}`}
              >
                {formatPlanName(
                  getComputedSubscriptionStatus(
                    selectedStore.subscription_status,
                    selectedStore.subscription_ends_at,
                    selectedStore.is_suspended
                  )
                )}
              </strong>
            </div>

            <div>
              <span>Monthly fee</span>
              <strong>{formatMonthlyFee(selectedStore.monthly_fee)}</strong>
            </div>

            <div>
              <span>Expires</span>
              <strong>{formatSubscriptionDate(selectedStore.subscription_ends_at)}</strong>
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
                Monthly fee:{" "}
                {formatMonthlyFee(subscriptionUsage?.monthly_fee ?? selectedStore.monthly_fee)}
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
            placeholder="THE GAME Store"
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
            placeholder="thegame"
            required
          />
        </label>

        <label>
          Bio
          <textarea
            value={storeForm.bio}
            onChange={(e) => setStoreForm((prev: StoreForm) => ({ ...prev, bio: e.target.value }))}
            placeholder="Tell customers what your store sells."
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
            placeholder="233544193559"
          />
        </label>

        {subscriptionUsage?.can_upload_images === false && (
          <p className="plan-restriction-note">
            Logo and banner uploads are disabled on your current plan. Upgrade to enable store branding images.
          </p>
        )}

        <label>
          Store logo
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={loadingSubscriptionUsage || subscriptionUsage?.can_upload_images === false}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadStoreImage(file, "logo");
            }}
          />
        </label>

        {storeForm.logo_url && (
          <div className="uploaded-image-preview">
            <img src={storeForm.logo_url} alt="Store logo preview" />
            <p>Logo uploaded successfully</p>
          </div>
        )}

        <label>
          Store banner
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={loadingSubscriptionUsage || subscriptionUsage?.can_upload_images === false}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadStoreImage(file, "banner");
            }}
          />
        </label>

        {storeForm.banner_url && (
          <div className="uploaded-image-preview">
            <img src={storeForm.banner_url} alt="Store banner preview" />
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
