const CART_KEY = "bakewise-cart";

const money = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  minimumFractionDigits: 2,
});

function getPageName() {
  return document.body.dataset.page || "home";
}

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  updateCartCount();
}

function cartCount() {
  return loadCart().reduce((sum, item) => sum + Number(item.quantity || 0), 0);
}

function cartTotal() {
  return loadCart().reduce((sum, item) => sum + Number(item.price || 0) * Number(item.quantity || 0), 0);
}

function updateCartCount() {
  const n = cartCount();
  document.querySelectorAll("[data-cart-count]").forEach((node) => {
    node.textContent = String(n);
  });
  document.querySelectorAll("a.cart-chip").forEach((chip) => {
    chip.setAttribute("aria-label", n === 0 ? "View cart (empty)" : `View cart, ${n} items`);
  });
}

function upsertCartItem(product, delta = 1) {
  const pid = Number(product.product_id);
  const cart = loadCart();
  const current = cart.find((item) => Number(item.product_id) === pid);

  if (current) {
    current.quantity += delta;
    if (current.quantity <= 0) {
      saveCart(cart.filter((item) => Number(item.product_id) !== pid));
      return;
    }
    saveCart(cart);
    return;
  }

  saveCart([
    ...cart,
    {
      product_id: pid,
      name: product.name,
      category: product.category,
      price: Number(product.price || 0),
      image_theme: product.image_theme,
      quantity: Math.max(delta, 1),
    },
  ]);
}

function removeCartItem(productId) {
  const pid = Number(productId);
  saveCart(loadCart().filter((item) => Number(item.product_id) !== pid));
}

function renderCartPage() {
  const emptyEl = document.getElementById("cartEmptyState");
  const mainEl = document.getElementById("cartMain");
  const linesEl = document.getElementById("cartPageLines");
  const totalEl = document.getElementById("cartPageTotal");
  const countEl = document.getElementById("cartPageCount");
  if (!emptyEl || !mainEl || !linesEl) {
    return;
  }

  const cart = loadCart();
  updateCartCount();
  renderProductsPageCart();
  renderCheckoutPage();

  if (cart.length === 0) {
    emptyEl.hidden = false;
    mainEl.hidden = true;
    if (countEl) {
      countEl.textContent = "";
      countEl.hidden = true;
    }
    return;
  }

  emptyEl.hidden = true;
  mainEl.hidden = false;
  if (countEl) {
    countEl.hidden = false;
    countEl.textContent = `${cartCount()} item${cartCount() === 1 ? "" : "s"} in your basket`;
  }

  linesEl.innerHTML = "";
  cart.forEach((item) => {
    const qty = Number(item.quantity || 0);
    const unit = Number(item.price || 0);
    const lineSubtotal = unit * qty;
    const row = document.createElement("article");
    row.className = "cart-line";
    row.setAttribute("role", "listitem");
    row.dataset.productId = String(item.product_id);
    row.innerHTML = `
      <div class="cart-line__cell cart-line__cell--thumb">
        <img src="${createProductImage(item)}" alt="" width="96" height="60" loading="lazy">
      </div>
      <div class="cart-line__cell cart-line__cell--info">
        <h3 class="cart-line__title">${escapeHtml(item.name)}</h3>
        <p class="product-category">${escapeHtml(item.category || "")}</p>
      </div>
      <div class="cart-line__cell cart-line__cell--numeric" data-label="Price">${money.format(unit)}</div>
      <div class="cart-line__cell cart-line__cell--qty" data-label="Quantity">
        <div class="quantity-controls">
          <button type="button" data-action="decrease" aria-label="Decrease quantity">−</button>
          <span class="quantity-controls__value" aria-live="polite">${qty}</span>
          <button type="button" data-action="increase" aria-label="Increase quantity">+</button>
        </div>
      </div>
      <div class="cart-line__cell cart-line__cell--numeric cart-line__subtotal" data-label="Subtotal">${money.format(
        lineSubtotal,
      )}</div>
      <div class="cart-line__cell cart-line__cell--action">
        <button type="button" class="cart-line__remove" data-remove aria-label="Remove ${escapeAttr(item.name)} from cart">Remove</button>
      </div>
    `;
    row.querySelector('[data-action="decrease"]').addEventListener("click", () => {
      upsertCartItem(item, -1);
      renderCartPage();
    });
    row.querySelector('[data-action="increase"]').addEventListener("click", () => {
      upsertCartItem(item, 1);
      renderCartPage();
    });
    row.querySelector("[data-remove]").addEventListener("click", () => {
      removeCartItem(item.product_id);
      renderCartPage();
    });
    linesEl.appendChild(row);
  });

  if (totalEl) {
    totalEl.textContent = money.format(cartTotal());
  }
}

function initCartPage() {
  renderCartPage();
}

function createProductImage(product) {
  const palettes = {
    Bread: ["#f7d88b", "#d68843"],
    Pastry: ["#ffd5c9", "#cf7154"],
    default: ["#edd7b8", "#8e4d2b"],
  };
  const [primary, secondary] = palettes[product.category] || palettes.default;
  const label = encodeURIComponent((product.name || "BakeWise").slice(0, 18));
  const category = encodeURIComponent(product.category || "Fresh Bake");
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="${primary}" />
          <stop offset="100%" stop-color="${secondary}" />
        </linearGradient>
      </defs>
      <rect width="640" height="420" fill="url(#bg)" rx="28" />
      <circle cx="500" cy="95" r="80" fill="rgba(255,255,255,0.24)" />
      <circle cx="120" cy="320" r="105" fill="rgba(255,255,255,0.18)" />
      <text x="48" y="248" font-size="46" font-family="Georgia, serif" fill="#fff7ec">${label}</text>
      <text x="50" y="300" font-size="24" font-family="Arial, sans-serif" fill="#fff7ec">${category}</text>
    </svg>
  `;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

/**
 * Call a BakeWise JSON API. Supports the app envelope `{ success, message, data }`
 * and older flat responses (e.g. legacy server) for the same URLs.
 */
async function fetchApi(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error("We could not reach the server. Check your connection and try again.");
  }

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      throw new Error("The server sent an unexpected response. Please try again later.");
    }
  } else {
    payload = {};
  }

  if (!response.ok) {
    const msg =
      (payload && payload.message) ||
      (payload && payload.error) ||
      `Something went wrong (${response.status}).`;
    const err = new Error(msg);
    if (payload && Array.isArray(payload.errors)) {
      err.fieldErrors = payload.errors;
    }
    throw err;
  }

  if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "success")) {
    if (!payload.success) {
      throw new Error(payload.message || "The request was not successful.");
    }
    return payload.data !== undefined ? payload.data : {};
  }

  return payload;
}

async function fetchJson(url, options = {}) {
  return fetchApi(url, options);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function escapeAttr(text) {
  return String(text == null ? "" : text)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function renderMiniCart(cartItemsNode, cartSummaryNode, cartTotalNode) {
  const cart = loadCart();
  if (cartSummaryNode) {
    cartSummaryNode.textContent = `${cartCount()} item${cartCount() === 1 ? "" : "s"} selected`;
  }
  if (cartTotalNode) {
    cartTotalNode.textContent = money.format(cartTotal());
  }

  if (!cartItemsNode) {
    return;
  }

  if (cart.length === 0) {
    cartItemsNode.innerHTML = '<article class="empty-card">Add products here to build an order.</article>';
    return;
  }

  cartItemsNode.innerHTML = "";
  cart.forEach((item) => {
    const card = document.createElement("article");
    card.className = "cart-item";
    card.innerHTML = `
      <img src="${createProductImage(item)}" alt="${escapeAttr(item.name)}">
      <div>
        <h3>${escapeHtml(item.name)}</h3>
        <p>${escapeHtml(item.category || "")}</p>
        <strong>${money.format(Number(item.price || 0))}</strong>
      </div>
      <div class="quantity-controls">
        <button type="button" data-action="decrease" aria-label="Decrease quantity">−</button>
        <span>${item.quantity}</span>
        <button type="button" data-action="increase" aria-label="Increase quantity">+</button>
      </div>
    `;
    card.querySelector('[data-action="decrease"]').addEventListener("click", () => {
      upsertCartItem(item, -1);
      renderProductsPageCart();
      renderCheckoutPage();
    });
    card.querySelector('[data-action="increase"]').addEventListener("click", () => {
      upsertCartItem(item, 1);
      renderProductsPageCart();
      renderCheckoutPage();
    });
    cartItemsNode.appendChild(card);
  });
}

function renderProductsPageCart() {
  renderMiniCart(
    document.getElementById("cartItems"),
    document.getElementById("cartSummary"),
    document.getElementById("cartTotal"),
  );
}

function renderCheckoutPage() {
  const cartItemsNode = document.getElementById("checkoutCartItems");
  const cartCountNode = document.getElementById("checkoutCartCount");
  const totalNode = document.getElementById("checkoutTotal");
  if (!cartItemsNode || !cartCountNode || !totalNode) {
    return;
  }

  const cart = loadCart();
  cartCountNode.textContent = `${cartCount()} item${cartCount() === 1 ? "" : "s"}`;
  totalNode.textContent = money.format(cartTotal());

  if (cart.length === 0) {
    cartItemsNode.innerHTML = '<article class="empty-card">Your cart is empty.</article>';
    return;
  }

  cartItemsNode.innerHTML = "";
  cart.forEach((item) => {
    const row = document.createElement("article");
    row.className = "checkout-item";
    row.setAttribute("role", "listitem");
    const unit = Number(item.price || 0);
    const qty = Number(item.quantity || 0);
    row.innerHTML = `
      <img src="${createProductImage(item)}" alt="${escapeAttr(item.name)}">
      <div>
        <h3>${escapeHtml(item.name)}</h3>
        <p>${qty} × ${money.format(unit)}</p>
      </div>
      <strong>${money.format(unit * qty)}</strong>
    `;
    cartItemsNode.appendChild(row);
  });
}

function buildProductCard(product) {
  const card = document.createElement("article");
  card.className = "product-card";
  const qty = Number(product.available_quantity || 0);
  const disabled = qty <= 0;
  const name = escapeHtml(product.name);
  const category = escapeHtml(product.category || "Uncategorized");
  const pid = escapeHtml(product.product_id);
  card.innerHTML = `
    <img src="${createProductImage(product)}" alt="${escapeAttr(product.name)}">
    <div class="product-card__content">
      <p class="product-category">${category}</p>
      <h3>${name}</h3>
      <p class="product-meta">Product #${pid}</p>
      <div class="product-card__footer">
        <strong>${money.format(Number(product.price || 0))}</strong>
        <span>${qty > 0 ? `${qty} in stock` : "Out of stock"}</span>
      </div>
      <button type="button" class="button button--solid button--full" data-add-to-cart ${disabled ? "disabled" : ""}>
        ${disabled ? "Out of stock" : "Add to cart"}
      </button>
    </div>
  `;
  const btn = card.querySelector("[data-add-to-cart]");
  if (btn && !disabled) {
    btn.addEventListener("click", () => {
      upsertCartItem(product, 1);
      renderProductsPageCart();
      updateCartCount();
    });
  }
  return card;
}

async function initHomePage() {
  const featuredNode = document.getElementById("featuredProducts");
  if (!featuredNode) {
    return;
  }
  const payload = await fetchJson("/api/storefront");
  document.getElementById("heroOrderingStatus").textContent = payload.accepting_orders
    ? "Accepting orders"
    : "Ordering paused";
  document.getElementById("heroProductCount").textContent = `${payload.featured_products.length} featured products`;

  featuredNode.innerHTML = "";
  payload.featured_products.forEach((product) => {
    featuredNode.appendChild(buildProductCard(product));
  });
}

async function initProductsPage() {
  const grid = document.getElementById("productGrid");
  if (!grid) {
    return;
  }

  const errorBox = document.getElementById("catalogError");
  const toolbar = document.getElementById("catalogToolbar");
  const hint = document.getElementById("catalogHint");
  const searchInput = document.getElementById("searchInput");
  const categoryFilters = document.getElementById("categoryFilters");
  const productCount = document.getElementById("productCount");

  let products = [];
  let activeCategory = "All";
  let searchValue = "";

  function showCatalogError(message) {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = message;
    errorBox.hidden = false;
    if (toolbar) {
      toolbar.classList.add("catalog-toolbar--muted");
    }
    if (hint) {
      hint.textContent = "";
    }
    productCount.textContent = "0 products";
    grid.innerHTML =
      '<p class="empty-card empty-card--error">We could not load the product list. Try refreshing the page in a moment.</p>';
  }

  function clearCatalogError() {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = "";
    errorBox.hidden = true;
    if (toolbar) {
      toolbar.classList.remove("catalog-toolbar--muted");
    }
  }

  function uniqueCategories(list) {
    const set = new Set();
    list.forEach((p) => {
      if (p && p.category) {
        set.add(p.category);
      }
    });
    return ["All", ...Array.from(set).sort((a, b) => a.localeCompare(b))];
  }

  function renderCategories(categories) {
    if (!categoryFilters) {
      return;
    }
    categoryFilters.innerHTML = "";
    categories.forEach((category) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "filter-chip";
      button.textContent = category;
      if (category === activeCategory) {
        button.dataset.active = "true";
      }
      button.addEventListener("click", () => {
        activeCategory = category;
        renderCategories(categories);
        renderProducts();
      });
      categoryFilters.appendChild(button);
    });
  }

  function renderProducts() {
    const filtered = products.filter((product) => {
      const byCategory = activeCategory === "All" || product.category === activeCategory;
      const haystack = `${product.name} ${product.category} ${product.product_id}`.toLowerCase();
      const bySearch = !searchValue || haystack.includes(searchValue);
      return byCategory && bySearch;
    });

    productCount.textContent = `${filtered.length} product${filtered.length === 1 ? "" : "s"}`;
    grid.innerHTML = "";

    if (products.length === 0) {
      grid.innerHTML =
        '<p class="empty-card">No products are listed yet. Check back soon, or ask the bakery to publish items in BakeWise.</p>';
      return;
    }

    if (filtered.length === 0) {
      grid.innerHTML =
        '<p class="empty-card">No products match your search. Try a different word or pick another category.</p>';
      return;
    }

    filtered.forEach((product) => {
      grid.appendChild(buildProductCard(product));
    });
  }

  try {
    const data = await fetchApi("/api/products");
    products = Array.isArray(data.products) ? data.products : [];
    clearCatalogError();

    if (hint) {
      hint.textContent =
        products.length === 0
          ? "Catalog is empty right now."
          : "Tip: use search and categories to narrow the list.";
    }

    const categories = uniqueCategories(products);
    activeCategory = "All";
    searchValue = "";
    if (searchInput) {
      searchInput.value = "";
      searchInput.addEventListener("input", (event) => {
        searchValue = (event.target.value || "").trim().toLowerCase();
        renderProducts();
      });
    }

    renderCategories(categories);
    renderProducts();
  } catch (error) {
    console.error(error);
    showCatalogError(error.message || "Something went wrong while loading products.");
  }

  renderProductsPageCart();
  updateCartCount();
}

function setCheckoutFieldError(fieldId, hasError) {
  const el = document.getElementById(fieldId);
  if (!el) {
    return;
  }
  el.classList.toggle("input--error", Boolean(hasError));
  el.setAttribute("aria-invalid", hasError ? "true" : "false");
}

function clearCheckoutFieldErrors() {
  ["customerName", "customerPhone", "paymentMethod", "pickupDate"].forEach((id) => setCheckoutFieldError(id, false));
}

async function initCheckoutPage() {
  const form = document.getElementById("checkoutForm");
  const emptyState = document.getElementById("checkoutEmptyState");
  const mainState = document.getElementById("checkoutMain");
  if (!form || !emptyState || !mainState) {
    return;
  }

  function syncCheckoutLayout() {
    const cart = loadCart();
    if (cart.length === 0) {
      emptyState.hidden = false;
      mainState.hidden = true;
      return false;
    }
    emptyState.hidden = true;
    mainState.hidden = false;
    renderCheckoutPage();
    updateCartCount();
    return true;
  }

  if (!syncCheckoutLayout()) {
    return;
  }

  const pickupDate = document.getElementById("pickupDate");
  const today = new Date().toISOString().split("T")[0];
  pickupDate.min = today;
  if (!pickupDate.value) {
    pickupDate.value = today;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const feedback = document.getElementById("checkoutFeedback");
    feedback.textContent = "";
    clearCheckoutFieldErrors();

    if (!syncCheckoutLayout()) {
      feedback.textContent = "Your cart is empty. Add something from the catalog, or open your cart to review.";
      feedback.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }

    const cart = loadCart();
    const customerName = document.getElementById("customerName").value.trim();
    const customerPhone = document.getElementById("customerPhone").value.trim().replace(/\s+/g, "");
    const paymentMethod = document.getElementById("paymentMethod").value.trim();
    const pickup = pickupDate.value;
    const notes = document.getElementById("orderNotes").value.trim();

    if (!customerName) {
      setCheckoutFieldError("customerName", true);
      feedback.textContent = "Please enter your name.";
      feedback.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    if (!customerPhone || customerPhone.length < 7) {
      setCheckoutFieldError("customerPhone", true);
      feedback.textContent = "Please enter a contact number with at least 7 digits.";
      feedback.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    if (!paymentMethod) {
      setCheckoutFieldError("paymentMethod", true);
      feedback.textContent = "Please choose a payment method.";
      feedback.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    if (!pickup) {
      setCheckoutFieldError("pickupDate", true);
      feedback.textContent = "Please choose a pickup date.";
      feedback.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }

    const submitButton = document.getElementById("submitOrderButton");
    submitButton.disabled = true;
    submitButton.textContent = "Placing order…";

    const orderPayload = {
      payment_method: paymentMethod,
      pickup_date_from: pickup,
      pickup_date_to: pickup,
      items: cart.map((item) => ({
        product_id: Number(item.product_id),
        quantity: Number(item.quantity),
      })),
      customer_name: customerName,
      contact_number: customerPhone,
    };
    if (notes) {
      orderPayload.notes = notes;
    }

    try {
      const data = await fetchJson("/api/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(orderPayload),
      });
      const order = data.order || data;
      const orderId = order.order_id ?? order.transaction_id;
      if (orderId == null) {
        feedback.textContent =
          "The order may have been created, but we could not read the order number. Please check with the bakery or try again.";
        submitButton.disabled = false;
        submitButton.textContent = "Place order";
        feedback.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return;
      }
      saveCart([]);
      updateCartCount();
      window.location.href = `/confirmation/${orderId}`;
    } catch (error) {
      let msg = error.message || "We could not place your order. Please try again.";
      if (error.fieldErrors && error.fieldErrors.length) {
        msg = `${msg} ${error.fieldErrors.join(" ")}`;
      }
      feedback.textContent = msg;
      submitButton.disabled = false;
      submitButton.textContent = "Place order";
      feedback.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  });
}

async function initConfirmationPage() {
  const title = document.getElementById("confirmationTitle");
  const meta = document.getElementById("confirmationMeta");
  const itemsNode = document.getElementById("confirmationItems");
  if (!title || !meta || !itemsNode) {
    return;
  }

  const orderId = window.BAKEWISE_CONFIG && window.BAKEWISE_CONFIG.order_id;
  if (orderId == null) {
    title.textContent = "We could not find this order.";
    meta.textContent = "Missing order reference. Return home and try again.";
    itemsNode.innerHTML = "";
    return;
  }

  try {
    const data = await fetchJson(`/api/orders/${orderId}`);
    const payload = data.order || data;
    const displayId = payload.order_id ?? payload.transaction_id;
    title.textContent = payload.customer_number
      ? `Thank you! Order ${payload.customer_number} is confirmed.`
      : `Thank you! Order #${displayId} is confirmed.`;

    let pickupLine = "Pickup date to be confirmed with the bakery.";
    if (payload.pickup_date_from) {
      pickupLine =
        payload.pickup_date_to && payload.pickup_date_to !== payload.pickup_date_from
          ? `Pickup: ${payload.pickup_date_from} – ${payload.pickup_date_to}`
          : `Pickup: ${payload.pickup_date_from}`;
    }

    meta.textContent = `${pickupLine} · Total ${money.format(payload.total)} · ${payload.payment_method} · ${payload.online_order_status || "pending"}`;

    itemsNode.innerHTML = "";
    (payload.items || []).forEach((item) => {
      const row = document.createElement("article");
      row.className = "confirmation-item";
      row.setAttribute("role", "listitem");
      const lineName = item.name || item.product_name || "Item";
      row.innerHTML = `
        <div>
          <h3>${escapeHtml(lineName)}</h3>
          <p>Quantity: ${item.quantity}</p>
        </div>
        <strong>${money.format(item.subtotal)}</strong>
      `;
      itemsNode.appendChild(row);
    });
  } catch (error) {
    console.error(error);
    title.textContent = "We could not load this order.";
    meta.textContent =
      error.message || "Try refreshing the page, or contact the bakery with your confirmation details if you have them.";
    itemsNode.innerHTML = "";
  }
}

async function init() {
  updateCartCount();
  const page = getPageName();
  try {
    if (page === "home") {
      await initHomePage();
    }
    if (page === "products") {
      await initProductsPage();
    }
    if (page === "cart") {
      initCartPage();
    }
    if (page === "checkout") {
      await initCheckoutPage();
    }
    if (page === "confirmation") {
      await initConfirmationPage();
    }
  } catch (error) {
    console.error(error);
  }
}

function refreshStorefrontFromStorage() {
  updateCartCount();
  if (document.getElementById("cartPageLines")) {
    renderCartPage();
  }
  if (document.getElementById("checkoutEmptyState") && document.getElementById("checkoutMain")) {
    const emptyState = document.getElementById("checkoutEmptyState");
    const mainState = document.getElementById("checkoutMain");
    const cart = loadCart();
    if (cart.length === 0) {
      emptyState.hidden = false;
      mainState.hidden = true;
    } else {
      emptyState.hidden = true;
      mainState.hidden = false;
      renderCheckoutPage();
    }
  }
  renderProductsPageCart();
}

window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    refreshStorefrontFromStorage();
  }
});

document.addEventListener("DOMContentLoaded", init);
