import StorefrontProductMedia from "./StorefrontProductMedia";


type UnknownRecord = Record<string, unknown>;

export type StorefrontProductCardData = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  imageUrl: string | null;
  price: unknown;
  stockQuantity: number | null;
  isFeatured: boolean;
  orderFields: unknown[];
};

const SELECTABLE_FIELD_TYPES = new Set([
  "select",
  "radio",
  "checkbox",
]);

function isRecord(
  value: unknown,
): value is UnknownRecord {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function readRequiredString(
  value: unknown,
): string {
  return typeof value === "string"
    ? value.trim()
    : "";
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

function readStockQuantity(
  value: unknown,
): number | null {
  return (
    typeof value === "number" &&
    Number.isFinite(value)
  )
    ? value
    : null;
}

export function normalizeStorefrontProduct(
  value: unknown,
): StorefrontProductCardData | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = readRequiredString(value.id);
  const name = readRequiredString(value.name);
  const slug = readRequiredString(value.slug);

  if (!id || !name || !slug) {
    return null;
  }

  return {
    id,
    name,
    slug,
    description: readOptionalString(
      value.description,
    ),
    imageUrl: readOptionalString(
      value.image_url,
    ),
    price: value.price,
    stockQuantity: readStockQuantity(
      value.stock_quantity,
    ),
    isFeatured: value.is_featured === true,
    orderFields: Array.isArray(value.order_fields)
      ? value.order_fields
      : [],
  };
}

function normalizeDisplayText(
  value: string,
): string {
  return value.replace(/\s+/g, " ").trim();
}

function normalizeComparisonText(
  value: string,
): string {
  return normalizeDisplayText(value)
    .replace(
      /^[\s.,!?;:'"(){}\[\]<>/_–—-]+|[\s.,!?;:'"(){}\[\]<>/_–—-]+$/g,
      "",
    )
    .toLowerCase();
}

function getSupportingDetail(
  description: string | null,
  productName: string,
): string {
  if (!description) {
    return "";
  }

  const normalizedDescription =
    normalizeDisplayText(description);

  if (!normalizedDescription) {
    return "";
  }

  if (
    normalizeComparisonText(normalizedDescription) ===
    normalizeComparisonText(productName)
  ) {
    return "";
  }

  return normalizedDescription;
}

function hasSelectableOptions(
  orderFields: unknown[],
): boolean {
  return orderFields.some((field) => {
    if (
      !isRecord(field) ||
      field.is_active !== true ||
      typeof field.field_type !== "string" ||
      !SELECTABLE_FIELD_TYPES.has(
        field.field_type,
      ) ||
      !Array.isArray(field.options)
    ) {
      return false;
    }

    return field.options.some(
      (option) =>
        isRecord(option) &&
        option.is_active === true,
    );
  });
}

export function isSparseProductCard({
  supportingDetail,
  lowStockStatus,
  optionsStatus,
  soldOut,
}: {
  supportingDetail: string;
  lowStockStatus: string;
  optionsStatus: string;
  soldOut: boolean;
}): boolean {
  return (
    !supportingDetail &&
    !lowStockStatus &&
    !optionsStatus &&
    !soldOut
  );
}

function getPriceParts(
  value: unknown,
): {
  currency: string;
  amount: string;
} | null {
  const amount =
    typeof value === "number"
      ? value
      : typeof value === "string" &&
          value.trim()
        ? Number(value)
        : Number.NaN;

  if (
    !Number.isFinite(amount) ||
    amount < 0
  ) {
    return null;
  }

  return {
    currency: "GHS",
    amount: new Intl.NumberFormat(
      "en-GH",
      {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      },
    ).format(amount),
  };
}

function getStockState(
  stockQuantity: number | null,
): {
  soldOut: boolean;
  status: string;
} {
  if (stockQuantity === null) {
    return {
      soldOut: false,
      status: "",
    };
  }

  if (stockQuantity <= 0) {
    return {
      soldOut: true,
      status: "",
    };
  }

  if (
    Number.isInteger(stockQuantity) &&
    stockQuantity >= 1 &&
    stockQuantity <= 3
  ) {
    return {
      soldOut: false,
      status: `Only ${stockQuantity} left`,
    };
  }

  return {
    soldOut: false,
    status: "",
  };
}

function getSafeIdSegment(
  value: string,
): string {
  return value.replace(
    /[^A-Za-z0-9_-]/g,
    "-",
  );
}

export default function StorefrontProductCard({
  product,
  storeSlug,
}: {
  product: StorefrontProductCardData;
  storeSlug: string;
}) {
  const supportingDetail = getSupportingDetail(
    product.description,
    product.name,
  );
  const selectableOptions = hasSelectableOptions(
    product.orderFields,
  );
  const stockState = getStockState(
    product.stockQuantity,
  );
  const priceParts = getPriceParts(product.price);

  const actionLabel = stockState.soldOut
    ? "View details"
    : selectableOptions
      ? "Choose options"
      : "View product";

  const optionsStatus =
    selectableOptions &&
    !stockState.soldOut
      ? "Options available"
      : "";

  const statusLabel =
    stockState.status || optionsStatus;

  const sparseContent = isSparseProductCard({
    supportingDetail,
    lowStockStatus: stockState.status,
    optionsStatus,
    soldOut: stockState.soldOut,
  });

  const badgeLabel = stockState.soldOut
    ? "Sold out"
    : product.isFeatured
      ? "Featured"
      : "";

  const safeId = getSafeIdSegment(product.id);
  const titleId =
    `storefront-product-${safeId}-title`;
  const priceId =
    `storefront-product-${safeId}-price`;
  const actionId =
    `storefront-product-${safeId}-action`;
  const statusId = statusLabel
    ? `storefront-product-${safeId}-status`
    : "";

  const describedBy = [
    priceId,
    statusId,
    actionId,
  ]
    .filter(Boolean)
    .join(" ");

  const href =
    `/${encodeURIComponent(storeSlug)}` +
    `/order/${encodeURIComponent(product.slug)}`;

  return (
    <article className="storefront-product-card">
      <a
        aria-describedby={describedBy}
        aria-labelledby={titleId}
        className="storefront-product-card-link"
        href={href}
      >
        <span className="storefront-product-card-media-shell">
          <StorefrontProductMedia
            imageUrl={product.imageUrl}
          />

          {badgeLabel && (
            <span
              className={
                "storefront-product-card-badge " +
                (
                  stockState.soldOut
                    ? "storefront-product-card-badge--sold-out"
                    : "storefront-product-card-badge--featured"
                )
              }
            >
              {badgeLabel}
            </span>
          )}
        </span>

        <span
          className={
            "storefront-product-card-content" +
            (
              sparseContent
                ? " storefront-product-card-content--sparse"
                : ""
            )
          }
        >
          <span
            className="storefront-product-card-title"
            id={titleId}
          >
            {product.name}
          </span>

          <span
            className={
              "storefront-product-card-price" +
              (priceParts
                ? ""
                : " storefront-product-card-price--unavailable")
            }
            id={priceId}
          >
            {priceParts ? (
              <>
                <span>{priceParts.currency}</span>
                <span>{priceParts.amount}</span>
              </>
            ) : (
              "Price unavailable"
            )}
          </span>

          {supportingDetail && (
            <span className="storefront-product-card-support">
              {supportingDetail}
            </span>
          )}

          {statusLabel && (
            <span
              className={
                "storefront-product-card-status " +
                (stockState.status
                  ? "storefront-product-card-status--low-stock"
                  : "storefront-product-card-status--options")
              }
              id={statusId}
            >
              {statusLabel}
            </span>
          )}

          <span
            className="storefront-product-card-action"
            id={actionId}
          >
            <span>{actionLabel}</span>
            <span
              aria-hidden="true"
              className="storefront-product-card-action-icon"
            >
              →
            </span>
          </span>
        </span>
      </a>
    </article>
  );
}
