import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  Bot,
  Building2,
  Check,
  CheckCircle2,
  CircleUserRound,
  ClipboardList,
  Copy,
  Mail,
  MapPin,
  Menu,
  MessageCircleQuestion,
  Minus,
  Moon,
  Package,
  Phone,
  Plus,
  Search,
  Send,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Star,
  Store,
  Sun,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useParams } from "react-router-dom";
import vendlyLogo from "../assets/vendly-logo.png";
import {
  createPublicChatOrder,
  createPublicChatSession,
  getPublicProduct,
  getPublicProductReviews,
  getPublicStore,
  getCustomerChats,
  getCustomerOrders,
  getPublicChatMessages,
  sendPublicChatMessage,
  submitPublicReview,
} from "../services/publicService";
import OrderReceipt from "../components/OrderReceipt";
import CustomerAccountModal from "../components/CustomerAccountModal";
import { useAuth } from "../context/authContextValue";
import { claimPublicChatSession } from "../services/publicService";

import "./StorefrontPage.css";

const EMPTY_CUSTOMER = {
  name: "",
  phoneNumber: "",
  secondaryPhoneNumber: "",
  email: "",
  deliveryNote: "",
  address: {
    line1: "",
    line2: "",
    city: "",
    district: "",
    postalCode: "",
  },
};

function money(minor = 0) {
  return `Rs ${Number(minor / 100).toLocaleString("en-LK", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function getInitialView() {
  const view = window.location.hash.replace("#", "");
  return ["catalog", "chatbot", "reviews", "contact"].includes(view) ? view : "catalog";
}

function getInitialTheme() {
  return localStorage.getItem("vendly-storefront-theme") === "dark"
    ? "dark"
    : "light";
}

function StorefrontPage({ linkType }) {
  const { user, isAuthLoading } = useAuth();
  const { storeCode, productCode } = useParams();
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const receivedSellerMessageIds = useRef(new Set());
  const [messageText, setMessageText] = useState("");
  const [cart, setCart] = useState([]);
  const [customer, setCustomer] = useState(EMPTY_CUSTOMER);
  const [activeView, setActiveView] = useState(getInitialView);
  const [theme, setTheme] = useState(getInitialTheme);
  const [searchText, setSearchText] = useState("");
  const [activeCategory, setActiveCategory] = useState("All");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [confirmedOrder, setConfirmedOrder] = useState(null);
  const [copiedField, setCopiedField] = useState("");
  const [reviews, setReviews] = useState([]);
  const [customerOrders, setCustomerOrders] = useState([]);
  const [storefrontReviewDraft, setStorefrontReviewDraft] = useState({
    orderNumber: "",
    phoneNumber: "",
    productId: "",
    type: "product",
    rating: "5",
    reviewText: "",
  });
  const [storefrontReviewMessage, setStorefrontReviewMessage] = useState("");
  const [storefrontReviewFiles, setStorefrontReviewFiles] = useState([]);
  const [reviewForm, setReviewForm] = useState({
    orderNumber: "",
    phoneNumber: "",
    rating: "5",
    reviewText: "",
  });
  const [reviewMessage, setReviewMessage] = useState("");
  const [isAccountOpen, setIsAccountOpen] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    let requestIsCurrent = true;

    async function loadStorefront() {
      if (isAuthLoading || !user) return;
      setIsLoading(true);
      setErrorMessage("");

      try {
        const catalogRequest =
          linkType === "product"
            ? getPublicProduct(productCode)
            : getPublicStore(storeCode);
        const sessionRequest = createPublicChatSession({
          storeCode: linkType === "store" ? storeCode : undefined,
          productCode: linkType === "product" ? productCode : undefined,
        });
        const reviewRequest =
          linkType === "product"
            ? getPublicProductReviews(productCode)
            : Promise.resolve({ reviews: [] });
        const [catalog, chatSession, reviewResponse] = await Promise.all([
          catalogRequest,
          sessionRequest,
          reviewRequest,
        ]);

        if (!requestIsCurrent) return;

        setBusiness(catalog.business);
        const customerOrderResponse = await getCustomerOrders(catalog.business.shortCode).catch(() => ({ orders: [] }));
        setCustomerOrders(customerOrderResponse.orders || []);
        setProducts(
          linkType === "product" ? [catalog.product] : catalog.products,
        );
        setSession(chatSession);
        const historyResponse = await getCustomerChats(catalog.business.shortCode).catch(() => ({ chats: [] }));
        // Mark messages already rendered from history so the live poller does
        // not append them a second time.
        historyResponse.chats?.forEach((chat) => {
          chat.messages?.forEach((message) => {
            if (message.role === "seller" && message.id) {
              receivedSellerMessageIds.current.add(message.id);
            }
          });
        });
        const previousChat = historyResponse.chats?.find((chat) =>
          chat.sessionId !== chatSession.sessionId && chat.messages?.length > 1,
        );
        const previousMessages = previousChat?.messages?.map((message) => ({
          role: message.role === "seller" ? "assistant" : message.role,
          text: message.message,
          action: message.metadata?.action,
        })) ?? [];
        setMessages(previousMessages.length > 0 ? previousMessages : [{
          role: "assistant",
          text: chatSession.message,
          action: chatSession.action,
          product: chatSession.product,
          products: chatSession.products,
        }]);
        setReviews(reviewResponse.reviews);
      } catch (error) {
        if (requestIsCurrent) setErrorMessage(error.message);
      } finally {
        if (requestIsCurrent) setIsLoading(false);
      }
    }

    loadStorefront();
    return () => {
      requestIsCurrent = false;
    };
  }, [isAuthLoading, linkType, productCode, storeCode, user]);

  useEffect(() => {
    if (!user || !session?.sessionId || !session?.sessionToken) return;
    claimPublicChatSession(session.sessionId, session.sessionToken).catch((error) => {
      setErrorMessage(error.message);
    });
  }, [session?.sessionId, session?.sessionToken, user]);

  // Seller replies are written to the same Firestore chat. Poll the protected
  // session endpoint so a storefront customer sees those replies without a
  // page refresh; only unseen seller messages are appended to local UI state.
  useEffect(() => {
    if (!session?.sessionId || !session?.sessionToken) return undefined;

    let isCurrent = true;
    async function loadSellerReplies() {
      try {
        // Status updates are written to the chat session that created the
        // order, while the customer may now be viewing a newer session. Read
        // both the current session and the customer's other store chats.
        const [currentResponse, historyResponse] = await Promise.all([
          getPublicChatMessages(session.sessionId, session.sessionToken),
          business?.shortCode
            ? getCustomerChats(business.shortCode).catch(() => ({ chats: [] }))
            : Promise.resolve({ chats: [] }),
        ]);
        const candidates = [
          ...(currentResponse.messages || []),
          ...(historyResponse.chats || []).flatMap((chat) => chat.messages || []),
        ];
        const unseen = candidates.filter(
          (message) => message.role === "seller" && message.id
            && !receivedSellerMessageIds.current.has(message.id),
        );
        if (!isCurrent || unseen.length === 0) return;
        unseen.forEach((message) => receivedSellerMessageIds.current.add(message.id));
        setMessages((current) => [
          ...current,
          ...unseen.map((message) => ({
            id: message.id,
            role: "assistant",
            text: message.message,
          })),
        ]);
      } catch {
        // The normal send flow reports errors. Silent polling should not cover
        // the storefront with an error if the network briefly disconnects.
      }
    }

    loadSellerReplies();
    const timer = window.setInterval(loadSellerReplies, 5000);
    return () => {
      isCurrent = false;
      window.clearInterval(timer);
    };
  }, [business?.shortCode, session?.sessionId, session?.sessionToken]);

  useEffect(() => {
    localStorage.setItem("vendly-storefront-theme", theme);
  }, [theme]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [messages, isSending]);

  useEffect(() => {
    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setIsCheckoutOpen(false);
        setIsCartOpen(false);
        setIsMobileMenuOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  const categories = useMemo(
    () => [
      "All",
      ...new Set(
        products.map((product) => product.categoryName).filter(Boolean),
      ),
    ],
    [products],
  );

  const visibleProducts = useMemo(() => {
    const query = searchText.trim().toLowerCase();

    return products.filter((product) => {
      const matchesCategory =
        activeCategory === "All" || product.categoryName === activeCategory;
      const matchesSearch =
        !query ||
        [product.name, product.brand, product.categoryName, product.description]
          .join(" ")
          .toLowerCase()
          .includes(query);
      return matchesCategory && matchesSearch;
    });
  }, [activeCategory, products, searchText]);

  const cartQuantity = useMemo(
    () => cart.reduce((total, item) => total + item.quantity, 0),
    [cart],
  );

  const cartSubtotal = useMemo(
    () =>
      cart.reduce(
        (total, item) => total + item.sellingPriceMinor * item.quantity,
        0,
      ),
    [cart],
  );

  function changeView(view) {
    setActiveView(view);
    setIsMobileMenuOpen(false);
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}#${view}`,
    );
  }

  function addToCart(product, variant) {
    if (!variant || variant.availableStock < 1) return;

    setCart((current) => {
      const existing = current.find((item) => item.variantId === variant.id);

      if (existing) {
        if (existing.quantity >= variant.availableStock) return current;
        return current.map((item) =>
          item.variantId === variant.id
            ? { ...item, quantity: item.quantity + 1 }
            : item,
        );
      }

      return [
        ...current,
        {
          variantId: variant.id,
          productName: product.name,
          size: variant.size,
          sku: variant.sku,
          imageUrl: product.media?.[0]?.url || "",
          sellingPriceMinor: product.sellingPriceMinor,
          availableStock: variant.availableStock,
          quantity: 1,
        },
      ];
    });
  }

  function updateCartQuantity(variantId, amount) {
    setCart((current) =>
      current
        .map((item) => {
          if (item.variantId !== variantId) return item;
          const quantity = Math.min(
            item.availableStock,
            Math.max(0, item.quantity + amount),
          );
          return { ...item, quantity };
        })
        .filter((item) => item.quantity > 0),
    );
  }

  function setCartQuantity(variantId, requestedQuantity) {
    const parsedQuantity = Number.parseInt(requestedQuantity, 10);

    setCart((current) =>
      current
        .map((item) => {
          if (item.variantId !== variantId) return item;
          return {
            ...item,
            quantity: Math.min(
              item.availableStock,
              Math.max(0, Number.isNaN(parsedQuantity) ? 0 : parsedQuantity),
            ),
          };
        })
        .filter((item) => item.quantity > 0),
    );
  }

  async function requestChatMessage(cleanMessage) {
    if (!cleanMessage || !session || isSending) return;

    setMessages((current) => [
      ...current,
      { role: "customer", text: cleanMessage },
    ]);
    setMessageText("");
    setIsSending(true);
    setErrorMessage("");

    try {
      const response = await sendPublicChatMessage(
        session.sessionId,
        session.sessionToken,
        cleanMessage,
        {
          cart: cart.map((item) => ({
            variantId: item.variantId,
            quantity: item.quantity,
          })),
        },
      );

      if (response.customerDraft) {
        setCustomer((current) => ({
          ...current,
          ...response.customerDraft,
          address: {
            ...current.address,
            ...(response.customerDraft.address || {}),
          },
        }));
      }

      if (response.order) {
        setConfirmedOrder(response.order);
        setCart([]);
      }

      setSession((current) => ({
        ...current,
        state: response.state,
      }));
      if (response.message) {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            text: response.message,
            action: response.action,
            product: response.product,
            products: response.products,
            cartSummary: response.cartSummary,
            customerDraft: response.customerDraft,
          },
        ]);
      }
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSending(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    await requestChatMessage(messageText.trim());
  }

  function addFromChat(product, variant) {
    addToCart(product, variant);
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        text: `${product.name}${variant.size ? `, size ${variant.size}` : ""} was added to your order draft. You can add another item or continue to checkout.`,
        action: "cart-updated",
      },
    ]);
  }

  function updateCustomer(event) {
    const { name, value } = event.target;

    if (name.startsWith("address.")) {
      const addressField = name.replace("address.", "");
      setCustomer((current) => ({
        ...current,
        address: { ...current.address, [addressField]: value },
      }));
      return;
    }

    setCustomer((current) => ({ ...current, [name]: value }));
  }

  async function checkout(event) {
    event.preventDefault();
    if (!session || cart.length === 0) return;

    setIsSending(true);
    setErrorMessage("");

    try {
      const response = await createPublicChatOrder(
        session.sessionId,
        session.sessionToken,
        {
          customer: {
            name: customer.name,
            phoneNumber: customer.phoneNumber,
            secondaryPhoneNumber: customer.secondaryPhoneNumber,
            email: customer.email,
            address: customer.address,
          },
          deliveryNote: customer.deliveryNote,
          items: cart.map((item) => ({
            variantId: item.variantId,
            quantity: item.quantity,
          })),
        },
      );
      setConfirmedOrder(response.order);
      setIsCheckoutOpen(false);
      setIsCartOpen(false);
      setCart([]);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSending(false);
    }
  }

  async function submitReview(event) {
    event.preventDefault();
    if (!business?.shortCode || products.length !== 1) return;

    setIsSending(true);
    setErrorMessage("");
    setReviewMessage("");

    try {
      await submitPublicReview(business.shortCode, {
        ...reviewForm,
        rating: Number(reviewForm.rating),
        productId: products[0].id,
      });
      setReviewMessage(
        "Thank you. Your verified review is waiting for approval.",
      );
      setReviewForm({
        orderNumber: "",
        phoneNumber: "",
        rating: "5",
        reviewText: "",
      });
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSending(false);
    }
  }

  async function submitStorefrontReview(event) {
    event.preventDefault();
    if (!business?.shortCode || !storefrontReviewDraft.orderNumber) return;

    setIsSending(true);
    setErrorMessage("");
    setStorefrontReviewMessage("");
    try {
      await submitPublicReview(business.shortCode, {
        orderNumber: storefrontReviewDraft.orderNumber,
        productId: storefrontReviewDraft.type === "product"
          ? storefrontReviewDraft.productId
          : "",
        rating: Number(storefrontReviewDraft.rating),
        reviewText: storefrontReviewDraft.reviewText,
        media: storefrontReviewFiles,
      });
      setStorefrontReviewMessage("Thank you. Your review is waiting for approval.");
      setStorefrontReviewDraft((current) => ({ ...current, productId: "", reviewText: "" }));
      setStorefrontReviewFiles([]);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSending(false);
    }
  }

  async function copyContact(value, field) {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedField(field);
    window.setTimeout(() => setCopiedField(""), 1600);
  }

  if (isLoading) {
    return (
      <main className="storefront-loading">
        <span className="storefront-loading__mark">V</span>
        <strong>Opening storefront…</strong>
      </main>
    );
  }

  if (!business) {
    return (
      <main className="storefront-loading storefront-loading--error">
        <Package size={38} />
        <strong>{errorMessage || "This store is unavailable."}</strong>
      </main>
    );
  }

  const storefrontClass = `storefront storefront--${theme}`;

  return (
    <main className={storefrontClass}>
      <aside
        className={`storefront-sidebar ${isMobileMenuOpen ? "storefront-sidebar--open" : ""}`}
      >
        <button
          className="storefront-sidebar__close"
          type="button"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-label="Close menu"
        >
          <X size={21} />
        </button>

          <div>
            <img className="sidebar__logo-image" src={vendlyLogo} alt="Vendly.lk"/>
            <small align ="center">Customer Storefront</small>
          </div>

        <nav className="storefront-nav" aria-label="Storefront navigation">
          <button
            className={activeView === "catalog" ? "is-active" : ""}
            type="button"
            onClick={() => changeView("catalog")}
          >
            <Store size={20} /> Catalog
          </button>
          <button
            className={activeView === "chatbot" ? "is-active" : ""}
            type="button"
            onClick={() => changeView("chatbot")}
          >
            <Bot size={21} /> Chatbot
          </button>
          <button
            className={activeView === "contact" ? "is-active" : ""}
            type="button"
            onClick={() => changeView("contact")}
          >
            <MessageCircleQuestion size={20} /> Contact
          </button>
          <button
            className={activeView === "reviews" ? "is-active" : ""}
            type="button"
            onClick={() => changeView("reviews")}
          >
            <Star size={20} /> Reviews
          </button>
          <button
            type="button"
            onClick={() => {
              setIsMobileMenuOpen(false);
              setIsAccountOpen(true);
            }}
          >
            <UserRound size={20} /> {user ? "My orders" : "Login / Guest"}
          </button>
        </nav>
      </aside>

      {isMobileMenuOpen && (
        <button
          className="storefront-sidebar-backdrop"
          type="button"
          aria-label="Close menu"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      <section className="storefront-workspace">
        <header className="storefront-topbar">
          <div className="storefront-topbar__title">
            <button
              className="storefront-icon-button storefront-topbar__menu"
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={21} />
            </button>
            <div>
              <strong>
                {activeView === "catalog" && "Catalog"}
                {activeView === "chatbot" &&
                  `${business.name} – AI Ordering Assistant`}
                {activeView === "reviews" && "Reviews"}
                {activeView === "contact" && "Contact"}
              </strong>
              <small>{business.name}</small>
            </div>
          </div>

          <div className="storefront-topbar__actions">
            <button
              className="storefront-icon-button"
              type="button"
              aria-label="Notifications"
            >
              <Bell size={20} />
            </button>
            <button
              className="storefront-icon-button"
              type="button"
              onClick={() =>
                setTheme((current) => (current === "light" ? "dark" : "light"))
              }
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            <button
              className="storefront-icon-button"
              type="button"
              aria-label="Customer account"
              onClick={() => setIsAccountOpen(true)}
            >
              {user ? (
                <span className="storefront-customer-avatar">
                  {user.isAnonymous ? "G" : (user.displayName || user.email || "C").charAt(0).toUpperCase()}
                </span>
              ) : <CircleUserRound size={21} />}
            </button>
            <button
              className="storefront-cart-button"
              type="button"
              onClick={() => setIsCartOpen(true)}
              aria-label={`Open cart with ${cartQuantity} items`}
            >
              <ShoppingCart size={21} />
              {cartQuantity > 0 && <span>{cartQuantity}</span>}
            </button>
          </div>
        </header>

        {errorMessage && (
          <div className="storefront-error" role="alert">
            <span>{errorMessage}</span>
            <button
              type="button"
              onClick={() => setErrorMessage("")}
              aria-label="Dismiss error"
            >
              <X size={17} />
            </button>
          </div>
        )}

        {activeView === "catalog" && (
          <CatalogView
            business={business}
            products={visibleProducts}
            categories={categories}
            activeCategory={activeCategory}
            searchText={searchText}
            linkType={linkType}
            reviews={reviews}
            reviewForm={reviewForm}
            reviewMessage={reviewMessage}
            isSending={isSending}
            onSearchChange={setSearchText}
            onCategoryChange={setActiveCategory}
            onAddToCart={addToCart}
            onOpenChat={() => changeView("chatbot")}
            onReviewFormChange={setReviewForm}
            onSubmitReview={submitReview}
          />
        )}

        {activeView === "chatbot" && (
          <ChatbotView
            business={business}
            cart={cart}
            customer={customer}
            chatState={session?.state || "browsing"}
            messages={messages}
            messageText={messageText}
            isSending={isSending}
            messagesEndRef={messagesEndRef}
            onMessageTextChange={setMessageText}
            onSendMessage={sendMessage}
            onQuickMessage={requestChatMessage}
            onAddFromChat={addFromChat}
            onDecreaseItem={(variantId) => updateCartQuantity(variantId, -1)}
            onIncreaseItem={(variantId) => updateCartQuantity(variantId, 1)}
            onSetItemQuantity={setCartQuantity}
            onRemoveItem={(variantId) =>
              setCart((current) =>
                current.filter((item) => item.variantId !== variantId),
              )
            }
            onOpenCheckout={() => setIsCheckoutOpen(true)}
          />
        )}

        {activeView === "reviews" && (
          <StorefrontReviewCenter
            orders={customerOrders}
            draft={storefrontReviewDraft}
            message={storefrontReviewMessage}
            isSending={isSending}
            onChange={setStorefrontReviewDraft}
            onSubmit={submitStorefrontReview}
            onFilesChange={async (event) => {
              const selectedFiles = Array.from(event.target.files || []).slice(0, 4);
              const encodedFiles = await Promise.all(selectedFiles.map((file) => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve({ type: "image", url: reader.result });
                reader.onerror = reject;
                reader.readAsDataURL(file);
              })));
              setStorefrontReviewFiles(encodedFiles);
            }}
          />
        )}

        {activeView === "contact" && (
          <ContactView
            business={business}
            copiedField={copiedField}
            onCopyContact={copyContact}
          />
        )}
      </section>

      <CartDrawer
        isOpen={isCartOpen}
        cart={cart}
        subtotal={cartSubtotal}
        onClose={() => setIsCartOpen(false)}
        onUpdateQuantity={updateCartQuantity}
        onCheckout={() => {
          setIsCartOpen(false);
          setIsCheckoutOpen(true);
        }}
      />

      {isCheckoutOpen && (
        <CheckoutModal
          cart={cart}
          customer={customer}
          subtotal={cartSubtotal}
          isSending={isSending}
          onClose={() => setIsCheckoutOpen(false)}
          onCustomerChange={updateCustomer}
          onSubmit={checkout}
        />
      )}

      {confirmedOrder && (
        <OrderSuccess
          business={business}
          order={confirmedOrder}
          closeLabel="Return to Storefront"
          onClose={() => {
            setConfirmedOrder(null);
            setCustomer(EMPTY_CUSTOMER);
            window.location.reload();
          }}
        />
      )}

      <CustomerAccountModal
        isOpen={isAccountOpen}
        onClose={() => setIsAccountOpen(false)}
        user={user}
        storeCode={business.shortCode}
      />
    </main>
  );
}

function CatalogView({
  business,
  products,
  categories,
  activeCategory,
  searchText,
  linkType,
  reviews,
  reviewForm,
  reviewMessage,
  isSending,
  onSearchChange,
  onCategoryChange,
  onAddToCart,
  onOpenChat,
  onReviewFormChange,
  onSubmitReview,
}) {
  return (
    <div className="storefront-page storefront-catalog-page">
      <section className="storefront-catalog-hero">
        <h1>
          Welcome to <span>{business.name}</span>
        </h1>
        <p>Discover products, check live availability, and order securely.</p>
      </section>

      <div className="storefront-search">
        <Search size={21} />
        <input
          value={searchText}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search products, brands or categories…"
          aria-label="Search products"
        />
      </div>

      <div className="storefront-categories" aria-label="Product categories">
        {categories.map((category) => (
          <button
            className={activeCategory === category ? "is-active" : ""}
            type="button"
            key={category}
            onClick={() => onCategoryChange(category)}
          >
            {category}
          </button>
        ))}
      </div>

      <section className="storefront-product-grid">
        {products.map((product) => (
          <ProductCard
            product={product}
            key={product.id}
            onAddToCart={onAddToCart}
            onOpenChat={onOpenChat}
          />
        ))}
        {products.length === 0 && (
          <div className="storefront-empty-state">
            <Search size={34} />
            <h2>No matching products</h2>
            <p>Try a different search or category.</p>
          </div>
        )}
      </section>

      {linkType === "product" && (
        <ProductReviews
          reviews={reviews}
          reviewForm={reviewForm}
          reviewMessage={reviewMessage}
          isSending={isSending}
          onReviewFormChange={onReviewFormChange}
          onSubmitReview={onSubmitReview}
        />
      )}
    </div>
  );
}

function ProductCard({ product, onAddToCart, onOpenChat }) {
  const firstVariant = product.variants?.[0];
  const hasMultipleVariants = product.variants?.length > 1;

  return (
    <article className="storefront-product-card">
      <div className="storefront-product-card__media">
        {product.media?.[0]?.url ? (
          <img src={product.media[0].url} alt={product.name} />
        ) : (
          <Package size={52} />
        )}
        <strong>{money(product.sellingPriceMinor)}</strong>
        {product.compareAtPriceMinor > product.sellingPriceMinor && (
          <small>{money(product.compareAtPriceMinor)}</small>
        )}
      </div>

      <div className="storefront-product-card__body">
        <span>{product.categoryName || product.brand || "Product"}</span>
        <h2>{product.name}</h2>
        <p>
          {product.description ||
            product.aiDescription ||
            "Ask our chatbot for more information."}
        </p>
        <div className="storefront-product-card__stock">
          <CheckCircle2 size={15} /> {product.availableStock} available
          {product.approvedReviewCount > 0 && (
            <span>
              <Star size={14} fill="currentColor" />{" "}
              {product.approvedReviewCount} reviews
            </span>
          )}
        </div>

        {hasMultipleVariants && (
          <div className="storefront-product-card__variants">
            {product.variants.map((variant) => (
              <button
                type="button"
                key={variant.id}
                onClick={() => onAddToCart(product, variant)}
                title={`Add ${variant.size || variant.sku} to cart`}
              >
                {variant.size ? `Size ${variant.size}` : variant.sku}
              </button>
            ))}
          </div>
        )}

        <div className="storefront-product-card__actions">
          <button
            type="button"
            disabled={!firstVariant}
            onClick={() => onAddToCart(product, firstVariant)}
          >
            <ShoppingCart size={17} />
            {hasMultipleVariants ? "Add first size" : "Add to Cart"}
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            aria-label={`Ask about ${product.name}`}
          >
            <Bot size={17} />
          </button>
        </div>
      </div>
    </article>
  );
}

function ChatCatalogCard({ product, productIndex, isOrderMode, cart, onQuickMessage, onAddFromChat, onDecreaseItem, onIncreaseItem }) {
  const variant = product.variants?.[0];
  const selectedItem = cart.find((item) => item.variantId === variant?.id);
  const quantity = selectedItem?.quantity ?? 0;
  const availableStock = variant?.availableStock ?? product.availableStock ?? 0;

  if (!isOrderMode) {
    return (
      <article className="storefront-chat-catalog-card">
        {product.media?.[0]?.url ? <img src={product.media[0].url} alt="" /> : <Package size={24} />}
        <strong>{productIndex + 1}. {product.name}</strong>
        <small>{money(product.sellingPriceMinor)} · {availableStock} available</small>
        <button type="button" onClick={() => onQuickMessage(String(productIndex + 1))}>View product details</button>
      </article>
    );
  }

  return (
    <article className={`storefront-chat-catalog-card ${quantity ? "is-selected" : ""}`}>
      {product.media?.[0]?.url ? <img src={product.media[0].url} alt="" /> : <Package size={24} />}
      <strong>{product.name}</strong>
      <small>{money(product.sellingPriceMinor)}</small>
      <small>{availableStock} available</small>
      <button className="storefront-chat-catalog-card__select" type="button" disabled={!variant || availableStock < 1} onClick={() => onAddFromChat(product, variant)}>
        {quantity ? "Selected" : "Select"}
      </button>
      <div className="storefront-chat-catalog-card__quantity" aria-label={`Quantity for ${product.name}`}>
        <button type="button" aria-label={`Remove one ${product.name}`} disabled={!quantity} onClick={() => onDecreaseItem(variant.id)}>-</button>
        <strong>{quantity}</strong>
        <button type="button" aria-label={`Add one ${product.name}`} disabled={!variant || quantity >= availableStock} onClick={() => quantity ? onIncreaseItem(variant.id) : onAddFromChat(product, variant)}>+</button>
      </div>
    </article>
  );
}

function ChatProductVariantControl({
  product,
  variant,
  cart,
  onAddFromChat,
  onDecreaseItem,
  onIncreaseItem,
  onSetItemQuantity,
}) {
  const selectedItem = cart.find((item) => item.variantId === variant.id);
  const quantity = selectedItem?.quantity ?? 0;
  const availableStock = variant.availableStock ?? 0;
  const variantLabel = variant.size ? `Size ${variant.size}` : variant.sku;

  return (
    <div className={`storefront-chat-product__variant-row ${quantity ? "is-selected" : ""}`}>
      <span>
        <strong>{variantLabel}</strong>
        <small>{availableStock} available</small>
      </span>

      {quantity === 0 ? (
        <button
          type="button"
          disabled={availableStock < 1}
          onClick={() => onAddFromChat(product, variant)}
        >
          <Plus size={14} /> Add
        </button>
      ) : (
        <div className="storefront-chat-product__quantity">
          <button
            type="button"
            onClick={() => onDecreaseItem(variant.id)}
            aria-label={`Remove one ${product.name}, ${variantLabel}`}
          >
            <Minus size={14} />
          </button>
          <input
            type="number"
            min="1"
            max={availableStock}
            value={quantity}
            aria-label={`Quantity for ${product.name}, ${variantLabel}`}
            onChange={(event) =>
              onSetItemQuantity(variant.id, event.target.value)
            }
          />
          <button
            type="button"
            disabled={quantity >= availableStock}
            onClick={() => onIncreaseItem(variant.id)}
            aria-label={`Add one ${product.name}, ${variantLabel}`}
          >
            <Plus size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function ChatbotView({
  business,
  cart,
  customer,
  chatState,
  messages,
  messageText,
  isSending,
  messagesEndRef,
  onMessageTextChange,
  onSendMessage,
  onQuickMessage,
  onAddFromChat,
  onDecreaseItem,
  onIncreaseItem,
  onSetItemQuantity,
  onRemoveItem,
  onOpenCheckout,
}) {
  return (
    <div className="storefront-page storefront-chat-page">
      <section className="storefront-chat-panel">
        <header className="storefront-chat-panel__header">
          <div>
            <span />
            <strong>Order Chat</strong>
          </div>
          <small>
            <CheckCircle2 size={14} /> Ready
          </small>
        </header>

        <div className="storefront-chat-messages">
          {messages.map((message, index) => (
            <div
              className={`storefront-chat-message storefront-chat-message--${message.role}`}
              key={`${message.role}-${index}`}
            >
              <span className="storefront-chat-message__avatar">
                {message.role === "assistant" ? (
                  <Bot size={18} />
                ) : (
                  <UserRound size={18} />
                )}
              </span>
              <div className="storefront-chat-message__content">
                <p>{message.text}</p>

                {message.role === "assistant" &&
                  [
                    "show-catalog",
                    "start-order",
                    "show-category",
                    "suggest-alternatives",
                  ].includes(message.action) &&
                  !message.product &&
                  message.products?.length > 0 && (
                    <div className="storefront-chat-catalog">
                      {message.products.map((product, productIndex) => (
                        <ChatCatalogCard
                          key={product.id}
                          product={product}
                          productIndex={productIndex}
                          isOrderMode={message.action === "start-order"}
                          cart={cart}
                          onQuickMessage={onQuickMessage}
                          onAddFromChat={onAddFromChat}
                          onDecreaseItem={onDecreaseItem}
                          onIncreaseItem={onIncreaseItem}
                        />
                      ))}
                    </div>
                  )}

                {message.role === "assistant" && message.product && (
                  <div className="storefront-chat-product">
                    <div>
                      {message.product.media?.[0]?.url ? (
                        <img src={message.product.media[0].url} alt="" />
                      ) : (
                        <Package size={28} />
                      )}
                      <span>
                        <strong>{message.product.name}</strong>
                        <small>
                          {money(message.product.sellingPriceMinor)}
                        </small>
                      </span>
                    </div>
                    <p className="storefront-chat-product__description">
                      {message.product.description ||
                        message.product.aiDescription ||
                        "The seller has not added a product description yet."}
                    </p>
                    <div className="storefront-chat-product__variants">
                      {message.product.variants?.map((variant) => (
                        <ChatProductVariantControl
                          key={variant.id}
                          product={message.product}
                          variant={variant}
                          cart={cart}
                          onAddFromChat={onAddFromChat}
                          onDecreaseItem={onDecreaseItem}
                          onIncreaseItem={onIncreaseItem}
                          onSetItemQuantity={onSetItemQuantity}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {message.role === "assistant" &&
                  message.action === "confirm-order" && (
                    <div className="storefront-chat-confirmation">
                      <strong>Confirm order before submission</strong>
                      <div className="storefront-chat-confirmation__items">
                        {message.cartSummary?.map((item) => (
                          <span key={item.variantId}>
                            {item.quantity} × {item.productName}
                            {item.size ? ` · Size ${item.size}` : ""}
                            <strong>{money(item.lineTotalMinor)}</strong>
                          </span>
                        ))}
                      </div>
                      <div className="storefront-chat-confirmation__customer">
                        <span>{message.customerDraft?.name}</span>
                        <span>{message.customerDraft?.phoneNumber}</span>
                        <span>
                          {[
                            message.customerDraft?.address?.line1,
                            message.customerDraft?.address?.city,
                            message.customerDraft?.address?.district,
                          ]
                            .filter(Boolean)
                            .join(", ")}
                        </span>
                      </div>
                      <div className="storefront-chat-confirmation__actions">
                        <button
                          type="button"
                          onClick={() => onQuickMessage("change order")}
                          disabled={isSending}
                        >
                          Change details
                        </button>
                        <button
                          type="button"
                          onClick={() => onQuickMessage("confirm order")}
                          disabled={isSending}
                        >
                          <Check size={15} /> Confirm order
                        </button>
                      </div>
                    </div>
                  )}
              </div>
            </div>
          ))}

          {isSending && (
            <div className="storefront-chat-message storefront-chat-message--assistant">
              <span className="storefront-chat-message__avatar">
                <Bot size={18} />
              </span>
              <div
                className="storefront-typing"
                aria-label="Assistant is typing"
              >
                <i />
                <i />
                <i />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="storefront-chat-quick-actions">
          <button
            type="button"
            onClick={() => onQuickMessage("Show products")}
            disabled={isSending}
          >
            Show products
          </button>
          <button
            type="button"
            onClick={() => onQuickMessage("I want to order")}
            disabled={isSending}
          >
            I want to order
          </button>
          <button
            type="button"
            onClick={() => onQuickMessage("Show customer reviews")}
            disabled={isSending}
          >
            Reviews
          </button>
        </div>

        <form className="storefront-chat-input" onSubmit={onSendMessage}>
          <input
            value={messageText}
            onChange={(event) => onMessageTextChange(event.target.value)}
            placeholder="Type a message…"
            aria-label="Chat message"
          />
          <button
            type="submit"
            disabled={isSending || !messageText.trim()}
            aria-label="Send message"
          >
            <Send size={20} />
          </button>
        </form>
      </section>

      <aside className="storefront-draft">

        <section>
          <h3>Products & quantity</h3>
          <div className="storefront-draft__items">
            {cart.map((item) => (
              <article key={item.variantId}>
                <div className="storefront-draft__item-image">
                  {item.imageUrl ? (
                    <img src={item.imageUrl} alt="" />
                  ) : (
                    <Package size={22} />
                  )}
                </div>
                <div className="storefront-draft__item-details">
                  <strong>{item.productName}</strong>
                  <span>
                    Qty: {item.quantity}
                    {item.size ? ` · Size ${item.size}` : ""}
                  </span>
                  <small>{money(item.sellingPriceMinor * item.quantity)}</small>
                </div>
                <button
                  type="button"
                  onClick={() => onRemoveItem(item.variantId)}
                  aria-label={`Remove ${item.productName}`}
                >
                  <Trash2 size={16} />
                </button>
              </article>
            ))}
            {cart.length === 0 && <p>No products selected yet.</p>}
          </div>
        </section>

        <section>
          <h3>Customer details</h3>
          <DraftField label="Customer Name" value={customer.name} />
          <DraftField label="Phone No" value={customer.phoneNumber} />
          {customer.secondaryPhoneNumber && (
            <DraftField label="2nd Phone No" value={customer.secondaryPhoneNumber} />
          )}
          <DraftField
            label="Address"
            value={[
              customer.address.line1,
              customer.address.city,
              customer.address.district,
            ]
              .filter(Boolean)
              .join(", ")}
          />
        </section>

        <div className="storefront-draft__bottom">
          <section>
            <h3>Status</h3>
            <div
              className={`storefront-draft__status ${cart.length ? "is-active" : ""}`}
            >
              <span />{" "}
              {chatState === "awaiting-confirmation"
                ? "Awaiting order confirmation"
                : chatState.startsWith("collecting-")
                  ? "Collecting customer details"
                  : cart.length
                    ? "Items selected · Ready to order"
                    : "Waiting for product selection"}
            </div>
          </section>
          <button
            type="button"
            disabled={cart.length === 0}
            onClick={onOpenCheckout}
          >
            Continue to checkout <Check size={17} />
          </button>
          <small>Ordering from {business.name}</small>
        </div>
      </aside>
    </div>
  );
}

function DraftField({ label, value }) {
  return (
    <div className="storefront-draft__field">
      <span>{label}</span>
      <strong className={value ? "" : "is-empty"}>
        {value || "Awaiting input…"}
      </strong>
    </div>
  );
}

function ContactView({ business, copiedField, onCopyContact }) {
  const phone = business.phone || "Not provided by this seller";
  const email = business.email || "Not provided by this seller";

  return (
    <div className="storefront-page storefront-contact-page">
      <section className="storefront-contact-hero">
        <h1>
          Welcome to <span>{business.name}</span>
        </h1>
        <p>We are here to help. Reach out through any of the channels below.</p>
      </section>

      <div className="storefront-contact-grid">
        <ContactCard
          icon={<Phone size={25} />}
          title="Contact No."
          description="Call us directly for assistance with your orders or enquiries."
          value={phone}
          canCopy={Boolean(business.phone)}
          copied={copiedField === "phone"}
          onCopy={() => onCopyContact(business.phone, "phone")}
        />
        <ContactCard
          icon={<Mail size={25} />}
          title="Email"
          description="Drop us an email anytime. The seller will reply as soon as possible."
          value={email}
          canCopy={Boolean(business.email)}
          copied={copiedField === "email"}
          onCopy={() => onCopyContact(business.email, "email")}
        />
      </div>

      <section className="storefront-contact-note">
        <Building2 size={22} />
        <div>
          <strong>{business.name}</strong>
          <span>Powered by Vendly.lk secure ordering</span>
        </div>
      </section>
    </div>
  );
}

function ContactCard({
  icon,
  title,
  description,
  value,
  canCopy,
  copied,
  onCopy,
}) {
  return (
    <article className="storefront-contact-card">
      <span className="storefront-contact-card__icon">{icon}</span>
      <h2>{title}</h2>
      <p>{description}</p>
      <button type="button" disabled={!canCopy} onClick={onCopy}>
        <strong>{value}</strong>
        {canCopy && (copied ? <Check size={17} /> : <Copy size={16} />)}
      </button>
    </article>
  );
}

function CartDrawer({
  isOpen,
  cart,
  subtotal,
  onClose,
  onUpdateQuantity,
  onCheckout,
}) {
  return (
    <>
      {isOpen && (
        <button
          className="storefront-modal-backdrop"
          type="button"
          aria-label="Close cart"
          onClick={onClose}
        />
      )}
      <aside
        className={`storefront-cart ${isOpen ? "storefront-cart--open" : ""}`}
        aria-hidden={!isOpen}
      >
        <header>
          <div>
            <ShoppingCart size={22} />
            <h2>Your Cart</h2>
            <span>
              {cart.reduce((total, item) => total + item.quantity, 0)}
            </span>
          </div>
          <button type="button" onClick={onClose} aria-label="Close cart">
            <X size={20} />
          </button>
        </header>

        <div className="storefront-cart__items">
          {cart.map((item) => (
            <article key={item.variantId}>
              <div className="storefront-cart__image">
                {item.imageUrl ? (
                  <img src={item.imageUrl} alt="" />
                ) : (
                  <Package size={28} />
                )}
              </div>
              <div className="storefront-cart__details">
                <strong>{item.productName}</strong>
                <span>
                  {item.size ? `Size ${item.size} · ` : ""}
                  {money(item.sellingPriceMinor)}
                </span>
                <div>
                  <button
                    type="button"
                    onClick={() => onUpdateQuantity(item.variantId, -1)}
                  >
                    <Minus size={14} />
                  </button>
                  <strong>{item.quantity}</strong>
                  <button
                    type="button"
                    onClick={() => onUpdateQuantity(item.variantId, 1)}
                  >
                    <Plus size={14} />
                  </button>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onUpdateQuantity(item.variantId, -item.quantity)}
                aria-label={`Remove ${item.productName}`}
              >
                <Trash2 size={16} />
              </button>
            </article>
          ))}
          {cart.length === 0 && (
            <div className="storefront-cart__empty">
              <ShoppingBag size={38} />
              <h3>Your cart is empty</h3>
              <p>Add a product from the catalog or chatbot.</p>
            </div>
          )}
        </div>

        <footer>
          <div>
            <span>Subtotal</span>
            <strong>{money(subtotal)}</strong>
          </div>
          <div>
            <span>Total</span>
            <strong>{money(subtotal)}</strong>
          </div>
          <small>
            Delivery will be calculated from your district and order weight.
          </small>
          <button
            type="button"
            disabled={cart.length === 0}
            onClick={onCheckout}
          >
            Checkout <Check size={18} />
          </button>
        </footer>
      </aside>
    </>
  );
}

function CheckoutModal({
  cart,
  customer,
  subtotal,
  isSending,
  onClose,
  onCustomerChange,
  onSubmit,
}) {
  return (
    <div className="storefront-modal-layer" role="presentation">
      <button
        className="storefront-modal-backdrop"
        type="button"
        aria-label="Close checkout"
        onClick={onClose}
      />
      <form className="storefront-checkout-modal" onSubmit={onSubmit}>
        <header>
          <span>
            <ShoppingBag size={22} />
          </span>
          <div>
            <h2>Contact & Delivery Details</h2>
            <p>Please provide accurate shipping information.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close checkout">
            <X size={21} />
          </button>
        </header>

        <div className="storefront-checkout-modal__body">
          <label>
            <span>Full Name *</span>
            <div>
              <UserRound size={17} />
              <input
                name="name"
                value={customer.name}
                onChange={onCustomerChange}
                placeholder="Your full name"
                required
              />
            </div>
          </label>
          <label>
            <span>Phone Number *</span>
            <div>
              <Phone size={17} />
              <input
                name="phoneNumber"
                value={customer.phoneNumber}
                onChange={onCustomerChange}
                placeholder="077 123 4567"
                required
              />
            </div>
          </label>
          <label>
            <span>2nd Phone Number (Optional)</span>
            <div>
              <Phone size={17} />
              <input
                name="secondaryPhoneNumber"
                value={customer.secondaryPhoneNumber}
                onChange={onCustomerChange}
                placeholder="071 234 5678"
              />
            </div>
          </label>
          <label className="is-wide">
            <span>Street Address *</span>
            <div>
              <MapPin size={17} />
              <input
                name="address.line1"
                value={customer.address.line1}
                onChange={onCustomerChange}
                placeholder="No. 123, Main Street"
                required
              />
            </div>
          </label>
          <label>
            <span>District *</span>
            <div>
              <MapPin size={17} />
              <input
                name="address.district"
                value={customer.address.district}
                onChange={onCustomerChange}
                placeholder="e.g. Colombo"
                required
              />
            </div>
          </label>
          <label>
            <span>Nearest City *</span>
            <div>
              <Building2 size={17} />
              <input
                name="address.city"
                value={customer.address.city}
                onChange={onCustomerChange}
                placeholder="e.g. Nugegoda"
                required
              />
            </div>
          </label>
          <label>
            <span>Email (Optional)</span>
            <div>
              <Mail size={17} />
              <input
                name="email"
                type="email"
                value={customer.email}
                onChange={onCustomerChange}
                placeholder="you@example.com"
              />
            </div>
          </label>
          <label>
            <span>Postal Code (Optional)</span>
            <div>
              <Building2 size={17} />
              <input
                name="address.postalCode"
                value={customer.address.postalCode}
                onChange={onCustomerChange}
                placeholder="10250"
              />
            </div>
          </label>
          <label className="is-wide">
            <span>Delivery Note (Optional)</span>
            <div>
              <ClipboardList size={17} />
              <textarea
                name="deliveryNote"
                value={customer.deliveryNote}
                onChange={onCustomerChange}
                placeholder="Call before dispatch or other courier instructions"
                rows="2"
              />
            </div>
          </label>
        </div>

        <div className="storefront-checkout-summary">
          <span>
            {cart.reduce((total, item) => total + item.quantity, 0)} items
          </span>
          <span>
            Subtotal: <strong>{money(subtotal)}</strong>
          </span>
          <small>
            Delivery fee is calculated securely when the order is placed.
          </small>
        </div>

        <footer>
          <span>
            <ShieldCheck size={16} /> Secure cash-on-delivery checkout
          </span>
          <div>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={isSending}>
              {isSending ? "Placing order…" : "Place Order"} <Check size={17} />
            </button>
          </div>
        </footer>
      </form>
    </div>
  );
}

function OrderSuccess({ business, order, onClose, closeLabel }) {
  return <OrderReceipt business={business} order={order} onClose={onClose} closeLabel={closeLabel} />;
  /* Previous receipt design retained temporarily for easy visual comparison.
  return (
    <div className="storefront-success-layer">
      <section className="storefront-success">
        <span className="storefront-success__icon">
          <Check size={34} strokeWidth={3} />
        </span>
        <h1>Order placed successfully!</h1>
        <p>
          Your order <strong>{order.orderNumber}</strong> is confirmed and{" "}
          {business.name} will process it shortly.
        </p>

        <div className="storefront-success__items">
          <h2>
            <ClipboardList size={20} /> Ordered Items
          </h2>
          <div>
            {order.items.map((item) => (
              <article key={item.variantId}>
                <div>
                  {item.mediaUrl ? (
                    <img src={item.mediaUrl} alt="" />
                  ) : (
                    <Package size={30} />
                  )}
                </div>
                <strong>{item.name}</strong>
                <span>
                  Qty: {item.quantity}
                  {item.size ? ` · Size ${item.size}` : ""}
                </span>
                <small>{money(item.lineTotalMinor)}</small>
              </article>
            ))}
          </div>
        </div>

        <div className="storefront-success__summary">
          <div>
            <span>Items subtotal</span>
            <strong>{money(order.subtotalMinor)}</strong>
          </div>
          <div>
            <span>Delivery fee</span>
            <strong>{money(order.deliveryFeeMinor)}</strong>
          </div>
          {order.discountTotalMinor > 0 && (
            <div>
              <span>Discount</span>
              <strong>- {money(order.discountTotalMinor)}</strong>
            </div>
          )}
          <div className="is-total">
            <span>Total</span>
            <strong>{money(order.totalAmountMinor)}</strong>
          </div>
        </div>

        <div className="storefront-success__actions">
          <button type="button" onClick={onDownloadReceipt}>
            <Download size={17} /> Download Receipt
          </button>
          <button type="button" onClick={onReturn}>
            Return to Storefront
          </button>
        </div>
      </section>
    </div>
  );
  */
}

function StorefrontReviewCenter({
  orders,
  draft,
  message,
  isSending,
  onChange,
  onSubmit,
  onFilesChange,
}) {
  const selectedOrder = orders.find(
    (order) => order.orderNumber === draft.orderNumber,
  );
  const productItems = selectedOrder?.items || [];

  return (
    <div className="storefront-page storefront-review-center">
      <section className="storefront-review-center__hero">
        <h1>Reviews</h1>
        <p>Share your experience with the products and seller.</p>
      </section>
      <form className="storefront-review-center__form" onSubmit={onSubmit}>
        <h2>Review a delivered order</h2>
        <label>
          Order
          <select
            value={draft.orderNumber}
            onChange={(event) => onChange((current) => ({
              ...current,
              orderNumber: event.target.value,
              productId: "",
            }))}
            required
          >
            <option value="">Select an order</option>
            {orders.map((order) => (
              <option key={order.id} value={order.orderNumber}>
                {order.orderNumber} ({order.fulfilmentStatus || "processing"})
              </option>
            ))}
          </select>
        </label>
        <label>
          What would you like to review?
          <select
            value={draft.type}
            onChange={(event) => onChange((current) => ({
              ...current,
              type: event.target.value,
              productId: "",
            }))}
          >
            <option value="product">A product</option>
            <option value="seller">The seller</option>
          </select>
        </label>
        {draft.type === "product" && (
          <label>
            Product
            <select
              value={draft.productId}
              onChange={(event) => onChange((current) => ({
                ...current,
                productId: event.target.value,
              }))}
              required
            >
              <option value="">Select a product</option>
              {productItems.map((item) => (
                <option key={item.productId} value={item.productId}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Rating
          <select
            value={draft.rating}
            onChange={(event) => onChange((current) => ({
              ...current,
              rating: event.target.value,
            }))}
          >
            <option value="5">★★★★★ Excellent</option>
            <option value="4">★★★★ Good</option>
            <option value="3">★★★ Average</option>
            <option value="2">★★ Poor</option>
            <option value="1">★ Very poor</option>
          </select>
        </label>
        <label>
          Your review
          <textarea
            value={draft.reviewText}
            onChange={(event) => onChange((current) => ({
              ...current,
              reviewText: event.target.value,
            }))}
            placeholder="Tell us about your experience"
            rows={5}
            required
          />
        </label>
        <label>
          Review images (optional)
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={onFilesChange}
          />
          <small>Select up to 4 images. They will be sent with your review.</small>
        </label>
        <button type="submit" disabled={isSending || orders.length === 0}>
          {isSending ? "Submitting..." : "Submit review"}
        </button>
        {orders.length === 0 && (
          <p className="storefront-review-center__hint">
            Your signed-in delivered orders will appear here.
          </p>
        )}
        {message && <p className="storefront-reviews__success">{message}</p>}
      </form>
    </div>
  );
}

function ProductReviews({
  reviews,
  reviewForm,
  reviewMessage,
  isSending,
  onReviewFormChange,
  onSubmitReview,
}) {
  return (
    <section className="storefront-reviews">
      <div>
        <h2>Verified customer reviews</h2>
        <div className="storefront-reviews__list">
          {reviews.map((review) => (
            <article key={review.id}>
              <header>
                <strong>{review.customerName}</strong>
                <span>
                  <Star size={14} fill="currentColor" /> {review.rating}/5
                </span>
              </header>
              <p>{review.reviewText}</p>
              <small>Verified purchase</small>
            </article>
          ))}
          {reviews.length === 0 && <p>No approved reviews yet.</p>}
        </div>
      </div>
      <form onSubmit={onSubmitReview}>
        <h3>Review a delivered order</h3>
        <input
          value={reviewForm.orderNumber}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              orderNumber: event.target.value,
            }))
          }
          placeholder="Order number (VD-000001)"
          required
        />
        <input
          value={reviewForm.phoneNumber}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              phoneNumber: event.target.value,
            }))
          }
          placeholder="Order phone number"
          required
        />
        <select
          value={reviewForm.rating}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              rating: event.target.value,
            }))
          }
        >
          <option value="5">5 - Excellent</option>
          <option value="4">4 - Good</option>
          <option value="3">3 - Average</option>
          <option value="2">2 - Poor</option>
          <option value="1">1 - Very poor</option>
        </select>
        <textarea
          value={reviewForm.reviewText}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              reviewText: event.target.value,
            }))
          }
          placeholder="Write your review"
          rows="4"
          required
        />
        <button type="submit" disabled={isSending}>
          Submit verified review
        </button>
        {reviewMessage && (
          <p className="storefront-reviews__success">{reviewMessage}</p>
        )}
      </form>
    </section>
  );
}

export default StorefrontPage;
