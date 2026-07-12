import { useEffect, useState } from "react";
import { LoginPage } from "./pages/LoginPage";
import { OrdersPage } from "./pages/OrdersPage";
import { ProductsPage } from "./pages/ProductsPage";
import { Sidebar } from "./layouts/Sidebar";
import { DashboardShell } from "./layouts/DashboardShell";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";




type AdminStoreListItem = {
  id: string;
  owner_id: string;
  owner_email: string;
  owner_name: string;
  slug: string;
  name: string;
  plan_name: string;
  subscription_status: string;
  monthly_fee: string | number;
  subscription_ends_at?: string | null;
  last_payment_at?: string | null;
  is_active: boolean;
  is_suspended: boolean;
};

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
function getApiErrorMessage(data: any, fallback: string) {
  const detail = data?.detail;

  if (!detail) return fallback;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join(", ");
  }

  return JSON.stringify(detail);
}
const PUBLIC_STORE_URL = import.meta.env.VITE_PUBLIC_STORE_URL || "http://localhost:3000";
const SUPPORT_WHATSAPP_NUMBER = import.meta.env.VITE_SUPPORT_WHATSAPP || "233544193559";


function getComputedSubscriptionStatus(
  status?: string | null,
  subscriptionEndsAt?: string | null,
  isSuspended?: boolean | null
) {
  if (isSuspended || status === "suspended") {
    return "suspended";
  }

  if (status === "active" && subscriptionEndsAt) {
    const expiryTime = new Date(subscriptionEndsAt).getTime();

    if (Number.isFinite(expiryTime) && expiryTime <= Date.now()) {
      return "expired";
    }
  }

  return status || "trial";
}

function getSubscriptionTimeLabel(
  status?: string | null,
  subscriptionEndsAt?: string | null,
  isSuspended?: boolean | null
) {
  const computedStatus = getComputedSubscriptionStatus(
    status,
    subscriptionEndsAt,
    isSuspended
  );

  if (computedStatus === "suspended") {
    return "Suspended";
  }

  if (!subscriptionEndsAt) {
    return "No expiry date";
  }

  const expiryTime = new Date(subscriptionEndsAt).getTime();

  if (!Number.isFinite(expiryTime)) {
    return "Invalid expiry date";
  }

  const diffMs = expiryTime - Date.now();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    return "Expired";
  }

  if (diffDays === 0) {
    return "Expires today";
  }

  if (diffDays === 1) {
    return "1 day left";
  }

  return `${diffDays} days left`;
}

function getSubscriptionTimeClass(
  status?: string | null,
  subscriptionEndsAt?: string | null,
  isSuspended?: boolean | null
) {
  const computedStatus = getComputedSubscriptionStatus(
    status,
    subscriptionEndsAt,
    isSuspended
  );

  if (computedStatus === "suspended" || computedStatus === "expired") {
    return "danger";
  }

  if (!subscriptionEndsAt) {
    return "neutral";
  }

  const expiryTime = new Date(subscriptionEndsAt).getTime();

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
    store.subscription_ends_at,
    store.is_suspended
  );

  if (status === "expired" || status === "suspended") {
    return true;
  }

  const timeClass = getSubscriptionTimeClass(
    store.subscription_status,
    store.subscription_ends_at,
    store.is_suspended
  );

  return timeClass === "warning" || timeClass === "danger";
}

function getSubscriptionBannerTitle(store: Store) {
  const status = getComputedSubscriptionStatus(
    store.subscription_status,
    store.subscription_ends_at,
    store.is_suspended
  );

  if (status === "suspended") {
    return "Store suspended";
  }

  if (status === "expired") {
    return "Subscription expired";
  }

  return "Subscription renewal reminder";
}

function getSubscriptionBannerMessage(store: Store) {
  const status = getComputedSubscriptionStatus(
    store.subscription_status,
    store.subscription_ends_at,
    store.is_suspended
  );

  if (status === "suspended") {
    return "Your public store is temporarily unavailable. Please contact support to reactivate it.";
  }

  if (status === "expired") {
    return "Your public store is not accepting orders right now. Renew your subscription to reactivate selling.";
  }

  return `Your subscription has ${getSubscriptionTimeLabel(
    store.subscription_status,
    store.subscription_ends_at,
    store.is_suspended
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
  | "adminSummary"
  | "adminSellers"
  | "adminPlans"
  | "adminPayments";

const dashboardTabs: DashboardTab[] = [
  "orders",
  "products",
  "settings",
  "adminSummary",
  "adminSellers",
  "adminPlans",
  "adminPayments",
];

function getInitialDashboardTab(): DashboardTab {
  if (typeof window === "undefined") return "orders";

  const hashTab = window.location.hash.replace("#", "") as DashboardTab;
  if (dashboardTabs.includes(hashTab)) return hashTab;

  const savedTab = window.localStorage.getItem("storeplug.activeTab") as DashboardTab | null;
  if (savedTab && dashboardTabs.includes(savedTab)) return savedTab;

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

  const [activeTab, setActiveTab] = useState<DashboardTab>(() => getInitialDashboardTab());
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    if (!token || typeof window === "undefined") return;

    localStorage.setItem("storeplug.activeTab", activeTab);

    const nextHash = `#${activeTab}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${nextHash}`);
    }
  }, [token, activeTab]);
  const [message, setMessage] = useState("");
  
  
  const [adminStores, setAdminStores] = useState<AdminStoreListItem[]>([]);
  const [adminStoreFilter, setAdminStoreFilter] = useState<"all" | "active" | "trial" | "expired" | "suspended" | "expiring">("all");
  const [adminStoreSearch, setAdminStoreSearch] = useState("");
  const [loadingAdminStores, setLoadingAdminStores] = useState(false);
  const [adminPlanDrafts, setAdminPlanDrafts] = useState<Record<string, string>>({});
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
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });

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

    const loginBase =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1" ||
      /^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$/.test(window.location.hostname)
        ? "/api/v1"
        : API_URL;

    const url = `${loginBase}/auth/login`;
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
    setToken("");
    setStores([]);
    setSelectedStore(null);
    setOrders([]);
    setProducts([]);
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
  async function loadStores() {
    const data = await apiFetch("/stores/");
    setStores(data);

    if (data.length > 0) {
      const current = selectedStore
        ? data.find((store: Store) => store.id === selectedStore.id)
        : null;

      setSelectedStore(current || data[0]);
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

    setError("");
    setMessage("");
    setUploadingProductImage(true);

    try {
      const dataBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = () => {
          const result = String(reader.result || "");
          const base64 = result.includes(",") ? result.split(",")[1] : result;
          resolve(base64);
        };

        reader.onerror = () => reject(new Error("Could not read image file."));
        reader.readAsDataURL(file);
      });

      const data = await apiFetch(
        `/stores/${selectedStore.id}/uploads/product-image`,
        {
          method: "POST",
          body: JSON.stringify({
            filename: file.name,
            content_type: file.type,
            data_base64: dataBase64,
          }),
        }
      );

      setProductForm((prev) => ({
        ...prev,
        image_url: data.image_url,
      }));

      setMessage("Image uploaded successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image upload failed");
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
      image_url: productForm.image_url || null,
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


  async function uploadStoreImage(file: File, imageType: "logo" | "banner") {
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

    setError("");
    setMessage("");
try {
      const dataBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = () => {
          const result = String(reader.result || "");
          const base64 = result.includes(",") ? result.split(",")[1] : result;
          resolve(base64);
        };

        reader.onerror = () => reject(new Error("Could not read image file."));
        reader.readAsDataURL(file);
      });

      const data = await apiFetch(
        `/stores/${selectedStore.id}/uploads/store-image`,
        {
          method: "POST",
          body: JSON.stringify({
            filename: file.name,
            content_type: file.type,
            image_type: imageType,
            data_base64: dataBase64,
          }),
        }
      );

      setStoreForm((prev) => ({
        ...prev,
        [imageType === "logo" ? "logo_url" : "banner_url"]: data.image_url,
      }));

      setMessage(`${imageType === "logo" ? "Logo" : "Banner"} uploaded successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image upload failed");
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
      await loadAdminStores();

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
  function exportAdminStoresCsv() {
    if (adminStores.length === 0) {
      setError("No sellers to export. Refresh sellers first.");
      return;
    }

    const storesToExport = filteredAdminStores.length > 0 ? filteredAdminStores : adminStores;

    const headers = [
      "Store Name",
      "Store Slug",
      "Owner Name",
      "Owner Email",
      "Plan",
      "Status",
      "Monthly Fee",
      "Expires At",
      "Time Left",
      "Is Active",
      "Is Suspended",
    ];

    const rows = storesToExport.map((store) => {
      const computedStatus = getComputedSubscriptionStatus(
        store.subscription_status,
        store.subscription_ends_at,
        store.is_suspended
      );

      return [
        store.name,
        store.slug,
        store.owner_name,
        store.owner_email,
        store.plan_name,
        computedStatus,
        String(store.monthly_fee),
        store.subscription_ends_at || "",
        getSubscriptionTimeLabel(
          store.subscription_status,
          store.subscription_ends_at,
          store.is_suspended
        ),
        store.is_active ? "Yes" : "No",
        store.is_suspended ? "Yes" : "No",
      ];
    });

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
    link.download = `seller-stores-${new Date()
      .toISOString()
      .slice(0, 10)}.csv`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
    setMessage("Seller list exported.");
  }
  async function loadAdminStores() {
    if (!isPlatformAdmin) {
      return;
    }

    setLoadingAdminStores(true);
    setError("");

    try {
      const data: AdminStoreListItem[] = await apiFetch("/admin/stores");
      setAdminStores(data);

      setAdminPlanDrafts((prev) => {
        const next = { ...prev };

        data.forEach((store) => {
          next[store.id] = store.plan_name || "starter";
        });

        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load admin stores.");
    } finally {
      setLoadingAdminStores(false);
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
  async function adminChangeStorePlan(store: AdminStoreListItem) {
    const nextPlanName = (adminPlanDrafts[store.id] || store.plan_name || "starter")
      .toLowerCase()
      .trim();

    if (!nextPlanName) {
      setError("Please select a plan.");
      return;
    }

    const selectedPlan = subscriptionPlans.find((plan) => plan.name === nextPlanName);

    if (!selectedPlan) {
      setError("Selected plan not found. Refresh subscription plans and try again.");
      return;
    }

    if (nextPlanName === store.plan_name) {
      setMessage(`${store.name} is already on the ${formatPlanName(store.plan_name)} plan.`);
      return;
    }

    const confirmed = window.confirm(
      `Change ${store.name} from ${formatPlanName(store.plan_name)} to ${selectedPlan.display_name}? Monthly fee will become ${formatMonthlyFee(selectedPlan.monthly_fee)}.`
    );

    if (!confirmed) {
      setAdminPlanDrafts((prev) => ({
        ...prev,
        [store.id]: store.plan_name || "starter",
      }));
      return;
    }

    setError("");
    setMessage("");
try {
      const updatedStore = await apiFetch(`/admin/stores/${store.id}/plan`, {
        method: "PATCH",
        body: JSON.stringify({
          plan_name: nextPlanName,
        }),
      });

      setAdminStores((prev) =>
        prev.map((item) =>
          item.id === store.id
            ? {
                ...item,
                plan_name: updatedStore.plan_name,
                monthly_fee: updatedStore.monthly_fee,
                subscription_status: updatedStore.subscription_status,
                subscription_ends_at: updatedStore.subscription_ends_at,
              }
            : item
        )
      );

      setAdminPlanDrafts((prev) => ({
        ...prev,
        [store.id]: updatedStore.plan_name,
      }));

      setStores((prev) =>
        prev.map((item) =>
          item.id === store.id
            ? {
                ...item,
                plan_name: updatedStore.plan_name,
                monthly_fee: updatedStore.monthly_fee,
                subscription_status: updatedStore.subscription_status,
                subscription_ends_at: updatedStore.subscription_ends_at,
              }
            : item
        )
      );

      setSelectedStore((prev) =>
        prev && prev.id === store.id
          ? {
              ...prev,
              plan_name: updatedStore.plan_name,
              monthly_fee: updatedStore.monthly_fee,
              subscription_status: updatedStore.subscription_status,
              subscription_ends_at: updatedStore.subscription_ends_at,
            }
          : prev
      );

      await loadAdminSubscriptionSummary();

      if (selectedStore?.id === store.id) {
        await loadSubscriptionUsage(store.id);
      }

      setMessage(`${store.name} moved to ${formatPlanName(updatedStore.plan_name)} plan.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change seller plan.");
    }
  }
  async function adminSetStoreSuspension(store: AdminStoreListItem, suspend: boolean) {
    const action = suspend ? "suspend" : "reactivate";

    const confirmed = window.confirm(
      suspend
        ? `Suspend ${store.name}? Customers will not be able to order from this store.`
        : `Reactivate ${store.name}? Customers will be able to view and order again.`
    );

    if (!confirmed) {
      return;
    }

    setError("");
    setMessage("");
try {
      await apiFetch(`/admin/stores/${store.id}/status`, {
        method: "PATCH",
        body: JSON.stringify(
          suspend
            ? {
                subscription_status: "suspended",
                is_suspended: true,
                note: "Suspended from dashboard",
              }
            : {
                subscription_status: "active",
                is_suspended: false,
                is_active: true,
                note: "Reactivated from dashboard",
              }
        ),
      });

      await loadAdminStores();
      await loadAdminSubscriptionSummary();
      await loadStores();

      setMessage(
        suspend
          ? "Seller store suspended."
          : "Seller store reactivated."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not ${action} seller store.`);
    }
  }
  function getSubscriptionPlanByName(planName?: string | null) {
    const cleanPlanName = (planName || "").toLowerCase().trim();

    return subscriptionPlans.find((plan) => plan.name === cleanPlanName);
  }

  function getMonthlyFeeForPlan(
    planName?: string | null,
    fallbackFee?: string | number | null
  ) {
    const plan = getSubscriptionPlanByName(planName);
    const fee = Number(plan?.monthly_fee ?? fallbackFee ?? 0);

    return Number.isFinite(fee) && fee >= 0 ? fee : 0;
  }
  async function extendAdminStoreSubscription(storeId: string) {
    const store = adminStores.find((item) => item.id === storeId);
    const planName = (store?.plan_name || "business").toLowerCase().trim();
    const defaultMonthlyFee = getMonthlyFeeForPlan(planName, store?.monthly_fee ?? 100);

    const amountText = window.prompt("Amount paid in GHS?", String(defaultMonthlyFee));

    if (amountText === null) {
      return;
    }

    const amountPaid = Number(amountText);

    if (!Number.isFinite(amountPaid) || amountPaid < 0) {
      setError("Please enter a valid amount paid.");
      return;
    }

    const method = window.prompt("Payment method? manual, momo, bank, cash, or paystack", "momo");

    if (method === null) {
      return;
    }

    const cleanMethod = method.trim().toLowerCase();

    if (!["manual", "momo", "bank", "cash", "paystack"].includes(cleanMethod)) {
      setError("Payment method must be manual, momo, bank, cash, or paystack.");
      return;
    }

    const reference = window.prompt("Payment reference? Example: MoMo transaction ID", "") || "";
    const note = window.prompt("Payment note?", "Seller subscription payment received") || "";

    const confirmed = window.confirm(
      `Extend this seller subscription by 30 days for GHS ${amountPaid.toFixed(2)} via ${cleanMethod}?`
    );

    if (!confirmed) {
      return;
    }

    setError("");
    setMessage("");
try {
      await apiFetch(`/admin/stores/${storeId}/subscription/extend`, {
        method: "POST",
        body: JSON.stringify({
          plan_name: planName,
          amount_paid: amountPaid,
          extend_days: 30,
          payment_method: cleanMethod,
          payment_reference: reference.trim() || null,
          note: note.trim() || null,
          mark_active: true,
        }),
      });

      await loadAdminStores();
      await loadAdminSubscriptionSummary();
      await loadAdminSubscriptionPayments();
      setMessage("Seller subscription extended and payment recorded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not extend seller subscription.");
    }
  }
  async function extendSelectedStoreSubscription() {
    if (!selectedStore) {
      setError("Please select a store first.");
      return;
    }

    const planName = (selectedStore.plan_name || "business").toLowerCase().trim();
    const defaultMonthlyFee = getMonthlyFeeForPlan(planName, selectedStore.monthly_fee ?? 100);

    const amountText = window.prompt("Amount paid in GHS?", String(defaultMonthlyFee));

    if (amountText === null) {
      return;
    }

    const amountPaid = Number(amountText);

    if (!Number.isFinite(amountPaid) || amountPaid < 0) {
      setError("Please enter a valid amount paid.");
      return;
    }

    const method = window.prompt("Payment method? manual, momo, bank, cash, or paystack", "momo");

    if (method === null) {
      return;
    }

    const cleanMethod = method.trim().toLowerCase();

    if (!["manual", "momo", "bank", "cash", "paystack"].includes(cleanMethod)) {
      setError("Payment method must be manual, momo, bank, cash, or paystack.");
      return;
    }

    const reference = window.prompt("Payment reference? Example: MoMo transaction ID", "") || "";
    const note = window.prompt("Payment note?", "Seller subscription payment received") || "";

    const confirmed = window.confirm(
      `Extend ${selectedStore.name} by 30 days for GHS ${amountPaid.toFixed(2)} via ${cleanMethod}?`
    );

    if (!confirmed) {
      return;
    }

    setError("");
    setMessage("");
try {
      const updatedStore = await apiFetch(
        `/admin/stores/${selectedStore.id}/subscription/extend`,
        {
          method: "POST",
          body: JSON.stringify({
            plan_name: planName,
            amount_paid: amountPaid,
            extend_days: 30,
            payment_method: cleanMethod,
            payment_reference: reference.trim() || null,
            note: note.trim() || null,
            mark_active: true,
          }),
        }
      );

      setSelectedStore(updatedStore);

      setStores((prev) =>
        prev.map((store) => (store.id === updatedStore.id ? updatedStore : store))
      );

      await loadAdminStores();
      await loadAdminSubscriptionSummary();
      await loadAdminSubscriptionPayments();

      setMessage("Subscription extended and payment recorded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not extend subscription.");
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

    const payload = {
      name: storeForm.name,
      slug: makeSlug(storeForm.slug),
      bio: storeForm.bio || null,
      whatsapp_number: storeForm.whatsapp_number || null,
      logo_url: storeForm.logo_url || null,
      banner_url: storeForm.banner_url || null,
      category: storeForm.category || null,
    };

    try {
      const updatedStore = await apiFetch(`/stores/${selectedStore.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      setSelectedStore(updatedStore);
      setStores((prev) =>
        prev.map((store) => (store.id === updatedStore.id ? updatedStore : store))
      );

      setMessage("Store settings updated.");

            {selectedStore && (
              <div className="subscription-summary-card">
                <div>
                  <span>Current plan</span>
                  <strong>{formatPlanName(selectedStore.plan_name)}</strong>
                </div>

                <div>
                  <span>Status</span>
                  <strong className={`subscription-status ${selectedStore.subscription_status || "trial"}`}>
                    {formatPlanName(selectedStore.subscription_status)}
                  </strong>
                </div>

                <div>
                  <span>Monthly fee</span>
                  <strong>{formatMonthlyFee(selectedStore.monthly_fee)}</strong>
                </div>

                <div>
                  <span>Expires</span>
                  <strong>{formatSubscriptionDate(selectedStore.subscription_ends_at)}</strong>
                </div>

                <div>
                  <span>Time left</span>
                  <strong
                    className={`subscription-time ${getSubscriptionTimeClass(
                      selectedStore.subscription_status,
                      selectedStore.subscription_ends_at,
                      selectedStore.is_suspended
                    )}`}
                  >
                    {getSubscriptionTimeLabel(
                      selectedStore.subscription_status,
                      selectedStore.subscription_ends_at,
                      selectedStore.is_suspended
                    )}
                  </strong>
                </div>
              </div>
            )}
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update store settings");
    }
  }


  // AUTO LOAD SUBSCRIPTION USAGE
  useEffect(() => {
    if (!selectedStore?.id) {
      setSubscriptionUsage(null);
      return;
    }

    loadSubscriptionUsage(selectedStore.id).catch((err) =>
      setError(err instanceof Error ? err.message : "Could not load subscription usage")
    );
  }, [selectedStore?.id]);
  useEffect(() => {
    if (token) {
      loadStores().catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load stores")
      );
    }
  }, [token]);

  useEffect(() => {
    if (selectedStore) {
      setStoreForm({
        name: selectedStore.name || "",
        slug: selectedStore.slug || "",
        bio: selectedStore.bio || "",
        whatsapp_number: selectedStore.whatsapp_number || "",
        logo_url: selectedStore.logo_url || "",
        banner_url: selectedStore.banner_url || "",
        category: selectedStore.category || "",
      });

      loadOrders(selectedStore.id).catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load orders")
      );

      loadProducts(selectedStore.id).catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load products")
      );
    }
  }, [selectedStore?.id]);


  useEffect(() => {
    // Auto-load admin subscription dashboard data when admin opens Settings.
    if (token && isPlatformAdmin && ["adminSummary", "adminSellers", "adminPlans", "adminPayments"].includes(activeTab)) {
      loadSubscriptionPlans().catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load subscription plans")
      );

      loadAdminSubscriptionSummary().catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load subscription summary")
      );

      loadAdminStores().catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load admin stores")
      );

      loadAdminSubscriptionPayments().catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load subscription payments")
      );
    }
  }, [token, isPlatformAdmin, activeTab]);
  const filteredAdminStores = adminStores.filter((store) => {
    const computedStatus = getComputedSubscriptionStatus(
      store.subscription_status,
      store.subscription_ends_at,
      store.is_suspended
    );

    const searchText = adminStoreSearch.trim().toLowerCase();

    const matchesSearch =
      !searchText ||
      store.name.toLowerCase().includes(searchText) ||
      store.slug.toLowerCase().includes(searchText) ||
      store.owner_name.toLowerCase().includes(searchText) ||
      store.owner_email.toLowerCase().includes(searchText);

    if (!matchesSearch) {
      return false;
    }

    if (adminStoreFilter === "all") {
      return true;
    }

    if (adminStoreFilter === "expiring") {
      return (
        computedStatus === "active" &&
        getSubscriptionTimeClass(
          store.subscription_status,
          store.subscription_ends_at,
          store.is_suspended
        ) === "warning"
      );
    }

    return computedStatus === adminStoreFilter;
  });
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
      selectedStoreName={selectedStore?.name || "Merchant dashboard"}
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
            setSelectedStore(store || null);
          }}
          onOpenTab={(tab) => {
            setActiveTab(tab);
            setIsSidebarOpen(false);
          }}
          onLoadAdminSubscriptionSummary={loadAdminSubscriptionSummary}
          onLoadAdminStores={loadAdminStores}
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
                ? "Business overview"
                : activeTab === "adminSellers"
                  ? "Seller management"
                  : activeTab === "adminPlans"
                    ? "Plan settings"
                    : activeTab === "adminPayments"
                      ? "Payments"
                      : selectedStore?.name || "Dashboard"}
            </h1>
            <p className="muted">
              {activeTab === "orders" && "Track customer orders and payment status."}
              {activeTab === "products" && "Add, edit, and manage your products."}
              {activeTab === "settings" && "Update your public store profile."}
              {activeTab === "adminSummary" && "Revenue, subscriptions, and platform health."}
              {activeTab === "adminSellers" && "Manage seller stores, renewals, and suspensions."}
              {activeTab === "adminPlans" && "Control plan pricing, product limits, and feature access."}
              {activeTab === "adminPayments" && "Review subscription payment records and exports."}
            </p>
          </div>

          <button
            onClick={() => {
              if (selectedStore) {
                loadStores();
                loadOrders(selectedStore.id);
                loadProducts(selectedStore.id);
              }

              if (isPlatformAdmin && ["adminSummary", "adminSellers", "adminPlans", "adminPayments"].includes(activeTab)) {
                loadSubscriptionPlans();
                loadAdminSubscriptionSummary();
                loadAdminStores();
                loadAdminSubscriptionPayments();
              }
            }}
          >
            {isPlatformAdmin && ["adminSummary", "adminSellers", "adminPlans", "adminPayments"].includes(activeTab) ? "Refresh admin data" : "Refresh"}
          </button>
        </div>

        {error && <div className="error-box">{error}</div>}
        {message && <div className="success-box">{message}</div>}

        {/* SELLER SUBSCRIPTION WARNING BANNER */}
        {selectedStore && shouldShowSubscriptionBanner(selectedStore) && (
          <div
            className={`subscription-warning-banner ${getSubscriptionTimeClass(
              selectedStore.subscription_status,
              selectedStore.subscription_ends_at,
              selectedStore.is_suspended
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
                  selectedStore.subscription_ends_at,
                  selectedStore.is_suspended
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
            getAllowedOrderStatusActions={(status) =>
              getAllowedOrderStatusActions(status as any) as string[]
            }
            formatOrderStatusActionLabel={(status) =>
              formatOrderStatusActionLabel(status as any)
            }
            confirmManualPayment={confirmManualPayment}
            updateOrderStatus={(orderId, nextStatus) =>
              updateOrderStatus(orderId, nextStatus as any)
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

        {(activeTab === "settings" || activeTab === "adminSummary" || activeTab === "adminSellers" || activeTab === "adminPlans" || activeTab === "adminPayments") && (
          <div className={activeTab === "settings" ? "settings-layout store-profile-page" : `settings-layout admin-layout admin-page-${activeTab}`}>
            <form className="settings-card" onSubmit={saveStoreSettings}>
              <h2>
                {activeTab === "settings"
                  ? "Store profile"
                  : activeTab === "adminSummary"
                    ? "Business overview"
                    : activeTab === "adminSellers"
                      ? "Seller management"
                      : activeTab === "adminPlans"
                        ? "Plan settings"
                        : "Payments"}
              </h2>

              
              {/* SETTINGS SUBSCRIPTION CARD */}
              {selectedStore && (
                <div className="subscription-summary-card">
                  <div>
                    <span>Current plan</span>
                    <strong>{formatPlanName(selectedStore.plan_name)}</strong>
                  </div>

                  <div>
                    <span>Status</span>
                    <strong
                      className={`subscription-status ${getComputedSubscriptionStatus(
                        selectedStore.subscription_status,
                        selectedStore.subscription_ends_at,
                        selectedStore.is_suspended
                      )}`}
                    >
                      {formatPlanName(
                        getComputedSubscriptionStatus(
                          selectedStore.subscription_status,
                          selectedStore.subscription_ends_at,
                          selectedStore.is_suspended
                        )
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>Monthly fee</span>
                    <strong>{formatMonthlyFee(selectedStore.monthly_fee)}</strong>
                  </div>

                  <div>
                    <span>Expires</span>
                    <strong>{formatSubscriptionDate(selectedStore.subscription_ends_at)}</strong>
                  </div>
                </div>
              )}

              {/* PRODUCT USAGE CARD */}
              {selectedStore && (
                <div className="product-usage-card">
                  <div className="product-usage-head">
                    <div>
                      <span>Product usage</span>
                      <h3>
                        {subscriptionUsage?.display_name ||
                          formatPlanName(selectedStore.plan_name)}
                      </h3>
                    </div>

                    <strong>
                      {loadingSubscriptionUsage
                        ? "Loading..."
                        : formatProductUsageLabel(subscriptionUsage)}
                    </strong>
                  </div>

                  <div className="product-usage-progress">
                    <div
                      className={`product-usage-progress-fill ${getProductUsageClass(
                        subscriptionUsage
                      )}`}
                      style={{
                        width: `${getProductUsagePercent(subscriptionUsage)}%`,
                      }}
                    />
                  </div>

                  <div className="product-usage-meta">
                    <span>{formatRemainingProducts(subscriptionUsage)}</span>
                    <span>
                      Monthly fee:{" "}
                      {formatMonthlyFee(
                        subscriptionUsage?.monthly_fee ?? selectedStore.monthly_fee
                      )}
                    </span>
                  </div>

                  {subscriptionUsage && (
                    <div className="plan-feature-chips">
                      <span
                        className={`plan-feature-chip ${
                          subscriptionUsage.can_upload_images ? "enabled" : "disabled"
                        }`}
                      >
                        Images: {subscriptionUsage.can_upload_images ? "Enabled" : "Disabled"}
                      </span>

                      <span
                        className={`plan-feature-chip ${
                          subscriptionUsage.can_receive_online_payments ? "enabled" : "disabled"
                        }`}
                      >
                        Online payments:{" "}
                        {subscriptionUsage.can_receive_online_payments ? "Enabled" : "Disabled"}
                      </span>

                      <span
                        className={`plan-feature-chip ${
                          subscriptionUsage.can_use_custom_domain ? "enabled" : "disabled"
                        }`}
                      >
                        Custom domain:{" "}
                        {subscriptionUsage.can_use_custom_domain ? "Enabled" : "Disabled"}
                      </span>

                      <span
                        className={`plan-feature-chip ${
                          subscriptionUsage.plan_is_active ? "enabled" : "disabled"
                        }`}
                      >
                        Plan: {subscriptionUsage.plan_is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                  )}
                </div>
              )}
              {/* ADMIN SELECTED STORE EXTEND BUTTON */}
              {isPlatformAdmin && activeTab === "adminSellers" && (
                <button
                  type="button"
                  className="extend-subscription-btn"
                  onClick={extendSelectedStoreSubscription}
                >
                  Extend subscription 30 days
                </button>
              )}



              {/* ADMIN PLAN SETTINGS PANEL */}
              {isPlatformAdmin && activeTab === "adminPlans" && (
                <div className="admin-plans-panel">
                  <div className="admin-stores-header">
                    <div>
                      <h3>Subscription plan settings</h3>
                      <p>Control product limits, prices, and features for each seller plan.</p>
                    </div>

                    <button
                      type="button"
                      onClick={loadSubscriptionPlans}
                      disabled={loadingSubscriptionPlans}
                    >
                      {loadingSubscriptionPlans ? "Loading..." : "Refresh plans"}
                    </button>
                  </div>

                  {subscriptionPlans.length === 0 ? (
                    <p className="muted">Click Refresh plans to load subscription plans.</p>
                  ) : (
                    <div className="plan-settings-grid">
                      {subscriptionPlans.map((plan) => {
                        const draft = planDrafts[plan.name];

                        if (!draft) {
                          return null;
                        }

                        return (
                          <div className="plan-settings-card" key={plan.id}>
                            <div className="plan-settings-title">
                              <div>
                                <span>{plan.name}</span>
                                <h4>{draft.display_name}</h4>
                              </div>

                              <strong>{draft.product_limit ? `${draft.product_limit} products` : "Unlimited"}</strong>
                            </div>

                            <label>
                              Display name
                              <input
                                value={draft.display_name}
                                onChange={(e) =>
                                  updatePlanDraft(plan.name, "display_name", e.target.value)
                                }
                              />
                            </label>

                            <label>
                              Monthly fee
                              <input
                                type="number"
                                min="0"
                                step="0.01"
                                value={draft.monthly_fee}
                                onChange={(e) =>
                                  updatePlanDraft(plan.name, "monthly_fee", e.target.value)
                                }
                              />
                            </label>

                            <label>
                              Product limit
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={draft.product_limit}
                                placeholder="Blank means unlimited"
                                onChange={(e) =>
                                  updatePlanDraft(plan.name, "product_limit", e.target.value)
                                }
                              />
                            </label>

                            <div className="plan-checkboxes">
                              <label>
                                <input
                                  type="checkbox"
                                  checked={draft.can_upload_images}
                                  onChange={(e) =>
                                    updatePlanDraft(plan.name, "can_upload_images", e.target.checked)
                                  }
                                />
                                Image uploads
                              </label>

                              <label>
                                <input
                                  type="checkbox"
                                  checked={draft.can_use_custom_domain}
                                  onChange={(e) =>
                                    updatePlanDraft(plan.name, "can_use_custom_domain", e.target.checked)
                                  }
                                />
                                Custom domain
                              </label>

                                                            <label>
                                <input
                                  type="checkbox"
                                  checked={draft.can_receive_online_payments}
                                  onChange={(e) =>
                                    updatePlanDraft(
                                      plan.name,
                                      "can_receive_online_payments",
                                      e.target.checked
                                    )
                                  }
                                />
                                Online payments
                              </label>

                              <label>
                                <input
                                  type="checkbox"
                                  checked={draft.is_active}
                                  onChange={(e) =>
                                    updatePlanDraft(plan.name, "is_active", e.target.checked)
                                  }
                                />
                                Plan active
                              </label>
                            </div>

                            <button
                              type="button"
                              className="save-plan-btn"
                              onClick={() => saveSubscriptionPlan(plan.name)}
                            >
                              Save plan
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
              {/* ADMIN SUBSCRIPTION SUMMARY PANEL */}
              {isPlatformAdmin && activeTab === "adminSummary" && (
                <div className="admin-summary-panel">
                  <div className="admin-stores-header">
                    <div>
                      <h3>Subscription business summary</h3>
                      <p>Quick overview of seller subscriptions and revenue.</p>
                    </div>

                    <button
                      type="button"
                      onClick={loadAdminSubscriptionSummary}
                      disabled={loadingAdminSubscriptionSummary}
                    >
                      {loadingAdminSubscriptionSummary ? "Loading..." : "Refresh summary"}
                    </button>
                  </div>

                  {!adminSubscriptionSummary ? (
                    <p className="muted">Click Refresh summary to load business numbers.</p>
                  ) : (
                    <div className="admin-summary-grid">
                      <div className="admin-summary-card">
                        <span>Total sellers</span>
                        <strong>{adminSubscriptionSummary.total_stores}</strong>
                      </div>

                      <div className="admin-summary-card good">
                        <span>Active</span>
                        <strong>{adminSubscriptionSummary.active_stores}</strong>
                      </div>

                      <div className="admin-summary-card">
                        <span>Trial</span>
                        <strong>{adminSubscriptionSummary.trial_stores}</strong>
                      </div>

                      <div className="admin-summary-card danger">
                        <span>Expired</span>
                        <strong>{adminSubscriptionSummary.expired_stores}</strong>
                      </div>

                      <div className="admin-summary-card danger">
                        <span>Suspended</span>
                        <strong>{adminSubscriptionSummary.suspended_stores}</strong>
                      </div>

                      <div className="admin-summary-card warning">
                        <span>Expiring in 7 days</span>
                        <strong>{adminSubscriptionSummary.expiring_within_7_days}</strong>
                      </div>

                      <div className="admin-summary-card money">
                        <span>Monthly recurring</span>
                        <strong>{formatMonthlyFee(adminSubscriptionSummary.monthly_recurring_total)}</strong>
                      </div>

                      <div className="admin-summary-card money">
                        <span>Revenue this month</span>
                        <strong>{formatMonthlyFee(adminSubscriptionSummary.subscription_revenue_this_month)}</strong>
                      </div>

                      <div className="admin-summary-card money">
                        <span>Total subscription revenue</span>
                        <strong>{formatMonthlyFee(adminSubscriptionSummary.subscription_revenue_total)}</strong>
                      </div>

                      <div className="admin-summary-card">
                        <span>Payment records</span>
                        <strong>{adminSubscriptionSummary.recent_payment_count}</strong>
                      </div>
                    </div>
                  )}
                </div>
              )}
              {/* ADMIN ALL STORES PANEL */}
              {isPlatformAdmin && activeTab === "adminSellers" && (
                <div className="admin-stores-panel">
                  <div className="admin-stores-header">
                    <div>
                      <h3>Admin seller stores</h3>
                      <p>Extend subscriptions for sellers who have paid you.</p>
                    </div>

                    <div className="admin-header-actions">
                      <button
                        type="button"
                        onClick={loadAdminStores}
                        disabled={loadingAdminStores}
                      >
                        {loadingAdminStores ? "Loading..." : "Refresh sellers"}
                      </button>

                      <button
                        type="button"
                        onClick={exportAdminStoresCsv}
                      >
                        Export sellers CSV
                      </button>
                    </div>
                  </div>

                  {adminStores.length === 0 ? (
                    <p className="muted">Click Refresh sellers to load all stores.</p>
                  ) : (
                    <>
                      <div className="admin-store-search">
                        <input
                          value={adminStoreSearch}
                          onChange={(e) => setAdminStoreSearch(e.target.value)}
                          placeholder="Search sellers by store, slug, owner, or email..."
                        />

                        {adminStoreSearch && (
                          <button
                            type="button"
                            onClick={() => setAdminStoreSearch("")}
                          >
                            Clear
                          </button>
                        )}
                      </div>

                      <div className="admin-store-filters">
                        {(["all", "active", "trial", "expired", "suspended", "expiring"] as const).map((filter) => (
                          <button
                            key={filter}
                            type="button"
                            className={adminStoreFilter === filter ? "active" : ""}
                            onClick={() => setAdminStoreFilter(filter)}
                          >
                            {filter === "expiring" ? "Expiring soon" : formatPlanName(filter)}
                          </button>
                        ))}
                      </div>

                      <div className="admin-store-list">
                        {filteredAdminStores.map((store) => (
                        <div className="admin-store-card" key={store.id}>
                          <div>
                            <h4>{store.name}</h4>
                            <p>/{store.slug}</p>
                            <p>{store.owner_name} — {store.owner_email}</p>
                          </div>

                          <div>
                            <span>Plan</span>
                            <strong>{formatPlanName(store.plan_name)}</strong>
                          </div>

                          <div>
                            <span>Status</span>
                            <strong
                              className={`subscription-status ${getComputedSubscriptionStatus(
                                store.subscription_status,
                                store.subscription_ends_at,
                                store.is_suspended
                              )}`}
                            >
                              {formatPlanName(
                                getComputedSubscriptionStatus(
                                  store.subscription_status,
                                  store.subscription_ends_at,
                                  store.is_suspended
                                )
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>Monthly fee</span>
                            <strong>{formatMonthlyFee(store.monthly_fee)}</strong>
                          </div>

                          <div className="admin-plan-change">
                            <label>
                              <span>Change plan</span>
                              <select
                                value={adminPlanDrafts[store.id] || store.plan_name || "starter"}
                                onChange={(e) =>
                                  setAdminPlanDrafts((prev) => ({
                                    ...prev,
                                    [store.id]: e.target.value,
                                  }))
                                }
                                disabled={loadingSubscriptionPlans || subscriptionPlans.length === 0}
                              >
                                {subscriptionPlans.length === 0 ? (
                                  <option value={store.plan_name || "starter"}>
                                    {formatPlanName(store.plan_name)}
                                  </option>
                                ) : (
                                  subscriptionPlans.map((plan) => (
                                    <option key={plan.id} value={plan.name}>
                                      {plan.display_name} — {formatMonthlyFee(plan.monthly_fee)}
                                    </option>
                                  ))
                                )}
                              </select>
                            </label>

                            <button
                              type="button"
                              className="save-store-plan-btn"
                              onClick={() => adminChangeStorePlan(store)}
                              disabled={
                                loadingSubscriptionPlans ||
                                subscriptionPlans.length === 0 ||
                                (adminPlanDrafts[store.id] || store.plan_name) === store.plan_name
                              }
                            >
                              Save plan
                            </button>
                          </div>

                          <div>
                            <span>Expires</span>
                            <strong>{formatSubscriptionDate(store.subscription_ends_at)}</strong>
                          </div>

                          <div>
                            <span>Time left</span>
                            <strong
                              className={`subscription-time ${getSubscriptionTimeClass(
                                store.subscription_status,
                                store.subscription_ends_at,
                                store.is_suspended
                              )}`}
                            >
                              {getSubscriptionTimeLabel(
                                store.subscription_status,
                                store.subscription_ends_at,
                                store.is_suspended
                              )}
                            </strong>
                          </div>

                          <div className="admin-store-actions">
                            <button
                              type="button"
                              className="extend-subscription-btn"
                              onClick={() => extendAdminStoreSubscription(store.id)}
                            >
                              Extend 30 days
                            </button>

                            {store.is_suspended || store.subscription_status === "suspended" ? (
                              <button
                                type="button"
                                className="reactivate-store-btn"
                                onClick={() => adminSetStoreSuspension(store, false)}
                              >
                                Reactivate
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="suspend-store-btn"
                                onClick={() => adminSetStoreSuspension(store, true)}
                              >
                                Suspend
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  
                      {filteredAdminStores.length === 0 && (
                        <p className="muted">No sellers match this filter.</p>
                      )}
                    </>)}
                </div>
              )}{/* ADMIN SUBSCRIPTION PAYMENTS PANEL */}
              {isPlatformAdmin && activeTab === "adminPayments" && (
                <div className="admin-stores-panel">
                  <div className="admin-stores-header">
                    <div>
                      <h3>Subscription payment history</h3>
                      <p>Recent seller subscription payments recorded by admins.</p>
                    </div>

                    <div className="admin-header-actions">
                      <button
                        type="button"
                        onClick={loadAdminSubscriptionPayments}
                        disabled={loadingAdminSubscriptionPayments}
                      >
                        {loadingAdminSubscriptionPayments ? "Loading..." : "Refresh payments"}
                      </button>

                      <button
                        type="button"
                        onClick={exportSubscriptionPaymentsCsv}
                      >
                        Export CSV
                      </button>
                    </div>
                  </div>

                  {adminSubscriptionPayments.length === 0 ? (
                    <p className="muted">Click Refresh payments to load recent payments.</p>
                  ) : (
                    <>
                      <div className="admin-store-search">
                        <input
                          value={subscriptionPaymentSearch}
                          onChange={(e) => setSubscriptionPaymentSearch(e.target.value)}
                          placeholder="Search payments by store, reference, method, admin, or note..."
                        />

                        {subscriptionPaymentSearch && (
                          <button
                            type="button"
                            onClick={() => setSubscriptionPaymentSearch("")}
                          >
                            Clear
                          </button>
                        )}
                      </div>

                      <div className="subscription-payment-filters">
                        {(["all", "manual", "momo", "bank", "cash", "paystack"] as const).map((method) => (
                          <button
                            key={method}
                            type="button"
                            className={subscriptionPaymentMethodFilter === method ? "active" : ""}
                            onClick={() => setSubscriptionPaymentMethodFilter(method)}
                          >
                            {formatPlanName(method)}
                          </button>
                        ))}
                      </div>

                      <div className="admin-store-list">
                        {filteredSubscriptionPayments.map((payment) => (
                        <div className="admin-store-card" key={payment.id}>
                          <div>
                            <h4>{payment.store_name}</h4>
                            <p>/{payment.store_slug}</p>
                            <p>Approved by: {payment.approved_by_email || "Unknown admin"}</p>
                          </div>

                          <div>
                            <span>Plan</span>
                            <strong>{formatPlanName(payment.plan_name)}</strong>
                          </div>

                          <div>
                            <span>Amount</span>
                            <strong>
                              {payment.currency} {Number(payment.amount).toFixed(2)}
                            </strong>
                          </div>

                          <div>
                            <span>Method</span>
                            <strong>{formatPlanName(payment.payment_method)}</strong>
                          </div>

                          <div>
                            <span>Reference</span>
                            <strong>{payment.payment_reference || "N/A"}</strong>
                          </div>

                          <div>
                            <span>Covered</span>
                            <strong>{payment.covered_days} days</strong>
                          </div>

                          <div>
                            <span>Paid</span>
                            <strong>{formatSubscriptionDate(payment.paid_at)}</strong>
                          </div>
                        </div>
                      ))}
                    </div>
                  
                      {filteredSubscriptionPayments.length === 0 && (
                        <p className="muted">No payments match this filter.</p>
                      )}
                    </>)}
                </div>
              )}<label>
                Store name
                <input
                  value={storeForm.name}
                  onChange={(e) =>
                    setStoreForm((prev) => ({ ...prev, name: e.target.value }))
                  }
                  placeholder="THE GAME Store"
                  required
                />
              </label>

              <label>
                Store slug
                <input
                  value={storeForm.slug}
                  onChange={(e) =>
                    setStoreForm((prev) => ({
                      ...prev,
                      slug: makeSlug(e.target.value),
                    }))
                  }
                  placeholder="thegame"
                  required
                />
              </label>

              <label>
                Bio
                <textarea
                  value={storeForm.bio}
                  onChange={(e) =>
                    setStoreForm((prev) => ({ ...prev, bio: e.target.value }))
                  }
                  placeholder="Tell customers what your store sells."
                />
              </label>

              <label>
                WhatsApp number
                <input
                  value={storeForm.whatsapp_number}
                  onChange={(e) =>
                    setStoreForm((prev) => ({
                      ...prev,
                      whatsapp_number: e.target.value,
                    }))
                  }
                  placeholder="233544193559"
                />
              </label>              {subscriptionUsage?.can_upload_images === false && (
                <p className="plan-restriction-note">
                  Logo and banner uploads are disabled on your current plan. Upgrade to enable store branding images.
                </p>
              )}


                            <label>
                Store logo
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={loadingSubscriptionUsage || subscriptionUsage?.can_upload_images === false}
                  onChange={(e) => {
                    const file = e.target.files?.[0];

                    if (file) {
                      uploadStoreImage(file, "logo");
                    }
                  }}
                />
              </label>

              {storeForm.logo_url && (
                <div className="uploaded-image-preview">
                  <img src={storeForm.logo_url} alt="Store logo preview" />
                  <p>Logo uploaded successfully</p>
                </div>
              )}

                            <label>
                Store banner
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={loadingSubscriptionUsage || subscriptionUsage?.can_upload_images === false}
                  onChange={(e) => {
                    const file = e.target.files?.[0];

                    if (file) {
                      uploadStoreImage(file, "banner");
                    }
                  }}
                />
              </label>

              {storeForm.banner_url && (
                <div className="uploaded-image-preview">
                  <img src={storeForm.banner_url} alt="Store banner preview" />
                  <p>Banner uploaded successfully</p>
                </div>
              )}

              <label>
                Category
                <input
                  value={storeForm.category}
                  onChange={(e) =>
                    setStoreForm((prev) => ({ ...prev, category: e.target.value }))
                  }
                  placeholder="Fashion"
                />
              </label>

              <button type="submit">Save store settings</button>
            </form>

            <aside className="settings-preview">
              <h2>Preview</h2>

              {storeForm.banner_url && (
                <img className="banner-preview" src={storeForm.banner_url} alt="Store banner" />
              )}

              {storeForm.logo_url && (
                <img className="logo-preview" src={storeForm.logo_url} alt="Store logo" />
              )}

              <h3>{storeForm.name || "Store name"}</h3>
              <p className="muted">/{storeForm.slug || "store-slug"}</p>
              <p>{storeForm.bio || "Store bio will appear here."}</p>
              <p>WhatsApp: {storeForm.whatsapp_number || "Not added"}</p>
              <p>Category: {storeForm.category || "Not added"}</p>
            </aside>
          </div>
        )}
    </DashboardShell>
  );
}
