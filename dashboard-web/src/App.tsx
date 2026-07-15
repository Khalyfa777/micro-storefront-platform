import { useEffect, useEffectEvent, useLayoutEffect, useState } from "react";
import { LoginPage } from "./pages/LoginPage";
import { OrdersPage } from "./pages/OrdersPage";
import { ProductsPage } from "./pages/ProductsPage";
import { StoreProfilePage } from "./pages/StoreProfilePage";
import { SecurityPage } from "./pages/SecurityPage";
import { AdminSummaryPage } from "./pages/AdminSummaryPage";
import { AdminPlansPage } from "./pages/AdminPlansPage";
import { AdminPaymentsPage } from "./pages/AdminPaymentsPage";
import { AdminSellersPage } from "./pages/AdminSellersPage";
import type {
  AdminSellerListItem,
  AdminSellerListResponse,
} from "./types/admin-seller";
import { Sidebar } from "./layouts/Sidebar";
import { DashboardShell } from "./layouts/DashboardShell";
import {
  resolvePublicStoreBaseUrl,
} from "./utils/public-store-url";
import {
  resolveDashboardApiBaseUrl,
  toPortableDashboardMediaReference,
} from "./utils/api-url";

import {
  normalizeGhanaWhatsAppNumber,
} from "./utils/phone";
import "./App.css";

const API_URL =
  resolveDashboardApiBaseUrl();

const MAX_IMAGE_UPLOAD_BYTES =
  3 * 1024 * 1024;

const ALLOWED_IMAGE_UPLOAD_TYPES =
  new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
  ]);

function getImageUploadValidationError(
  file: File,
): string | null {
  if (
    !ALLOWED_IMAGE_UPLOAD_TYPES.has(
      file.type,
    )
  ) {
    return (
      "Only JPG, PNG, and WEBP " +
      "images are allowed."
    );
  }

  if (
    file.size >
    MAX_IMAGE_UPLOAD_BYTES
  ) {
    return (
      "Image is too large. " +
      "Maximum size is 3MB."
    );
  }

  return null;
}




type AdminSubscriptionPaymentItem = {
  id: string;
  store_id: string;
  store_name: string;
  store_slug: string;
  plan_name: string;
  amount: string | number;
  currency: string;
  payment_method: string;
  payment_reference?: string | null;
  note?: string | null;
  covered_days: number;
  approved_by_email?: string | null;
  paid_at: string;
  created_at: string;
};
type AdminSubscriptionSummary = {
  total_stores: number;
  active_stores: number;
  trial_stores: number;
  expired_stores: number;
  suspended_stores: number;
  expiring_within_7_days: number;
  monthly_recurring_total: string | number;
  subscription_revenue_total: string | number;
  subscription_revenue_this_month: string | number;
  recent_payment_count: number;
};
type AdminSubscriptionPlanItem = {
  id: string;
  name: string;
  display_name: string;
  monthly_fee: string | number;
  is_quote_only: boolean;
  product_limit?: number | null;
  can_upload_images: boolean;
  can_use_custom_domain: boolean;
  can_receive_online_payments: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type SubscriptionPlanDraft = {
  display_name: string;
  monthly_fee: string;
  is_quote_only: boolean;
  product_limit: string;
  can_upload_images: boolean;
  can_use_custom_domain: boolean;
  can_receive_online_payments: boolean;
  is_active: boolean;
};
type StoreSubscriptionUsage = {
  plan_name: string;
  display_name: string;
  monthly_fee: string | number;
  is_quote_only: boolean;
  product_limit?: number | null;
  active_products: number;
  remaining_products?: number | null;
  is_unlimited: boolean;
  can_upload_images: boolean;
  can_use_custom_domain: boolean;
  can_receive_online_payments: boolean;
  plan_is_active: boolean;
};
function getRoleFromToken(token: string) {
  try {
    const payload = token.split(".")[1];

    if (!payload) {
      return "";
    }

    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const parsed = JSON.parse(atob(normalized));

    return parsed.role || "";
  } catch {
    return "";
  }
}

function isPlatformAdminToken(token: string) {
  return ["admin", "platform_admin", "super_admin"].includes(getRoleFromToken(token));
}

function formatPlanName(value?: string | null) {
  if (!value) return "Starter";

  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatSubscriptionDate(value?: string | null) {
  if (!value) return "Not set";

  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatMonthlyFee(value?: string | number | null) {
  if (value === null || value === undefined || value === "") {
    return "GHS 0";
  }

  return `GHS ${Number(value).toFixed(2)}`;
}
type ApiErrorPayload = {
  detail?: unknown;
};

function getApiErrorMessage(
  data: unknown,
  fallback: string,
) {
  if (
    !data
    || typeof data !== "object"
    || !("detail" in data)
  ) {
    return fallback;
  }

  const detail = (
    data as ApiErrorPayload
  ).detail;

  if (!detail) {
    return fallback;
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (
          item
          && typeof item === "object"
        ) {
          const candidate = item as {
            msg?: unknown;
            message?: unknown;
          };

          if (
            typeof candidate.msg === "string"
          ) {
            return candidate.msg;
          }

          if (
            typeof candidate.message
            === "string"
          ) {
            return candidate.message;
          }
        }

        return JSON.stringify(item);
      })
      .join(", ");
  }

  return JSON.stringify(detail) || fallback;
}
const PUBLIC_STORE_URL = resolvePublicStoreBaseUrl();
const SUPPORT_WHATSAPP_NUMBER = import.meta.env.VITE_SUPPORT_WHATSAPP || "233544193559";


function getSubscriptionExpiryDate(
  status?: string | null,
  trialEndsAt?: string | null,
  subscriptionEndsAt?: string | null,
) {
  return (status || "trial") === "trial"
    ? trialEndsAt
    : subscriptionEndsAt;
}

function getComputedSubscriptionStatus(
  status?: string | null,
  trialEndsAt?: string | null,
  subscriptionEndsAt?: string | null,
  isSuspended?: boolean | null,
) {
  const normalizedStatus = status || "trial";

  if (isSuspended || normalizedStatus === "suspended") {
    return "suspended";
  }

  if (
    normalizedStatus === "trial" ||
    normalizedStatus === "active"
  ) {
    const expiryValue = getSubscriptionExpiryDate(
      normalizedStatus,
      trialEndsAt,
      subscriptionEndsAt,
    );

    if (!expiryValue) {
      return "expired";
    }

    const expiryTime = new Date(expiryValue).getTime();

    if (
      !Number.isFinite(expiryTime) ||
      expiryTime <= Date.now()
    ) {
      return "expired";
    }
  }

  return normalizedStatus;
}

function getSubscriptionTimeLabel(
  status?: string | null,
  trialEndsAt?: string | null,
  subscriptionEndsAt?: string | null,
  isSuspended?: boolean | null,
) {
  const computedStatus = getComputedSubscriptionStatus(
    status,
    trialEndsAt,
    subscriptionEndsAt,
    isSuspended,
  );

  if (computedStatus === "suspended") {
    return "Suspended";
  }

  if (computedStatus === "expired") {
    return status === "trial"
      ? "Trial expired"
      : "Expired";
  }

  const expiryValue = getSubscriptionExpiryDate(
    status,
    trialEndsAt,
    subscriptionEndsAt,
  );

  if (!expiryValue) {
    return "No expiry date";
  }

  const expiryTime = new Date(expiryValue).getTime();

  if (!Number.isFinite(expiryTime)) {
    return "Invalid expiry date";
  }

  const diffMs = expiryTime - Date.now();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) {
    return status === "trial"
      ? "Trial expired"
      : "Expired";
  }

  if (diffDays === 1) {
    return "1 day left";
  }

  return `${diffDays} days left`;
}

function getSubscriptionTimeClass(
  status?: string | null,
  trialEndsAt?: string | null,
  subscriptionEndsAt?: string | null,
  isSuspended?: boolean | null,
) {
  const computedStatus = getComputedSubscriptionStatus(
    status,
    trialEndsAt,
    subscriptionEndsAt,
    isSuspended,
  );

  if (
    computedStatus === "suspended" ||
    computedStatus === "expired"
  ) {
    return "danger";
  }

  const expiryValue = getSubscriptionExpiryDate(
    status,
    trialEndsAt,
    subscriptionEndsAt,
  );

  if (!expiryValue) {
    return "neutral";
  }

  const expiryTime = new Date(expiryValue).getTime();

  if (!Number.isFinite(expiryTime)) {
    return "danger";
  }

  const diffMs = expiryTime - Date.now();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) {
    return "danger";
  }

  if (diffDays <= 7) {
    return "warning";
  }

  return "good";
}

function getProductUsagePercent(usage?: StoreSubscriptionUsage | null) {
  if (!usage || usage.is_unlimited || !usage.product_limit || usage.product_limit <= 0) {
    return 100;
  }

  return Math.min(
    Math.round((usage.active_products / usage.product_limit) * 100),
    100
  );
}

function getProductUsageClass(usage?: StoreSubscriptionUsage | null) {
  if (!usage || usage.is_unlimited || !usage.product_limit) {
    return "good";
  }

  const percent = getProductUsagePercent(usage);

  if (percent >= 100) {
    return "danger";
  }

  if (percent >= 80) {
    return "warning";
  }

  return "good";
}

function formatProductUsageLabel(usage?: StoreSubscriptionUsage | null) {
  if (!usage) {
    return "Loading product usage...";
  }

  if (usage.is_unlimited) {
    return `${usage.active_products} active products / Unlimited`;
  }

  return `${usage.active_products} / ${usage.product_limit} active products`;
}

function formatRemainingProducts(usage?: StoreSubscriptionUsage | null) {
  if (!usage) {
    return "Loading...";
  }

  if (usage.is_unlimited) {
    return "Unlimited remaining";
  }

  return `${usage.remaining_products ?? 0} products remaining`;
}
type Store = {
  id: string;
  owner_id?: string;
  slug: string;
  name: string;
  bio?: string | null;
  logo_url?: string | null;
  banner_url?: string | null;
  whatsapp_number?: string | null;
  category?: string | null;
  is_active?: boolean;
  is_suspended?: boolean;
  publication_status:
    | "draft"
    | "published";
  plan_name?: string;
  subscription_status?: string;
  trial_ends_at?: string | null;
  subscription_ends_at?: string | null;
  last_payment_at?: string | null;
  monthly_fee?: string | number;
};

type OrderItem = {
  id: string;
  product_name: string;
  unit_price: string;
  quantity: number;
  line_total: string;
};

type Order = {
  id: string;
  order_number: string;
  status: string;
  payment_method?: string | null;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  delivery_address?: string | null;
  total: string;
  currency: string;
  inventory_deducted?: boolean;
  created_at: string;
  items: OrderItem[];
};

type Product = {
  id: string;
  store_id: string;
  name: string;
  slug: string;
  description?: string | null;
  image_url?: string | null;
  product_type: string;
  price: string;
  stock_quantity?: number | null;
  is_active: boolean;
  is_featured: boolean;
};

type ProductForm = {
  name: string;
  slug: string;
  description: string;
  image_url: string;
  product_type: string;
  price: string;
  stock_quantity: string;
  is_active: boolean;
  is_featured: boolean;
};

type StoreForm = {
  name: string;
  slug: string;
  bio: string;
  whatsapp_number: string;
  logo_url: string;
  banner_url: string;
  category: string;
};


function shouldShowSubscriptionBanner(store?: Store | null) {
  if (!store) {
    return false;
  }

  const status = getComputedSubscriptionStatus(
    store.subscription_status,
    store.trial_ends_at,
    store.subscription_ends_at,
    store.is_suspended,
  );

  if (status === "expired" || status === "suspended") {
    return true;
  }

  const timeClass = getSubscriptionTimeClass(
    store.subscription_status,
    store.trial_ends_at,
    store.subscription_ends_at,
    store.is_suspended,
  );

  return timeClass === "warning" || timeClass === "danger";
}

function getSubscriptionBannerTitle(store: Store) {
  const status = getComputedSubscriptionStatus(
    store.subscription_status,
    store.trial_ends_at,
    store.subscription_ends_at,
    store.is_suspended,
  );

  if (status === "suspended") {
    return "Store suspended";
  }

  if (status === "expired") {
    return store.subscription_status === "trial"
      ? "Trial expired"
      : "Subscription expired";
  }

  return "Subscription renewal reminder";
}

function getSubscriptionBannerMessage(store: Store) {
  const status = getComputedSubscriptionStatus(
    store.subscription_status,
    store.trial_ends_at,
    store.subscription_ends_at,
    store.is_suspended,
  );

  if (status === "suspended") {
    return "Your public store is temporarily unavailable. Please contact support to reactivate it.";
  }

  if (status === "expired") {
    return store.subscription_status === "trial"
      ? "Your free trial has ended. Activate a paid plan to continue accepting orders."
      : "Your public store is not accepting orders right now. Renew your subscription to reactivate selling.";
  }

  return `Your subscription has ${getSubscriptionTimeLabel(
    store.subscription_status,
    store.trial_ends_at,
    store.subscription_ends_at,
    store.is_suspended,
  ).toLowerCase()}. Renew early to avoid interruption.`;
}

function getSubscriptionRenewalUrl(store: Store) {
  const message = `Hello, I want to renew my subscription for ${store.name} /${store.slug}.`;

  return `https://wa.me/${SUPPORT_WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`;
}
const emptyProductForm: ProductForm = {
  name: "",
  slug: "",
  description: "",
  image_url: "",
  product_type: "physical",
  price: "",
  stock_quantity: "0",
  is_active: true,
  is_featured: false,
};


const PRODUCT_DRAFT_STORAGE_PREFIX =
  "storeplug.productDraft.";

const PRODUCT_DRAFT_MAX_AGE_MS =
  24 * 60 * 60 * 1000;

type StoredProductDraft = {
  form: ProductForm;
  editingProductId: string;
  isOpen: boolean;
  savedAt: number;
};

function getProductDraftStorageKey(
  storeId: string,
) {
  return (
    PRODUCT_DRAFT_STORAGE_PREFIX +
    storeId
  );
}

function normalizeStoredProductForm(
  value: unknown,
): ProductForm | null {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value)
  ) {
    return null;
  }

  const form = value as Record<
    string,
    unknown
  >;

  return {
    name:
      typeof form.name === "string"
        ? form.name
        : "",
    slug:
      typeof form.slug === "string"
        ? form.slug
        : "",
    description:
      typeof form.description === "string"
        ? form.description
        : "",
    image_url:
      typeof form.image_url === "string"
        ? form.image_url
        : "",
    product_type:
      typeof form.product_type === "string"
        ? form.product_type
        : "physical",
    price:
      typeof form.price === "string"
        ? form.price
        : "",
    stock_quantity:
      typeof form.stock_quantity === "string"
        ? form.stock_quantity
        : "0",
    is_active:
      typeof form.is_active === "boolean"
        ? form.is_active
        : true,
    is_featured:
      typeof form.is_featured === "boolean"
        ? form.is_featured
        : false,
  };
}

function readStoredProductDraft(
  storeId: string,
): StoredProductDraft | null {
  if (typeof window === "undefined") {
    return null;
  }

  const key =
    getProductDraftStorageKey(storeId);

  try {
    const raw =
      window.sessionStorage.getItem(key);

    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as {
      form?: unknown;
      editingProductId?: unknown;
      isOpen?: unknown;
      savedAt?: unknown;
    };

    if (
      typeof parsed.savedAt !== "number" ||
      Date.now() - parsed.savedAt >
        PRODUCT_DRAFT_MAX_AGE_MS
    ) {
      window.sessionStorage.removeItem(key);
      return null;
    }

    const form =
      normalizeStoredProductForm(
        parsed.form,
      );

    if (!form) {
      window.sessionStorage.removeItem(key);
      return null;
    }

    const editingProductId =
      typeof parsed.editingProductId ===
      "string"
        ? parsed.editingProductId
        : "";

    const isOpen =
      parsed.isOpen === true ||
      Boolean(editingProductId);

    if (!isOpen) {
      window.sessionStorage.removeItem(key);
      return null;
    }

    return {
      form,
      editingProductId,
      isOpen,
      savedAt: parsed.savedAt,
    };
  } catch {
    window.sessionStorage.removeItem(key);
    return null;
  }
}

function writeStoredProductDraft(
  storeId: string,
  draft: Omit<
    StoredProductDraft,
    "savedAt"
  >,
) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(
    getProductDraftStorageKey(storeId),
    JSON.stringify({
      ...draft,
      savedAt: Date.now(),
    }),
  );
}

function removeStoredProductDraft(
  storeId: string,
) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.removeItem(
    getProductDraftStorageKey(storeId),
  );
}

function clearStoredProductDrafts() {
  if (typeof window === "undefined") {
    return;
  }

  Object.keys(window.sessionStorage)
    .filter((key) =>
      key.startsWith(
        PRODUCT_DRAFT_STORAGE_PREFIX,
      ),
    )
    .forEach((key) => {
      window.sessionStorage.removeItem(key);
    });
}


const emptyStoreForm: StoreForm = {
  name: "",
  slug: "",
  bio: "",
  whatsapp_number: "",
  logo_url: "",
  banner_url: "",
  category: "",
};

function makeSlug(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const ORDER_STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["paid", "cancelled"],
  paid: ["processing", "completed", "cancelled"],
  processing: ["completed", "cancelled"],
  completed: ["cancelled"],
  cancelled: [],
};

function getAllowedOrderStatusActions(status: string): string[] {
  return ORDER_STATUS_TRANSITIONS[status?.toLowerCase()] || [];
}

function formatOrderStatusActionLabel(status: string): string {
  const labels: Record<string, string> = {
    paid: "Paid",
    processing: "Processing",
    completed: "Completed",
    cancelled: "Cancelled",
  };

  return labels[status] || status;
}

type DashboardTab =
  | "orders"
  | "products"
  | "settings"
  | "security"
  | "adminSummary"
  | "adminSellers"
  | "adminPlans"
  | "adminPayments";

const dashboardTabs: DashboardTab[] = [
  "orders",
  "products",
  "settings",
  "security",
  "adminSummary",
  "adminSellers",
  "adminPlans",
  "adminPayments",
];

const platformAdminTabs: DashboardTab[] = [
  "adminSummary",
  "adminSellers",
  "adminPlans",
  "adminPayments",
];

const merchantTabs: DashboardTab[] = [
  "orders",
  "products",
  "settings",
  "security",
];

const dashboardPathTabs: Record<string, DashboardTab> = {
  "/admin": "adminSummary",
  "/admin/overview": "adminSummary",
  "/admin/sellers": "adminSellers",
  "/admin/plans": "adminPlans",
  "/admin/payments": "adminPayments",
};

function getDashboardTabFromPathname(
  pathname: string,
): DashboardTab | null {
  const normalizedPath =
    pathname.replace(/\/+$/, "") || "/";

  return dashboardPathTabs[normalizedPath] || null;
}

function getRequestedDashboardTab(): DashboardTab | null {
  if (typeof window === "undefined") return null;

  const pathTab = getDashboardTabFromPathname(
    window.location.pathname,
  );

  if (pathTab) return pathTab;

  const hashTab = window.location.hash.replace(
    "#",
    "",
  ) as DashboardTab;

  if (dashboardTabs.includes(hashTab)) return hashTab;

  const savedTab = window.localStorage.getItem(
    "storeplug.activeTab",
  ) as DashboardTab | null;

  if (savedTab && dashboardTabs.includes(savedTab)) {
    return savedTab;
  }

  return null;
}

function getInitialDashboardTab(token: string): DashboardTab {
  const requestedTab = getRequestedDashboardTab();
  const allowedTabs = isPlatformAdminToken(token)
    ? dashboardTabs
    : merchantTabs;

  if (
    requestedTab &&
    allowedTabs.includes(requestedTab)
  ) {
    return requestedTab;
  }

  return "orders";
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");

  const isPlatformAdmin = isPlatformAdminToken(token);
const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [, setLoginDebug] = useState("");

  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);

  const [subscriptionUsage, setSubscriptionUsage] = useState<StoreSubscriptionUsage | null>(null);
  const [loadingSubscriptionUsage, setLoadingSubscriptionUsage] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  const [productForm, setProductForm] = useState<ProductForm>(emptyProductForm);
  const [editingProductId, setEditingProductId] = useState<string>("");
  const [isProductFormOpen, setIsProductFormOpen] = useState(false);

  const [storeForm, setStoreForm] = useState<StoreForm>(emptyStoreForm);

  const [activeTab, setActiveTab] = useState<DashboardTab>(() => getInitialDashboardTab(token));
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useLayoutEffect(() => {
    if (
      !token ||
      typeof window === "undefined" ||
      isPlatformAdmin
    ) {
      return;
    }

    const pathTab = getDashboardTabFromPathname(
      window.location.pathname,
    );

    if (
      pathTab === null ||
      !platformAdminTabs.includes(pathTab)
    ) {
      return;
    }

    localStorage.setItem(
      "storeplug.activeTab",
      "orders",
    );
    window.history.replaceState(
      null,
      "",
      "/#orders",
    );
  }, [token, isPlatformAdmin]);

  useEffect(() => {
    if (!token || typeof window === "undefined") return;

    const allowedTabs = isPlatformAdmin
      ? dashboardTabs
      : merchantTabs;

    if (!allowedTabs.includes(activeTab)) {
      return;
    }

    localStorage.setItem("storeplug.activeTab", activeTab);

    const nextHash = `#${activeTab}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${nextHash}`);
    }
  }, [token, isPlatformAdmin, activeTab]);

  useEffect(() => {
    if (
      !token ||
      !selectedStore
    ) {
      return;
    }

    if (
      !isProductFormOpen &&
      !editingProductId
    ) {
      removeStoredProductDraft(
        selectedStore.id,
      );
      return;
    }

    writeStoredProductDraft(
      selectedStore.id,
      {
        form: productForm,
        editingProductId,
        isOpen: true,
      },
    );
  }, [
    token,
    selectedStore,
    productForm,
    editingProductId,
    isProductFormOpen,
  ]);

  const [message, setMessage] = useState("");



  const [adminSellers, setAdminSellers] =
    useState<AdminSellerListItem[]>([]);

  const [
    adminSellerNextCursor,
    setAdminSellerNextCursor,
  ] = useState<string | null>(null);

  const [
    adminSellersHasMore,
    setAdminSellersHasMore,
  ] = useState(false);

  const [
    loadingAdminSellers,
    setLoadingAdminSellers,
  ] = useState(false);

  const [
    loadingMoreAdminSellers,
    setLoadingMoreAdminSellers,
  ] = useState(false);

  const [
    adminSellerListError,
    setAdminSellerListError,
  ] = useState("");

  const [subscriptionPlans, setSubscriptionPlans] = useState<AdminSubscriptionPlanItem[]>([]);
  const [planDrafts, setPlanDrafts] = useState<Record<string, SubscriptionPlanDraft>>({});
  const [loadingSubscriptionPlans, setLoadingSubscriptionPlans] = useState(false);
  const [adminSubscriptionSummary, setAdminSubscriptionSummary] = useState<AdminSubscriptionSummary | null>(null);
  const [loadingAdminSubscriptionSummary, setLoadingAdminSubscriptionSummary] = useState(false);
  const [adminSubscriptionPayments, setAdminSubscriptionPayments] = useState<AdminSubscriptionPaymentItem[]>([]);
  const [loadingAdminSubscriptionPayments, setLoadingAdminSubscriptionPayments] = useState(false);
  const [subscriptionPaymentSearch, setSubscriptionPaymentSearch] = useState("");
  const [subscriptionPaymentMethodFilter, setSubscriptionPaymentMethodFilter] = useState<"all" | "manual" | "momo" | "bank" | "cash" | "paystack">("all");

const [uploadingProductImage, setUploadingProductImage] = useState(false);
const [error, setError] = useState("");

  async function apiFetch(path: string, options: RequestInit = {}) {
    let res: Response;

    try {
      res = await fetch(`${API_URL}${path}`, {
        ...options,
        headers: {
          ...(
            options.body instanceof FormData
              ? {}
              : {
                  "Content-Type":
                    "application/json",
                }
          ),
          Authorization: `Bearer ${token}`,
          ...(options.headers || {}),
        },
      });
    } catch {
      throw new Error(
        "Could not reach StorePlug. Check your internet connection and try again.",
      );
    }

    if (res.status === 401) {
      localStorage.removeItem("token");
      setToken("");
      throw new Error("Your session has expired. Please log in again.");
    }

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      throw new Error(getApiErrorMessage(data, "Request failed"));
    }

    return data;
  }

  async function login(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (loginLoading) {
      return;
    }

    const formData = new FormData(e.currentTarget);
    const loginEmail = String(formData.get("email") || email || "").trim();
    const loginPassword = String(formData.get("password") || password || "");

    setError("");
    setMessage("");
    setLoginDebug("Login clicked.");

    if (!loginEmail) {
      setError("Enter your email address.");
      setLoginDebug("Stopped: email is empty.");
      return;
    }

    if (!/^\S+@\S+\.\S+$/.test(loginEmail)) {
      setError("Enter a valid email address.");
      setLoginDebug("Stopped: invalid email format.");
      return;
    }

    if (!loginPassword) {
      setError("Enter your password.");
      setLoginDebug("Stopped: password is empty.");
      return;
    }

    setLoginLoading(true);

    const url = `${API_URL}/auth/login`;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 12000);
    const startedAt = Date.now();

    try {
      setLoginDebug(`Host: ${window.location.hostname}\nTrying: ${url}`);
      setMessage("Signing in...");

      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        cache: "no-store",
        body: JSON.stringify({
          email: loginEmail,
          password: loginPassword,
        }),
        signal: controller.signal,
      });

      const elapsed = Date.now() - startedAt;
      setLoginDebug(`Response: HTTP ${res.status} in ${elapsed}ms`);

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        if ([400, 401, 403].includes(res.status)) {
          throw new Error("Invalid email or password.");
        }

        throw new Error(getApiErrorMessage(data, "Login failed. Please try again."));
      }

      if (!data?.access_token) {
        throw new Error("Login response did not include an access token.");
      }

      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      setActiveTab(
        getInitialDashboardTab(data.access_token),
      );
      setEmail(loginEmail);
      setPassword("");
      setMessage("");
      setLoginDebug("Login successful. Token saved.");
    } catch (err) {
      const elapsed = Date.now() - startedAt;

      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Login request timed out.");
        setLoginDebug(`Timeout after ${elapsed}ms while trying: ${url}`);
      } else {
        const rawMessage = err instanceof Error ? err.message : "Something went wrong";
        const friendlyMessage =
          rawMessage.toLowerCase().includes("load failed") ||
          rawMessage.toLowerCase().includes("failed to fetch") ||
          rawMessage.toLowerCase().includes("network")
            ? "Could not reach the server. Check your connection and try again."
            : rawMessage;

        setError(friendlyMessage);
        setLoginDebug(
          err instanceof Error
            ? `Failed after ${elapsed}ms: ${err.message}\nURL: ${url}`
            : `Failed after ${elapsed}ms\nURL: ${url}`
        );
      }
    } finally {
      window.clearTimeout(timeoutId);
      setLoginLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("storeplug.activeTab");
    clearStoredProductDrafts();
    setActiveTab("orders");

    if (typeof window !== "undefined") {
      window.history.replaceState(
        null,
        "",
        "/#orders",
      );
    }

    setToken("");
    setStores([]);
    setSelectedStore(null);
    setOrders([]);
    setProducts([]);
    setProductForm(emptyProductForm);
    setEditingProductId("");
    setIsProductFormOpen(false);
    setStoreForm(emptyStoreForm);
  }

  async function loadSubscriptionUsage(storeId: string) {
    setLoadingSubscriptionUsage(true);

    try {
      const data = await apiFetch(`/stores/${storeId}/subscription-usage`);
      setSubscriptionUsage(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load subscription usage.");
    } finally {
      setLoadingSubscriptionUsage(false);
    }
  }

  function selectStore(
    store: Store | null,
  ) {
    setSelectedStore(store);

    if (!store) {
      setProductForm(emptyProductForm);
      setEditingProductId("");
      setIsProductFormOpen(false);
      return;
    }

    const storedDraft =
      readStoredProductDraft(store.id);

    if (!storedDraft) {
      setProductForm(emptyProductForm);
      setEditingProductId("");
      setIsProductFormOpen(false);
      return;
    }

    setProductForm(storedDraft.form);
    setEditingProductId(
      storedDraft.editingProductId,
    );
    setIsProductFormOpen(
      storedDraft.isOpen,
    );
  }


  async function loadStores() {
    const data = await apiFetch("/stores/");
    setStores(data);

    if (data.length > 0) {
      const current = selectedStore
        ? data.find((store: Store) => store.id === selectedStore.id)
        : null;

      selectStore(current || data[0]);
    }
  }

  async function loadOrders(storeId: string) {
    const data = await apiFetch(`/stores/${storeId}/orders/`);
    setOrders(data);
  }

  async function loadProducts(storeId: string) {
    const data = await apiFetch(`/stores/${storeId}/products`);
    setProducts(data);
  }


  async function confirmManualPayment(orderId: string) {
    const ok = window.confirm(
      "Only confirm this if you have truly received payment manually through cash, MoMo, bank transfer, or pay-on-delivery. This will mark the order as paid and deduct inventory."
    );

    if (!ok) return;

    await updateOrderStatus(orderId, "paid");
  }
  async function updateOrderStatus(orderId: string, status: string) {
    if (!selectedStore) return;

    setError("");
    setMessage("");
try {
      await apiFetch(`/stores/${selectedStore.id}/orders/${orderId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });

      setMessage("Order status updated.");
      await loadOrders(selectedStore.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update order");
    }
  }

  function startEditingProduct(product: Product) {
    setEditingProductId(product.id);
    setIsProductFormOpen(true);
    setProductForm({
      name: product.name,
      slug: product.slug,
      description: product.description || "",
      image_url: product.image_url || "",
      product_type: product.product_type,
      price: String(product.price),
      stock_quantity:
        product.stock_quantity === null || product.stock_quantity === undefined
          ? ""
          : String(product.stock_quantity),
      is_active: product.is_active,
      is_featured: product.is_featured,
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelProductEdit() {
    if (selectedStore) {
      removeStoredProductDraft(
        selectedStore.id,
      );
    }

    setEditingProductId("");
    setProductForm(emptyProductForm);
    setIsProductFormOpen(false);
  }


  async function uploadProductImage(file: File) {
    if (!selectedStore) {
      setError("Please select a store first.");
      return;
    }

    if (loadingSubscriptionUsage) {
      setError("Please wait while your plan permissions load.");
      return;
    }

    if (subscriptionUsage?.can_upload_images === false) {
      setError("Your current plan does not allow image uploads. Upgrade your plan to upload images.");
      return;
    }

    const validationError =
      getImageUploadValidationError(
        file,
      );

    if (validationError) {
      setError(validationError);
      return;
    }

    setError("");
    setMessage("");
    setUploadingProductImage(true);

    try {
      const formData = new FormData();

      formData.append(
        "file",
        file,
        file.name,
      );

      const data = await apiFetch(
        `/stores/${selectedStore.id}/uploads/product-image`,
        {
          method: "POST",
          body: formData,
        },
      );

      setProductForm((prev) => ({
        ...prev,
        image_url: data.image_url,
      }));

      setMessage(
        "Image uploaded successfully.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Image upload failed",
      );
    } finally {
      setUploadingProductImage(false);
    }
  }

  function isProductSubmitDisabled() {
    return (
      loadingSubscriptionUsage ||
      isProductLimitReachedForCreate()
    );
  }

  function getProductSubmitLabel() {
    if (loadingSubscriptionUsage) {
      return "Checking plan...";
    }

    if (isProductLimitReachedForCreate()) {
      return "Limit reached";
    }

    return editingProductId ? "Save changes" : "Add product";
  }
  function isProductLimitReachedForCreate() {
    return (
      !editingProductId &&
      productForm.is_active &&
      !!subscriptionUsage &&
      !subscriptionUsage.is_unlimited &&
      (subscriptionUsage.remaining_products ?? 0) <= 0
    );
  }

  function getProductLimitReachedMessage() {
    const productLimit = subscriptionUsage?.product_limit ?? 0;

    return `Your current plan allows ${productLimit} active product${
      productLimit === 1 ? "" : "s"
    }. Upgrade your plan to add more.`;
  }
  async function saveProduct(e: React.FormEvent) {
    e.preventDefault();

    if (!selectedStore) return;

    setError("");
    setMessage("");

    if (loadingSubscriptionUsage) {
      setError("Please wait while your product limit loads.");
      return;
    }

    if (isProductLimitReachedForCreate()) {
      setError(`Product limit reached. ${getProductLimitReachedMessage()}`);
      return;
    }

    const payload = {
      name: productForm.name,
      slug: productForm.slug || makeSlug(productForm.name),
      description: productForm.description || null,
      image_url: toPortableDashboardMediaReference(
        productForm.image_url,
      ) || null,
      product_type: productForm.product_type || "physical",
      price: productForm.price,
      stock_quantity:
        productForm.stock_quantity === ""
          ? null
          : Number(productForm.stock_quantity),
      is_active: productForm.is_active,
      is_featured: productForm.is_featured,
    };

    try {
      if (editingProductId) {
        await apiFetch(`/stores/${selectedStore.id}/products/${editingProductId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });

        setMessage("Product updated.");
      } else {
        await apiFetch(`/stores/${selectedStore.id}/products`, {
          method: "POST",
          body: JSON.stringify(payload),
        });

        setMessage("Product created.");
      }

      removeStoredProductDraft(
        selectedStore.id,
      );
      setProductForm(emptyProductForm);
      setEditingProductId("");
      setIsProductFormOpen(false);
      await loadProducts(selectedStore.id);
      await loadSubscriptionUsage(selectedStore.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save product");
    }
  }

  async function toggleProductActive(product: Product) {
    if (!selectedStore) return;

    setError("");
    setMessage("");
    if (
      !product.is_active &&
      !!subscriptionUsage &&
      !subscriptionUsage.is_unlimited &&
      (subscriptionUsage.remaining_products ?? 0) <= 0
    ) {
      setError(`You have reached your active product limit. ${getProductLimitReachedMessage()}`);
      return;
    }
try {
      await apiFetch(`/stores/${selectedStore.id}/products/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !product.is_active }),
      });

      setMessage(product.is_active ? "Product deactivated." : "Product activated.");
      await loadProducts(selectedStore.id);
      await loadSubscriptionUsage(selectedStore.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update product");
    }
  }

  async function deleteProduct(product: Product) {
    if (!selectedStore) return;

    const confirmed = window.confirm(
      `Deactivate ${product.name}? It will disappear from the public store.`
    );

    if (!confirmed) return;

    setError("");
    setMessage("");
try {
      await apiFetch(`/stores/${selectedStore.id}/products/${product.id}`, {
        method: "DELETE",
      });

      setMessage("Product deactivated.");
      await loadProducts(selectedStore.id);
      await loadSubscriptionUsage(selectedStore.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not deactivate product");
    }
  }


  async function uploadStoreImage(
    file: File,
    imageType: "logo" | "banner",
  ) {
    if (!selectedStore) {
      setError("Please select a store first.");
      return;
    }

    if (loadingSubscriptionUsage) {
      setError("Please wait while your plan permissions load.");
      return;
    }

    if (subscriptionUsage?.can_upload_images === false) {
      setError("Your current plan does not allow image uploads. Upgrade your plan to upload images.");
      return;
    }

    const validationError =
      getImageUploadValidationError(
        file,
      );

    if (validationError) {
      setError(validationError);
      return;
    }

    setError("");
    setMessage("");

    try {
      const formData = new FormData();

      formData.append(
        "file",
        file,
        file.name,
      );

      formData.append(
        "image_type",
        imageType,
      );

      const data = await apiFetch(
        `/stores/${selectedStore.id}/uploads/store-image`,
        {
          method: "POST",
          body: formData,
        },
      );

      setStoreForm((prev) => ({
        ...prev,
        [
          imageType === "logo"
            ? "logo_url"
            : "banner_url"
        ]: data.image_url,
      }));

      setMessage(
        `${
          imageType === "logo"
            ? "Logo"
            : "Banner"
        } uploaded successfully.`,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Image upload failed",
      );
    }
  }


  function updatePlanDraft(
    planName: string,
    key: keyof SubscriptionPlanDraft,
    value: string | boolean
  ) {
    setPlanDrafts((prev) => ({
      ...prev,
      [planName]: {
        ...prev[planName],
        [key]: value,
      },
    }));
  }

  async function loadSubscriptionPlans() {
    if (!isPlatformAdmin) {
      return;
    }

    setLoadingSubscriptionPlans(true);
    setError("");

    try {
      const data = await apiFetch("/admin/subscription-plans");
      setSubscriptionPlans(data);

      const drafts: Record<string, SubscriptionPlanDraft> = {};

      data.forEach((plan: AdminSubscriptionPlanItem) => {
        drafts[plan.name] = {
          display_name: plan.display_name,
          monthly_fee: String(plan.monthly_fee),
          is_quote_only: plan.is_quote_only,
          product_limit:
            plan.product_limit === null || plan.product_limit === undefined
              ? ""
              : String(plan.product_limit),
          can_upload_images: plan.can_upload_images,
          can_use_custom_domain: plan.can_use_custom_domain,
          can_receive_online_payments: plan.can_receive_online_payments,
          is_active: plan.is_active,
        };
      });

      setPlanDrafts(drafts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load subscription plans.");
    } finally {
      setLoadingSubscriptionPlans(false);
    }
  }

  async function saveSubscriptionPlan(planName: string) {
    const draft = planDrafts[planName];

    if (!draft) {
      setError("Plan draft not found.");
      return;
    }

    const monthlyFee = Number(draft.monthly_fee);
    const productLimitText = draft.product_limit.trim();
    const productLimit =
      productLimitText === "" ? null : Number(productLimitText);

    if (!Number.isFinite(monthlyFee) || monthlyFee < 0) {
      setError("Monthly fee must be a valid number.");
      return;
    }

    if (
      productLimit !== null &&
      (!Number.isInteger(productLimit) || productLimit < 0)
    ) {
      setError("Product limit must be a whole number, or blank for unlimited.");
      return;
    }

    setError("");
    setMessage("");
try {
      const updatedPlan = await apiFetch(`/admin/subscription-plans/${planName}`, {
        method: "PATCH",
        body: JSON.stringify({
          display_name: draft.display_name,
          monthly_fee: monthlyFee,
          is_quote_only: draft.is_quote_only,
          product_limit: productLimit,
          can_upload_images: draft.can_upload_images,
          can_use_custom_domain: draft.can_use_custom_domain,
          can_receive_online_payments: draft.can_receive_online_payments,
          is_active: draft.is_active,
        }),
      });

      setSubscriptionPlans((prev) =>
        prev.map((plan) => (plan.name === updatedPlan.name ? updatedPlan : plan))
      );

      await loadAdminSubscriptionSummary();

      if (selectedStore?.id) {
        await loadSubscriptionUsage(selectedStore.id);
      }

      setMessage(`${updatedPlan.display_name} plan updated.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update subscription plan.");
    }
  }
  async function loadAdminSubscriptionSummary() {
    if (!isPlatformAdmin) {
      return;
    }

    setLoadingAdminSubscriptionSummary(true);
    setError("");

    try {
      const data = await apiFetch("/admin/subscription-summary");
      setAdminSubscriptionSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load subscription summary.");
    } finally {
      setLoadingAdminSubscriptionSummary(false);
    }
  }
  async function loadAdminSellers(
    append = false,
  ) {
    if (!isPlatformAdmin) {
      return;
    }

    if (
      append &&
      !adminSellerNextCursor
    ) {
      return;
    }

    if (append) {
      setLoadingMoreAdminSellers(true);
    } else {
      setLoadingAdminSellers(true);
    }

    setAdminSellerListError("");

    try {
      const query = new URLSearchParams({
        limit: "25",
      });

      if (
        append &&
        adminSellerNextCursor
      ) {
        query.set(
          "cursor",
          adminSellerNextCursor,
        );
      }

      const data = (
        await apiFetch(
          `/admin/sellers?${query.toString()}`,
        )
      ) as AdminSellerListResponse;

      setAdminSellers((current) => {
        if (!append) {
          return data.items;
        }

        const existingIds = new Set(
          current.map(
            (seller) => seller.seller_id,
          ),
        );

        return [
          ...current,
          ...data.items.filter(
            (seller) =>
              !existingIds.has(
                seller.seller_id,
              ),
          ),
        ];
      });

      setAdminSellerNextCursor(
        data.next_cursor,
      );

      setAdminSellersHasMore(
        data.has_more,
      );
    } catch (loadError) {
      setAdminSellerListError(
        loadError instanceof Error
          ? loadError.message
          : "Could not load seller accounts.",
      );
    } finally {
      if (append) {
        setLoadingMoreAdminSellers(false);
      } else {
        setLoadingAdminSellers(false);
      }
    }
  }

  function exportSubscriptionPaymentsCsv() {
    if (adminSubscriptionPayments.length === 0) {
      setError("No subscription payments to export. Refresh payments first.");
      return;
    }

    const headers = [
      "Store Name",
      "Store Slug",
      "Plan",
      "Amount",
      "Currency",
      "Payment Method",
      "Payment Reference",
      "Covered Days",
      "Approved By",
      "Paid At",
      "Note",
    ];

    const paymentsToExport =
      filteredSubscriptionPayments.length > 0
        ? filteredSubscriptionPayments
        : adminSubscriptionPayments;

    const rows = paymentsToExport.map((payment) => [
      payment.store_name,
      payment.store_slug,
      payment.plan_name,
      String(payment.amount),
      payment.currency,
      payment.payment_method,
      payment.payment_reference || "",
      String(payment.covered_days),
      payment.approved_by_email || "",
      payment.paid_at,
      payment.note || "",
    ]);

    const escapeCsv = (value: string) =>
      `"${value.replace(/"/g, '""')}"`;

    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCsv).join(","))
      .join("\n");

    const blob = new Blob([csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `subscription-payments-${new Date()
      .toISOString()
      .slice(0, 10)}.csv`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
    setMessage("Subscription payments exported.");
  }
  async function loadAdminSubscriptionPayments() {
    if (!isPlatformAdmin) {
      return;
    }

    setLoadingAdminSubscriptionPayments(true);
    setError("");

    try {
      const data = await apiFetch("/admin/subscription-payments");
      setAdminSubscriptionPayments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load subscription payments.");
    } finally {
      setLoadingAdminSubscriptionPayments(false);
    }
  }
  async function saveStoreSettings(e: React.FormEvent) {
    e.preventDefault();

    if (!selectedStore) return;

    setError("");
    setMessage("");

    if (loadingSubscriptionUsage) {
      setError("Please wait while your product limit loads.");
      return;
    }

    if (isProductLimitReachedForCreate()) {
      setError(`Product limit reached. ${getProductLimitReachedMessage()}`);
      return;
    }

    let whatsappNumber: string | null;

    try {
      whatsappNumber =
        normalizeGhanaWhatsAppNumber(
          storeForm.whatsapp_number,
        );
    } catch (validationError) {
      setError(
        validationError instanceof Error
          ? validationError.message
          : "Enter a valid Ghana WhatsApp number.",
      );
      return;
    }

    const payload = {
      name: storeForm.name.trim(),
      slug: makeSlug(storeForm.slug),
      bio: storeForm.bio.trim() || null,
      whatsapp_number: whatsappNumber,
      logo_url: toPortableDashboardMediaReference(
        storeForm.logo_url,
      ) || null,
      banner_url: toPortableDashboardMediaReference(
        storeForm.banner_url,
      ) || null,
      category: storeForm.category.trim() || null,
    };

    try {
      const updatedStore = await apiFetch(`/stores/${selectedStore.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      setSelectedStore(updatedStore);
      setStoreForm((current) => ({
        ...current,
        whatsapp_number:
          updatedStore.whatsapp_number || "",
      }));
      setStores((prev) =>
        prev.map((store) => (store.id === updatedStore.id ? updatedStore : store))
      );

      setMessage("Store settings updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update store settings");
    }
  }


  const runSubscriptionUsageAutoLoad =
    useEffectEvent(
      (storeId: string | null) => {
        if (!storeId) {
          setSubscriptionUsage(null);
          return;
        }

        void loadSubscriptionUsage(
          storeId,
        ).catch((loadError) =>
          setError(
            loadError instanceof Error
              ? loadError.message
              : (
                  "Could not load "
                  + "subscription usage"
                ),
          ),
        );
      },
    );

  const runStoreListAutoLoad =
    useEffectEvent(() => {
      void loadStores().catch(
        (loadError) =>
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Could not load stores",
          ),
      );
    });

  const runSelectedStoreAutoLoad =
    useEffectEvent(() => {
      if (!selectedStore) {
        return;
      }

      setStoreForm({
        name: selectedStore.name || "",
        slug: selectedStore.slug || "",
        bio: selectedStore.bio || "",
        whatsapp_number:
          selectedStore.whatsapp_number || "",
        logo_url:
          selectedStore.logo_url || "",
        banner_url:
          selectedStore.banner_url || "",
        category:
          selectedStore.category || "",
      });

      void loadOrders(
        selectedStore.id,
      ).catch((loadError) =>
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Could not load orders",
        ),
      );

      void loadProducts(
        selectedStore.id,
      ).catch((loadError) =>
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Could not load products",
        ),
      );
    });

  const runAdminTabAutoLoad =
    useEffectEvent(
      (tab: DashboardTab) => {
        if (tab === "adminSummary") {
          void loadAdminSubscriptionSummary()
            .catch((loadError) =>
              setError(
                loadError instanceof Error
                  ? loadError.message
                  : (
                      "Could not load "
                      + "subscription summary"
                    ),
              ),
            );

          return;
        }

        if (tab === "adminSellers") {
          void loadAdminSellers().catch(
            (loadError) =>
              setAdminSellerListError(
                loadError instanceof Error
                  ? loadError.message
                  : (
                      "Could not load "
                      + "seller accounts"
                    ),
              ),
          );

          void loadSubscriptionPlans()
            .catch((loadError) =>
              setError(
                loadError instanceof Error
                  ? loadError.message
                  : (
                      "Could not load "
                      + "subscription plans"
                    ),
              ),
            );

          return;
        }

        if (tab === "adminPlans") {
          void loadSubscriptionPlans()
            .catch((loadError) =>
              setError(
                loadError instanceof Error
                  ? loadError.message
                  : (
                      "Could not load "
                      + "subscription plans"
                    ),
              ),
            );

          return;
        }

        if (tab === "adminPayments") {
          void loadAdminSubscriptionPayments()
            .catch((loadError) =>
              setError(
                loadError instanceof Error
                  ? loadError.message
                  : (
                      "Could not load "
                      + "subscription payments"
                    ),
              ),
            );
        }
      },
    );

  useEffect(() => {
    const timeoutId = window.setTimeout(
      () => {
        runSubscriptionUsageAutoLoad(
          selectedStore?.id ?? null,
        );
      },
      0,
    );

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [selectedStore?.id]);

  useEffect(() => {
    if (!token) {
      return;
    }

    const timeoutId = window.setTimeout(
      () => {
        runStoreListAutoLoad();
      },
      0,
    );

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [token]);

  useEffect(() => {
    const timeoutId = window.setTimeout(
      () => {
        runSelectedStoreAutoLoad();
      },
      0,
    );

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [selectedStore?.id]);

  useEffect(() => {
    if (!token || !isPlatformAdmin) {
      return;
    }

    const timeoutId = window.setTimeout(
      () => {
        runAdminTabAutoLoad(activeTab);
      },
      0,
    );

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [
    token,
    isPlatformAdmin,
    activeTab,
  ]);

  const filteredSubscriptionPayments = adminSubscriptionPayments.filter((payment) => {
    const searchText = subscriptionPaymentSearch.trim().toLowerCase();

    const matchesSearch =
      !searchText ||
      payment.store_name.toLowerCase().includes(searchText) ||
      payment.store_slug.toLowerCase().includes(searchText) ||
      payment.payment_method.toLowerCase().includes(searchText) ||
      (payment.payment_reference || "").toLowerCase().includes(searchText) ||
      (payment.approved_by_email || "").toLowerCase().includes(searchText) ||
      (payment.note || "").toLowerCase().includes(searchText);

    if (!matchesSearch) {
      return false;
    }

    if (subscriptionPaymentMethodFilter === "all") {
      return true;
    }

    return payment.payment_method === subscriptionPaymentMethodFilter;
  });
  const isAdminWorkspace =
    isPlatformAdmin &&
    platformAdminTabs.includes(activeTab);

  if (!token) {
    return (
      <LoginPage
        email={email}
        setEmail={setEmail}
        password={password}
        setPassword={setPassword}
        showLoginPassword={showLoginPassword}
        setShowLoginPassword={setShowLoginPassword}
        error={error}
        loginLoading={loginLoading}
        login={login}
      />
    );
  }

  return (
    <DashboardShell
      isSidebarOpen={isSidebarOpen}
      selectedStoreName={
        activeTab === "security"
          ? "Account security"
          : isAdminWorkspace
            ? "Platform Admin"
            : selectedStore?.name ||
              "Merchant dashboard"
      }
      onOpenSidebar={() => setIsSidebarOpen(true)}
      sidebar={
        <Sidebar
          isSidebarOpen={isSidebarOpen}
          selectedStore={selectedStore}
          stores={stores}
          activeTab={activeTab}
          isPlatformAdmin={isPlatformAdmin}
          publicStoreUrl={PUBLIC_STORE_URL}
          onClose={() => setIsSidebarOpen(false)}
          onSelectStore={(storeId) => {
            const store = stores.find((item) => item.id === storeId);
            selectStore(store || null);
          }}
          onOpenTab={(tab) => {
            if (
              !isPlatformAdmin &&
              platformAdminTabs.includes(tab)
            ) {
              setActiveTab("orders");
              setIsSidebarOpen(false);
              return;
            }

            setActiveTab(tab);
            setIsSidebarOpen(false);
          }}
          onLoadAdminSubscriptionSummary={loadAdminSubscriptionSummary}
          onLoadAdminSubscriptionPayments={loadAdminSubscriptionPayments}
          onLoadSubscriptionPlans={loadSubscriptionPlans}
          onLogout={logout}
        />
      }
    >
        <div className={`topbar topbar-${activeTab}`}>
          <div>
            <h1>
              {activeTab === "adminSummary"
                ? "Platform overview"
                : activeTab === "adminSellers"
                  ? "Sellers"
                  : activeTab === "adminPlans"
                    ? "Plan settings"
                    : activeTab === "adminPayments"
                      ? "Payments"
                      : activeTab === "security"
                        ? "Security"
                        : selectedStore?.name || "Dashboard"}
            </h1>
            <p className="muted">
              {activeTab === "orders" && "Track customer orders and payment status."}
              {activeTab === "products" && "Add, edit, and manage your products."}
              {activeTab === "settings" && "Update your public store profile."}
              {activeTab === "security" && "Change your password and protect active sessions."}
              {activeTab === "adminSummary" && "Revenue, subscriptions, and platform health."}
              {activeTab === "adminSellers" && "Manage seller accounts, onboarding, stores, and access."}
              {activeTab === "adminPlans" && "Control plan pricing, product limits, and feature access."}
              {activeTab === "adminPayments" && "Review subscription payment records and exports."}
            </p>
          </div>

          {activeTab !== "security" && (
            <button
              onClick={() => {
                if (selectedStore) {
                  loadStores();
                  loadOrders(selectedStore.id);
                  loadProducts(selectedStore.id);
                }

                if (
                  isPlatformAdmin &&
                  activeTab === "adminSellers"
                ) {
                  loadAdminSellers();
                  loadSubscriptionPlans();
                } else if (
                  isPlatformAdmin &&
                  ["adminSummary", "adminPlans", "adminPayments"].includes(activeTab)
                ) {
                  loadSubscriptionPlans();
                  loadAdminSubscriptionSummary();
                  loadAdminSubscriptionPayments();
                }
              }}
            >
              {isPlatformAdmin && ["adminSummary", "adminSellers", "adminPlans", "adminPayments"].includes(activeTab) ? "Refresh platform data" : "Refresh"}
            </button>
          )}
        </div>


        {error && <div className="error-box">{error}</div>}
        {message && (
          <div
            className={
              activeTab === "products"
                ? "success-box success-box-products"
                : "success-box"
            }
            role="status"
            aria-live="polite"
          >
            {message}
          </div>
        )}

        {/* SELLER SUBSCRIPTION WARNING BANNER */}
        {!isAdminWorkspace &&
          activeTab !== "security" &&
          selectedStore &&
          shouldShowSubscriptionBanner(selectedStore) && (
          <div
            className={`subscription-warning-banner ${getSubscriptionTimeClass(
              selectedStore.subscription_status,
              selectedStore.trial_ends_at,
              selectedStore.subscription_ends_at,
              selectedStore.is_suspended,
            )}`}
          >
            <div>
              <h3>{getSubscriptionBannerTitle(selectedStore)}</h3>
              <p>{getSubscriptionBannerMessage(selectedStore)}</p>
            </div>

            <div className="subscription-warning-actions">
              <strong>
                {getSubscriptionTimeLabel(
                  selectedStore.subscription_status,
                  selectedStore.trial_ends_at,
                  selectedStore.subscription_ends_at,
                  selectedStore.is_suspended,
                )}
              </strong>

              <a
                className="renew-subscription-btn"
                href={getSubscriptionRenewalUrl(selectedStore)}
                target="_blank"
                rel="noreferrer"
              >
                Renew subscription
              </a>
            </div>
          </div>
        )}

        {activeTab === "orders" && (
          <OrdersPage
            orders={orders}
            getAllowedOrderStatusActions={
              getAllowedOrderStatusActions
            }
            formatOrderStatusActionLabel={
              formatOrderStatusActionLabel
            }
            confirmManualPayment={
              confirmManualPayment
            }
            updateOrderStatus={
              updateOrderStatus
            }
          />
        )}

        {activeTab === "products" && (
          <ProductsPage
            products={products}
            productForm={productForm}
            setProductForm={setProductForm}
            subscriptionUsage={subscriptionUsage}
            loadingSubscriptionUsage={loadingSubscriptionUsage}
            uploadingProductImage={uploadingProductImage}
            editingProductId={editingProductId}
            isProductFormOpen={isProductFormOpen}
            setIsProductFormOpen={setIsProductFormOpen}
            saveProduct={saveProduct}
            makeSlug={makeSlug}
            uploadProductImage={uploadProductImage}
            isProductLimitReachedForCreate={isProductLimitReachedForCreate}
            getProductLimitReachedMessage={getProductLimitReachedMessage}
            isProductSubmitDisabled={isProductSubmitDisabled}
            getProductSubmitLabel={getProductSubmitLabel}
            cancelProductEdit={cancelProductEdit}
            startEditingProduct={startEditingProduct}
            toggleProductActive={toggleProductActive}
            deleteProduct={deleteProduct}
          />
        )}

        {activeTab === "settings" && (
          <StoreProfilePage
            selectedStore={selectedStore}
            storeForm={storeForm}
            setStoreForm={setStoreForm}
            subscriptionUsage={subscriptionUsage}
            loadingSubscriptionUsage={loadingSubscriptionUsage}
            saveStoreSettings={saveStoreSettings}
            makeSlug={makeSlug}
            uploadStoreImage={uploadStoreImage}
            formatPlanName={formatPlanName}
            getComputedSubscriptionStatus={getComputedSubscriptionStatus}
            formatMonthlyFee={formatMonthlyFee}
            formatSubscriptionDate={formatSubscriptionDate}
            formatProductUsageLabel={formatProductUsageLabel}
            getProductUsageClass={getProductUsageClass}
            getProductUsagePercent={getProductUsagePercent}
            formatRemainingProducts={formatRemainingProducts}
          />
        )}

        {activeTab === "security" && (
          <SecurityPage
            changePassword={(payload) =>
              apiFetch(
                "/auth/change-password",
                {
                  method: "POST",
                  body: JSON.stringify(payload),
                },
              )
            }
            onPasswordChanged={logout}
          />
        )}

        {isAdminWorkspace && (
          <section
            className={`admin-workspace admin-page-${activeTab}`}
            aria-label="Platform Admin workspace"
          >
            {activeTab === "adminSellers" && (
              <AdminSellersPage
                adminSellers={adminSellers}
                loadingAdminSellers={
                  loadingAdminSellers
                }
                loadingMoreAdminSellers={
                  loadingMoreAdminSellers
                }
                adminSellerListError={
                  adminSellerListError
                }
                adminSellersHasMore={
                  adminSellersHasMore
                }
                loadAdminSellers={
                  loadAdminSellers
                }
                apiFetch={apiFetch}
                onSellerCreated={() =>
                  loadAdminSellers(false)
                }
                subscriptionPlans={subscriptionPlans}
              />
            )}

            {activeTab === "adminPlans" && (
              <AdminPlansPage
                subscriptionPlans={subscriptionPlans}
                planDrafts={planDrafts}
                loadingSubscriptionPlans={
                  loadingSubscriptionPlans
                }
                loadSubscriptionPlans={
                  loadSubscriptionPlans
                }
                updatePlanDraft={(
                  planName,
                  field,
                  value,
                ) =>
                  updatePlanDraft(
                    planName,
                    field as keyof SubscriptionPlanDraft,
                    value,
                  )
                }
                saveSubscriptionPlan={
                  saveSubscriptionPlan
                }
              />
            )}

            {activeTab === "adminSummary" && (
              <AdminSummaryPage
                adminSubscriptionSummary={
                  adminSubscriptionSummary
                }
                loadingAdminSubscriptionSummary={
                  loadingAdminSubscriptionSummary
                }
                loadAdminSubscriptionSummary={
                  loadAdminSubscriptionSummary
                }
                formatMonthlyFee={
                  formatMonthlyFee
                }
              />
            )}

            {activeTab === "adminPayments" && (
              <AdminPaymentsPage
                adminSubscriptionPayments={
                  adminSubscriptionPayments
                }
                filteredSubscriptionPayments={
                  filteredSubscriptionPayments
                }
                subscriptionPaymentSearch={
                  subscriptionPaymentSearch
                }
                setSubscriptionPaymentSearch={
                  setSubscriptionPaymentSearch
                }
                subscriptionPaymentMethodFilter={
                  subscriptionPaymentMethodFilter
                }
                setSubscriptionPaymentMethodFilter={
                  setSubscriptionPaymentMethodFilter
                }
                loadAdminSubscriptionPayments={
                  loadAdminSubscriptionPayments
                }
                loadingAdminSubscriptionPayments={
                  loadingAdminSubscriptionPayments
                }
                exportSubscriptionPaymentsCsv={
                  exportSubscriptionPaymentsCsv
                }
                formatPlanName={formatPlanName}
                formatSubscriptionDate={
                  formatSubscriptionDate
                }
              />
            )}
          </section>
        )}
    </DashboardShell>
  );
}
