type DashboardTab =
  | "orders"
  | "products"
  | "settings"
  | "adminSummary"
  | "adminSellers"
  | "adminPlans"
  | "adminPayments";

type StoreOption = {
  id: string;
  name: string;
  slug: string;
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
  onLoadAdminStores: () => void;
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
  onLoadAdminStores,
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
            <p className="muted">Merchant dashboard</p>
          </div>

          <button
            type="button"
            className="sidebar-close"
            onClick={onClose}
            aria-label="Close dashboard menu"
          >
            <span></span>
            <span></span>
          </button>
        </div>

        <div className="store-switcher">
          <label>Current store</label>
          <select
            value={selectedStore?.id || ""}
            onChange={(e) => onSelectStore(e.target.value)}
          >
            {stores.map((store) => (
              <option key={store.id} value={store.id}>
                {store.name}
              </option>
            ))}
          </select>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-group">
            <p className="nav-group-title">Store</p>

            <button
              className={activeTab === "orders" ? "nav-btn active" : "nav-btn"}
              onClick={() => onOpenTab("orders")}
            >
              Orders
            </button>

            <button
              className={activeTab === "products" ? "nav-btn active" : "nav-btn"}
              onClick={() => onOpenTab("products")}
            >
              Products
            </button>

            <button
              className={activeTab === "settings" ? "nav-btn active" : "nav-btn"}
              onClick={() => onOpenTab("settings")}
            >
              Store profile
            </button>
          </div>

          {isPlatformAdmin && (
            <div className="nav-group">
              <p className="nav-group-title">Admin</p>

              <button
                className={activeTab === "adminSummary" ? "nav-btn active" : "nav-btn"}
                onClick={() => {
                  onOpenTab("adminSummary");
                  onLoadAdminSubscriptionSummary();
                }}
              >
                Business overview
              </button>

              <button
                className={activeTab === "adminSellers" ? "nav-btn active" : "nav-btn"}
                onClick={() => {
                  onOpenTab("adminSellers");
                  onLoadAdminStores();
                  onLoadAdminSubscriptionPayments();
                }}
              >
                Sellers
              </button>

              <button
                className={activeTab === "adminPlans" ? "nav-btn active" : "nav-btn"}
                onClick={() => {
                  onOpenTab("adminPlans");
                  onLoadSubscriptionPlans();
                }}
              >
                Plans
              </button>

              <button
                className={activeTab === "adminPayments" ? "nav-btn active" : "nav-btn"}
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
            <a
              className="public-link"
              href={publicStoreUrl + "/" + (selectedStore?.slug || "")}
              target="_blank"
              rel="noreferrer"
            >
              Open public store
            </a>

            <button className="logout-btn" onClick={onLogout}>
              Logout
            </button>
          </div>
        </nav>
      </aside>
    </>
  );
}
