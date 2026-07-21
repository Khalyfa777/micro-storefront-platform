function CatalogueStateIcon() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
    >
      <path
        d="M5.25 5.5A2.25 2.25 0 0 1 7.5 3.25h9a2.25 2.25 0 0 1 2.25 2.25v13a2.25 2.25 0 0 1-2.25 2.25h-9a2.25 2.25 0 0 1-2.25-2.25v-13Zm2.25-.75a.75.75 0 0 0-.75.75v13c0 .41.34.75.75.75h9a.75.75 0 0 0 .75-.75v-13a.75.75 0 0 0-.75-.75h-9Zm1.5 3A.75.75 0 0 1 9.75 7h4.5a.75.75 0 0 1 0 1.5h-4.5A.75.75 0 0 1 9 7.75Zm0 4A.75.75 0 0 1 9.75 11h4.5a.75.75 0 0 1 0 1.5h-4.5A.75.75 0 0 1 9 11.75Zm0 4A.75.75 0 0 1 9.75 15h2.5a.75.75 0 0 1 0 1.5h-2.5A.75.75 0 0 1 9 15.75Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function StorefrontCatalogueEmptyState() {
  return (
    <div className="storefront-catalogue-empty">
      <span className="storefront-catalogue-state-icon">
        <CatalogueStateIcon />
      </span>
      <h3>No products yet</h3>
      <p>
        This store is getting its catalogue ready.
        Please check back soon.
      </p>
    </div>
  );
}

export function StorefrontRouteErrorState({
  storeSlug,
}: {
  storeSlug: string;
}) {
  return (
    <main className="store-page storefront-route-state-page">
      <section className="storefront-route-error" role="alert">
        <span className="storefront-catalogue-state-icon">
          <CatalogueStateIcon />
        </span>
        <h1>We couldn’t load this store.</h1>
        <p>
          Check your connection and try again.
        </p>
        <a
          className="btn btn-dark"
          href={`/${encodeURIComponent(storeSlug)}`}
        >
          Try again
        </a>
      </section>
    </main>
  );
}

function LoadingProductCard() {
  return (
    <div
      aria-hidden="true"
      className="storefront-product-card storefront-product-card--loading"
    >
      <div className="storefront-product-card-link">
        <span className="storefront-product-card-loading-media" />
        <span className="storefront-product-card-loading-content">
          <span className="storefront-skeleton-line storefront-skeleton-line--title" />
          <span className="storefront-skeleton-line storefront-skeleton-line--price" />
          <span className="storefront-skeleton-line storefront-skeleton-line--support" />
          <span className="storefront-skeleton-line storefront-skeleton-line--action" />
        </span>
      </div>
    </div>
  );
}

export function StorefrontRouteLoadingState() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading store"
      className="store-page storefront-route-loading"
    >
      <section className="store-profile-hero storefront-route-loading-hero">
        <div
          aria-hidden="true"
          className="storefront-loading-banner"
        />
        <div
          aria-hidden="true"
          className="store-profile-card storefront-loading-profile-card"
        >
          <span className="storefront-loading-logo" />
          <span className="storefront-loading-profile-copy">
            <span className="storefront-skeleton-line storefront-skeleton-line--eyebrow" />
            <span className="storefront-skeleton-line storefront-skeleton-line--store-name" />
            <span className="storefront-skeleton-line storefront-skeleton-line--store-bio" />
            <span className="storefront-loading-actions">
              <span />
              <span />
            </span>
          </span>
        </div>
      </section>

      <section className="storefront-catalogue">
        <div
          aria-hidden="true"
          className="storefront-catalogue-heading storefront-catalogue-heading--loading"
        >
          <span className="storefront-skeleton-line storefront-skeleton-line--heading" />
          <span className="storefront-skeleton-line storefront-skeleton-line--count" />
        </div>

        <div className="storefront-catalogue-grid">
          <LoadingProductCard />
          <LoadingProductCard />
          <LoadingProductCard />
        </div>
      </section>
    </main>
  );
}
