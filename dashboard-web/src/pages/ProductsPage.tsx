import { useEffect, useRef, useState } from "react";
import type { Dispatch, FormEvent, SetStateAction } from "react";
import { resolveDashboardMediaUrl } from "../utils/api-url";

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
  id?: string;
  value: string;
  label: string;
  price_adjustment: string;
  is_active: boolean;
  sort_order: number;
};

type ProductOrderField = {
  id?: string;
  product_id?: string;
  key: string;
  label: string;
  field_type: ProductOrderFieldType;
  placeholder: string;
  help_text: string;
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
  store_id: string;
  name: string;
  slug: string;
  description?: string | null;
  image_url?: string | null;
  product_type: ProductType;
  default_fulfillment_method: FulfillmentMethod;
  allowed_fulfillment_methods: FulfillmentMethod[];
  order_fields: ProductOrderField[];
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
  product_type: ProductType;
  default_fulfillment_method: FulfillmentMethod;
  allowed_fulfillment_methods: FulfillmentMethod[];
  order_fields: ProductOrderField[];
  price: string;
  stock_quantity: string;
  is_active: boolean;
  is_featured: boolean;
};

type ProductThumbnailProps = {
  product: Product;
};

const PRODUCT_TYPES: Array<{
  value: ProductType;
  label: string;
  description: string;
}> = [
  {
    value: "physical",
    label: "Physical item",
    description: "Clothing, gadgets, beauty products, and other tangible goods.",
  },
  {
    value: "digital",
    label: "Digital item",
    description: "Files, codes, eSIMs, licences, and downloadable products.",
  },
  {
    value: "subscription",
    label: "Subscription",
    description: "Recurring access, memberships, plans, and account activations.",
  },
  {
    value: "service",
    label: "Service",
    description: "Remote, on-site, appointment-based, or custom services.",
  },
  {
    value: "food",
    label: "Food & catering",
    description: "Meals, drinks, catering packages, and made-to-order food.",
  },
  {
    value: "booking",
    label: "Booking",
    description: "Reservations, sessions, rentals, and scheduled experiences.",
  },
  {
    value: "custom",
    label: "Custom order",
    description: "Made-to-order items or special requests you confirm with each customer.",
  },
];

const ALL_FULFILLMENT_METHODS: FulfillmentMethod[] = [
  "delivery",
  "pickup",
  "digital_delivery",
  "activation",
  "appointment",
  "on_site_service",
  "remote_service",
  "reservation",
  "seller_confirmation",
];

const DEFAULT_FULFILLMENT_BY_PRODUCT_TYPE: Record<
  ProductType,
  FulfillmentMethod[]
> = {
  physical: ["delivery", "pickup"],
  digital: ["digital_delivery"],
  subscription: ["activation"],
  service: ["appointment", "remote_service"],
  food: ["delivery", "pickup"],
  booking: ["reservation"],
  custom: ["seller_confirmation"],
};

const COMPATIBLE_FULFILLMENT_BY_PRODUCT_TYPE: Record<
  ProductType,
  FulfillmentMethod[]
> = {
  physical: [
    "delivery",
    "pickup",
    "seller_confirmation",
  ],
  digital: [
    "digital_delivery",
    "activation",
    "seller_confirmation",
  ],
  subscription: [
    "activation",
    "digital_delivery",
    "seller_confirmation",
  ],
  service: [
    "appointment",
    "on_site_service",
    "remote_service",
    "seller_confirmation",
  ],
  food: [
    "delivery",
    "pickup",
    "seller_confirmation",
  ],
  booking: [
    "reservation",
    "appointment",
    "seller_confirmation",
  ],
  custom: [...ALL_FULFILLMENT_METHODS],
};

const FIELD_TYPES: Array<{
  value: ProductOrderFieldType;
  label: string;
}> = [
  { value: "text", label: "Short answer" },
  { value: "textarea", label: "Long answer" },
  { value: "select", label: "Choose from a list" },
  { value: "radio", label: "Show all choices" },
  { value: "checkbox", label: "Confirmation checkbox" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "time", label: "Time" },
  { value: "datetime", label: "Date and time" },
  { value: "phone", label: "Phone number" },
  { value: "email", label: "Email address" },
];

type QuickFieldDefinition = {
  label: string;
  field: Omit<ProductOrderField, "sort_order">;
  recommendedProductTypes?: ProductType[];
  recommendedNameKeywords?: string[];
};

const QUICK_FIELDS: QuickFieldDefinition[] = [
  {
    label: "Shoe size",
    recommendedNameKeywords: [
      "shoe",
      "shoes",
      "sneaker",
      "sneakers",
      "trainer",
      "trainers",
      "boot",
      "boots",
      "heel",
      "heels",
      "sandal",
      "sandals",
      "slipper",
      "slippers",
      "loafer",
      "loafers",
    ],
    field: {
      key: "shoe_size",
      label: "Shoe size",
      field_type: "select",
      placeholder: "Choose a shoe size",
      help_text: "Select the shoe size you want.",
      is_required: true,
      is_sensitive: false,
      include_in_whatsapp: true,
      is_active: true,
      validation_rules: {},
      options: [
        {
          value: "option-1",
          label: "",
          price_adjustment: "0.00",
          is_active: true,
          sort_order: 0,
        },
      ],
    },
  },
  {
    label: "Clothing size",
    recommendedNameKeywords: [
      "shirt",
      "shirts",
      "t shirt",
      "t shirts",
      "tee",
      "tees",
      "dress",
      "dresses",
      "jeans",
      "trouser",
      "trousers",
      "pants",
      "hoodie",
      "hoodies",
      "jacket",
      "jackets",
      "skirt",
      "skirts",
      "shorts",
      "jersey",
      "jerseys",
      "blouse",
      "blouses",
    ],
    field: {
      key: "clothing_size",
      label: "Clothing size",
      field_type: "select",
      placeholder: "Choose a clothing size",
      help_text: "Select the clothing size you want.",
      is_required: true,
      is_sensitive: false,
      include_in_whatsapp: true,
      is_active: true,
      validation_rules: {},
      options: [
        {
          value: "option-1",
          label: "",
          price_adjustment: "0.00",
          is_active: true,
          sort_order: 0,
        },
      ],
    },
  },
  {
    label: "Colour",
    recommendedNameKeywords: [
      "shoe",
      "shoes",
      "sneaker",
      "sneakers",
      "trainer",
      "trainers",
      "boot",
      "boots",
      "shirt",
      "shirts",
      "t shirt",
      "t shirts",
      "tee",
      "tees",
      "dress",
      "dresses",
      "jeans",
      "trouser",
      "trousers",
      "pants",
      "hoodie",
      "hoodies",
      "jacket",
      "jackets",
      "skirt",
      "skirts",
      "shorts",
      "jersey",
      "jerseys",
      "blouse",
      "blouses",
    ],
    field: {
      key: "colour",
      label: "Colour",
      field_type: "text",
      placeholder: "e.g. Black",
      help_text: "Enter your preferred colour.",
      is_required: true,
      is_sensitive: false,
      include_in_whatsapp: true,
      is_active: true,
      validation_rules: { max_length: 80 },
      options: [],
    },
  },
  {
    label: "Package / plan",
    recommendedProductTypes: ["subscription"],
    recommendedNameKeywords: [
      "package",
      "packages",
      "plan",
      "plans",
      "bundle",
      "bundles",
      "membership",
      "memberships",
      "subscription",
      "subscriptions",
    ],
    field: {
      key: "package",
      label: "Package or plan",
      field_type: "select",
      placeholder: "Choose a package",
      help_text: "Add your own package names and price differences.",
      is_required: true,
      is_sensitive: false,
      include_in_whatsapp: true,
      is_active: true,
      validation_rules: {},
      options: [
        {
          value: "option-1",
          label: "",
          price_adjustment: "0.00",
          is_active: true,
          sort_order: 0,
        },
      ],
    },
  },
  {
    label: "Date",
    recommendedProductTypes: ["service", "booking"],
    field: {
      key: "preferred_date",
      label: "Preferred date",
      field_type: "date",
      placeholder: "",
      help_text: "Choose the date that works best.",
      is_required: true,
      is_sensitive: false,
      include_in_whatsapp: true,
      is_active: true,
      validation_rules: {},
      options: [],
    },
  },
  {
    label: "Time",
    recommendedProductTypes: ["service", "booking"],
    field: {
      key: "preferred_time",
      label: "Preferred time",
      field_type: "time",
      placeholder: "",
      help_text: "Choose the time that works best.",
      is_required: true,
      is_sensitive: false,
      include_in_whatsapp: true,
      is_active: true,
      validation_rules: {},
      options: [],
    },
  },
  {
    label: "Email address",
    recommendedProductTypes: ["digital"],
    field: {
      key: "delivery_email",
      label: "Email address",
      field_type: "email",
      placeholder: "name@example.com",
      help_text: "Where should the order details be sent?",
      is_required: true,
      is_sensitive: false,
      include_in_whatsapp: true,
      is_active: true,
      validation_rules: {},
      options: [],
    },
  },
];

function normalizeRecommendationText(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ");
}

function isQuickFieldRecommended(
  quickField: QuickFieldDefinition,
  productName: string,
  productType: ProductType,
) {
  if (
    quickField.recommendedProductTypes?.includes(productType)
  ) {
    return true;
  }

  const normalizedProductName =
    ` ${normalizeRecommendationText(productName)} `;

  return (
    quickField.recommendedNameKeywords?.some((keyword) => {
      const normalizedKeyword =
        normalizeRecommendationText(keyword);

      return (
        normalizedKeyword.length > 0 &&
        normalizedProductName.includes(
          ` ${normalizedKeyword} `,
        )
      );
    }) ?? false
  );
}

function formatFulfillmentMethod(method: FulfillmentMethod) {
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

  return labels[method];
}

function formatProductType(productType: ProductType) {
  return PRODUCT_TYPES.find((item) => item.value === productType)?.label
    ?? "Custom order";
}

function makeFieldKey(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/^[^a-z]+/, "")
    .slice(0, 50);
}

function makeUniqueFieldKey(base: string, fields: ProductOrderField[]) {
  const normalizedBase = makeFieldKey(base) || "order_field";
  const existing = new Set(fields.map((field) => field.key));

  if (!existing.has(normalizedBase)) {
    return normalizedBase;
  }

  let suffix = 2;
  while (existing.has(`${normalizedBase}_${suffix}`)) {
    suffix += 1;
  }

  return `${normalizedBase}_${suffix}`.slice(0, 50);
}

function makeOptionValue(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}

function isChoiceField(fieldType: ProductOrderFieldType) {
  return fieldType === "select" || fieldType === "radio";
}

function normalizeValidationRulesForFieldType(
  fieldType: ProductOrderFieldType,
  rules: Record<string, unknown>,
) {
  if (
    fieldType === "text" ||
    fieldType === "textarea" ||
    fieldType === "email" ||
    fieldType === "phone"
  ) {
    return Object.fromEntries(
      Object.entries(rules).filter(
        ([rule]) =>
          rule === "min_length" ||
          rule === "max_length",
      ),
    );
  }

  if (fieldType === "number") {
    return Object.fromEntries(
      Object.entries(rules).filter(
        ([rule]) =>
          rule === "min" ||
          rule === "max",
      ),
    );
  }

  return {};
}

function serializeProductForm(form: ProductForm) {
  return JSON.stringify(form);
}

function ProductThumbnail({
  product,
}: ProductThumbnailProps) {
  const [failedImageUrl, setFailedImageUrl] =
    useState<string | null>(null);

  const imageUrl = resolveDashboardMediaUrl(
    product.image_url,
  ) || null;
  const imageFailed =
    imageUrl !== null &&
    failedImageUrl === imageUrl;

  const initial =
    product.name.trim().slice(0, 1).toUpperCase()
    || "P";

  return (
    <div className="product-thumb-box">
      {imageUrl && !imageFailed ? (
        <img
          src={imageUrl}
          alt={product.name}
          loading="lazy"
          onError={() => setFailedImageUrl(imageUrl)}
        />
      ) : (
        <span
          className="product-thumb-fallback"
          aria-hidden="true"
        >
          {initial}
        </span>
      )}
    </div>
  );
}

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

type ProductsPageProps = {
  products: Product[];
  productForm: ProductForm;
  setProductForm: Dispatch<SetStateAction<ProductForm>>;
  subscriptionUsage: StoreSubscriptionUsage | null;
  loadingSubscriptionUsage: boolean;
  uploadingProductImage: boolean;
  editingProductId: string | null;
  isProductFormOpen: boolean;
  setIsProductFormOpen: Dispatch<SetStateAction<boolean>>;
  saveProduct: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  makeSlug: (value: string) => string;
  uploadProductImage: (file: File) => void | Promise<void>;
  isProductLimitReachedForCreate: () => boolean;
  getProductLimitReachedMessage: () => string;
  isProductSubmitDisabled: () => boolean;
  getProductSubmitLabel: () => string;
  cancelProductEdit: () => void;
  startEditingProduct: (product: Product) => void;
  toggleProductActive: (product: Product) => void | Promise<void>;
  deleteProduct: (product: Product) => void | Promise<void>;
};

export function ProductsPage({
  products,
  productForm,
  setProductForm,
  subscriptionUsage,
  loadingSubscriptionUsage,
  uploadingProductImage,
  editingProductId,
  isProductFormOpen,
  setIsProductFormOpen,
  saveProduct,
  makeSlug,
  uploadProductImage,
  isProductLimitReachedForCreate,
  getProductLimitReachedMessage,
  isProductSubmitDisabled,
  getProductSubmitLabel,
  cancelProductEdit,
  startEditingProduct,
  toggleProductActive,
  deleteProduct,
}: ProductsPageProps) {
  const [openProductActionsId, setOpenProductActionsId] =
    useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(1);
  const [expandedFieldIndex, setExpandedFieldIndex] =
    useState<number | null>(null);
  const [stepMessage, setStepMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement | null>(null);
  const initialFormSnapshotRef = useRef("");
  const formSessionRef = useRef("");

  const formIsOpen =
    isProductFormOpen || Boolean(editingProductId);

  const currentFormSnapshot =
    serializeProductForm(productForm);

  const productPreviewUrl = resolveDashboardMediaUrl(
    productForm.image_url,
  );

  const selectedProductType =
    PRODUCT_TYPES.find(
      (item) => item.value === productForm.product_type,
    ) ?? PRODUCT_TYPES[0];

  const recommendedFulfillmentMethods =
    DEFAULT_FULFILLMENT_BY_PRODUCT_TYPE[
      productForm.product_type
    ];

  const compatibleFulfillmentMethods =
    COMPATIBLE_FULFILLMENT_BY_PRODUCT_TYPE[
      productForm.product_type
    ];

  const additionalFulfillmentMethods =
    compatibleFulfillmentMethods.filter(
      (method) =>
        !recommendedFulfillmentMethods.includes(method),
    );

  const additionalSelectedCount =
    additionalFulfillmentMethods.filter((method) =>
      productForm.allowed_fulfillment_methods.includes(method),
    ).length;

  const recommendedQuickFields = QUICK_FIELDS.filter(
    (quickField) =>
      isQuickFieldRecommended(
        quickField,
        productForm.name,
        productForm.product_type,
      ),
  );

  const recommendedQuickFieldLabels = new Set(
    recommendedQuickFields.map(
      (quickField) => quickField.label,
    ),
  );

  const otherQuickFields = QUICK_FIELDS.filter(
    (quickField) =>
      !recommendedQuickFieldLabels.has(quickField.label),
  );

  useEffect(() => {
    const sessionKey = editingProductId
      ? `edit:${editingProductId}`
      : isProductFormOpen
        ? "new"
        : "";

    if (!sessionKey) {
      formSessionRef.current = "";
      initialFormSnapshotRef.current = "";
      setActiveStep(1);
      setExpandedFieldIndex(null);
      setStepMessage("");
      setIsSubmitting(false);
      return;
    }

    if (formSessionRef.current === sessionKey) {
      return;
    }

    formSessionRef.current = sessionKey;
    setActiveStep(1);
    setExpandedFieldIndex(null);
    setStepMessage("");
    setIsSubmitting(false);

    if (editingProductId) {
      initialFormSnapshotRef.current =
        serializeProductForm(productForm);
      return;
    }

    setProductForm((previous) => {
      const defaults =
        DEFAULT_FULFILLMENT_BY_PRODUCT_TYPE[
          previous.product_type
        ];

      const alreadyUsesDefaults =
        previous.default_fulfillment_method === defaults[0] &&
        previous.allowed_fulfillment_methods.length ===
          defaults.length &&
        defaults.every((method) =>
          previous.allowed_fulfillment_methods.includes(method),
        );

      const nextForm = alreadyUsesDefaults
        ? previous
        : {
            ...previous,
            default_fulfillment_method: defaults[0],
            allowed_fulfillment_methods: [...defaults],
          };

      initialFormSnapshotRef.current =
        serializeProductForm(nextForm);

      return nextForm;
    });
  }, [
    editingProductId,
    isProductFormOpen,
    productForm,
    setProductForm,
  ]);

  useEffect(() => {
    if (
      !formIsOpen ||
      !initialFormSnapshotRef.current ||
      currentFormSnapshot ===
        initialFormSnapshotRef.current
    ) {
      return;
    }

    const handleBeforeUnload = (
      event: BeforeUnloadEvent,
    ) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener(
      "beforeunload",
      handleBeforeUnload,
    );

    return () => {
      window.removeEventListener(
        "beforeunload",
        handleBeforeUnload,
      );
    };
  }, [currentFormSnapshot, formIsOpen]);

  function hasUnsavedChanges() {
    return (
      formIsOpen &&
      Boolean(initialFormSnapshotRef.current) &&
      currentFormSnapshot !==
        initialFormSnapshotRef.current
    );
  }

  function requestCloseForm() {
    if (
      hasUnsavedChanges() &&
      !window.confirm(
        "Discard your unsaved product changes?",
      )
    ) {
      return;
    }

    initialFormSnapshotRef.current = "";
    formSessionRef.current = "";
    cancelProductEdit();
  }


  function scrollFormIntoView() {
    window.requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  function applyProductType(nextType: ProductType) {
    if (nextType === productForm.product_type) {
      return;
    }

    if (
      editingProductId &&
      !window.confirm(
        "Change this product type? StorePlug will update the recommended delivery or service options. Your customer questions will remain.",
      )
    ) {
      return;
    }

    const defaults =
      DEFAULT_FULFILLMENT_BY_PRODUCT_TYPE[nextType];

    setProductForm((previous) => ({
      ...previous,
      product_type: nextType,
      default_fulfillment_method: defaults[0],
      allowed_fulfillment_methods: [...defaults],
    }));
  }

  function toggleFulfillmentMethod(
    method: FulfillmentMethod,
    checked: boolean,
  ) {
    setProductForm((previous) => {
      const selected =
        previous.allowed_fulfillment_methods;

      let nextSelected = checked
        ? Array.from(new Set([...selected, method]))
        : selected.filter(
            (candidate) => candidate !== method,
          );

      if (nextSelected.length === 0) {
        nextSelected = [method];
      }

      nextSelected = ALL_FULFILLMENT_METHODS.filter(
        (candidate) => nextSelected.includes(candidate),
      );

      const nextDefault = nextSelected.includes(
        previous.default_fulfillment_method,
      )
        ? previous.default_fulfillment_method
        : nextSelected[0];

      return {
        ...previous,
        allowed_fulfillment_methods: nextSelected,
        default_fulfillment_method: nextDefault,
      };
    });
  }

  function updateOrderField(
    index: number,
    updater: (
      field: ProductOrderField,
    ) => ProductOrderField,
  ) {
    setProductForm((previous) => ({
      ...previous,
      order_fields: previous.order_fields.map(
        (field, fieldIndex) =>
          fieldIndex === index
            ? updater(field)
            : field,
      ),
    }));
  }

  function addBlankOrderField() {
    const unfinishedIndex =
      productForm.order_fields.findIndex(
        (field) => !field.label.trim(),
      );

    if (unfinishedIndex >= 0) {
      setExpandedFieldIndex(unfinishedIndex);
      setStepMessage(
        "Finish the open question before adding another.",
      );
      return;
    }

    const nextIndex = productForm.order_fields.length;

    setProductForm((previous) => {
      const nextKey = makeUniqueFieldKey(
        `order_field_${nextIndex + 1}`,
        previous.order_fields,
      );

      return {
        ...previous,
        order_fields: [
          ...previous.order_fields,
          {
            key: nextKey,
            label: "",
            field_type: "text",
            placeholder: "",
            help_text: "",
            is_required: false,
            is_sensitive: false,
            include_in_whatsapp: true,
            is_active: true,
            sort_order: nextIndex,
            validation_rules: {},
            options: [],
          },
        ],
      };
    });

    setExpandedFieldIndex(nextIndex);
    setStepMessage("");
  }

  function addQuickField(
    quickField: (typeof QUICK_FIELDS)[number],
  ) {
    const existingIndex =
      productForm.order_fields.findIndex(
        (field) =>
          field.key === quickField.field.key ||
          field.label.trim().toLowerCase() ===
            quickField.field.label.trim().toLowerCase(),
      );

    if (existingIndex >= 0) {
      setExpandedFieldIndex(existingIndex);
      setStepMessage(
        `${quickField.label} is already added.`,
      );
      return;
    }

    const nextIndex = productForm.order_fields.length;

    setProductForm((previous) => {
      const field = quickField.field;
      const nextKey = makeUniqueFieldKey(
        field.key,
        previous.order_fields,
      );

      return {
        ...previous,
        order_fields: [
          ...previous.order_fields,
          {
            ...field,
            key: nextKey,
            sort_order: previous.order_fields.length,
            validation_rules: {
              ...field.validation_rules,
            },
            options: field.options.map(
              (option) => ({ ...option }),
            ),
          },
        ],
      };
    });

    setExpandedFieldIndex(nextIndex);
    setStepMessage("");
  }

  function removeOrderField(index: number) {
    setProductForm((previous) => ({
      ...previous,
      order_fields: previous.order_fields
        .filter(
          (_, fieldIndex) => fieldIndex !== index,
        )
        .map((field, fieldIndex) => ({
          ...field,
          sort_order: fieldIndex,
        })),
    }));

    setExpandedFieldIndex((currentIndex) => {
      if (currentIndex === null) {
        return null;
      }

      if (currentIndex === index) {
        return null;
      }

      return currentIndex > index
        ? currentIndex - 1
        : currentIndex;
    });
  }

  function moveOrderField(
    index: number,
    direction: -1 | 1,
  ) {
    const targetIndex = index + direction;

    setProductForm((previous) => {
      if (
        targetIndex < 0 ||
        targetIndex >= previous.order_fields.length
      ) {
        return previous;
      }

      const fields = [...previous.order_fields];
      const [field] = fields.splice(index, 1);
      fields.splice(targetIndex, 0, field);

      return {
        ...previous,
        order_fields: fields.map(
          (item, fieldIndex) => ({
            ...item,
            sort_order: fieldIndex,
          }),
        ),
      };
    });

    setExpandedFieldIndex((currentIndex) => {
      if (currentIndex === index) {
        return targetIndex;
      }

      if (currentIndex === targetIndex) {
        return index;
      }

      return currentIndex;
    });
  }

  function addFieldOption(fieldIndex: number) {
    updateOrderField(fieldIndex, (field) => ({
      ...field,
      options: [
        ...field.options,
        {
          value: `option-${field.options.length + 1}`,
          label: "",
          price_adjustment: "0.00",
          is_active: true,
          sort_order: field.options.length,
        },
      ],
    }));
  }

  function updateFieldOption(
    fieldIndex: number,
    optionIndex: number,
    updater: (
      option: ProductOrderFieldOption,
    ) => ProductOrderFieldOption,
  ) {
    updateOrderField(fieldIndex, (field) => ({
      ...field,
      options: field.options.map(
        (option, currentOptionIndex) =>
          currentOptionIndex === optionIndex
            ? updater(option)
            : option,
      ),
    }));
  }

  function removeFieldOption(
    fieldIndex: number,
    optionIndex: number,
  ) {
    updateOrderField(fieldIndex, (field) => ({
      ...field,
      options: field.options
        .filter(
          (_, currentOptionIndex) =>
            currentOptionIndex !== optionIndex,
        )
        .map((option, currentOptionIndex) => ({
          ...option,
          sort_order: currentOptionIndex,
        })),
    }));
  }

  function validateStep(step: number) {
    if (step === 1) {
      if (
        !productForm.name.trim() ||
        !productForm.slug.trim()
      ) {
        setStepMessage(
          "Add a product name and product link to continue.",
        );
        return false;
      }
    }

    if (step === 2) {
      if (
        productForm.allowed_fulfillment_methods.length ===
        0
      ) {
        setStepMessage(
          "Choose at least one way customers can receive this.",
        );
        return false;
      }
    }

    if (step === 3) {
      const invalidFieldIndex =
        productForm.order_fields.findIndex(
          (field) =>
            !field.label.trim() ||
            (
              isChoiceField(field.field_type) &&
              (
                field.options.length === 0 ||
                field.options.some(
                  (option) => !option.label.trim(),
                )
              )
            ),
        );

      if (invalidFieldIndex >= 0) {
        setExpandedFieldIndex(invalidFieldIndex);
        setStepMessage(
          "Finish the highlighted customer question to continue.",
        );
        return false;
      }
    }

    if (step === 4) {
      const price = Number(productForm.price);

      if (
        !productForm.price.trim() ||
        !Number.isFinite(price) ||
        price <= 0
      ) {
        setStepMessage(
          "Enter a valid product price to continue.",
        );
        return false;
      }
    }

    setStepMessage("");
    return true;
  }

  function goToStep(nextStep: number) {
    if (
      nextStep > activeStep &&
      !validateStep(activeStep)
    ) {
      return;
    }

    setActiveStep(
      Math.max(1, Math.min(4, nextStep)),
    );
    setStepMessage("");
    scrollFormIntoView();
  }

  async function handleFormSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (activeStep < 4) {
      goToStep(activeStep + 1);
      return;
    }

    if (!validateStep(4) || isSubmitting) {
      return;
    }

    setIsSubmitting(true);

    try {
      await saveProduct(event);
    } finally {
      setIsSubmitting(false);
    }
  }

  function getAvailabilityCopy(
    productType: ProductType,
  ) {
    if (
      productType === "physical" ||
      productType === "food"
    ) {
      return {
        label: "Stock available",
        cardLabel: "Stock",
        placeholder: "e.g. 25",
        help: "Leave blank if stock is unlimited.",
      };
    }

    if (
      productType === "service" ||
      productType === "booking"
    ) {
      return {
        label: "Available slots",
        cardLabel: "Slots",
        placeholder: "e.g. 10",
        help: "Leave blank if bookings are unlimited.",
      };
    }

    if (
      productType === "digital" ||
      productType === "subscription"
    ) {
      return {
        label: "Sales limit",
        cardLabel: "Sales limit",
        placeholder: "e.g. 100",
        help: "Leave blank if sales are unlimited.",
      };
    }

    return {
      label: "Order limit",
      cardLabel: "Order limit",
      placeholder: "e.g. 20",
      help: "Leave blank if orders are unlimited.",
    };
  }

  const availabilityCopy =
    getAvailabilityCopy(productForm.product_type);

  const fulfillmentPrompt =
    productForm.product_type === "service" ||
    productForm.product_type === "booking"
      ? "How will you provide it?"
      : "How will customers get it?";

  return (
    <div className="products-layout premium-products-page product-wizard-page">
      {!formIsOpen && (
        <div className="product-toolbar compact-product-toolbar">
          <div>
            <h2>Products</h2>
            <p>Manage what you sell.</p>
          </div>

          <button
            type="button"
            className="product-create-trigger"
            onClick={() => setIsProductFormOpen(true)}
          >
            Add product
          </button>
        </div>
      )}

      {formIsOpen && (
        <form
          ref={formRef}
          className="product-form premium-product-form conversational-product-form product-step-form"
          onSubmit={handleFormSubmit}
        >
          <div className="form-section-title conversational-form-heading product-wizard-heading">
            <div>
              <span className="section-kicker">
                {editingProductId
                  ? "Editing product"
                  : "New product"}{" "}
                · Step {activeStep} of 4
              </span>
              <h2>
                {editingProductId
                  ? "Edit product"
                  : "Add a product"}
              </h2>
              <p>
                Complete four short steps to make this
                product ready for customers.
              </p>
            </div>

            <button
              type="button"
              className="product-form-close-button"
              onClick={requestCloseForm}
            >
              Close
            </button>
          </div>

          <div
            className="product-wizard-progress"
            aria-label={`Step ${activeStep} of 4`}
          >
            {[1, 2, 3, 4].map((step) => (
              <span
                key={step}
                className={
                  step < activeStep
                    ? "complete"
                    : step === activeStep
                      ? "current"
                      : ""
                }
              />
            ))}
          </div>

          {stepMessage && (
            <div
              className="product-step-message"
              role="alert"
            >
              {stepMessage}
            </div>
          )}

          {isProductLimitReachedForCreate() && (
            <div className="product-limit-warning">
              <strong>Product limit reached</strong>
              <p>{getProductLimitReachedMessage()}</p>
            </div>
          )}

          {activeStep === 1 && (
            <section className="product-config-section active-product-step">
              <div className="product-config-section-head">
                <div>
                  <h3>Product details</h3>
                  <p>
                    Add the information customers will
                    see in your store.
                  </p>
                </div>
              </div>

              <div className="product-config-grid product-config-grid-two">
                <label>
                  Product name
                  <input
                    value={productForm.name}
                    onChange={(event) => {
                      const name = event.target.value;

                      setProductForm((previous) => ({
                        ...previous,
                        name,
                        slug: editingProductId
                          ? previous.slug
                          : makeSlug(name),
                      }));
                    }}
                    placeholder="e.g. Premium Canvas Tote"
                    required
                  />
                </label>

                <label>
                  Product link
                  <div className="product-slug-input single-border-input">
                    <span aria-hidden="true">/</span>
                    <input
                      value={productForm.slug}
                      onChange={(event) =>
                        setProductForm((previous) => ({
                          ...previous,
                          slug: makeSlug(
                            event.target.value,
                          ),
                        }))
                      }
                      placeholder="premium-canvas-tote"
                      required
                    />
                  </div>
                </label>
              </div>

              <label>
                Description
                <textarea
                  value={productForm.description}
                  onChange={(event) =>
                    setProductForm((previous) => ({
                      ...previous,
                      description: event.target.value,
                    }))
                  }
                  placeholder="Describe what the customer will receive."
                />
              </label>

              <label
                className={
                  "upload-dropzone " +
                  (
                    subscriptionUsage
                      ?.can_upload_images === false
                      ? "disabled"
                      : ""
                  )
                }
              >
                <input
                  className="upload-file-input"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={
                    uploadingProductImage ||
                    loadingSubscriptionUsage ||
                    subscriptionUsage
                      ?.can_upload_images === false
                  }
                  onChange={(event) => {
                    const file =
                      event.target.files?.[0];

                    if (file) {
                      void uploadProductImage(file);
                    }
                  }}
                />

                <span className="upload-icon">+</span>
                <span>
                  <strong>
                    {uploadingProductImage
                      ? "Uploading image..."
                      : "Upload product image"}
                  </strong>
                  <small>
                    JPEG, PNG, or WEBP · maximum 3MB
                  </small>
                </span>
              </label>

              {subscriptionUsage
                ?.can_upload_images === false && (
                <p className="plan-restriction-note">
                  Image uploads are unavailable on your
                  current plan.
                </p>
              )}

              {productPreviewUrl && (
                <div className="uploaded-image-preview conversational-image-preview">
                  <img
                    src={productPreviewUrl}
                    alt="Product preview"
                  />
                  <div>
                    <strong>Image ready</strong>
                    <p>
                      This is how the image will appear
                      in your store.
                    </p>
                  </div>
                </div>
              )}
            </section>
          )}

          {activeStep === 2 && (
            <section className="product-config-section active-product-step">
              <div className="product-config-section-head">
                <div>
                  <h3>Order setup</h3>
                  <p>
                    Choose what you sell and how customers
                    will receive it.
                  </p>
                </div>
              </div>

              <div className="product-type-grid compact-product-type-grid">
                {PRODUCT_TYPES.map((productType) => (
                  <button
                    key={productType.value}
                    type="button"
                    className={
                      productForm.product_type ===
                      productType.value
                        ? "product-type-card selected"
                        : "product-type-card"
                    }
                    onClick={() =>
                      applyProductType(productType.value)
                    }
                    aria-pressed={
                      productForm.product_type ===
                      productType.value
                    }
                  >
                    <strong>{productType.label}</strong>
                  </button>
                ))}
              </div>

              <div className="selected-product-type-note">
                <strong>{selectedProductType.label}</strong>
                <p>{selectedProductType.description}</p>
              </div>

              <div className="fulfillment-config-panel compact-fulfillment-panel">
                <div className="fulfillment-config-copy">
                  <span className="config-label">
                    {fulfillmentPrompt}
                  </span>
                  <p>
                    We selected the most common options.
                    Change them to match your business.
                  </p>
                </div>

                <div className="fulfillment-choice-grid compact-fulfillment-grid">
                  {recommendedFulfillmentMethods.map(
                    (method) => {
                      const checked =
                        productForm
                          .allowed_fulfillment_methods
                          .includes(method);

                      return (
                        <label
                          key={method}
                          className={
                            checked
                              ? "fulfillment-choice selected"
                              : "fulfillment-choice"
                          }
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) =>
                              toggleFulfillmentMethod(
                                method,
                                event.target.checked,
                              )
                            }
                          />
                          <span>
                            {formatFulfillmentMethod(method)}
                          </span>
                        </label>
                      );
                    },
                  )}
                </div>

                <details className="fulfillment-more-options">
                  <summary>
                    {additionalSelectedCount === 0
                      ? "Other options"
                      : `Other options · ${additionalSelectedCount} selected`}
                  </summary>

                  <div className="fulfillment-choice-grid compact-fulfillment-grid">
                    {additionalFulfillmentMethods.map(
                      (method) => {
                        const checked =
                          productForm
                            .allowed_fulfillment_methods
                            .includes(method);

                        return (
                          <label
                            key={method}
                            className={
                              checked
                                ? "fulfillment-choice selected"
                                : "fulfillment-choice"
                            }
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(event) =>
                                toggleFulfillmentMethod(
                                  method,
                                  event.target.checked,
                                )
                              }
                            />
                            <span>
                              {formatFulfillmentMethod(
                                method,
                              )}
                            </span>
                          </label>
                        );
                      },
                    )}
                  </div>
                </details>

                <label className="default-fulfillment-select">
                  Selected by default
                  <select
                    value={
                      productForm
                        .default_fulfillment_method
                    }
                    onChange={(event) =>
                      setProductForm((previous) => ({
                        ...previous,
                        default_fulfillment_method:
                          event.target
                            .value as FulfillmentMethod,
                      }))
                    }
                  >
                    {productForm
                      .allowed_fulfillment_methods
                      .map((method) => (
                        <option
                          key={method}
                          value={method}
                        >
                          {formatFulfillmentMethod(method)}
                        </option>
                      ))}
                  </select>
                  <small>
                    Customers can change this when ordering.
                  </small>
                </label>
              </div>
            </section>
          )}

          {activeStep === 3 && (
            <section className="product-config-section active-product-step">
              <div className="product-config-section-head product-config-section-head-actions">
                <div>
                  <h3>Customer options</h3>
                  <p>
                    Add size, colour, date, or other details
                    customers must choose.
                  </p>
                </div>

                <button
                  type="button"
                  className="order-field-add-button"
                  onClick={addBlankOrderField}
                >
                  + Add a question
                </button>
              </div>

              {recommendedQuickFields.length > 0 && (
                <div className="smart-option-recommendation">
                  <div className="smart-option-recommendation-copy">
                    <span>
                      Recommended for{" "}
                      {productForm.name.trim() ||
                        "this product"}
                    </span>
                    <p>
                      Suggestions only. Add the exact
                      options you sell and set an extra
                      charge only when needed.
                    </p>
                  </div>

                  <div className="smart-option-recommendation-actions">
                    {recommendedQuickFields.map(
                      (quickField) => (
                        <button
                          key={quickField.label}
                          type="button"
                          onClick={() =>
                            addQuickField(quickField)
                          }
                        >
                          + {quickField.label}
                        </button>
                      ),
                    )}
                  </div>
                </div>
              )}

              <div className="quick-field-bar compact-quick-field-bar">
                <span>
                  {recommendedQuickFields.length > 0
                    ? "Other common options"
                    : "Popular options"}
                </span>
                <div>
                  {otherQuickFields.map((quickField) => (
                    <button
                      key={quickField.label}
                      type="button"
                      onClick={() =>
                        addQuickField(quickField)
                      }
                    >
                      + {quickField.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="order-field-safety-note compact-safety-note">
                <strong>Protect your customers</strong>
                <p>
                  Never ask for passwords, PINs, OTPs, or
                  card details.
                </p>
              </div>

              {productForm.order_fields.length === 0 ? (
                <div className="order-fields-empty-state">
                  <span>0</span>
                  <div>
                    <strong>No customer options added</strong>
                    <p>
                      Add an option only when customers
                      need to choose something before
                      ordering.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="order-field-builder-list collapsed-question-list">
                  {productForm.order_fields.map(
                    (field, fieldIndex) => {
                      const isExpanded =
                        expandedFieldIndex === fieldIndex;
                      const optionCount =
                        isChoiceField(field.field_type)
                          ? field.options.length
                          : 0;

                      const configuredOptionLabels =
                        isChoiceField(field.field_type)
                          ? field.options
                              .map((option) =>
                                option.label.trim(),
                              )
                              .filter(Boolean)
                          : [];

                      const hasIncompleteChoices =
                        isChoiceField(field.field_type) &&
                        field.options.some(
                          (option) => !option.label.trim(),
                        );

                      const visibleOptionLabels =
                        configuredOptionLabels.slice(0, 4);

                      const hiddenOptionCount =
                        configuredOptionLabels.length -
                        visibleOptionLabels.length;

                      return (
                        <article
                          className={
                            isExpanded
                              ? "order-field-builder-card expanded"
                              : "order-field-builder-card collapsed"
                          }
                          key={`order-field-${fieldIndex}`}
                        >
                          <div className="question-summary-row">
                            <div>
                              <span className="order-field-index">
                                Question {fieldIndex + 1}
                              </span>
                              <strong>
                                {field.label || "New question"}
                              </strong>
                              <small>
                                {field.is_required
                                  ? "Required"
                                  : "Optional"}
                                {isChoiceField(
                                  field.field_type,
                                )
                                  ? hasIncompleteChoices
                                    ? " · Finish choices"
                                    : ` · ${optionCount} ${
                                        optionCount === 1
                                          ? "choice"
                                          : "choices"
                                      }`
                                  : ""}
                              </small>

                              {visibleOptionLabels.length > 0 && (
                                <small className="question-choice-preview">
                                  Choices:{" "}
                                  {visibleOptionLabels.join(", ")}
                                  {hiddenOptionCount > 0
                                    ? ` +${hiddenOptionCount} more`
                                    : ""}
                                </small>
                              )}
                            </div>

                            <button
                              type="button"
                              className="question-edit-button"
                              onClick={() =>
                                setExpandedFieldIndex(
                                  isExpanded
                                    ? null
                                    : fieldIndex,
                                )
                              }
                            >
                              {isExpanded ? "Done" : "Edit"}
                            </button>
                          </div>

                          {isExpanded && (
                            <div className="question-editor-body">
                              <div className="question-editor-actions">
                                <div>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      moveOrderField(
                                        fieldIndex,
                                        -1,
                                      )
                                    }
                                    disabled={fieldIndex === 0}
                                    aria-label="Move question up"
                                  >
                                    ↑
                                  </button>

                                  <button
                                    type="button"
                                    onClick={() =>
                                      moveOrderField(
                                        fieldIndex,
                                        1,
                                      )
                                    }
                                    disabled={
                                      fieldIndex ===
                                      productForm
                                        .order_fields
                                        .length -
                                        1
                                    }
                                    aria-label="Move question down"
                                  >
                                    ↓
                                  </button>
                                </div>

                                <button
                                  type="button"
                                  className="order-field-remove-button"
                                  onClick={() =>
                                    removeOrderField(
                                      fieldIndex,
                                    )
                                  }
                                >
                                  Remove question
                                </button>
                              </div>

                              <div className="order-field-grid">
                                <label>
                                  What should we ask?
                                  <input
                                    value={field.label}
                                    onChange={(event) => {
                                      const nextLabel =
                                        event.target.value;

                                      updateOrderField(
                                        fieldIndex,
                                        (
                                          currentField,
                                        ) => {
                                          const previousGeneratedKey =
                                            makeFieldKey(
                                              currentField.label,
                                            );

                                          const shouldRefreshKey =
                                            !currentField.key ||
                                            currentField.key ===
                                              previousGeneratedKey;

                                          return {
                                            ...currentField,
                                            label: nextLabel,
                                            key: shouldRefreshKey
                                              ? makeUniqueFieldKey(
                                                  nextLabel ||
                                                    `field_${
                                                      fieldIndex +
                                                      1
                                                    }`,
                                                  productForm
                                                    .order_fields
                                                    .filter(
                                                      (
                                                        _,
                                                        currentIndex,
                                                      ) =>
                                                        currentIndex !==
                                                        fieldIndex,
                                                    ),
                                                )
                                              : currentField.key,
                                          };
                                        },
                                      );
                                    }}
                                    placeholder="e.g. Shoe size"
                                    required
                                  />
                                </label>

                                <label>
                                  How should customers answer?
                                  <select
                                    value={field.field_type}
                                    onChange={(event) => {
                                      const nextType =
                                        event.target
                                          .value as ProductOrderFieldType;

                                      updateOrderField(
                                        fieldIndex,
                                        (
                                          currentField,
                                        ) => ({
                                          ...currentField,
                                          field_type:
                                            nextType,
                                          validation_rules:
                                            normalizeValidationRulesForFieldType(
                                              nextType,
                                              currentField.validation_rules,
                                            ),
                                          options:
                                            isChoiceField(
                                              nextType,
                                            )
                                              ? currentField
                                                  .options
                                                  .length > 0
                                                ? currentField
                                                    .options
                                                : [
                                                    {
                                                      value:
                                                        "option-1",
                                                      label: "",
                                                      price_adjustment:
                                                        "0.00",
                                                      is_active:
                                                        true,
                                                      sort_order:
                                                        0,
                                                    },
                                                  ]
                                              : [],
                                        }),
                                      );
                                    }}
                                  >
                                    {FIELD_TYPES.map(
                                      (fieldType) => (
                                        <option
                                          key={
                                            fieldType.value
                                          }
                                          value={
                                            fieldType.value
                                          }
                                        >
                                          {fieldType.label}
                                        </option>
                                      ),
                                    )}
                                  </select>
                                </label>
                              </div>

                              {isChoiceField(
                                field.field_type,
                              ) && (
                                <div className="order-option-editor compact-option-editor">
                                  <div className="order-option-editor-head">
                                    <div>
                                      <strong>
                                        Available choices
                                      </strong>
                                      <p>
                                        Add an extra charge
                                        only when a choice
                                        costs more.
                                      </p>
                                    </div>

                                    <button
                                      type="button"
                                      onClick={() =>
                                        addFieldOption(
                                          fieldIndex,
                                        )
                                      }
                                    >
                                      + Add choice
                                    </button>
                                  </div>

                                  <div className="order-option-list">
                                    {field.options.map(
                                      (
                                        option,
                                        optionIndex,
                                      ) => (
                                        <div
                                          className="order-option-row"
                                          key={`order-option-${fieldIndex}-${optionIndex}`}
                                        >
                                          <label>
                                            Choice name
                                            <input
                                              value={
                                                option.label
                                              }
                                              onChange={(
                                                event,
                                              ) => {
                                                const nextLabel =
                                                  event
                                                    .target
                                                    .value;

                                                updateFieldOption(
                                                  fieldIndex,
                                                  optionIndex,
                                                  (
                                                    currentOption,
                                                  ) => {
                                                    const previousGeneratedValue =
                                                      makeOptionValue(
                                                        currentOption.label,
                                                      );

                                                    const shouldRefreshValue =
                                                      !currentOption.value ||
                                                      currentOption.value ===
                                                        previousGeneratedValue ||
                                                      /^option-\d+$/.test(
                                                        currentOption.value,
                                                      );

                                                    return {
                                                      ...currentOption,
                                                      label:
                                                        nextLabel,
                                                      value:
                                                        shouldRefreshValue
                                                          ? makeOptionValue(
                                                              nextLabel,
                                                            ) ||
                                                            `option-${
                                                              optionIndex +
                                                              1
                                                            }`
                                                          : currentOption.value,
                                                    };
                                                  },
                                                );
                                              }}
                                              placeholder="e.g. Large"
                                              required
                                            />
                                          </label>

                                          <label>
                                            Extra charge
                                            <div className="price-adjustment-input clean-input-group">
                                              <span>GHS</span>
                                              <input
                                                type="number"
                                                min="0"
                                                step="0.01"
                                                inputMode="decimal"
                                                value={
                                                  option
                                                    .price_adjustment
                                                }
                                                onChange={(
                                                  event,
                                                ) =>
                                                  updateFieldOption(
                                                    fieldIndex,
                                                    optionIndex,
                                                    (
                                                      currentOption,
                                                    ) => ({
                                                      ...currentOption,
                                                      price_adjustment:
                                                        event
                                                          .target
                                                          .value,
                                                    }),
                                                  )
                                                }
                                              />
                                            </div>
                                          </label>

                                          <button
                                            type="button"
                                            className="order-option-remove-button"
                                            onClick={() =>
                                              removeFieldOption(
                                                fieldIndex,
                                                optionIndex,
                                              )
                                            }
                                            disabled={
                                              field.options
                                                .length === 1
                                            }
                                          >
                                            Remove
                                          </button>
                                        </div>
                                      ),
                                    )}
                                  </div>
                                </div>
                              )}

                              <div className="question-policy-list">
                                <label className="simple-check-row">
                                  <input
                                    type="checkbox"
                                    checked={
                                      field.is_required
                                    }
                                    onChange={(event) =>
                                      updateOrderField(
                                        fieldIndex,
                                        (
                                          currentField,
                                        ) => ({
                                          ...currentField,
                                          is_required:
                                            event.target
                                              .checked,
                                        }),
                                      )
                                    }
                                  />
                                  <span>
                                    <strong>
                                      Required question
                                    </strong>
                                    <small>
                                      Customers must answer
                                      before ordering.
                                    </small>
                                  </span>
                                </label>

                                <label className="simple-check-row">
                                  <input
                                    type="checkbox"
                                    checked={field.is_sensitive}
                                    onChange={(event) =>
                                      updateOrderField(
                                        fieldIndex,
                                        (
                                          currentField,
                                        ) => ({
                                          ...currentField,
                                          is_sensitive:
                                            event.target
                                              .checked,
                                          include_in_whatsapp:
                                            event.target
                                              .checked
                                              ? false
                                              : currentField
                                                  .include_in_whatsapp,
                                        }),
                                      )
                                    }
                                  />
                                  <span>
                                    <strong>
                                      Sensitive answer
                                    </strong>
                                    <small>
                                      Keep this answer private.
                                      It stays out of WhatsApp
                                      and remains collapsed in
                                      order details until opened.
                                    </small>
                                  </span>
                                </label>

                                <label className="simple-check-row">
                                  <input
                                    type="checkbox"
                                    checked={
                                      field.include_in_whatsapp
                                    }
                                    disabled={field.is_sensitive}
                                    onChange={(event) =>
                                      updateOrderField(
                                        fieldIndex,
                                        (
                                          currentField,
                                        ) => ({
                                          ...currentField,
                                          include_in_whatsapp:
                                            event.target
                                              .checked,
                                        }),
                                      )
                                    }
                                  />
                                  <span>
                                    <strong>
                                      Include answer in
                                      WhatsApp summary
                                    </strong>
                                    <small>
                                      {field.is_sensitive
                                        ? "Sensitive answers stay in StorePlug and cannot be included in WhatsApp."
                                        : "Turn this off to keep the answer in StorePlug only."}
                                    </small>
                                  </span>
                                </label>
                              </div>

                              <details className="question-more-settings">
                                <summary>
                                  More settings
                                </summary>

                                <div>
                                  <label>
                                    Example answer
                                    <input
                                      value={
                                        field.placeholder
                                      }
                                      onChange={(event) =>
                                        updateOrderField(
                                          fieldIndex,
                                          (
                                            currentField,
                                          ) => ({
                                            ...currentField,
                                            placeholder:
                                              event.target
                                                .value,
                                          }),
                                        )
                                      }
                                      placeholder="Optional example"
                                    />
                                  </label>

                                  <label>
                                    Helpful note
                                    <input
                                      value={
                                        field.help_text
                                      }
                                      onChange={(event) =>
                                        updateOrderField(
                                          fieldIndex,
                                          (
                                            currentField,
                                          ) => ({
                                            ...currentField,
                                            help_text:
                                              event.target
                                                .value,
                                          }),
                                        )
                                      }
                                      placeholder="Optional guidance for customers"
                                    />
                                  </label>
                                </div>
                              </details>
                            </div>
                          )}
                        </article>
                      );
                    },
                  )}
                </div>
              )}
            </section>
          )}

          {activeStep === 4 && (
            <section className="product-config-section active-product-step">
              <div className="product-config-section-head">
                <div>
                  <h3>Price and availability</h3>
                  <p>
                    Set the price and decide how this
                    product appears in your store.
                  </p>
                </div>
              </div>

              <div className="two-cols conversational-price-grid">
                <label>
                  Base price
                  <div className="price-adjustment-input product-base-price-input single-border-input">
                    <span aria-hidden="true">GHS</span>
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={productForm.price}
                      onChange={(event) =>
                        setProductForm(
                          (previous) => ({
                            ...previous,
                            price:
                              event.target.value,
                          }),
                        )
                      }
                      placeholder="150.00"
                      required
                    />
                  </div>
                </label>

                <label>
                  {availabilityCopy.label}
                  <input
                    type="number"
                    min="0"
                    value={
                      productForm.stock_quantity
                    }
                    onChange={(event) =>
                      setProductForm(
                        (previous) => ({
                          ...previous,
                          stock_quantity:
                            event.target.value,
                        }),
                      )
                    }
                    placeholder={
                      availabilityCopy.placeholder
                    }
                  />
                  <small>
                    {availabilityCopy.help}
                  </small>
                </label>
              </div>

              <div className="checks premium-switches conversational-switches">
                <label className="premium-switch-row">
                  <input
                    type="checkbox"
                    checked={productForm.is_active}
                    onChange={(event) =>
                      setProductForm(
                        (previous) => ({
                          ...previous,
                          is_active:
                            event.target.checked,
                        }),
                      )
                    }
                  />

                  <span
                    className={
                      "premium-switch " +
                      (
                        productForm.is_active
                          ? "on"
                          : ""
                      )
                    }
                  >
                    <span />
                  </span>

                  <span>
                    <strong>Show in store</strong>
                    <small>
                      Customers can see and order this
                      product.
                    </small>
                  </span>
                </label>

                <label className="premium-switch-row">
                  <input
                    type="checkbox"
                    checked={productForm.is_featured}
                    onChange={(event) =>
                      setProductForm(
                        (previous) => ({
                          ...previous,
                          is_featured:
                            event.target.checked,
                        }),
                      )
                    }
                  />

                  <span
                    className={
                      "premium-switch " +
                      (
                        productForm.is_featured
                          ? "on"
                          : ""
                      )
                    }
                  >
                    <span />
                  </span>

                  <span>
                    <strong>
                      Feature this product
                    </strong>
                    <small>
                      Give it more visibility in your
                      store.
                    </small>
                  </span>
                </label>
              </div>
            </section>
          )}

          <div className="product-wizard-actions">
            {activeStep > 1 ? (
              <button
                type="button"
                className="wizard-back-button"
                onClick={() =>
                  goToStep(activeStep - 1)
                }
              >
                Back
              </button>
            ) : (
              <button
                type="button"
                className="wizard-cancel-button"
                onClick={requestCloseForm}
              >
                Cancel
              </button>
            )}

            {activeStep < 4 ? (
              <button
                type="button"
                className="wizard-next-button"
                onClick={() =>
                  goToStep(activeStep + 1)
                }
              >
                Continue
              </button>
            ) : (
              <button
                type="submit"
                className="wizard-next-button"
                disabled={
                  isProductSubmitDisabled() ||
                  isSubmitting
                }
              >
                {isSubmitting
                  ? "Saving..."
                  : getProductSubmitLabel()}
              </button>
            )}
          </div>
        </form>
      )}

      <div className="product-list premium-product-list">
        {products.length === 0 && (
          <div className="empty-product-state">
            <h3>No products yet</h3>
            <p>
              Add your first product to start selling
              from your store.
            </p>
          </div>
        )}

        {products.map((product) => {
          const defaultMethod =
            product.default_fulfillment_method ||
            "seller_confirmation";

          const orderFieldCount =
            product.order_fields?.length ?? 0;

          const cardAvailability =
            getAvailabilityCopy(product.product_type);

          return (
            <article
              className="product-card premium-product-card conversational-product-card compact-product-card"
              key={product.id}
            >
              <div className="product-card-top">
                <ProductThumbnail product={product} />

                <div className="product-main-info">
                  <div className="product-title-row">
                    <div>
                      <h3>{product.name}</h3>
                      <p className="product-slug">
                        /{product.slug}
                      </p>
                    </div>

                    <div className="product-card-status">
                      <span
                        className={
                          "pill product-status-pill " +
                          (
                            product.is_active
                              ? "active-pill"
                              : "inactive-pill"
                          )
                        }
                      >
                        {product.is_active
                          ? "In store"
                          : "Hidden"}
                      </span>

                      {product.is_featured && (
                        <span className="pill featured-pill">
                          Featured
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {product.description && (
                <p className="product-desc">
                  {product.description}
                </p>
              )}

              <div className="product-card-summary">
                <div className="product-card-summary-primary">
                  <span>
                    {formatProductType(
                      product.product_type,
                    )}
                  </span>
                  <span aria-hidden="true">·</span>
                  <span>
                    {formatFulfillmentMethod(
                      defaultMethod,
                    )}
                  </span>
                </div>
                <span className="product-card-summary-secondary">
                  {orderFieldCount === 0
                    ? "No options"
                    : `${orderFieldCount} ${
                        orderFieldCount === 1
                          ? "option"
                          : "options"
                      }`}
                </span>
              </div>

              <div className="product-card-stats">
                <div>
                  <span>Price</span>
                  <strong>
                    GHS{" "}
                    {Number(product.price).toFixed(2)}
                  </strong>
                </div>

                <div>
                  <span>
                    {cardAvailability.cardLabel}
                  </span>
                  <strong>
                    {product.stock_quantity ??
                      "Unlimited"}
                  </strong>
                </div>
              </div>

              <div className="product-card-actions product-card-actions-compact">
                <button
                  type="button"
                  className="product-action-btn product-edit-btn"
                  onClick={() => {
                    setOpenProductActionsId(null);
                    startEditingProduct(product);
                  }}
                >
                  Edit
                </button>

                <button
                  type="button"
                  className="product-action-btn product-more-actions-trigger"
                  aria-expanded={
                    openProductActionsId === product.id
                  }
                  aria-controls={`product-actions-${product.id}`}
                  onClick={() => {
                    setOpenProductActionsId(
                      (currentProductId) =>
                        currentProductId ===
                        product.id
                          ? null
                          : product.id,
                    );
                  }}
                >
                  {openProductActionsId === product.id
                    ? "Less"
                    : "More"}
                  <span aria-hidden="true">
                    {openProductActionsId === product.id
                      ? "↑"
                      : "•••"}
                  </span>
                </button>

                {openProductActionsId === product.id && (
                  <div
                    className="product-more-actions-panel"
                    id={`product-actions-${product.id}`}
                  >
                    <button
                      type="button"
                      className="product-action-btn"
                      onClick={() => {
                        setOpenProductActionsId(null);
                        void toggleProductActive(
                          product,
                        );
                      }}
                    >
                      {product.is_active
                        ? "Hide from store"
                        : "Show in store"}
                    </button>

                    <button
                      type="button"
                      className="product-action-btn danger"
                      onClick={() => {
                        setOpenProductActionsId(null);
                        void deleteProduct(product);
                      }}
                    >
                      Remove product
                    </button>
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
