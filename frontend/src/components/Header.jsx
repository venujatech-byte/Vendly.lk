// Icons used by global search, theme controls, notifications, and the profile.
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { logoutUser } from "../services/authService";

import {
  Bell,
  ChevronDown,
  Moon,
  Search,
  Settings,
  Sun,
  LogOut,
  UserRound,
} from "lucide-react";

import "./Header.css";
import { useAuth } from "../context/authContextValue";
import {
  getNotifications,
  markNotificationRead,
} from "../services/notificationService";
import StaffSettings from "./StaffSettings";
import { searchBusiness } from "../services/searchService";
import ProfileModal from "./ProfileModal";

function getNotificationPath(notification) {
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

function Header({ title, theme, onToggleTheme }) {
  const navigate = useNavigate();
  const location = useLocation();
  const searchInputReference = useRef(null);
  const knownNotificationIdsReference = useRef(new Set());
  const notificationsLoadedReference = useRef(false);
  const { user, sellerProfile, business, membership } = useAuth();
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
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  //Notification panel
  const [isNotiPanelOpen, setIsNotiPanelOpen] = useState(false);
  //Settongs Panel
  const [isSettingsPanelOpen, setIsSettingsPanelOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState({
    orders: [],
    products: [],
    customers: [],
  });
  const [isSearchOpen, setIsSearchOpen] = useState(false);

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
      {/* The title is supplied by the page route in App.jsx. */}
      <h1 className="header__title">{title}</h1>

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
          onClick={() => setIsSettingsPanelOpen((currentValue) => !currentValue)}
          aria-label="Open settings"
          title="Settings"
        >
          <Settings size={20} aria-hidden="true" />
        </button>

        {isSettingsPanelOpen && (
            <div className="header__settings-dropdown" role="menu">
              <StaffSettings
                businessId={business?.id}
                currentRole={membership?.role}
              />
            </div>
          )}
        </div>

        {/* Notification bell and unread notification count. */}
        <div className="header__notification-menu">
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
                <strong>Notifications</strong>
                <span>{unreadNotificationCount} unread</span>
              </div>

              <div className="header__notification-list">
                {notifications.length === 0 ? (
                  <p className="header__notification-empty">No notifications yet.</p>
                ) : (
                  notifications.slice(0, 8).map((notification) => (
                    <button
                      className={`header__notification-item ${
                        notification.isRead
                          ? ""
                          : "header__notification-item--unread"
                      }`}
                      key={notification.id}
                      type="button"
                      role="menuitem"
                      onClick={() => handleNotificationClick(notification)}
                    >
                      <strong>{notification.title}</strong>
                      <span>{notification.message}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Current business profile menu. */}

        <div className="header__profile-menu">
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
                  setIsProfileModalOpen(true);
                }}
                role="menuitem"
              >
                <UserRound size={17} aria-hidden="true" />
                My Profile
              </button>
              <button
                className="header__dropdown-item"
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

      <ProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        user={user}
      />
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
