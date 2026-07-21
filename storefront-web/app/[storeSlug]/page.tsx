import { Suspense } from "react";

import {
  StorefrontCatalogueEmptyState,
  StorefrontRouteErrorState,
  StorefrontRouteLoadingState,
} from "../components/StorefrontCatalogueStates";
import StorefrontProductCard, {
  normalizeStorefrontProduct,
  type StorefrontProductCardData,
} from "../components/StorefrontProductCard";
import {
  resolveStorefrontApiBaseUrl,
  resolveStorefrontMediaUrl,
} from "../lib/api-url";
import { getWhatsAppNumber } from "../lib/phone";

const API_URL =
  resolveStorefrontApiBaseUrl();

type UnknownRecord = Record<string, unknown>;

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
        products: unknown[];
      };
    }
  | {
      ok: false;
      status: number;
      detail: string;
      kind: "http" | "network" | "invalid";
    };

function isRecord(
  value: unknown,
): value is UnknownRecord {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function readOptionalString(
  value: unknown,
): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const normalized = value.trim();
  return normalized || null;
}

function normalizeStore(
  value: unknown,
): Store | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = readOptionalString(value.id);
  const slug = readOptionalString(value.slug);
  const name = readOptionalString(value.name);

  if (!id || !slug || !name) {
    return null;
  }

  return {
    id,
    slug,
    name,
    bio: readOptionalString(value.bio),
    logo_url: readOptionalString(value.logo_url),
    banner_url: readOptionalString(value.banner_url),
    whatsapp_number: readOptionalString(
      value.whatsapp_number,
    ),
    category: readOptionalString(value.category),
    can_receive_online_payments:
      value.can_receive_online_payments === true,
  };
}

function normalizeStorePayload(
  value: unknown,
): {
  store: Store;
  products: unknown[];
} | null {
  if (!isRecord(value)) {
    return null;
  }

  const store = normalizeStore(value.store);

  if (!store || !Array.isArray(value.products)) {
    return null;
  }

  return {
    store,
    products: value.products,
  };
}

async function getStore(
  storeSlug: string,
): Promise<StoreFetchResult> {
  try {
    const res = await fetch(
      `${API_URL}/public/stores/${storeSlug}`,
      {
        cache: "no-store",
      },
    );

    const data: unknown = await res
      .json()
      .catch(() => null);

    if (!res.ok) {
      const detail =
        isRecord(data) &&
        typeof data.detail === "string"
          ? data.detail
          : "Store is not available.";

      return {
        ok: false,
        status: res.status,
        detail,
        kind: "http",
      };
    }

    const normalized = normalizeStorePayload(data);

    if (!normalized) {
      return {
        ok: false,
        status: 500,
        detail: "Store data could not be loaded.",
        kind: "invalid",
      };
    }

    return {
      ok: true,
      data: normalized,
    };
  }
  catch {
    return {
      ok: false,
      status: 0,
      detail: "Store data could not be loaded.",
      kind: "network",
    };
  }
}

function getDisplayProducts(
  products: unknown[],
): StorefrontProductCardData[] {
  const renderable = products
    .map(normalizeStorefrontProduct)
    .filter(
      (
        product,
      ): product is StorefrontProductCardData =>
        product !== null,
    );

  const featured = renderable.filter(
    (product) => product.isFeatured,
  );
  const standard = renderable.filter(
    (product) => !product.isFeatured,
  );

  return [...featured, ...standard];
}

function StoreUnavailableState({
  unavailable,
}: {
  unavailable: boolean;
}) {
  return (
    <main className="not-found">
      <div className="not-found-card">
        <h1>
          {unavailable
            ? "Store temporarily unavailable"
            : "Store not found"}
        </h1>

        <p>
          {unavailable
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

async function StorePageContent({
  storeSlug,
}: {
  storeSlug: string;
}) {
  const result = await getStore(storeSlug);

  if (result.ok === false) {
    if (result.status === 403) {
      return <StoreUnavailableState unavailable />;
    }

    if (result.status === 404) {
      return <StoreUnavailableState unavailable={false} />;
    }

    return (
      <StorefrontRouteErrorState
        storeSlug={storeSlug}
      />
    );
  }

  const store = result.data.store;
  const products = getDisplayProducts(
    result.data.products,
  );
  const whatsappNumber = getWhatsAppNumber(
    store.whatsapp_number,
  );

  const bannerUrl = resolveStorefrontMediaUrl(
    store.banner_url,
  );

  const logoUrl = resolveStorefrontMediaUrl(
    store.logo_url,
  );

  return (
    <main className="store-page">
      <section className="store-profile-hero">
        {bannerUrl ? (
          <img
            alt={store.name}
            className="store-banner"
            src={bannerUrl}
          />
        ) : (
          <div className="store-banner store-banner-empty" />
        )}

        <div className="store-profile-card">
          <div className="store-profile-summary">
            {logoUrl ? (
              <img
                alt={store.name}
                className="store-logo"
                src={logoUrl}
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
            {store.bio ||
              "Shop products and place orders directly."}
          </p>

          <div className="store-actions">
            {whatsappNumber && (
              <a
                className="btn store-action-primary"
                href={`https://wa.me/${whatsappNumber}`}
                rel="noreferrer"
                target="_blank"
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

      <section className="storefront-catalogue">
        <div className="storefront-catalogue-heading">
          <h2>Products</h2>
          <span>
            {products.length}{" "}
            {products.length === 1
              ? "product"
              : "products"}
          </span>
        </div>

        {products.length > 0 ? (
          <div className="storefront-catalogue-grid">
            {products.map((product) => (
              <StorefrontProductCard
                key={product.id}
                product={product}
                storeSlug={store.slug}
              />
            ))}
          </div>
        ) : (
          <StorefrontCatalogueEmptyState />
        )}
      </section>
    </main>
  );
}

export default async function StorePage({
  params,
}: {
  params: Promise<{ storeSlug: string }>;
}) {
  const { storeSlug } = await params;

  return (
    <Suspense
      fallback={<StorefrontRouteLoadingState />}
    >
      <StorePageContent storeSlug={storeSlug} />
    </Suspense>
  );
}
