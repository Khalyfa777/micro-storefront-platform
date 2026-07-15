import SafeProductImage from "../components/SafeProductImage";
import {
  resolveStorefrontApiBaseUrl,
  resolveStorefrontMediaUrl,
} from "../lib/api-url";
import { getWhatsAppNumber } from "../lib/phone";

const API_URL =
  resolveStorefrontApiBaseUrl();

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

function getProductInitial(name?: string | null) {
  const cleanName = String(name || "").trim();
  return cleanName.charAt(0).toUpperCase() || "P";
}

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

type StoreFetchResult =
  | {
      ok: true;
      data: {
        store: Store;
        products: Product[];
      };
    }
  | {
      ok: false;
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
      ok: false,
      status: res.status,
      detail: data?.detail || "Store is not available.",
    };
  }

  return {
    ok: true,
    data,
  };
}

export default async function StorePage({
  params,
}: {
  params: Promise<{ storeSlug: string }>;
}) {
  const { storeSlug } = await params;
  const result = await getStore(storeSlug);

  if (!result.ok) {
    const isUnavailable = "status" in result && result.status === 403;

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
  const whatsappNumber = getWhatsAppNumber(
    store.whatsapp_number,
  );

  const bannerUrl =
    resolveStorefrontMediaUrl(
      store.banner_url,
    );

  const logoUrl =
    resolveStorefrontMediaUrl(
      store.logo_url,
    );

  return (
    <main className="store-page">
      <section className="store-profile-hero">
        {bannerUrl ? (
          <img className="store-banner" src={bannerUrl} alt={store.name} />
        ) : (
          <div className="store-banner store-banner-empty" />
        )}

        <div className="store-profile-card">
          <div className="store-profile-summary">
            {logoUrl ? (
              <img
                className="store-logo"
                src={logoUrl}
                alt={store.name}
              />
            ) : (
              <div className="store-logo store-logo-empty">
                {store.name.slice(0, 1).toUpperCase()}
              </div>
            )}

            <div className="store-profile-heading">
              <p className="eyebrow store-category-badge">
                {store.category || "Micro Storefront"}
              </p>
              <h1>{store.name}</h1>
            </div>
          </div>

          <p className="store-bio">
            {store.bio || "Shop products and place orders directly."}
          </p>

          <div className="store-actions">
            {whatsappNumber && (
              <a
                className="btn store-action-primary"
                href={`https://wa.me/${whatsappNumber}`}
                target="_blank"
                rel="noreferrer"
              >
                Chat on WhatsApp
              </a>
            )}

            <a
              className="btn store-action-secondary"
              href="/track"
            >
              Track order
            </a>
          </div>
        </div>
      </section>

      <section className="products-section">
        <div className="section-head">
          <div>
            <p className="eyebrow">Products</p>
            <h2>Available items</h2>
          </div>

          <span>
            {products.length}{" "}
            {products.length === 1
              ? "item"
              : "items"}
          </span>
        </div>

        <div className="product-grid">
          {products.map((product) => {
            const stock = product.stock_quantity;
            const hasStock = typeof stock === "number";
            const isSoldOut = hasStock && stock <= 0;
            const description = product.description?.trim();

            return (
              <article className="product-card" key={product.id}>

                <SafeProductImage
                  imageUrl={product.image_url}
                  productName={product.name}
                />

                <div className="product-body">
                  <div className="product-top">
                    <h3>{product.name}</h3>
                    {product.is_featured && <span>Featured</span>}
                  </div>

                  {description && <p>{description}</p>}

                  <div className="product-meta-row">
                    <strong>
                      {formatMoney(product.price)}
                    </strong>
                    <span>
                      {hasStock
                        ? isSoldOut
                          ? "Sold out"
                          : `${stock} available`
                        : "Available"}
                    </span>
                  </div>

                  {isSoldOut ? (
                    <button className="order-btn disabled" disabled>
                      Sold out
                    </button>
                  ) : (
                    <a className="order-btn" href={`/${store.slug}/order/${product.slug}`}>
                      Order now
                    </a>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
