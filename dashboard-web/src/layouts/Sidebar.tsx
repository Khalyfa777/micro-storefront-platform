import {
  buildPublicStoreUrl,
} from "../utils/public-store-url";

type DashboardTab =
  | "orders"
  | "products"
  | "settings"
  | "security"
  | "adminSummary"
  | "adminSellers"
  | "adminPlans"
  | "adminPayments";

type StoreOption = {
  id: string;
  name: string;
  slug: string;
  publication_status:
    | "draft"
    | "published";
};

type SidebarProps = {
  isSidebarOpen: boolean;
  selectedStore: StoreOption | null;
  stores: StoreOption[];
  activeTab: DashboardTab;
  isPlatformAdmin: boolean;
  publicStoreUrl: string;
  onClose: () => void;
  onSelectStore: (storeId: string) => void;
  onOpenTab: (tab: DashboardTab) => void;
  onLoadAdminSubscriptionSummary: () => void;
  onLoadAdminSubscriptionPayments: () => void;
  onLoadSubscriptionPlans: () => void;
  onLogout: () => void;
};

export function Sidebar({
  isSidebarOpen,
  selectedStore,
  stores,
  activeTab,
  isPlatformAdmin,
  publicStoreUrl,
  onClose,
  onSelectStore,
  onOpenTab,
  onLoadAdminSubscriptionSummary,
  onLoadAdminSubscriptionPayments,
  onLoadSubscriptionPlans,
  onLogout,
}: SidebarProps) {
  return (
    <>
      {isSidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={onClose}
          aria-label="Close dashboard menu"
        />
      )}

      <aside className={isSidebarOpen ? "sidebar open" : "sidebar"}>
        <div className="sidebar-brand">
          <div className="brand-mark">SP</div>

          <div className="brand-copy">
            <h2>StorePlug</h2>
            <p className="muted">
              {isPlatformAdmin
                ? "Platform workspace"
                : "Merchant dashboard"}
            </p>
          </div>

          <button
            type="button"
            className="sidebar-close"
            onClick={onClose}
            aria-label="Close dashboard menu"
          >
            <span />
            <span />
          </button>
        </div>

        <nav className="sidebar-nav" aria-label="Dashboard navigation">
          <div className="nav-group store-nav-group">
            <p className="nav-group-title">Store</p>

            <div className="store-switcher">
              <label htmlFor="storeplug-current-store">
                Current store
              </label>

              <select
                id="storeplug-current-store"
                value={selectedStore?.id || ""}
                onChange={(event) =>
                  onSelectStore(event.target.value)
                }
                disabled={stores.length === 0}
              >
                {stores.length === 0 ? (
                  <option value="">
                    No store available
                  </option>
                ) : (
                  stores.map((store) => (
                    <option
                      key={store.id}
                      value={store.id}
                    >
                      {store.name}
                    </option>
                  ))
                )}
              </select>
            </div>

            <button
              type="button"
              className={
                activeTab === "orders"
                  ? "nav-btn active"
                  : "nav-btn"
              }
              onClick={() => onOpenTab("orders")}
            >
              Orders
            </button>

            <button
              type="button"
              className={
                activeTab === "products"
                  ? "nav-btn active"
                  : "nav-btn"
              }
              onClick={() => onOpenTab("products")}
            >
              Products
            </button>

            <button
              type="button"
              className={
                activeTab === "settings"
                  ? "nav-btn active"
                  : "nav-btn"
              }
              onClick={() => onOpenTab("settings")}
            >
              Store profile
            </button>
          </div>

          <div className="nav-group account-nav-group">
            <p className="nav-group-title">
              Account
            </p>

            <button
              type="button"
              className={
                activeTab === "security"
                  ? "nav-btn active"
                  : "nav-btn"
              }
              onClick={() => onOpenTab("security")}
            >
              Security
            </button>
          </div>

          {isPlatformAdmin && (
            <div className="nav-group platform-admin-nav">
              <div className="platform-admin-nav-heading">
                <p className="nav-group-title">
                  Platform Admin
                </p>

                <span className="platform-context-badge">
                  Admin
                </span>
              </div>

              <button
                type="button"
                className={
                  activeTab === "adminSummary"
                    ? "nav-btn active"
                    : "nav-btn"
                }
                onClick={() => {
                  onOpenTab("adminSummary");
                  onLoadAdminSubscriptionSummary();
                }}
              >
                Platform overview
              </button>

              <button
                type="button"
                className={
                  activeTab === "adminSellers"
                    ? "nav-btn active"
                    : "nav-btn"
                }
                onClick={() => {
                  onOpenTab("adminSellers");
                }}
              >
                Sellers
              </button>

              <button
                type="button"
                className={
                  activeTab === "adminPlans"
                    ? "nav-btn active"
                    : "nav-btn"
                }
                onClick={() => {
                  onOpenTab("adminPlans");
                  onLoadSubscriptionPlans();
                }}
              >
                Plans
              </button>

              <button
                type="button"
                className={
                  activeTab === "adminPayments"
                    ? "nav-btn active"
                    : "nav-btn"
                }
                onClick={() => {
                  onOpenTab("adminPayments");
                  onLoadAdminSubscriptionPayments();
                }}
              >
                Payments
              </button>
            </div>
          )}

          <div className="nav-group nav-footer">
            {selectedStore?.publication_status ===
              "published" && (
              <a
                className="public-link"
                href={buildPublicStoreUrl(publicStoreUrl, selectedStore.slug)}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open public store
              </a>
            )}

            <button
              type="button"
              className="logout-btn"
              onClick={onLogout}
            >
              Logout
            </button>
          </div>
        </nav>
      </aside>
    </>
  );
}
