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

  return (
    <main className="store-page">
      <section className="store-profile-hero">
        {store.banner_url ? (
          <img className="store-banner" src={store.banner_url} alt={store.name} />
        ) : (
          <div className="store-banner store-banner-empty" />
        )}

        <div className="store-profile-card">
          {store.logo_url ? (
            <img className="store-logo" src={store.logo_url} alt={store.name} />
          ) : (
            <div className="store-logo store-logo-empty">
              {store.name.slice(0, 1).toUpperCase()}
            </div>
          )}

          <div>
            <p className="eyebrow">{store.category || "Micro Storefront"}</p>
            <h1>{store.name}</h1>
            <p>{store.bio || "Shop products and place orders directly."}</p>

            <div className="store-actions">
              {store.whatsapp_number && (
                <a
                  className="btn btn-light"
                  href={`https://wa.me/${store.whatsapp_number}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Message on WhatsApp
                </a>
              )}

              <a className="btn btn-dark" href="/track">
                Track order
              </a>

              <span className="store-slug">/{store.slug}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="products-section">
        <div className="section-head">
          <div>
            <p className="eyebrow">Products</p>
            <h2>Available items</h2>
          </div>

          <span>{products.length} item(s)</span>
        </div>

        <div className="product-grid">
          {products.map((product) => {
            const stock = product.stock_quantity;
            const hasStock = typeof stock === "number";
            const isSoldOut = hasStock && stock <= 0;

            return (
              <article className="product-card" key={product.id}>
                {product.image_url ? (
                  <img
                    className="product-image"
                    src={product.image_url}
                    alt={product.name}
                  />
                ) : (
                  <div className="product-image-placeholder">Product Image</div>
                )}

                <div className="product-body">
                  <div className="product-top">
                    <h3>{product.name}</h3>
                    {product.is_featured && <span>Featured</span>}
                  </div>

                  <p>{product.description || "No description added."}</p>

                  <div className="product-meta-row">
                    <strong>GHS {Number(product.price).toFixed(2)}</strong>
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