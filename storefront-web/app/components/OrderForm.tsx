"use client";

import SafeProductImage from "./SafeProductImage";
import { getWhatsAppNumber } from "../lib/phone";
import {
  resolveStorefrontApiBaseUrl,
} from "../lib/api-url";

import {
  useRef,
  useState,
} from "react";

const API_URL = resolveStorefrontApiBaseUrl();

const ORDER_ATTEMPT_STORAGE_PREFIX =
  "storeplug:order-attempt";

type PendingOrderAttempt = {
  fingerprint: string;
  idempotencyKey: string;
};

type ProductType =
  | "physical"
  | "digital"
  | "subscription"
  | "service"
  | "food"
  | "booking"
  | "custom";

type FulfillmentMethod =
  | "delivery"
  | "pickup"
  | "digital_delivery"
  | "activation"
  | "appointment"
  | "on_site_service"
  | "remote_service"
  | "reservation"
  | "seller_confirmation";

type ProductOrderFieldType =
  | "text"
  | "textarea"
  | "select"
  | "radio"
  | "checkbox"
  | "number"
  | "date"
  | "time"
  | "datetime"
  | "phone"
  | "email";

type ProductOrderFieldOption = {
  id: string;
  value: string;
  label: string;
  price_adjustment: string;
  is_active: boolean;
  sort_order: number;
};

type ProductOrderField = {
  id: string;
  product_id: string;
  key: string;
  label: string;
  field_type: ProductOrderFieldType;
  placeholder?: string | null;
  help_text?: string | null;
  is_required: boolean;
  is_sensitive: boolean;
  include_in_whatsapp: boolean;
  is_active: boolean;
  sort_order: number;
  validation_rules: Record<string, unknown>;
  options: ProductOrderFieldOption[];
};

type Product = {
  id: string;
  name: string;
  slug: string;
  price: string;
  description?: string | null;
  image_url?: string | null;
  stock_quantity?: number | null;
  product_type: ProductType;
  default_fulfillment_method: FulfillmentMethod;
  allowed_fulfillment_methods: FulfillmentMethod[];
  order_fields: ProductOrderField[];
};

type Store = {
  slug: string;
  name: string;
  whatsapp_number?: string | null;
  can_receive_online_payments: boolean;
};

type CreatedOrder = {
  id: string;
  order_number: string;
  total: string;
  currency: string;
  fulfillment_method: FulfillmentMethod;
  whatsapp_handoff_status: string;
  whatsapp_message?: string | null;
};

type SelectedOptions = Record<string, string | boolean>;

type HandoffChannel = "none" | "whatsapp";

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

function canonicalizeFingerprintValue(
  value: unknown,
): unknown {
  if (Array.isArray(value)) {
    return value.map(canonicalizeFingerprintValue);
  }

  if (
    typeof value === "object" &&
    value !== null
  ) {
    const entries = Object.entries(
      value as Record<string, unknown>,
    ).sort(([leftKey], [rightKey]) => {
      if (leftKey < rightKey) {
        return -1;
      }

      if (leftKey > rightKey) {
        return 1;
      }

      return 0;
    });

    return Object.fromEntries(
      entries.map(([key, entryValue]) => [
        key,
        canonicalizeFingerprintValue(entryValue),
      ]),
    );
  }

  return value;
}

function fingerprintOrderPayload(
  payload: unknown,
) {
  const serialized = JSON.stringify(
    canonicalizeFingerprintValue(payload),
  );

  let firstHash = 2166136261;
  let secondHash = 5381;

  for (
    let index = 0;
    index < serialized.length;
    index += 1
  ) {
    const code = serialized.charCodeAt(index);

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
    const raw = window.sessionStorage.getItem(
      storageKey,
    );

    if (!raw) {
      return null;
    }

    const parsed: unknown = JSON.parse(raw);

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
      fingerprint: candidate.fingerprint,
      idempotencyKey: candidate.idempotencyKey,
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
    // The in-memory reference still protects
    // retries during this page session.
  }
}

function clearPendingOrderAttempt(
  storageKey: string,
  idempotencyKey: string,
) {
  try {
    const stored = readPendingOrderAttempt(
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

function formatMoney(
  value: string | number,
  currency = "GHS",
) {
  const amount = Number(value);

  if (!Number.isFinite(amount)) {
    return `${currency} 0.00`;
  }

  const fixed = amount.toFixed(2);
  const [whole, decimal] = fixed.split(".");
  const grouped = whole.replace(
    /\B(?=(\d{3})+(?!\d))/g,
    ",",
  );

  return `${currency} ${grouped}.${decimal}`;
}

function formatFulfillmentMethod(
  method: FulfillmentMethod,
) {
  const labels: Record<FulfillmentMethod, string> = {
    delivery: "Delivery",
    pickup: "Pickup",
    digital_delivery: "Digital delivery",
    activation: "Activation",
    appointment: "Appointment",
    on_site_service: "On-site service",
    remote_service: "Remote service",
    reservation: "Reservation",
    seller_confirmation: "Confirm with seller",
  };

  return labels[method] ?? "Confirm with seller";
}

function getFulfillmentDescription(
  method: FulfillmentMethod,
) {
  const descriptions: Record<FulfillmentMethod, string> = {
    delivery: "Delivered to your location.",
    pickup: "Collect it from the seller.",
    digital_delivery: "Sent to you online.",
    activation: "The seller will activate it for you.",
    appointment: "Choose an appointment time.",
    on_site_service: "The seller comes to your location.",
    remote_service: "Provided online or by phone.",
    reservation: "Reserve your preferred date or time.",
    seller_confirmation: "The seller will confirm the next step.",
  };

  return descriptions[method];
}

function fulfillmentNeedsLocation(
  method: FulfillmentMethod,
) {
  return (
    method === "delivery" ||
    method === "on_site_service"
  );
}

function formatProductType(productType: ProductType) {
  const labels: Record<ProductType, string> = {
    physical: "Physical item",
    digital: "Digital item",
    subscription: "Subscription",
    service: "Service",
    food: "Food & catering",
    booking: "Booking",
    custom: "Custom order",
  };

  return labels[productType] ?? "Custom order";
}

function getInputType(
  fieldType: ProductOrderFieldType,
) {
  if (fieldType === "datetime") {
    return "datetime-local";
  }

  if (
    fieldType === "email" ||
    fieldType === "number" ||
    fieldType === "date" ||
    fieldType === "time"
  ) {
    return fieldType;
  }

  return "text";
}

function readNumberRule(
  rules: Record<string, unknown>,
  key: string,
) {
  const value = rules[key];

  if (
    typeof value === "number" ||
    typeof value === "string"
  ) {
    return value;
  }

  return undefined;
}

function readLengthRule(
  rules: Record<string, unknown>,
  key: string,
) {
  const value = rules[key];
  const number = Number(value);

  return Number.isInteger(number) && number >= 0
    ? number
    : undefined;
}

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
  const [selectedOptions, setSelectedOptions] =
    useState<SelectedOptions>({});

  const allowedFulfillmentMethods =
    product.allowed_fulfillment_methods?.length > 0
      ? product.allowed_fulfillment_methods
      : [product.default_fulfillment_method || "seller_confirmation"];

  const [fulfillmentMethod, setFulfillmentMethod] =
    useState<FulfillmentMethod>(() => {
      const preferred = product.default_fulfillment_method;
      return allowedFulfillmentMethods.includes(preferred)
        ? preferred
        : allowedFulfillmentMethods[0];
    });

  const [submittingChannel, setSubmittingChannel] =
    useState<HandoffChannel | null>(null);
  const [paying, setPaying] = useState(false);
  const [createdOrder, setCreatedOrder] =
    useState<CreatedOrder | null>(null);
  const [
    completedHandoffChannel,
    setCompletedHandoffChannel,
  ] = useState<HandoffChannel | null>(null);
  const [error, setError] = useState("");

  const formRef = useRef<HTMLFormElement | null>(null);
  const pendingAttemptRef =
    useRef<PendingOrderAttempt | null>(null);

  const attemptStorageKey = [
    ORDER_ATTEMPT_STORAGE_PREFIX,
    store.slug,
    product.id,
  ].join(":");

  const stock = product.stock_quantity;
  const hasStockTracking = typeof stock === "number";
  const isSoldOut = hasStockTracking && stock <= 0;
  const orderControlsDisabled =
    isSoldOut || submittingChannel !== null;
  const maxQuantity = hasStockTracking ? stock : 100;
  const whatsappNumber = getWhatsAppNumber(
    store.whatsapp_number,
  );
  const productDescription =
    product.description?.trim();

  const activeOrderFields = (product.order_fields || [])
    .filter((field) => field.is_active)
    .sort((left, right) =>
      left.sort_order - right.sort_order ||
      left.label.localeCompare(right.label),
    );

  const optionPriceAdjustment = activeOrderFields.reduce(
    (total, field) => {
      if (
        field.field_type !== "select" &&
        field.field_type !== "radio"
      ) {
        return total;
      }

      const selectedValue = selectedOptions[field.key];
      const selectedOption = field.options.find(
        (option) =>
          option.is_active &&
          option.value === selectedValue,
      );
      const adjustment = Number(
        selectedOption?.price_adjustment ?? 0,
      );

      return Number.isFinite(adjustment)
        ? total + adjustment
        : total;
    },
    0,
  );

  const configuredUnitPrice =
    Number(product.price) + optionPriceAdjustment;
  const estimatedTotal = configuredUnitPrice * quantity;
  const needsAddress =
    fulfillmentNeedsLocation(fulfillmentMethod);
  const onlinePaymentsEnabled =
    store.can_receive_online_payments === true;

  function updateSelectedOption(
    key: string,
    value: string | boolean,
  ) {
    setSelectedOptions((previous) => ({
      ...previous,
      [key]: value,
    }));
  }

  function selectFulfillmentMethod(
    method: FulfillmentMethod,
  ) {
    setFulfillmentMethod(method);

    if (!fulfillmentNeedsLocation(method)) {
      setDeliveryAddress("");
    }
  }

  function getCleanSelectedOptions() {
    return Object.fromEntries(
      Object.entries(selectedOptions).filter(([, value]) =>
        typeof value === "boolean" ||
        String(value).trim().length > 0,
      ),
    );
  }

  async function createOrder(
    handoffChannel: HandoffChannel,
  ) {
    setError("");
    setCreatedOrder(null);
    setCompletedHandoffChannel(null);

    if (isSoldOut) {
      setError("This product is currently sold out.");
      return;
    }

    if (hasStockTracking && quantity > stock) {
      setError(`Only ${stock} left in stock for ${product.name}`);
      return;
    }

    if (
      handoffChannel === "whatsapp" &&
      !whatsappNumber
    ) {
      setError("This seller has not connected a WhatsApp number.");
      return;
    }

    const normalizedCustomerEmail =
      customerEmail.trim();

    if (
      handoffChannel === "none" &&
      onlinePaymentsEnabled &&
      !normalizedCustomerEmail
    ) {
      setError(
        "Enter your email address to continue to payment.",
      );

      const emailInput =
        formRef.current?.elements.namedItem(
          "customer-email",
        );

      if (emailInput instanceof HTMLInputElement) {
        emailInput.focus();
      }

      return;
    }

    if (
      needsAddress &&
      !deliveryAddress.trim()
    ) {
      setError(
        fulfillmentMethod === "on_site_service"
          ? "Enter the service location."
          : "Enter the delivery location.",
      );

      const locationInput =
        formRef.current?.elements.namedItem(
          "delivery-address",
        );

      if (
        locationInput instanceof
        HTMLTextAreaElement
      ) {
        locationInput.focus();
      }

      return;
    }

    setSubmittingChannel(handoffChannel);

    try {
      const orderPayload = {
        store_slug: store.slug,
        customer_name: customerName,
        customer_phone: customerPhone,
        customer_email:
          normalizedCustomerEmail || null,
        delivery_address: needsAddress
          ? deliveryAddress.trim() || null
          : null,
        customer_note: customerNote || null,
        fulfillment_method: fulfillmentMethod,
        handoff_channel: handoffChannel,
        items: [
          {
            product_id: product.id,
            quantity,
            selected_options: getCleanSelectedOptions(),
          },
        ],
      };

      const payloadFingerprint =
        fingerprintOrderPayload(orderPayload);

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
          fingerprint: payloadFingerprint,
          idempotencyKey:
            createOrderIdempotencyKey(),
        };
      }

      pendingAttemptRef.current = pendingAttempt;

      persistPendingOrderAttempt(
        attemptStorageKey,
        pendingAttempt,
      );

      const response = await fetch(
        `${API_URL}/public/orders`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key":
              pendingAttempt.idempotencyKey,
          },
          body: JSON.stringify(orderPayload),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not create order",
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
        pendingAttemptRef.current = null;
      }

      const order = data as CreatedOrder;
      setCreatedOrder(order);
      setCompletedHandoffChannel(
        handoffChannel,
      );

      if (handoffChannel === "whatsapp") {
        if (
          order.whatsapp_handoff_status !== "ready" ||
          !order.whatsapp_message ||
          !whatsappNumber
        ) {
          throw new Error(
            `Order ${order.order_number} was created, but WhatsApp could not be opened automatically.`,
          );
        }

        const whatsappUrl =
          `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(
            order.whatsapp_message,
          )}`;

        window.location.assign(whatsappUrl);
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Something went wrong",
      );
    } finally {
      setSubmittingChannel(null);
    }
  }

  async function submitOrder(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    await createOrder("none");
  }

  async function submitWhatsAppOrder() {
    if (!formRef.current?.reportValidity()) {
      return;
    }

    await createOrder("whatsapp");
  }

  async function payNow() {
    if (!createdOrder?.id) {
      setError("Create an order first before paying.");
      return;
    }

    const normalizedCustomerEmail =
      customerEmail.trim();

    if (!normalizedCustomerEmail) {
      setError(
        "A valid email address is required for online payment. Start a new order and enter your email address.",
      );
      return;
    }

    setError("");
    setPaying(true);

    try {
      const response = await fetch(
        `${API_URL}/payments/initialize`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            order_id: createdOrder.id,
            customer_email:
              normalizedCustomerEmail,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Could not initialize payment",
        );
      }

      window.location.href = data.authorization_url;
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Something went wrong",
      );
      setPaying(false);
    }
  }

  const whatsappResumeUrl =
    createdOrder?.whatsapp_message &&
    whatsappNumber
      ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(
          createdOrder.whatsapp_message,
        )}`
      : null;

  const trustNoteUsesWhatsApp =
    createdOrder &&
    completedHandoffChannel === "whatsapp";

  return (
    <div className="order-page conversational-order-page">
      <div className="order-shell conversational-order-shell">
        <a className="back-link" href={`/${store.slug}`}>
          Back to store
        </a>

        <div className="order-layout conversational-order-layout">
          <section className="order-summary conversational-order-summary">
            <div className="order-product-card">
              <SafeProductImage
                imageUrl={product.image_url}
                productName={product.name}
              />
            </div>

            <div className="product-context-row">
              <p className="store-label">{store.name}</p>
              <span className="product-type-badge">
                {formatProductType(product.product_type)}
              </span>
            </div>

            <h1>{product.name}</h1>
            {productDescription && (
              <p className="order-product-description">
                {productDescription}
              </p>
            )}

            <div className="order-summary-ledger">
              <div className="summary-row">
                <span>Base price</span>
                <strong>
                  {formatMoney(product.price)}
                </strong>
              </div>

              {optionPriceAdjustment !== 0 && (
                <div className="summary-row">
                  <span>Selected options</span>
                  <strong>
                    {optionPriceAdjustment > 0 ? "+" : ""}
                    {formatMoney(optionPriceAdjustment)}
                  </strong>
                </div>
              )}

              <div className="summary-row">
                <span>How you'll receive it</span>
                <strong>
                  {formatFulfillmentMethod(
                    fulfillmentMethod,
                  )}
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

              {activeOrderFields.map((field) => {
                const value = selectedOptions[field.key];

                if (
                  value === undefined ||
                  value === ""
                ) {
                  return null;
                }

                const displayValue =
                  field.field_type === "select" ||
                  field.field_type === "radio"
                    ? field.options.find(
                        (option) =>
                          option.value === value,
                      )?.label ?? String(value)
                    : typeof value === "boolean"
                      ? value
                        ? "Yes"
                        : "No"
                      : String(value);

                return (
                  <div className="summary-row" key={field.key}>
                    <span>{field.label}</span>
                    <strong>{displayValue}</strong>
                  </div>
                );
              })}
            </div>

            <div className="summary-total">
              <span>Estimated total</span>
              <strong>
                {formatMoney(estimatedTotal)}
              </strong>
            </div>

            <div className="order-trust-note">
                <strong>
                  {createdOrder
                    ? trustNoteUsesWhatsApp
                      ? "Your order is saved before WhatsApp opens."
                      : "Your order has been saved."
                    : "Your order is saved when you place it."}
                </strong>
                <p>
                  {createdOrder
                    ? trustNoteUsesWhatsApp
                      ? "Your item will only be held after payment or seller confirmation."
                      : "The seller will contact you about payment and fulfilment."
                    : "Choose your preferred order option below. Your item will only be held after payment or seller confirmation."}
                </p>
              </div>
          </section>

          <form
            ref={formRef}
            className={
              createdOrder
                ? "order-form order-form-complete conversational-order-form"
                : "order-form conversational-order-form"
            }
            onSubmit={submitOrder}
          >
            <div className="checkout-form-heading">
              <span>Order details</span>
              <h2>
                {createdOrder
                  ? "Order created"
                  : "Complete your order"}
              </h2>
              <p className="form-muted">
                {createdOrder
                  ? "Save the reference below. You can track this order at any time."
                  : "Choose your options and provide the details the seller needs."}
              </p>
            </div>

            {!createdOrder && (
              <>
                <section className="checkout-form-section">
                  <div className="checkout-section-title">
                    <span>1</span>
                    <div>
                      <strong>Your details</strong>
                      <p>Used for order updates and seller contact.</p>
                    </div>
                  </div>

                  <div className="checkout-field-grid">
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
                        disabled={orderControlsDisabled}
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
                        disabled={orderControlsDisabled}
                      />
                    </label>
                  </div>

                  <label>
                    {onlinePaymentsEnabled
                      ? "Email address (required for payment)"
                      : "Email address (optional)"}
                    <input
                      name="customer-email"
                      type="email"
                      autoComplete="email"
                      maxLength={255}
                      value={customerEmail}
                      onChange={(event) =>
                        setCustomerEmail(
                          event.target.value,
                        )
                      }
                      placeholder="name@example.com"
                      disabled={orderControlsDisabled}
                    />
                  </label>
                </section>

                <section className="checkout-form-section">
                  <div className="checkout-section-title">
                    <span>2</span>
                    <div>
                      <strong>How will you receive it?</strong>
                      <p>Choose the option that works for you.</p>
                    </div>
                  </div>

                  <div className="customer-fulfillment-grid">
                    {allowedFulfillmentMethods.map((method) => (
                      <label
                        key={method}
                        className={
                          fulfillmentMethod === method
                            ? "customer-fulfillment-card selected"
                            : "customer-fulfillment-card"
                        }
                      >
                        <input
                          type="radio"
                          name="fulfillment-method"
                          value={method}
                          checked={fulfillmentMethod === method}
                          onChange={() =>
                            selectFulfillmentMethod(method)
                          }
                          disabled={orderControlsDisabled}
                        />
                        <span>
                          <strong>
                            {formatFulfillmentMethod(method)}
                          </strong>
                          <small>
                            {getFulfillmentDescription(method)}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>

                  {needsAddress && (
                    <label>
                      {fulfillmentMethod === "on_site_service"
                        ? "Service location"
                        : "Delivery location"}
                      <textarea
                        name="delivery-address"
                        autoComplete="street-address"
                        value={deliveryAddress}
                        onChange={(event) =>
                          setDeliveryAddress(
                            event.target.value,
                          )
                        }
                        placeholder={
                          fulfillmentMethod === "on_site_service"
                            ? "Where should the seller provide the service?"
                            : "Area, landmark, street, or full address"
                        }
                        required
                        disabled={orderControlsDisabled}
                      />
                    </label>
                  )}
                </section>

                {activeOrderFields.length > 0 && (
                  <section className="checkout-form-section">
                    <div className="checkout-section-title">
                      <span>3</span>
                      <div>
                        <strong>Choose your options</strong>
                        <p>Select the details for your order.</p>
                      </div>
                    </div>

                    <div className="dynamic-order-fields">
                      {activeOrderFields.map((field) => {
                        const rules = field.validation_rules || {};
                        const value = selectedOptions[field.key];
                        const fieldId = `order-field-${field.id}`;

                        if (field.field_type === "textarea") {
                          return (
                            <label key={field.id} htmlFor={fieldId}>
                              {field.label}
                              <textarea
                                id={fieldId}
                                name={field.key}
                                value={
                                  typeof value === "string"
                                    ? value
                                    : ""
                                }
                                onChange={(event) =>
                                  updateSelectedOption(
                                    field.key,
                                    event.target.value,
                                  )
                                }
                                placeholder={field.placeholder || ""}
                                required={field.is_required}
                                minLength={readLengthRule(rules, "min_length")}
                                maxLength={readLengthRule(rules, "max_length")}
                                disabled={orderControlsDisabled}
                              />
                              {field.help_text && (
                                <small>{field.help_text}</small>
                              )}
                              {field.is_sensitive && (
                                <small className="private-field-note">
                                  Kept out of the WhatsApp summary.
                                </small>
                              )}
                            </label>
                          );
                        }

                        if (field.field_type === "select") {
                          return (
                            <label key={field.id} htmlFor={fieldId}>
                              {field.label}
                              <select
                                id={fieldId}
                                name={field.key}
                                value={
                                  typeof value === "string"
                                    ? value
                                    : ""
                                }
                                onChange={(event) =>
                                  updateSelectedOption(
                                    field.key,
                                    event.target.value,
                                  )
                                }
                                required={field.is_required}
                                disabled={orderControlsDisabled}
                              >
                                <option value="">
                                  {field.placeholder || "Choose an option"}
                                </option>
                                {field.options
                                  .filter((option) => option.is_active)
                                  .sort((left, right) =>
                                    left.sort_order - right.sort_order,
                                  )
                                  .map((option) => (
                                    <option key={option.id} value={option.value}>
                                      {option.label}
                                      {Number(option.price_adjustment) !== 0
                                        ? ` (${Number(option.price_adjustment) > 0 ? "+" : ""}${formatMoney(option.price_adjustment)})`
                                        : ""}
                                    </option>
                                  ))}
                              </select>
                              {field.help_text && (
                                <small>{field.help_text}</small>
                              )}
                            </label>
                          );
                        }

                        if (field.field_type === "radio") {
                          return (
                            <fieldset
                              className="dynamic-radio-field"
                              key={field.id}
                            >
                              <legend>{field.label}</legend>
                              {field.help_text && (
                                <p>{field.help_text}</p>
                              )}
                              <div className="dynamic-radio-options">
                                {field.options
                                  .filter((option) => option.is_active)
                                  .sort((left, right) =>
                                    left.sort_order - right.sort_order,
                                  )
                                  .map((option) => (
                                    <label
                                      key={option.id}
                                      className={
                                        value === option.value
                                          ? "dynamic-radio-card selected"
                                          : "dynamic-radio-card"
                                      }
                                    >
                                      <input
                                        type="radio"
                                        name={field.key}
                                        value={option.value}
                                        checked={value === option.value}
                                        onChange={() =>
                                          updateSelectedOption(
                                            field.key,
                                            option.value,
                                          )
                                        }
                                        required={field.is_required}
                                        disabled={orderControlsDisabled}
                                      />
                                      <span>
                                        <strong>{option.label}</strong>
                                        {Number(option.price_adjustment) !== 0 && (
                                          <small>
                                            {Number(option.price_adjustment) > 0
                                              ? "+"
                                              : ""}
                                            {formatMoney(option.price_adjustment)}
                                          </small>
                                        )}
                                      </span>
                                    </label>
                                  ))}
                              </div>
                            </fieldset>
                          );
                        }

                        if (field.field_type === "checkbox") {
                          return (
                            <label
                              key={field.id}
                              className="dynamic-checkbox-field"
                            >
                              <input
                                type="checkbox"
                                name={field.key}
                                checked={value === true}
                                onChange={(event) =>
                                  updateSelectedOption(
                                    field.key,
                                    event.target.checked,
                                  )
                                }
                                required={field.is_required}
                                disabled={orderControlsDisabled}
                              />
                              <span>
                                <strong>{field.label}</strong>
                                {field.help_text && (
                                  <small>{field.help_text}</small>
                                )}
                              </span>
                            </label>
                          );
                        }

                        return (
                          <label key={field.id} htmlFor={fieldId}>
                            {field.label}
                            <input
                              id={fieldId}
                              name={field.key}
                              type={getInputType(field.field_type)}
                              inputMode={
                                field.field_type === "phone"
                                  ? "tel"
                                  : field.field_type === "number"
                                    ? "decimal"
                                    : undefined
                              }
                              autoComplete={
                                field.field_type === "email"
                                  ? "email"
                                  : field.field_type === "phone"
                                    ? "tel"
                                    : "off"
                              }
                              value={
                                typeof value === "string"
                                  ? value
                                  : ""
                              }
                              onChange={(event) =>
                                updateSelectedOption(
                                  field.key,
                                  event.target.value,
                                )
                              }
                              placeholder={field.placeholder || ""}
                              required={field.is_required}
                              min={readNumberRule(rules, "min")}
                              max={readNumberRule(rules, "max")}
                              step={
                                field.field_type === "number"
                                  ? "any"
                                  : undefined
                              }
                              minLength={readLengthRule(rules, "min_length")}
                              maxLength={readLengthRule(rules, "max_length")}
                              disabled={orderControlsDisabled}
                            />
                            {field.help_text && (
                              <small>{field.help_text}</small>
                            )}
                            {field.is_sensitive && (
                              <small className="private-field-note">
                                Kept out of the WhatsApp summary.
                              </small>
                            )}
                          </label>
                        );
                      })}
                    </div>
                  </section>
                )}

                <section className="checkout-form-section">
                  <div className="checkout-section-title">
                    <span>{activeOrderFields.length > 0 ? "4" : "3"}</span>
                    <div>
                      <strong>Quantity & note</strong>
                      <p>Review the amount and add any final instruction.</p>
                    </div>
                  </div>

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
                        const nextQuantity = Number(
                          event.target.value,
                        );

                        if (hasStockTracking) {
                          setQuantity(
                            Math.min(
                              Math.max(nextQuantity, 1),
                              stock,
                            ),
                          );
                        } else {
                          setQuantity(
                            Math.min(
                              Math.max(nextQuantity, 1),
                              100,
                            ),
                          );
                        }
                      }}
                      required
                      disabled={orderControlsDisabled}
                    />
                  </label>

                  <label>
                    Note to seller (optional)
                    <textarea
                      name="customer-note"
                      autoComplete="off"
                      value={customerNote}
                      onChange={(event) =>
                        setCustomerNote(
                          event.target.value,
                        )
                      }
                      placeholder="Add any final instruction for the seller."
                      disabled={orderControlsDisabled}
                    />
                  </label>
                </section>
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
                This product is currently sold out.
              </div>
            )}

            {createdOrder && (
              <div
                className="success-box order-success-box conversational-order-success"
                aria-live="polite"
              >
                <span className="order-success-label">
                  Order reference
                </span>

                <strong className="order-success-number">
                  {createdOrder.order_number}
                </strong>

                <p>
                  Your order was created successfully for {formatMoney(
                    createdOrder.total,
                    createdOrder.currency,
                  )}.
                </p>

                <div className="order-success-actions">
                  <a
                    className="inline-link"
                    href={`/track?order=${encodeURIComponent(
                      createdOrder.order_number,
                    )}`}
                  >
                    Track this order
                  </a>

                  {whatsappResumeUrl && (
                    <a
                      className="inline-link whatsapp-resume-link"
                      href={whatsappResumeUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Continue on WhatsApp
                    </a>
                  )}
                </div>
              </div>
            )}

            {!createdOrder ? (
              <div className="checkout-actions">
                {whatsappNumber && (
                  <button
                    className="whatsapp-order-btn"
                    type="button"
                    onClick={() => void submitWhatsAppOrder()}
                    disabled={
                      submittingChannel !== null ||
                      isSoldOut
                    }
                  >
                    <span className="whatsapp-order-icon" aria-hidden="true">
                      WA
                    </span>
                    <span>
                      <strong>
                        {submittingChannel === "whatsapp"
                          ? "Saving your order..."
                          : "Order on WhatsApp"}
                      </strong>
                      <small>
                        Your order details will be ready to send in WhatsApp.
                      </small>
                    </span>
                  </button>
                )}

                <button
                  className={
                    whatsappNumber
                      ? "secondary-order-submit"
                      : "submit-order-btn"
                  }
                  type="submit"
                  disabled={
                    submittingChannel !== null ||
                    isSoldOut
                  }
                >
                  {submittingChannel === "none"
                    ? "Saving your order..."
                    : onlinePaymentsEnabled
                      ? "Continue to payment"
                      : "Place order without WhatsApp"}
                </button>
              </div>
            ) : onlinePaymentsEnabled ? (
              <button
                className="submit-order-btn pay-btn"
                type="button"
                onClick={payNow}
                disabled={paying}
              >
                {paying
                  ? "Opening Paystack..."
                  : "Pay this order now"}
              </button>
            ) : (
              <div className="payment-disabled-box">
                <strong>Complete payment with the seller</strong>
                <p>
                  {whatsappResumeUrl
                    ? "Continue on WhatsApp for payment details, or wait for the seller to contact you."
                    : "The seller will contact you with payment details and confirm the next steps."}
                </p>
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
