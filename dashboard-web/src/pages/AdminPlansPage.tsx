type AdminSubscriptionPlanItem = {
  id: string;
  name: string;
};

type SubscriptionPlanDraft = {
  display_name: string;
  monthly_fee: string;
  product_limit: string;
  can_upload_images: boolean;
  can_use_custom_domain: boolean;
  can_receive_online_payments: boolean;
  is_active: boolean;
};

type SubscriptionPlanDraftField =
  keyof SubscriptionPlanDraft;

type AdminPlansPageProps = {
  subscriptionPlans:
    AdminSubscriptionPlanItem[];
  planDrafts:
    Record<string, SubscriptionPlanDraft>;
  loadingSubscriptionPlans: boolean;
  loadSubscriptionPlans:
    () => void | Promise<void>;
  updatePlanDraft: (
    planName: string,
    field: SubscriptionPlanDraftField,
    value: string | boolean,
  ) => void;
  saveSubscriptionPlan:
    (planName: string) => void | Promise<void>;
};

export function AdminPlansPage({
  subscriptionPlans,
  planDrafts,
  loadingSubscriptionPlans,
  loadSubscriptionPlans,
  updatePlanDraft,
  saveSubscriptionPlan,
}: AdminPlansPageProps) {
  return (
    <div className="admin-plans-panel">
      <div className="admin-stores-header">
        <div>
          <h3>Subscription plan settings</h3>
          <p>Control product limits, prices, and features for each seller plan.</p>
        </div>

        <button
          type="button"
          onClick={loadSubscriptionPlans}
          disabled={loadingSubscriptionPlans}
        >
          {loadingSubscriptionPlans ? "Loading..." : "Refresh plans"}
        </button>
      </div>

      {subscriptionPlans.length === 0 ? (
        <p className="muted">Click Refresh plans to load subscription plans.</p>
      ) : (
        <div className="plan-settings-grid">
          {subscriptionPlans.map((plan) => {
            const draft = planDrafts[plan.name];

            if (!draft) {
              return null;
            }

            return (
              <div className="plan-settings-card" key={plan.id}>
                <div className="plan-settings-title">
                  <div>
                    <span>{plan.name}</span>
                    <h4>{draft.display_name}</h4>
                  </div>

                  <strong>{draft.product_limit ? `${draft.product_limit} products` : "Unlimited"}</strong>
                </div>

                <label>
                  Display name
                  <input
                    value={draft.display_name}
                    onChange={(e) =>
                      updatePlanDraft(plan.name, "display_name", e.target.value)
                    }
                  />
                </label>

                <label>
                  Monthly fee
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={draft.monthly_fee}
                    onChange={(e) =>
                      updatePlanDraft(plan.name, "monthly_fee", e.target.value)
                    }
                  />
                </label>

                <label>
                  Product limit
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={draft.product_limit}
                    placeholder="Blank means unlimited"
                    onChange={(e) =>
                      updatePlanDraft(plan.name, "product_limit", e.target.value)
                    }
                  />
                </label>

                <div className="plan-checkboxes">
                  <label>
                    <input
                      type="checkbox"
                      checked={draft.can_upload_images}
                      onChange={(e) =>
                        updatePlanDraft(plan.name, "can_upload_images", e.target.checked)
                      }
                    />
                    Image uploads
                  </label>

                  <label>
                    <input
                      type="checkbox"
                      checked={draft.can_use_custom_domain}
                      onChange={(e) =>
                        updatePlanDraft(plan.name, "can_use_custom_domain", e.target.checked)
                      }
                    />
                    Custom domain
                  </label>

                  <label>
                    <input
                      type="checkbox"
                      checked={draft.can_receive_online_payments}
                      onChange={(e) =>
                        updatePlanDraft(
                          plan.name,
                          "can_receive_online_payments",
                          e.target.checked
                        )
                      }
                    />
                    Online payments
                  </label>

                  <label>
                    <input
                      type="checkbox"
                      checked={draft.is_active}
                      onChange={(e) =>
                        updatePlanDraft(plan.name, "is_active", e.target.checked)
                      }
                    />
                    Plan active
                  </label>
                </div>

                <button
                  type="button"
                  className="save-plan-btn"
                  onClick={() => saveSubscriptionPlan(plan.name)}
                >
                  Save plan
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
