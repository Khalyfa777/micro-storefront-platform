import type { Dispatch, FormEvent, SetStateAction } from "react";

type Product = any;
type ProductForm = any;
type StoreSubscriptionUsage = any;

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
  return (
          <div className="products-layout premium-products-page">
            <div className="product-toolbar">
              <div>
                <span className="section-kicker">Inventory</span>
                <h2>Products</h2>
                <p>Manage listings, pricing, stock, and visibility.</p>
              </div>

              <button
                type="button"
                className="product-create-trigger"
                onClick={() => {
                  if (isProductFormOpen || editingProductId) {
                    cancelProductEdit();
                    return;
                  }

                  setIsProductFormOpen(true);
                }}
              >
                {isProductFormOpen || editingProductId ? "Close form" : "Add product"}
              </button>
            </div>

            {(isProductFormOpen || editingProductId) && (
              <form className="product-form premium-product-form" onSubmit={saveProduct}>
                <div className="form-section-title">
                  <h2>{editingProductId ? "Edit product" : "Add product"}</h2>
                  <p>{editingProductId ? "Update this listing." : "Create a new storefront listing."}</p>
                </div>

                {isProductLimitReachedForCreate() && (
                  <div className="product-limit-warning">
                    <strong>Product limit reached</strong>
                    <p>{getProductLimitReachedMessage()}</p>
                  </div>
                )}

                <label>
                  Product name
                  <input
                    value={productForm.name}
                    onChange={(e) => {
                      const name = e.target.value;
                      setProductForm((prev: ProductForm) => ({
                        ...prev,
                        name,
                        slug: editingProductId ? prev.slug : makeSlug(name),
                      }));
                    }}
                    placeholder="Nike Dunk Low"
                    required
                  />
                </label>

                <label>
                  Slug
                  <input
                    value={productForm.slug}
                    onChange={(e) =>
                      setProductForm((prev: ProductForm) => ({
                        ...prev,
                        slug: makeSlug(e.target.value),
                      }))
                    }
                    placeholder="nike-dunk-low"
                    required
                  />
                </label>

                <label>
                  Description
                  <textarea
                    value={productForm.description}
                    onChange={(e) =>
                      setProductForm((prev: ProductForm) => ({
                        ...prev,
                        description: e.target.value,
                      }))
                    }
                    placeholder="Short product description"
                  />
                </label>

                <label className={"upload-dropzone " + (subscriptionUsage?.can_upload_images === false ? "disabled" : "")}>
                  <input
                    className="upload-file-input"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={uploadingProductImage || loadingSubscriptionUsage || subscriptionUsage?.can_upload_images === false}
                    onChange={(e) => {
                      const file = e.target.files?.[0];

                      if (file) {
                        uploadProductImage(file);
                      }
                    }}
                  />

                  <span className="upload-icon">+</span>
                  <span>
                    <strong>{uploadingProductImage ? "Uploading image..." : "Upload product image"}</strong>
                    <small>JPEG, PNG, or WEBP</small>
                  </span>
                </label>

                {subscriptionUsage?.can_upload_images === false && (
                  <p className="plan-restriction-note">
                    Image uploads are disabled on your current plan. Upgrade to enable product images.
                  </p>
                )}

                {productForm.image_url && (
                  <div className="uploaded-image-preview">
                    <img src={productForm.image_url} alt="Product preview" />
                    <p>Image uploaded successfully</p>
                  </div>
                )}

                <div className="two-cols">
                  <label>
                    Price
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={productForm.price}
                      onChange={(e) =>
                        setProductForm((prev: ProductForm) => ({
                          ...prev,
                          price: e.target.value,
                        }))
                      }
                      placeholder="850"
                      required
                    />
                  </label>

                  <label>
                    Stock
                    <input
                      type="number"
                      min="0"
                      value={productForm.stock_quantity}
                      onChange={(e) =>
                        setProductForm((prev: ProductForm) => ({
                          ...prev,
                          stock_quantity: e.target.value,
                        }))
                      }
                      placeholder="10"
                    />
                  </label>
                </div>

                <div className="checks premium-switches">
                  <label className="premium-switch-row">
                    <input
                      type="checkbox"
                      checked={productForm.is_active}
                      onChange={(e) =>
                        setProductForm((prev: ProductForm) => ({
                          ...prev,
                          is_active: e.target.checked,
                        }))
                      }
                    />
                    <span className={"premium-switch " + (productForm.is_active ? "on" : "")}>
                      <span></span>
                    </span>
                    <span>
                      <strong>Active</strong>
                      <small>Show on public store</small>
                    </span>
                  </label>

                  <label className="premium-switch-row">
                    <input
                      type="checkbox"
                      checked={productForm.is_featured}
                      onChange={(e) =>
                        setProductForm((prev: ProductForm) => ({
                          ...prev,
                          is_featured: e.target.checked,
                        }))
                      }
                    />
                    <span className={"premium-switch " + (productForm.is_featured ? "on" : "")}>
                      <span></span>
                    </span>
                    <span>
                      <strong>Featured</strong>
                      <small>Highlight product</small>
                    </span>
                  </label>
                </div>

                <div className="form-actions premium-form-actions">
                  <button type="submit" disabled={isProductSubmitDisabled()}>
                    {getProductSubmitLabel()}
                  </button>

                  {(editingProductId || isProductFormOpen) && (
                    <button type="button" className="secondary-form-btn" onClick={cancelProductEdit}>
                      Cancel
                    </button>
                  )}
                </div>
              </form>
            )}

            <div className="product-list premium-product-list">
              {products.length === 0 && (
                <div className="empty-product-state">
                  <h3>No products yet</h3>
                  <p>Add your first product to start selling from your storefront.</p>
                </div>
              )}

              {products.map((product) => (
                <article className="product-card premium-product-card" key={product.id}>
                  <div className="product-card-top">
                    <div className="product-thumb-box">
                      {product.image_url ? (
                        <img src={product.image_url} alt={product.name} />
                      ) : (
                        <span>{product.name.slice(0, 1).toUpperCase()}</span>
                      )}
                    </div>

                    <div className="product-main-info">
                      <div className="product-title-row">
                        <div>
                          <h3>{product.name}</h3>
                          <p className="product-slug">/{product.slug}</p>
                        </div>

                        <div className="product-card-status">
                          <span className={"pill product-status-pill " + (product.is_active ? "active-pill" : "inactive-pill")}>
                            {product.is_active ? "Active" : "Inactive"}
                          </span>

                          {product.is_featured && <span className="pill featured-pill">Featured</span>}
                        </div>
                      </div>

                      {product.description && (
                        <p className="product-desc">{product.description}</p>
                      )}
                    </div>
                  </div>

                  <div className="product-card-stats">
                    <div>
                      <span>Price</span>
                      <strong>GHS {Number(product.price).toFixed(2)}</strong>
                    </div>

                    <div>
                      <span>Stock</span>
                      <strong>{product.stock_quantity ?? "Unlimited"}</strong>
                    </div>
                  </div>

                  <div className="product-card-actions">
                    <button type="button" className="product-action-btn" onClick={() => startEditingProduct(product)}>
                      Edit
                    </button>

                    <button type="button" className="product-action-btn" onClick={() => toggleProductActive(product)}>
                      {product.is_active ? "Deactivate" : "Activate"}
                    </button>

                    <button type="button" className="product-action-btn danger" onClick={() => deleteProduct(product)}>
                      Remove
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
  );
}
