"use client";

import SafeProductImage from "./SafeProductImage";

import {
  useRef,
  useState,
} from "react";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api/v1";

const ORDER_ATTEMPT_STORAGE_PREFIX =
  "storeplug:order-attempt";

type PendingOrderAttempt = {
  fingerprint: string;
  idempotencyKey: string;
};

function createOrderIdempotencyKey() {
  if (
    typeof window.crypto?.randomUUID ===
    "function"
  ) {
    return `checkout:${window.crypto.randomUUID()}`;
  }

  return [
    "checkout",
    Date.now(),
    Math.random().toString(36).slice(2),
    Math.random().toString(36).slice(2),
  ].join(":");
}

function fingerprintOrderPayload(
  payload: unknown,
) {
  const serialized = JSON.stringify(payload);

  let firstHash = 2166136261;
  let secondHash = 5381;

  for (
    let index = 0;
    index < serialized.length;
    index += 1
  ) {
    const code =
      serialized.charCodeAt(index);

    firstHash ^= code;
    firstHash = Math.imul(
      firstHash,
      16777619,
    );

    secondHash =
      Math.imul(secondHash, 33) ^ code;
  }

  return [
    (firstHash >>> 0).toString(16),
    (secondHash >>> 0).toString(16),
    serialized.length,
  ].join(":");
}

function readPendingOrderAttempt(
  storageKey: string,
): PendingOrderAttempt | null {
  try {
    const raw =
      window.sessionStorage.getItem(
        storageKey,
      );

    if (!raw) {
      return null;
    }

    const parsed: unknown =
      JSON.parse(raw);

    if (
      typeof parsed !== "object" ||
      parsed === null
    ) {
      return null;
    }

    const candidate =
      parsed as Partial<PendingOrderAttempt>;

    if (
      typeof candidate.fingerprint !==
        "string" ||
      typeof candidate.idempotencyKey !==
        "string" ||
      !/^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$/.test(
        candidate.idempotencyKey,
      )
    ) {
      return null;
    }

    return {
      fingerprint:
        candidate.fingerprint,
      idempotencyKey:
        candidate.idempotencyKey,
    };
  } catch {
    return null;
  }
}

function persistPendingOrderAttempt(
  storageKey: string,
  attempt: PendingOrderAttempt,
) {
  try {
    window.sessionStorage.setItem(
      storageKey,
      JSON.stringify(attempt),
    );
  } catch {
    // The in-memory ref still protects
    // retries during this page session.
  }
}

function clearPendingOrderAttempt(
  storageKey: string,
  idempotencyKey: string,
) {
  try {
    const stored =
      readPendingOrderAttempt(
        storageKey,
      );

    if (
      stored?.idempotencyKey ===
      idempotencyKey
    ) {
      window.sessionStorage.removeItem(
        storageKey,
      );
    }
  } catch {
    // Storage can be unavailable in some
    // privacy-restricted browsers.
  }
}

function formatMoney(value: string | number) {
  const amount = Number(value);

  if (!Number.isFinite(amount)) {
    return "GHS 0.00";
  }

  const fixed = amount.toFixed(2);
  const [whole, decimal] = fixed.split(".");
  const grouped = whole.replace(
    /\B(?=(\d{3})+(?!\d))/g,
    ",",
  );

  return `GHS ${grouped}.${decimal}`;
}
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
  can_receive_online_payments: boolean;
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

  const pendingAttemptRef =
    useRef<PendingOrderAttempt | null>(
      null,
    );

  const attemptStorageKey = [
    ORDER_ATTEMPT_STORAGE_PREFIX,
    store.slug,
    product.id,
  ].join(":");

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
      const orderPayload = {
        store_slug: store.slug,
        customer_name: customerName,
        customer_phone: customerPhone,
        customer_email:
          customerEmail || null,
        delivery_address:
          deliveryAddress || null,
        customer_note:
          customerNote || null,
        items: [
          {
            product_id: product.id,
            quantity,
          },
        ],
      };

      const payloadFingerprint =
        fingerprintOrderPayload(
          orderPayload,
        );

      let pendingAttempt =
        pendingAttemptRef.current ??
        readPendingOrderAttempt(
          attemptStorageKey,
        );

      if (
        !pendingAttempt ||
        pendingAttempt.fingerprint !==
          payloadFingerprint
      ) {
        pendingAttempt = {
          fingerprint:
            payloadFingerprint,
          idempotencyKey:
            createOrderIdempotencyKey(),
        };
      }

      pendingAttemptRef.current =
        pendingAttempt;

      persistPendingOrderAttempt(
        attemptStorageKey,
        pendingAttempt,
      );

      const res = await fetch(
        `${API_URL}/public/orders`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
            "Idempotency-Key":
              pendingAttempt.idempotencyKey,
          },
          body: JSON.stringify(
            orderPayload,
          ),
        },
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data.detail ||
            "Could not create order",
        );
      }

      clearPendingOrderAttempt(
        attemptStorageKey,
        pendingAttempt.idempotencyKey,
      );

      if (
        pendingAttemptRef.current
          ?.idempotencyKey ===
        pendingAttempt.idempotencyKey
      ) {
        pendingAttemptRef.current =
          null;
      }

      setOrderId(data.id);
      setOrderNumber(
        data.order_number,
      );
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
  const onlinePaymentsEnabled =
    store.can_receive_online_payments === true;

  return (
    <div className="order-page">
      <div className="order-shell">
        <a className="back-link" href={`/${store.slug}`}>
          Back to store
        </a>

        <div className="order-layout">
          <section className="order-summary">
            <div className="order-product-card">
              <SafeProductImage
                imageUrl={product.image_url}
                productName={product.name}
              />
            </div>
            <p className="store-label">{store.name}</p>
            <h1>{product.name}</h1>
            <p>{product.description || "No description added."}</p>

            <div className="summary-row">
              <span>Price</span>
              <strong>
                {formatMoney(product.price)}
              </strong>
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
              <strong>
                {formatMoney(total)}
              </strong>
            </div>
          </section>

          <form
            className={
              orderNumber
                ? "order-form order-form-complete"
                : "order-form"
            }
            onSubmit={submitOrder}
          >
            <h2>
              {orderNumber
                ? "Order confirmed"
                : "Place your order"}
            </h2>

            <p className="form-muted">
              {orderNumber
                ? "Your order has been created. Save the order number below."
                : "Enter your details to create your order."}
            </p>

            {!orderNumber && (
              <>
                <label>
                  Full name
                  <input
                    name="customer-name"
                    autoComplete="name"
                    value={customerName}
                    onChange={(event) =>
                      setCustomerName(
                        event.target.value,
                      )
                    }
                    placeholder="Your full name"
                    required
                    disabled={isSoldOut}
                  />
                </label>

                <label>
                  Phone number
                  <input
                    name="customer-phone"
                    autoComplete="tel"
                    inputMode="tel"
                    value={customerPhone}
                    onChange={(event) =>
                      setCustomerPhone(
                        event.target.value,
                      )
                    }
                    placeholder="Your phone number"
                    required
                    disabled={isSoldOut}
                  />
                </label>

                <label>
                  Email address (optional)
                  <input
                    name="customer-email"
                    type="email"
                    autoComplete="email"
                    value={customerEmail}
                    onChange={(event) =>
                      setCustomerEmail(
                        event.target.value,
                      )
                    }
                    placeholder="Optional email address"
                    disabled={isSoldOut}
                  />
                </label>

                <label>
                  Delivery address (optional)
                  <textarea
                    name="delivery-address"
                    autoComplete="street-address"
                    value={deliveryAddress}
                    onChange={(event) =>
                      setDeliveryAddress(
                        event.target.value,
                      )
                    }
                    placeholder="Delivery location or address"
                    disabled={isSoldOut}
                  />
                </label>

                <label>
                  Quantity
                  <input
                    name="quantity"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={maxQuantity}
                    value={quantity}
                    onChange={(event) => {
                      const nextQuantity =
                        Number(
                          event.target.value,
                        );

                      if (hasStockTracking) {
                        setQuantity(
                          Math.min(
                            Math.max(
                              nextQuantity,
                              1,
                            ),
                            stock,
                          ),
                        );
                      } else {
                        setQuantity(
                          Math.max(
                            nextQuantity,
                            1,
                          ),
                        );
                      }
                    }}
                    required
                    disabled={isSoldOut}
                  />
                </label>

                <label>
                  Note (optional)
                  <textarea
                    name="customer-note"
                    autoComplete="off"
                    value={customerNote}
                    onChange={(event) =>
                      setCustomerNote(
                        event.target.value,
                      )
                    }
                    placeholder="Any delivery note"
                    disabled={isSoldOut}
                  />
                </label>
              </>
            )}

            {error && (
              <div
                className="error-box"
                role="alert"
              >
                {error}
              </div>
            )}

            {isSoldOut && (
              <div
                className="error-box"
                role="alert"
              >
                This product is currently sold
                out.
              </div>
            )}

            {orderNumber && (
              <div
                className="success-box order-success-box"
                aria-live="polite"
              >
                <span className="order-success-label">
                  Order number
                </span>

                <strong className="order-success-number">
                  {orderNumber}
                </strong>

                <p>
                  Your order was created
                  successfully.
                </p>

                <a
                  className="inline-link"
                  href={`/track?order=${encodeURIComponent(
                    orderNumber,
                  )}`}
                >
                  Track this order
                </a>
              </div>
            )}

            {!orderNumber ? (
              <button
                className="submit-order-btn"
                type="submit"
                disabled={
                  loading ||
                  isSoldOut
                }
              >
                {loading
                  ? "Creating order..."
                  : isSoldOut
                    ? "Sold out"
                    : "Submit order"}
              </button>
            ) : !onlinePaymentsEnabled ? (
              <div className="payment-disabled-box">
                <strong>
                  Online payment unavailable
                </strong>

                <p>
                  This store is not accepting
                  online payments right now.
                  Contact the seller to complete
                  your order.
                </p>
              </div>
            ) : (
              <button
                className="submit-order-btn pay-btn"
                type="button"
                onClick={payNow}
                disabled={
                  paying ||
                  !onlinePaymentsEnabled
                }
              >
                {paying
                  ? "Opening Paystack..."
                  : "Pay now"}
              </button>
            )}

            {store.whatsapp_number && (
              <a
                className="whatsapp-mini"
                href={`https://wa.me/${store.whatsapp_number}?text=${encodeURIComponent(
                  `Hi ${store.name}, I want to ask about ${product.name}.`,
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
