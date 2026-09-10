// Icons used by global search, theme controls, notifications, and the profile.
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { logoutUser } from "../services/authService";

import {
  Bell,
  Boxes,
  CheckCheck,
  ChevronDown,
  CreditCard,
  LogOut,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  ShieldAlert,
  ShoppingBag,
  Sparkles,
  Sun,
  Truck,
  UserRound,
  UsersRound,
} from "lucide-react";

import "./Header.css";
import { useAuth } from "../context/authContextValue";
import {
  getNotifications,
  markNotificationRead,
} from "../services/notificationService";
import { searchBusiness } from "../services/searchService";


function formatRelativeTime(timestamp) {
  if (!timestamp) return "";
  try {
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return "";
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSeconds < 45) return "Just now";
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-LK", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}


function getNotificationVisuals(notification) {
  const type = notification.type || "";
  const title = (notification.title || "").toLowerCase();

  // 1. Order related (VD-xxxx, new-order, placed order)
  if (
    type === "new-order" ||
    notification.orderId ||
    title.includes("order") ||
    title.includes("placed") ||
    title.includes("vd-")
  ) {
    return {
      icon: ShoppingBag,
      tone: "order",
    };
  }

  // 2. Customer inquiry / chat / question
  if (
    type === "chat-needs-attention" ||
    notification.chatSessionId ||
    title.includes("question") ||
    title.includes("chat") ||
    title.includes("message") ||
    title.includes("customer") ||
    title.includes("help")
  ) {
    return {
      icon: MessageSquare,
      tone: "chat",
    };
  }

  // 3. Fraud / Risk alert
  if (
    type === "fraud-report" ||
    title.includes("fraud") ||
    title.includes("risk") ||
    title.includes("alert")
  ) {
    return {
      icon: ShieldAlert,
      tone: "danger",
    };
  }

  // 4. Inventory / Stock
  if (
    type.includes("stock") ||
    notification.productId ||
    title.includes("stock") ||
    title.includes("inventory")
  ) {
    return {
      icon: Boxes,
      tone: "warning",
    };
  }

  // 5. Courier / Delivery
  if (
    type.includes("courier") ||
    notification.courierId ||
    title.includes("courier") ||
    title.includes("delivery")
  ) {
    return {
      icon: Truck,
      tone: "success",
    };
  }

  return {
    icon: Bell,
    tone: "neutral",
  };
}

function getNotificationPath(notification) {
  if (notification.chatSessionId || notification.type === "chat-needs-attention") {
    const query = new URLSearchParams({ tab: "messages" });
    if (notification.chatSessionId) query.set("session", notification.chatSessionId);
    return `/customers?${query.toString()}`;
  }
  if (notification.orderId || ["new-order", "fraud-report"].includes(notification.type)) {
    const orderNumber =
      notification.orderNumber ||
      notification.title?.match(/[A-Z]{2,}-\d+/)?.[0] ||
      "";
    return orderNumber
      ? `/orders?search=${encodeURIComponent(orderNumber)}`
      : "/orders";
  }
  if (notification.productId || notification.type?.includes("stock")) {
    const productSearch = notification.productName || notification.sku || "";
    return productSearch
      ? `/inventory?search=${encodeURIComponent(productSearch)}`
      : "/inventory";
  }
  if (notification.customerId) return "/customers";
  if (notification.courierId || notification.type?.includes("courier")) return "/couriers";
  return "/";
}

function Header({
  title,
  theme,
  onToggleTheme,
  onOpenProfile,
  onOpenSettings,
  isSidebarCollapsed = false,
  onToggleSidebar,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const searchInputReference = useRef(null);
  const notificationMenuReference = useRef(null);
  const profileMenuReference = useRef(null);
  const knownNotificationIdsReference = useRef(new Set());
  const notificationsLoadedReference = useRef(false);
  const { sellerProfile, business, membership } = useAuth();
  const businessName = sellerProfile?.businessName ?? "Your Business";
  const businessInitials = businessName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
  const roleLabel = (membership?.role ?? "viewer")
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  // profile menu
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  //Notification panel
  const [isNotiPanelOpen, setIsNotiPanelOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [notificationFilter, setNotificationFilter] = useState("all");
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState({
    orders: [],
    products: [],
    customers: [],
  });
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Header popups behave like normal menus: touching anywhere outside one
  // closes it, so they never stay over the page after the seller moves on.
  useEffect(() => {
    function closeMenusFromOutside(event) {
      if (
        notificationMenuReference.current
        && !notificationMenuReference.current.contains(event.target)
      ) {
        setIsNotiPanelOpen(false);
      }

      if (
        profileMenuReference.current
        && !profileMenuReference.current.contains(event.target)
      ) {
        setIsProfileMenuOpen(false);
      }
    }

    function closeMenusWithEscape(event) {
      if (event.key === "Escape") {
        setIsNotiPanelOpen(false);
        setIsProfileMenuOpen(false);
        setIsSearchOpen(false);
      }
    }

    document.addEventListener("pointerdown", closeMenusFromOutside);
    window.addEventListener("keydown", closeMenusWithEscape);

    return () => {
      document.removeEventListener("pointerdown", closeMenusFromOutside);
      window.removeEventListener("keydown", closeMenusWithEscape);
    };
  }, []);

  useEffect(() => {
    let requestIsCurrent = true;
    let refreshTimer;

    if (!business?.id) {
      setNotifications([]);
      return undefined;
    }

    function showDeviceNotification(notification) {
      if (!("Notification" in window) || window.Notification.permission !== "granted") return;

      const deviceNotification = new window.Notification(notification.title || "Vendly notification", {
        body: notification.message || "Open Vendly to view the update.",
        tag: `vendly-${notification.id}`,
      });
      deviceNotification.onclick = () => {
        window.focus();
        navigate(getNotificationPath(notification));
        deviceNotification.close();
      };
    }

    async function refreshNotifications() {
      try {
        const records = await getNotifications(business.id);
        if (!requestIsCurrent) return;

        if (notificationsLoadedReference.current) {
          records
            .filter(
              (notification) =>
                !notification.isRead &&
                !knownNotificationIdsReference.current.has(notification.id),
            )
            .forEach(showDeviceNotification);
        }

        knownNotificationIdsReference.current = new Set(
          records.map((notification) => notification.id),
        );
        notificationsLoadedReference.current = true;
        setNotifications(records);
      } catch (error) {
        console.error("Notifications could not be loaded:", error);
      }
    }

    refreshNotifications();
    refreshTimer = window.setInterval(refreshNotifications, 30000);

    return () => {
      requestIsCurrent = false;
      window.clearInterval(refreshTimer);
    };
  }, [business?.id, navigate]);

  async function requestDeviceNotificationPermission() {
    if ("Notification" in window && window.Notification.permission === "default") {
      await window.Notification.requestPermission();
    }
  }

  useEffect(() => {
    function focusGlobalSearch(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchInputReference.current?.focus();
      }
    }

    window.addEventListener("keydown", focusGlobalSearch);
    return () => window.removeEventListener("keydown", focusGlobalSearch);
  }, []);

  useEffect(() => {
    const cleanSearch = searchText.trim();

    if (!business?.id || cleanSearch.length < 2) {
      setSearchResults({ orders: [], products: [], customers: [] });
      setIsSearchOpen(false);
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchBusiness(business.id, cleanSearch, controller.signal)
        .then((results) => {
          setSearchResults(results);
          setIsSearchOpen(true);
        })
        .catch((error) => {
          if (error.name !== "AbortError") {
            console.error("Global search failed:", error);
          }
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [business?.id, searchText]);

  function openSearchResult(path) {
    setIsSearchOpen(false);
    navigate(path);
  }

  const unreadNotificationCount = notifications.filter(
    (notification) => !notification.isRead,
  ).length;

  async function handleMarkAllRead() {
    if (!business?.id) return;
    const unreadList = notifications.filter((item) => !item.isRead);
    if (unreadList.length === 0) return;

    setNotifications((current) =>
      current.map((item) => ({ ...item, isRead: true })),
    );

    try {
      await Promise.all(
        unreadList.map((item) => markNotificationRead(business.id, item.id)),
      );
    } catch (error) {
      console.error("Could not mark all notifications as read:", error);
    }
  }

  const visibleNotifications = notifications.filter((notification) => {
    if (notificationFilter === "unread") return !notification.isRead;
    return true;
  });

  async function handleNotificationClick(notification) {
    if (!business?.id) return;

    try {
      if (!notification.isRead) {
        await markNotificationRead(business.id, notification.id);
        setNotifications((current) =>
          current.map((item) =>
            item.id === notification.id ? { ...item, isRead: true } : item,
          ),
        );
      }
    } catch (error) {
      console.error("Notification could not be marked as read:", error);
    } finally {
      setIsNotiPanelOpen(false);
      navigate(getNotificationPath(notification));
    }
  }
 

  // Accessible text changes to describe the action the theme button will perform.
  const themeButtonLabel =
    theme === "dark" ? "Switch to light mode" : "Switch to dark mode";

  return (
    <header className="header">
      {/* The title and sidebar collapse toggle on the left */}
      <div className="header__left">
        {onToggleSidebar && (
          <button
            className="header__sidebar-toggle"
            type="button"
            onClick={onToggleSidebar}
            aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isSidebarCollapsed ? (
              <PanelLeftOpen size={20} aria-hidden="true" />
            ) : (
              <PanelLeftClose size={20} aria-hidden="true" />
            )}
          </button>
        )}
        <h1 className="header__title">{title}</h1>
      </div>

      {/* Global search layout; the search behaviour will be connected later. */}
      <div className="header__search">
        <Search size={17} aria-hidden="true" />

        <input
          ref={searchInputReference}
          type="search"
          value={searchText}
          onChange={(event) => {
            const value = event.target.value;
            setSearchText(value);
            if (!value && location.search) navigate(location.pathname, { replace: true });
          }}
          onFocus={() => {
            if (searchText.trim().length >= 2) setIsSearchOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setIsSearchOpen(false);
          }}
          placeholder="Search orders, customers, products..."
          aria-label="Global search"
        />

        <kbd>Ctrl + K</kbd>

        {isSearchOpen && (
          <div className="header__search-results">
            {searchResults.orders.length > 0 && <strong>Orders</strong>}
            {searchResults.orders.map((order) => (
              <button
                key={order.id}
                type="button"
                onClick={() => openSearchResult(`/orders?search=${encodeURIComponent(order.orderNumber)}`)}
              >
                <span>{order.orderNumber}</span>
                <small>{order.customerName} · {order.status}</small>
              </button>
            ))}

            {searchResults.products.length > 0 && <strong>Products</strong>}
            {searchResults.products.map((product) => (
              <button
                key={product.id}
                type="button"
                onClick={() => openSearchResult(`/inventory?search=${encodeURIComponent(product.name)}`)}
              >
                <span>{product.name}</span>
                <small>{product.sku || "Product"} · {product.availableStock} available</small>
              </button>
            ))}

            {searchResults.customers.length > 0 && <strong>Customers</strong>}
            {searchResults.customers.map((customer) => (
              <button
                key={customer.id}
                type="button"
                onClick={() => openSearchResult(`/customers?search=${encodeURIComponent(customer.name)}`)}
              >
                <span>{customer.name}</span>
                <small>+{customer.phone} · {customer.riskLevel} risk</small>
              </button>
            ))}

            {Object.values(searchResults).every((items) => items.length === 0) && (
              <p>No matching orders, products or customers.</p>
            )}
          </div>
        )}
      </div>

      {/* Header controls for theme, settings, notifications, and business profile. */}
      <div className="header__actions">
        {/* Light/dark theme switch. */}
        <button
          className="header__icon-button"
          type="button"
          onClick={onToggleTheme}
          aria-label={themeButtonLabel}
          title={themeButtonLabel}
        >
          {theme === "dark" ? (
            <Sun size={20} aria-hidden="true" />
          ) : (
            <Moon size={20} aria-hidden="true" />
          )}
        </button>

        <span className="header__divider" aria-hidden="true" />

        {/* Application settings shortcut. */}
        <div className="header__settings-menu">
        <button
          className="header__icon-button"
          type="button"
          onClick={() => onOpenSettings("general")}
          aria-label="Open settings"
          title="Settings"
        >
          <Settings size={20} aria-hidden="true" />
        </button>
        </div>

        {/* Notification bell and unread notification count. */}
        <div className="header__notification-menu" ref={notificationMenuReference}>
          <button
            className="header__icon-button header__notification"
            type="button"
            onClick={() => {
              requestDeviceNotificationPermission();
              setIsNotiPanelOpen((currentValue) => !currentValue);
            }}
            aria-label="View notifications"
            title="Notifications"
            aria-haspopup="menu"
            aria-expanded={isNotiPanelOpen}
          >
            <Bell size={20} aria-hidden="true" />
            {unreadNotificationCount > 0 && (
              <span className="header__notification-count">
                {unreadNotificationCount > 99 ? "99+" : unreadNotificationCount}
              </span>
            )}
          </button>

          {isNotiPanelOpen && (
            <div className="header__notification-dropdown" role="menu">
              <div className="header__notification-heading">
                <div className="header__notification-heading-left">
                  <strong>Notifications</strong>
                  {unreadNotificationCount > 0 && (
                    <span className="header__notification-unread-badge">
                      {unreadNotificationCount} unread
                    </span>
                  )}
                </div>
                {unreadNotificationCount > 0 && (
                  <button
                    type="button"
                    className="header__notification-mark-all"
                    onClick={handleMarkAllRead}
                    title="Mark all notifications as read"
                  >
                    <CheckCheck size={14} aria-hidden="true" />
                    <span>Mark all read</span>
                  </button>
                )}
              </div>

              <div className="header__notification-filter-tabs">
                <button
                  type="button"
                  className={`header__notification-filter-btn ${
                    notificationFilter === "all" ? "is-active" : ""
                  }`}
                  onClick={() => setNotificationFilter("all")}
                >
                  All ({notifications.length})
                </button>
                <button
                  type="button"
                  className={`header__notification-filter-btn ${
                    notificationFilter === "unread" ? "is-active" : ""
                  }`}
                  onClick={() => setNotificationFilter("unread")}
                >
                  Unread ({unreadNotificationCount})
                </button>
              </div>

              <div className="header__notification-list">
                {visibleNotifications.length === 0 ? (
                  <div className="header__notification-empty">
                    <div className="header__notification-empty-icon">
                      <Bell size={24} strokeWidth={1.8} aria-hidden="true" />
                    </div>
                    <strong>
                      {notificationFilter === "unread"
                        ? "No unread notifications"
                        : "No notifications yet"}
                    </strong>
                    <p>
                      {notificationFilter === "unread"
                        ? "You are all caught up with your store activity."
                        : "New orders, customer messages and updates will appear here."}
                    </p>
                  </div>
                ) : (
                  visibleNotifications.slice(0, 25).map((notification) => {
                    const visuals = getNotificationVisuals(notification);
                    const VisualIcon = visuals.icon;
                    const relativeTime = formatRelativeTime(notification.createdAt);

                    return (
                      <button
                        className={`header__notification-item ${
                          notification.isRead
                            ? "header__notification-item--read"
                            : "header__notification-item--unread"
                        }`}
                        key={notification.id}
                        type="button"
                        role="menuitem"
                        onClick={() => handleNotificationClick(notification)}
                      >
                        <div
                          className={`header__notification-item-icon header__notification-item-icon--${visuals.tone}`}
                          aria-hidden="true"
                        >
                          <VisualIcon size={18} strokeWidth={2.2} />
                        </div>

                        <div className="header__notification-item-body">
                          <div className="header__notification-item-header">
                            <strong className="header__notification-item-title">
                              {notification.title}
                            </strong>
                            {relativeTime && (
                              <span className="header__notification-item-time">
                                {relativeTime}
                              </span>
                            )}
                          </div>
                          <p className="header__notification-item-msg">
                            {notification.message}
                          </p>
                        </div>

                        {!notification.isRead && (
                          <span
                            className="header__notification-unread-dot"
                            aria-label="Unread notification"
                          />
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Current business profile menu. */}

        <div className="header__profile-menu" ref={profileMenuReference}>
          <button
            className="header__business"
            type="button"
            onClick={() =>
              setIsProfileMenuOpen((currentValue) => !currentValue)
            }
            aria-label="Open business profile"
            aria-haspopup="menu"
            aria-expanded={isProfileMenuOpen}
          >
            <span className="header__avatar">{businessInitials}</span>

            <span className="header__business-details">
              <strong>{businessName}</strong>
              <small>{roleLabel}</small>
            </span>

            <ChevronDown size={16} aria-hidden="true" />
          </button>

          {isProfileMenuOpen && (
            <div className="header__profile-dropdown" role="menu">
              <button
                className="header__dropdown-item"
                type="button"
                onClick={() => {
                  setIsProfileMenuOpen(false);
                  onOpenProfile();
                }}
                role="menuitem"
              >
                <UserRound size={17} aria-hidden="true" />
                My Profile
              </button>
              <button
                className="header__dropdown-item"
                type="button"
                onClick={() => {
                  setIsProfileMenuOpen(false);
                  onOpenSettings("staff");
                }}
                role="menuitem"
              >
                <UsersRound size={17} aria-hidden="true" />
                Staff & permissions
              </button>
              <button
                className="header__dropdown-item"
                type="button"
                onClick={() => {
                  setIsProfileMenuOpen(false);
                  onOpenSettings("plan");
                }}
                role="menuitem"
              >
                <Sparkles size={17} aria-hidden="true" />
                Current plan
              </button>
              <button
                className="header__dropdown-item"
                type="button"
                onClick={() => {
                  setIsProfileMenuOpen(false);
                  onOpenSettings("billing");
                }}
                role="menuitem"
              >
                <CreditCard size={17} aria-hidden="true" />
                Billing
              </button>
              <button
                className="header__dropdown-item header__dropdown-item--danger"
                type="button"
                onClick={handleLogout}
                role="menuitem"
              >
                <LogOut size={17} aria-hidden="true" />
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

async function handleLogout() {
  try {
    await logoutUser();
  } catch (error) {
    console.error("Logout failed:", error);
  }
}

export default Header;
