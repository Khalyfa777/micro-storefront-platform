type OrderConfigurationSnapshot = {
  key?: string;
  label?: string;
  field_type?: string;
  value?: unknown;
  display_value?: unknown;
  is_sensitive?: boolean;
  include_in_whatsapp?: boolean;
  price_adjustment?: string | number;
};

type OrderItem = {
  id: string;
  product_name: string;
  quantity: number;
  line_total: string | number;
  selected_options?: Record<string, unknown>;
  configuration_snapshot?: OrderConfigurationSnapshot[];
};

type Order = {
  id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  delivery_address?: string | null;
  customer_note?: string | null;
  fulfillment_method?: string | null;
  currency: string;
  total: string | number;
  status: string;
  payment_method?: string | null;
  inventory_deducted?: boolean;
  items: OrderItem[];
};

type OrdersPageProps = {
  orders: Order[];
  getAllowedOrderStatusActions: (status: string) => string[];
  formatOrderStatusActionLabel: (status: string) => string;
  confirmManualPayment: (orderId: string) => void | Promise<void>;
  updateOrderStatus: (orderId: string, nextStatus: string) => void | Promise<void>;
};

type DisplayConfigurationEntry = {
  key: string;
  label: string;
  displayValue: string;
  isSensitive: boolean;
  priceAdjustment: number;
};

function humanizeToken(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function getOrderLocationLabel(
  fulfillmentMethod?: string | null,
): string | null {
  if (fulfillmentMethod === "delivery") {
    return "Delivery location";
  }

  if (fulfillmentMethod === "on_site_service") {
    return "Service location";
  }

  return null;
}

function formatOrderValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Not provided";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    return value.map(formatOrderValue).join(", ");
  }

  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nestedValue]) => (
        `${humanizeToken(key)}: ${formatOrderValue(nestedValue)}`
      ))
      .join("; ");
  }

  return String(value);
}

function getConfigurationEntries(
  item: OrderItem,
): DisplayConfigurationEntry[] {
  const snapshots = Array.isArray(item.configuration_snapshot)
    ? item.configuration_snapshot
    : [];

  if (snapshots.length > 0) {
    return snapshots.map((snapshot, index) => {
      const key = String(snapshot.key || `option-${index + 1}`);
      const label = String(
        snapshot.label || snapshot.key || `Option ${index + 1}`,
      ).trim();
      const numericAdjustment = Number(snapshot.price_adjustment || 0);

      return {
        key,
        label: label || `Option ${index + 1}`,
        displayValue: formatOrderValue(
          snapshot.display_value ?? snapshot.value,
        ),
        isSensitive: Boolean(snapshot.is_sensitive),
        priceAdjustment: Number.isFinite(numericAdjustment)
          ? numericAdjustment
          : 0,
      };
    });
  }

  return Object.entries(item.selected_options || {}).map(
    ([key, value]) => ({
      key,
      label: humanizeToken(key),
      displayValue: formatOrderValue(value),
      isSensitive: false,
      priceAdjustment: 0,
    }),
  );
}

function formatPriceAdjustment(
  currency: string,
  amount: number,
): string | null {
  if (!Number.isFinite(amount) || amount === 0) {
    return null;
  }

  const sign = amount > 0 ? "+" : "−";

  return `${sign} ${currency} ${Math.abs(amount).toFixed(2)}`;
}

function ConfigurationList({
  entries,
  currency,
}: {
  entries: DisplayConfigurationEntry[];
  currency: string;
}) {
  return (
    <dl className="order-configuration-list">
      {entries.map((entry, index) => {
        const adjustment = formatPriceAdjustment(
          currency,
          entry.priceAdjustment,
        );

        return (
          <div
            className="order-configuration-row"
            key={`${entry.key}-${index}`}
          >
            <dt>{entry.label}</dt>
            <dd>
              <span>{entry.displayValue}</span>
              {adjustment && (
                <small className="order-price-adjustment">
                  {adjustment}
                </small>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function OrdersPage({
  orders,
  getAllowedOrderStatusActions,
  formatOrderStatusActionLabel,
  confirmManualPayment,
  updateOrderStatus,
}: OrdersPageProps) {
  return (
    <div className="cards">
      {orders.length === 0 && <p>No orders yet.</p>}

      {orders.map((order) => (
        <article className="order-card" key={order.id}>
          <div className="card-head">
            <div>
              <h3>{order.order_number}</h3>
              <p>
                {order.customer_name} {" - "} {order.customer_phone}
              </p>
            </div>

            <div className="order-status-stack">
              <span className={`status ${order.status}`}>
                {order.status}
              </span>

              {order.payment_method && (
                <span className={`payment-method-badge ${order.payment_method}`}>
                  {order.payment_method === "paystack" ? "Paystack" : "Manual"}
                </span>
              )}
            </div>
          </div>

          <section
            className="order-meta-grid"
            aria-label="Customer and fulfilment details"
          >
            <div className="order-meta-item">
              <span>Fulfilment</span>
              <strong>
                {humanizeToken(
                  order.fulfillment_method || "seller_confirmation",
                )}
              </strong>
            </div>

            {order.customer_email && (
              <div className="order-meta-item">
                <span>Email</span>
                <strong>{order.customer_email}</strong>
              </div>
            )}

            {order.delivery_address &&
              getOrderLocationLabel(
                order.fulfillment_method,
              ) && (
                <div className="order-meta-item order-meta-wide">
                  <span>
                    {getOrderLocationLabel(
                      order.fulfillment_method,
                    )}
                  </span>
                  <strong>{order.delivery_address}</strong>
                </div>
              )}

            {order.customer_note && (
              <div className="order-meta-item order-meta-wide">
                <span>Customer note</span>
                <strong>{order.customer_note}</strong>
              </div>
            )}
          </section>

          <div className="order-items">
            {order.items.map((item) => {
              const configurationEntries = getConfigurationEntries(item);
              const standardEntries = configurationEntries.filter(
                (entry) => !entry.isSensitive,
              );
              const privateEntries = configurationEntries.filter(
                (entry) => entry.isSensitive,
              );

              return (
                <div className="order-item-card" key={item.id}>
                  <div className="item-row order-item-summary">
                    <span>
                      {item.product_name} {" x "} {item.quantity}
                    </span>
                    <strong>
                      {order.currency} {Number(item.line_total).toFixed(2)}
                    </strong>
                  </div>

                  {standardEntries.length > 0 && (
                    <div className="order-item-configuration">
                      <p className="order-detail-heading">
                        Customer choices
                      </p>
                      <ConfigurationList
                        entries={standardEntries}
                        currency={order.currency}
                      />
                    </div>
                  )}

                  {privateEntries.length > 0 && (
                    <details className="order-private-details">
                      <summary>
                        Show {privateEntries.length} private{" "}
                        {privateEntries.length === 1 ? "answer" : "answers"}
                      </summary>
                      <p>
                        Open only when this information is needed to fulfil
                        the order.
                      </p>
                      <ConfigurationList
                        entries={privateEntries}
                        currency={order.currency}
                      />
                    </details>
                  )}
                </div>
              );
            })}
          </div>

          <div className="item-row total">
            <span>Total</span>
            <strong>
              {order.currency} {Number(order.total).toFixed(2)}
            </strong>
          </div>

          <p className="muted">
            Stock updated: {order.inventory_deducted ? "Yes" : "No"}
          </p>

          <div className="actions">
            {getAllowedOrderStatusActions(order.status).map((nextStatus) => (
              <button
                key={nextStatus}
                onClick={() =>
                  nextStatus === "paid"
                    ? confirmManualPayment(order.id)
                    : updateOrderStatus(order.id, nextStatus)
                }
              >
                {formatOrderStatusActionLabel(nextStatus)}
              </button>
            ))}
          </div>
        </article>
      ))}

      {orders.length > 0 && (
        <p className="orders-end-note">End of orders</p>
      )}
    </div>
  );
}
