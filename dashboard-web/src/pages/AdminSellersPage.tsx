import type {
  Dispatch,
  SetStateAction,
} from "react";


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


type AdminSellersPageProps = {
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

  subscriptionPlans: AdminSubscriptionPlanItem[];
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


export function AdminSellersPage({
  adminStores,
  filteredAdminStores,
  adminStoreSearch,
  setAdminStoreSearch,
  adminStoreFilter,
  setAdminStoreFilter,
  adminPlanDrafts,
  setAdminPlanDrafts,
  subscriptionPlans,
  loadingSubscriptionPlans,
  loadAdminStores,
  loadingAdminStores,
  exportAdminStoresCsv,
  formatPlanName,
  formatMonthlyFee,
  formatSubscriptionDate,
  getComputedSubscriptionStatus,
  getSubscriptionTimeClass,
  getSubscriptionTimeLabel,
  extendSelectedStoreSubscription,
  extendAdminStoreSubscription,
  adminChangeStorePlan,
  adminSetStoreSuspension,
}: AdminSellersPageProps) {
  return (
    <>
      <button
        type="button"
        className="extend-subscription-btn"
        onClick={extendSelectedStoreSubscription}
      >
        Extend subscription 30 days
      </button>

      <div className="admin-stores-panel">
        <div className="admin-stores-header">
          <div>
            <h3>Admin seller stores</h3>
            <p>Extend subscriptions for sellers who have paid you.</p>
          </div>

          <div className="admin-header-actions">
            <button
              type="button"
              onClick={loadAdminStores}
              disabled={loadingAdminStores}
            >
              {loadingAdminStores ? "Loading..." : "Refresh sellers"}
            </button>

            <button type="button" onClick={exportAdminStoresCsv}>
              Export sellers CSV
            </button>
          </div>
        </div>

        {adminStores.length === 0 ? (
          <p className="muted">Click Refresh sellers to load all stores.</p>
        ) : (
          <>
            <div className="admin-store-search">
              <input
                value={adminStoreSearch}
                onChange={(e) => setAdminStoreSearch(e.target.value)}
                placeholder="Search sellers by store, slug, owner, or email..."
              />

              {adminStoreSearch && (
                <button type="button" onClick={() => setAdminStoreSearch("")}>
                  Clear
                </button>
              )}
            </div>

            <div className="admin-store-filters">
              {(["all", "active", "trial", "expired", "suspended", "expiring"] as const).map((filter) => (
                <button
                  key={filter}
                  type="button"
                  className={adminStoreFilter === filter ? "active" : ""}
                  onClick={() => setAdminStoreFilter(filter)}
                >
                  {filter === "expiring" ? "Expiring soon" : formatPlanName(filter)}
                </button>
              ))}
            </div>

            <div className="admin-store-list">
              {filteredAdminStores.map((store) => (
                <div className="admin-store-card" key={store.id}>
                  <div>
                    <h4>{store.name}</h4>
                    <p>/{store.slug}</p>
                    <p>{store.owner_name} ? {store.owner_email}</p>
                  </div>

                  <div>
                    <span>Plan</span>
                    <strong>{formatPlanName(store.plan_name)}</strong>
                  </div>

                  <div>
                    <span>Status</span>
                    <strong
                      className={`subscription-status ${getComputedSubscriptionStatus(
                        store.subscription_status,
                        store.subscription_ends_at,
                        store.is_suspended
                      )}`}
                    >
                      {formatPlanName(
                        getComputedSubscriptionStatus(
                          store.subscription_status,
                          store.subscription_ends_at,
                          store.is_suspended
                        )
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>Monthly fee</span>
                    <strong>{formatMonthlyFee(store.monthly_fee)}</strong>
                  </div>

                  <div className="admin-plan-change">
                    <label>
                      <span>Change plan</span>
                      <select
                        value={adminPlanDrafts[store.id] || store.plan_name || "starter"}
                        onChange={(e) =>
                          setAdminPlanDrafts((prev: Record<string, string>) => ({
                            ...prev,
                            [store.id]: e.target.value,
                          }))
                        }
                        disabled={loadingSubscriptionPlans || subscriptionPlans.length === 0}
                      >
                        {subscriptionPlans.length === 0 ? (
                          <option value={store.plan_name || "starter"}>
                            {formatPlanName(store.plan_name)}
                          </option>
                        ) : (
                          subscriptionPlans.map((plan) => (
                            <option key={plan.id} value={plan.name}>
                              {plan.display_name} ? {formatMonthlyFee(plan.monthly_fee)}
                            </option>
                          ))
                        )}
                      </select>
                    </label>

                    <button
                      type="button"
                      className="save-store-plan-btn"
                      onClick={() => adminChangeStorePlan(store)}
                      disabled={
                        loadingSubscriptionPlans ||
                        subscriptionPlans.length === 0 ||
                        (adminPlanDrafts[store.id] || store.plan_name) === store.plan_name
                      }
                    >
                      Save plan
                    </button>
                  </div>

                  <div>
                    <span>Expires</span>
                    <strong>{formatSubscriptionDate(store.subscription_ends_at)}</strong>
                  </div>

                  <div>
                    <span>Time left</span>
                    <strong
                      className={`subscription-time ${getSubscriptionTimeClass(
                        store.subscription_status,
                        store.subscription_ends_at,
                        store.is_suspended
                      )}`}
                    >
                      {getSubscriptionTimeLabel(
                        store.subscription_status,
                        store.subscription_ends_at,
                        store.is_suspended
                      )}
                    </strong>
                  </div>

                  <div className="admin-store-actions">
                    <button
                      type="button"
                      className="extend-subscription-btn"
                      onClick={() => extendAdminStoreSubscription(store.id)}
                    >
                      Extend 30 days
                    </button>

                    {store.is_suspended || store.subscription_status === "suspended" ? (
                      <button
                        type="button"
                        className="reactivate-store-btn"
                        onClick={() => adminSetStoreSuspension(store, false)}
                      >
                        Reactivate
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="suspend-store-btn"
                        onClick={() => adminSetStoreSuspension(store, true)}
                      >
                        Suspend
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {filteredAdminStores.length === 0 && (
              <p className="muted">No sellers match this filter.</p>
            )}
          </>
        )}
      </div>
    </>
  );
}
