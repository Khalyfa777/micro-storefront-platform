"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type OrderItem = {
  id: string;
  product_name: string;
  unit_price: string;
  quantity: number;
  line_total: string;
};

type Order = {
  id: string;
  order_number: string;
  store_slug?: string | null;
  status: string;
  customer_name: string;
  customer_phone: string;
  total: string;
  currency: string;
  created_at: string;
  items: OrderItem[];
};

export default function TrackOrderPage() {
  const [orderNumber, setOrderNumber] = useState("");
  const [phone, setPhone] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function lookupOrder(orderNo: string, phoneNo: string) {
    setError("");
    setOrder(null);
    setLoading(true);

    try {
      const res = await fetch(
        `${API_URL}/public/orders/${encodeURIComponent(
          orderNo.trim()
        )}?customer_phone=${encodeURIComponent(phoneNo.trim())}`
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Order not found");
      }

      setOrder(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function trackOrder(e: React.FormEvent) {
    e.preventDefault();
    await lookupOrder(orderNumber, phone);
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const orderParam = params.get("order") || "";
    const phoneParam = params.get("phone") || "";

    if (orderParam) setOrderNumber(orderParam);
    if (phoneParam) setPhone(phoneParam);

    if (orderParam && phoneParam) {
      lookupOrder(orderParam, phoneParam);
    }
  }, []);

  return (
    <main className="track-page">
      <section className="track-card">
        <p className="eyebrow">Order tracking</p>
        <h1>Track your order</h1>
        <p className="track-muted">
          Enter your order number and phone number to check your order status.
        </p>

        <form className="track-form" onSubmit={trackOrder}>
          <label>
            Order number
            <input
              value={orderNumber}
              onChange={(e) => setOrderNumber(e.target.value.toUpperCase())}
              placeholder="ORD-411794F1D8"
              required
            />
          </label>

          <label>
            Phone number
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="0544193559"
              required
            />
          </label>

          {error && <div className="error-box">{error}</div>}

          <button className="submit-order-btn" type="submit" disabled={loading}>
            {loading ? "Checking..." : "Track order"}
          </button>
        </form>

        {order && (
          <div className="track-result">
            <div className="track-result-head">
              <div>
                <p className="track-muted">Order number</p>
                <h2>{order.order_number}</h2>
              </div>

              <span className={`track-status ${order.status}`}>
                {order.status}
              </span>
            </div>

            <div className="track-items">
              {order.items.map((item) => (
                <div className="track-item" key={item.id}>
                  <span>
                    {item.product_name} x {item.quantity}
                  </span>
                  <strong>
                    {order.currency} {Number(item.line_total).toFixed(2)}
                  </strong>
                </div>
              ))}
            </div>

            <div className="track-total">
              <span>Total</span>
              <strong>
                {order.currency} {Number(order.total).toFixed(2)}
              </strong>
            </div>

            <p className="track-muted">
              Customer: {order.customer_name} - {order.customer_phone}
            </p>
          </div>
        )}

        <a className="track-store-link" href={order?.store_slug ? `/${order.store_slug}` : "/"}>Back to store</a>
      </section>
    </main>
  );
}