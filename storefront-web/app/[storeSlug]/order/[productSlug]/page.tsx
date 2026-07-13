import OrderForm from "../../../components/OrderForm";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type Product = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  image_url?: string | null;
  price: string;
  stock_quantity?: number | null;
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

async function getStore(storeSlug: string): Promise<StoreFetchResult> {
  const res = await fetch(`${API_URL}/public/stores/${storeSlug}`, {
    cache: "no-store",
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    return {
      data: null,
      status: res.status,
      detail: data?.detail || "Store is not available.",
    };
  }

  return {
    data,
    status: res.status,
    detail: "",
  };
}

export default async function ProductOrderPage({
  params,
}: {
  params: Promise<{ storeSlug: string; productSlug: string }>;
}) {
  const { storeSlug, productSlug } = await params;

  const result = await getStore(storeSlug);

  if (!result.data) {
    const isUnavailable = result.status === 403;

    return (
      <main className="not-found">
        <div className="not-found-card">
          <h1>
            {isUnavailable ? "Store temporarily unavailable" : "Store not found"}
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
  const products: Product[] = result.data.products || [];
  const product = products.find((item) => item.slug === productSlug);

  if (!product) {
    return (
      <main className="not-found">
        <div className="not-found-card">
          <h1>Product not found</h1>
          <p>This product does not exist or is currently unavailable.</p>
          <a className="btn btn-dark" href={`/${store.slug}`}>
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
          <a className="back-link" href={`/${store.slug}`}>
            Back to store
          </a>

          <div className="order-form-card">
            <h2>Sold out</h2>
            <p>This product is currently out of stock.</p>
            <a className="submit-order-btn" href={`/${store.slug}`}>
              Back to store
            </a>
          </div>
        </section>
      </main>
    );
  }

  return <OrderForm store={store} product={product} />;
}
