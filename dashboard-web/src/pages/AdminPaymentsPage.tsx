type AdminPaymentsPageProps = {
  adminSubscriptionPayments: any[];
  filteredSubscriptionPayments: any[];
  subscriptionPaymentSearch: string;
  setSubscriptionPaymentSearch: (value: string) => void;
  subscriptionPaymentMethodFilter: string;
  setSubscriptionPaymentMethodFilter: (value: any) => void;
  loadAdminSubscriptionPayments: () => void | Promise<void>;
  loadingAdminSubscriptionPayments: boolean;
  exportSubscriptionPaymentsCsv: () => void;
  formatPlanName: (value?: string | null) => string;
  formatSubscriptionDate: (value?: string | null) => string;
};

export function AdminPaymentsPage({
  adminSubscriptionPayments,
  filteredSubscriptionPayments,
  subscriptionPaymentSearch,
  setSubscriptionPaymentSearch,
  subscriptionPaymentMethodFilter,
  setSubscriptionPaymentMethodFilter,
  loadAdminSubscriptionPayments,
  loadingAdminSubscriptionPayments,
  exportSubscriptionPaymentsCsv,
  formatPlanName,
  formatSubscriptionDate,
}: AdminPaymentsPageProps) {
  return (
    <div className="admin-stores-panel">
      <div className="admin-stores-header">
        <div>
          <h3>Subscription payment history</h3>
          <p>Recent seller subscription payments recorded by admins.</p>
        </div>

        <div className="admin-header-actions">
          <button
            type="button"
            onClick={loadAdminSubscriptionPayments}
            disabled={loadingAdminSubscriptionPayments}
          >
            {loadingAdminSubscriptionPayments ? "Loading..." : "Refresh payments"}
          </button>

          <button type="button" onClick={exportSubscriptionPaymentsCsv}>
            Export CSV
          </button>
        </div>
      </div>

      {adminSubscriptionPayments.length === 0 ? (
        <p className="muted">Click Refresh payments to load recent payments.</p>
      ) : (
        <>
          <div className="admin-store-search">
            <input
              value={subscriptionPaymentSearch}
              onChange={(e) => setSubscriptionPaymentSearch(e.target.value)}
              placeholder="Search payments by store, reference, method, admin, or note..."
            />

            {subscriptionPaymentSearch && (
              <button type="button" onClick={() => setSubscriptionPaymentSearch("")}>
                Clear
              </button>
            )}
          </div>

          <div className="subscription-payment-filters">
            {(["all", "manual", "momo", "bank", "cash", "paystack"] as const).map((method) => (
              <button
                key={method}
                type="button"
                className={subscriptionPaymentMethodFilter === method ? "active" : ""}
                onClick={() => setSubscriptionPaymentMethodFilter(method)}
              >
                {formatPlanName(method)}
              </button>
            ))}
          </div>

          <div className="admin-store-list">
            {filteredSubscriptionPayments.map((payment) => (
              <div className="admin-store-card" key={payment.id}>
                <div>
                  <h4>{payment.store_name}</h4>
                  <p>/{payment.store_slug}</p>
                  <p>Approved by: {payment.approved_by_email || "Unknown admin"}</p>
                </div>

                <div>
                  <span>Plan</span>
                  <strong>{formatPlanName(payment.plan_name)}</strong>
                </div>

                <div>
                  <span>Amount</span>
                  <strong>
                    {payment.currency} {Number(payment.amount).toFixed(2)}
                  </strong>
                </div>

                <div>
                  <span>Method</span>
                  <strong>{formatPlanName(payment.payment_method)}</strong>
                </div>

                <div>
                  <span>Reference</span>
                  <strong>{payment.payment_reference || "N/A"}</strong>
                </div>

                <div>
                  <span>Covered</span>
                  <strong>{payment.covered_days} days</strong>
                </div>

                <div>
                  <span>Paid</span>
                  <strong>{formatSubscriptionDate(payment.paid_at)}</strong>
                </div>
              </div>
            ))}
          </div>

          {filteredSubscriptionPayments.length === 0 && (
            <p className="muted">No payments match this filter.</p>
          )}
        </>
      )}
    </div>
  );
}
