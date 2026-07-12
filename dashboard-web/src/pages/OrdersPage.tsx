type OrderItem = {
  id: string;
  product_name: string;
  quantity: number;
  line_total: string | number;
};

type Order = {
  id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string;
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

          <div className="order-items">
            {order.items.map((item) => (
              <div key={item.id} className="item-row">
                <span>
                  {item.product_name} {" x "} {item.quantity}
                </span>
                <strong>
                  {order.currency} {Number(item.line_total).toFixed(2)}
                </strong>
              </div>
            ))}
          </div>

          <div className="item-row total">
            <span>Total</span>
            <strong>
              {order.currency} {Number(order.total).toFixed(2)}
            </strong>
          </div>

          <p className="muted">
            Inventory deducted: {order.inventory_deducted ? "Yes" : "No"}
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
    </div>
  );
}
