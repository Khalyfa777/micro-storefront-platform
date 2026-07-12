type AdminSubscriptionSummary = {
  total_stores: number;
  active_stores: number;
  trial_stores: number;
  expired_stores: number;
  suspended_stores: number;
  expiring_within_7_days: number;
  monthly_recurring_total: string | number;
  subscription_revenue_this_month: string | number;
  subscription_revenue_total: string | number;
  recent_payment_count: number;
};

type AdminSummaryPageProps = {
  adminSubscriptionSummary: AdminSubscriptionSummary | null;
  loadingAdminSubscriptionSummary: boolean;
  loadAdminSubscriptionSummary: () => void | Promise<void>;
  formatMonthlyFee: (value?: string | number | null) => string;
};

export function AdminSummaryPage({
  adminSubscriptionSummary,
  loadingAdminSubscriptionSummary,
  loadAdminSubscriptionSummary,
  formatMonthlyFee,
}: AdminSummaryPageProps) {
  return (
    <div className="admin-summary-panel">
      <div className="admin-stores-header">
        <div>
          <h3>Subscription business summary</h3>
          <p>Quick overview of seller subscriptions and revenue.</p>
        </div>

        <button
          type="button"
          onClick={loadAdminSubscriptionSummary}
          disabled={loadingAdminSubscriptionSummary}
        >
          {loadingAdminSubscriptionSummary ? "Loading..." : "Refresh summary"}
        </button>
      </div>

      {!adminSubscriptionSummary ? (
        <p className="muted">Click Refresh summary to load business numbers.</p>
      ) : (
        <div className="admin-summary-grid">
          <div className="admin-summary-card">
            <span>Total sellers</span>
            <strong>{adminSubscriptionSummary.total_stores}</strong>
          </div>

          <div className="admin-summary-card good">
            <span>Active</span>
            <strong>{adminSubscriptionSummary.active_stores}</strong>
          </div>

          <div className="admin-summary-card">
            <span>Trial</span>
            <strong>{adminSubscriptionSummary.trial_stores}</strong>
          </div>

          <div className="admin-summary-card danger">
            <span>Expired</span>
            <strong>{adminSubscriptionSummary.expired_stores}</strong>
          </div>

          <div className="admin-summary-card danger">
            <span>Suspended</span>
            <strong>{adminSubscriptionSummary.suspended_stores}</strong>
          </div>

          <div className="admin-summary-card warning">
            <span>Expiring in 7 days</span>
            <strong>{adminSubscriptionSummary.expiring_within_7_days}</strong>
          </div>

          <div className="admin-summary-card money">
            <span>Monthly recurring</span>
            <strong>{formatMonthlyFee(adminSubscriptionSummary.monthly_recurring_total)}</strong>
          </div>

          <div className="admin-summary-card money">
            <span>Revenue this month</span>
            <strong>{formatMonthlyFee(adminSubscriptionSummary.subscription_revenue_this_month)}</strong>
          </div>

          <div className="admin-summary-card money">
            <span>Total subscription revenue</span>
            <strong>{formatMonthlyFee(adminSubscriptionSummary.subscription_revenue_total)}</strong>
          </div>

          <div className="admin-summary-card">
            <span>Payment records</span>
            <strong>{adminSubscriptionSummary.recent_payment_count}</strong>
          </div>
        </div>
      )}
    </div>
  );
}
