import OrderForm from "../../../components/OrderForm";
import {
  resolveStorefrontApiBaseUrl,
} from "../../../lib/api-url";

const API_URL =
  resolveStorefrontApiBaseUrl();

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
  field_type:
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
  description?: string | null;
  image_url?: string | null;
  price: string;
  stock_quantity?: number | null;
  product_type: ProductType;
  default_fulfillment_method: FulfillmentMethod;
  allowed_fulfillment_methods: FulfillmentMethod[];
  order_fields: ProductOrderField[];
  is_active: boolean;
  is_featured: boolean;
};

type Store = {
  id: string;
  slug: string;
  name: string;
  bio?: string | null;
  logo_url?: string | null;
  banner_url?: string | null;
  whatsapp_number?: string | null;
  category?: string | null;
  can_receive_online_payments: boolean;
};

type StoreFetchResult = {
  data: {
    store: Store;
    products: Product[];
  } | null;
  status: number;
  detail: string;
};

async function getStore(
  storeSlug: string,
): Promise<StoreFetchResult> {
  const response = await fetch(
    `${API_URL}/public/stores/${storeSlug}`,
    {
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    return {
      data: null,
      status: response.status,
      detail:
        data?.detail ||
        "Store is not available.",
    };
  }

  return {
    data,
    status: response.status,
    detail: "",
  };
}

export default async function ProductOrderPage({
  params,
}: {
  params: Promise<{
    storeSlug: string;
    productSlug: string;
  }>;
}) {
  const { storeSlug, productSlug } = await params;
  const result = await getStore(storeSlug);

  if (!result.data) {
    const isUnavailable = result.status === 403;

    return (
      <main className="not-found">
        <div className="not-found-card">
          <h1>
            {isUnavailable
              ? "Store temporarily unavailable"
              : "Store not found"}
          </h1>

          <p>
            {isUnavailable
              ? "This store is not accepting orders right now. Please check again later."
              : "This store does not exist or is currently unavailable."}
          </p>

          <a className="btn btn-dark" href="/track">
            Track order
          </a>
        </div>
      </main>
    );
  }

  const store: Store = result.data.store;
  const products: Product[] =
    result.data.products || [];
  const product = products.find(
    (item) => item.slug === productSlug,
  );

  if (!product) {
    return (
      <main className="not-found">
        <div className="not-found-card">
          <h1>Product not found</h1>
          <p>
            This product does not exist or is currently unavailable.
          </p>
          <a
            className="btn btn-dark"
            href={`/${store.slug}`}
          >
            Back to store
          </a>
        </div>
      </main>
    );
  }

  const stock = product.stock_quantity;
  const hasStock = typeof stock === "number";
  const isSoldOut = hasStock && stock <= 0;

  if (isSoldOut) {
    return (
      <main className="order-page">
        <section className="order-shell">
          <a
            className="back-link"
            href={`/${store.slug}`}
          >
            Back to store
          </a>

          <div className="order-form-card">
            <h2>Sold out</h2>
            <p>
              This product is currently out of stock.
            </p>
            <a
              className="submit-order-btn"
              href={`/${store.slug}`}
            >
              Back to store
            </a>
          </div>
        </section>
      </main>
    );
  }

  return (
    <OrderForm store={store} product={product} />
  );
}
