"use client";

import { useState } from "react";


const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
type Product = {
  id: string;
  name: string;
  slug: string;
  price: string;
  description?: string | null;
  image_url?: string | null;
  stock_quantity?: number | null;
};

type Store = {
  slug: string;
  name: string;
  whatsapp_number?: string | null;
  can_receive_online_payments?: boolean;
};

export default function OrderForm({
  store,
  product,
}: {
  store: Store;
  product: Product;
}) {
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [customerNote, setCustomerNote] = useState("");
  const [quantity, setQuantity] = useState(1);

  const [loading, setLoading] = useState(false);
  const [paying, setPaying] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [orderNumber, setOrderNumber] = useState("");
  const [error, setError] = useState("");

  const stock = product.stock_quantity;
  const hasStockTracking = typeof stock === "number";
  const isSoldOut = hasStockTracking && stock <= 0;
  const maxQuantity = hasStockTracking ? stock : 100;

  async function submitOrder(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOrderId("");
    setOrderNumber("");

    if (isSoldOut) {
      setError("This product is currently sold out.");
      return;
    }

    if (hasStockTracking && quantity > stock) {
      setError(`Only ${stock} left in stock for ${product.name}`);
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/public/orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          store_slug: store.slug,
          customer_name: customerName,
          customer_phone: customerPhone,
          customer_email: customerEmail || null,
          delivery_address: deliveryAddress || null,
          customer_note: customerNote || null,
          items: [
            {
              product_id: product.id,
              quantity,
            },
          ],
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Could not create order");
      }

      setOrderId(data.id);
      setOrderNumber(data.order_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function payNow() {
    if (!orderId) {
      setError("Create an order first before paying.");
      return;
    }

    setError("");
    setPaying(true);

    try {
      const res = await fetch(`${API_URL}/payments/initialize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          order_id: orderId,
          customer_email: customerEmail || "customer@example.com",
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Could not initialize payment");
      }

      window.location.href = data.authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setPaying(false);
    }
  }

  const total = Number(product.price) * quantity;
  const onlinePaymentsEnabled = store.can_receive_online_payments !== false;

  return (
    <div className="order-page">
      <div className="order-shell">
        <a className="back-link" href={`/${store.slug}`}>
          Back to store
        </a>

        <div className="order-layout">
          <section className="order-summary">
            {product.image_url ? (
              <img className="product-image order-product-image" src={product.image_url} alt={product.name} />
            ) : (
              <div className="product-image-placeholder">Product Image</div>
            )}
            <p className="store-label">{store.name}</p>
            <h1>{product.name}</h1>
            <p>{product.description || "No description added."}</p>

            <div className="summary-row">
              <span>Price</span>
              <strong>GHS {Number(product.price).toFixed(2)}</strong>
            </div>

            <div className="summary-row">
              <span>Stock</span>
              <strong>
                {hasStockTracking
                  ? isSoldOut
                    ? "Sold out"
                    : `${stock} available`
                  : "Available"}
              </strong>
            </div>

            <div className="summary-row">
              <span>Quantity</span>
              <strong>{quantity}</strong>
            </div>

            <div className="summary-total">
              <span>Total</span>
              <strong>GHS {total.toFixed(2)}</strong>
            </div>
          </section>

          <form className="order-form" onSubmit={submitOrder}>
            <h2>Place your order</h2>
            <p className="form-muted">
              Enter your details, create the order, then pay securely.
            </p>

            <label>
              Full name
              <input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Test Customer"
                required
                disabled={isSoldOut}
              />
            </label>

            <label>
              Phone number
              <input
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                placeholder="0244123456"
                required
                disabled={isSoldOut}
              />
            </label>

            <label>
              Email address optional
              <input
                type="email"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                placeholder="customer@example.com"
                disabled={isSoldOut}
              />
            </label>

            <label>
              Delivery address optional
              <textarea
                value={deliveryAddress}
                onChange={(e) => setDeliveryAddress(e.target.value)}
                placeholder="Accra, Ghana"
                disabled={isSoldOut}
              />
            </label>

            <label>
              Quantity
              <input
                type="number"
                min={1}
                max={maxQuantity}
                value={quantity}
                onChange={(e) => {
                  const nextQuantity = Number(e.target.value);
                  if (hasStockTracking) {
                    setQuantity(Math.min(Math.max(nextQuantity, 1), stock));
                  } else {
                    setQuantity(Math.max(nextQuantity, 1));
                  }
                }}
                required
                disabled={isSoldOut}
              />
            </label>

            <label>
              Note optional
              <textarea
                value={customerNote}
                onChange={(e) => setCustomerNote(e.target.value)}
                placeholder="Please call me before delivery."
                disabled={isSoldOut}
              />
            </label>

            {error && <div className="error-box">{error}</div>}

            {isSoldOut && (
              <div className="error-box">
                This product is currently sold out.
              </div>
            )}

            {orderNumber && (
              <div className="success-box">
                <p>
                  Order created successfully. Your order number is{" "}
                  <strong>{orderNumber}</strong>.
                </p>

                <a
                  className="inline-link"
                  href={`/track?order=${encodeURIComponent(orderNumber)}&phone=${encodeURIComponent(customerPhone)}`}
                >
                  Track this order
                </a>
              </div>
            )}

            {!orderNumber ? (
              <button
                className="submit-order-btn"
                type="submit"
                disabled={loading || isSoldOut}
              >
                {loading ? "Creating order..." : isSoldOut ? "Sold out" : "Submit order"}
              </button>
            ) : !onlinePaymentsEnabled ? (
              <div className="payment-disabled-box">
                <strong>Online payment unavailable</strong>
                <p>
                  This store is not accepting online payments right now. Contact the seller to complete your order.
                </p>
              </div>
            ) : (
              <button
                className="submit-order-btn pay-btn"
                type="button"
                onClick={payNow}
                disabled={paying || !onlinePaymentsEnabled}
              >
                {paying ? "Opening Paystack..." : "Pay now"}
              </button>
            )}

            {store.whatsapp_number && (
              <a
                className="whatsapp-mini"
                href={`https://wa.me/${store.whatsapp_number}?text=${encodeURIComponent(
                  `Hi ${store.name}, I want to ask about ${product.name}.`
                )}`}
                target="_blank"
                rel="noreferrer"
              >
                Message seller on WhatsApp
              </a>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}