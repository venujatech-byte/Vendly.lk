import { useEffect, useState } from "react";
import {
  AlertCircle,
  Clock3,
  Eye,
  EyeOff,
  Lock,
  LogIn,
  LogOut,
  Mail,
  MessageSquareText,
  PackageSearch,
  Sparkles,
  User,
  UserRound,
  X,
} from "lucide-react";
import {
  loginAsGuest,
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
} from "../services/authService";
import { getCustomerChats, getCustomerOrders } from "../services/publicService";
import googleLogo from "../assets/g.webp";
import "./CustomerAccountModal.css";

function readableStatus(value = "") {
  return value.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function CustomerAccountModal({ isOpen, onClose, user, storeCode, onOpenChat }) {
  const [mode, setMode] = useState("login");
  const [tab, setTab] = useState("orders");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [orders, setOrders] = useState([]);
  const [chats, setChats] = useState([]);
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    if (!isOpen || !user || !storeCode) return;
    let active = true;
    setIsBusy(true);
    setError("");

    Promise.allSettled([getCustomerOrders(storeCode), getCustomerChats(storeCode)])
      .then(([orderResult, chatResult]) => {
        if (!active) return;
        if (orderResult.status === "fulfilled") {
          setOrders(orderResult.value?.orders ?? []);
        }
        if (chatResult.status === "fulfilled") {
          setChats(chatResult.value?.chats ?? []);
        }
        if (orderResult.status === "rejected" && chatResult.status === "rejected") {
          setError("Could not load account history. Please try again.");
        }
      })
      .catch((requestError) => {
        if (active) setError(requestError?.message || "Failed to load account details.");
      })
      .finally(() => {
        if (active) setIsBusy(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen, storeCode, user]);

  if (!isOpen) return null;

  async function submit(event) {
    event.preventDefault();
    setIsBusy(true);
    setError("");
    try {
      if (mode === "register") {
        await registerWithEmail(form.name, form.email, form.password);
        await logoutUser();
        setError("Check your email and verify your address, then log in.");
        setMode("login");
      } else {
        await loginWithEmail(form.email, form.password);
      }
    } catch (authError) {
      setError(authError.message);
    } finally {
      setIsBusy(false);
    }
  }

  async function authenticate(action) {
    setIsBusy(true);
    setError("");
    try {
      await action();
    } catch (authError) {
      setError(authError.message);
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div
      className="customer-account-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section className="customer-account-modal" role="dialog" aria-modal="true" aria-label="Customer account">
        <header>
          <div>
            <UserRound size={20} />
            <div>
              <strong>{user ? "My account" : "Customer login"}</strong>
              <small>Save chats, orders and tracking details</small>
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close">
            <X size={19} />
          </button>
        </header>

        {!user ? (
          <div className="customer-account-auth">
            <div className="customer-account-switch">
              <button
                className={mode === "login" ? "is-active" : ""}
                type="button"
                onClick={() => setMode("login")}
              >
                Sign in
              </button>
              <button
                className={mode === "register" ? "is-active" : ""}
                type="button"
                onClick={() => setMode("register")}
              >
                Create account
              </button>
            </div>
            <form onSubmit={submit}>
              {mode === "register" && (
                <label>
                  <span>Full Name</span>
                  <div className="customer-modal-input-wrap">
                    <User size={16} className="customer-modal-input-icon" aria-hidden="true" />
                    <input
                      value={form.name}
                      onChange={(event) => setForm({ ...form, name: event.target.value })}
                      placeholder="Your name"
                      required
                    />
                  </div>
                </label>
              )}
              <label>
                <span>Email address</span>
                <div className="customer-modal-input-wrap">
                  <Mail size={16} className="customer-modal-input-icon" aria-hidden="true" />
                  <input
                    type="email"
                    value={form.email}
                    onChange={(event) => setForm({ ...form, email: event.target.value })}
                    placeholder="customer@example.com"
                    required
                  />
                </div>
              </label>
              <label>
                <span>Password</span>
                <div className="customer-modal-input-wrap customer-auth-password-row">
                  <Lock size={16} className="customer-modal-input-icon" aria-hidden="true" />
                  <input
                    type={showPassword ? "text" : "password"}
                    minLength={6}
                    value={form.password}
                    onChange={(event) => setForm({ ...form, password: event.target.value })}
                    placeholder="At least 6 characters"
                    required
                  />
                  <button
                    type="button"
                    className="customer-auth-toggle-pwd"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </label>

              {error && (
                <div className="customer-modal-auth-alert" role="alert">
                  <AlertCircle size={16} />
                  <span>{error}</span>
                </div>
              )}

              <button className="customer-account-primary" disabled={isBusy} type="submit">
                <LogIn size={17} />
                {mode === "login" ? "Sign In" : "Create Account"}
              </button>
            </form>
            <div className="customer-account-divider">
              <span>or continue with</span>
            </div>
            <button
              type="button"
              className="customer-modal-google-btn"
              onClick={() => authenticate(loginWithGoogle)}
              disabled={isBusy}
            >
              <img width="18" height="18" src={googleLogo} alt="" aria-hidden="true" />
              <span>Continue with Google</span>
            </button>
            <button
              type="button"
              className="customer-modal-guest-btn"
              onClick={() => authenticate(loginAsGuest)}
              disabled={isBusy}
            >
              <Sparkles size={16} />
              <span>Continue as guest</span>
            </button>
            <small className="customer-account-hint">
              Guest history is saved on this browser. Create an account anytime to access it across devices.
            </small>
          </div>
        ) : (
          <div className="customer-account-portal">
            <div className="customer-account-identity">
              <span>{user.isAnonymous ? "G" : (user.displayName || user.email || "C").charAt(0).toUpperCase()}</span>
              <div>
                <strong>{user.isAnonymous ? "Guest customer" : user.displayName || "Customer"}</strong>
                <small>{user.isAnonymous ? "History saved on this device" : user.email}</small>
              </div>
              <button type="button" onClick={() => authenticate(logoutUser)}>
                <LogOut size={16} /> Log out
              </button>
            </div>
            <nav>
              <button className={tab === "orders" ? "is-active" : ""} type="button" onClick={() => setTab("orders")}>
                <PackageSearch size={16} /> Orders
              </button>
              <button className={tab === "chats" ? "is-active" : ""} type="button" onClick={() => setTab("chats")}>
                <MessageSquareText size={16} /> Chats
              </button>
            </nav>
            {isBusy && <p className="customer-account-empty">Loading history…</p>}
            {!isBusy && tab === "orders" && (
              <div className="customer-account-list">
                {orders.length ? (
                  orders.map((order) => (
                    <article key={order.id}>
                      <div>
                        <strong>{order.orderNumber}</strong>
                        <span className={`customer-order-status customer-order-status--${order.fulfilmentStatus}`}>
                          {readableStatus(order.fulfilmentStatus)}
                        </span>
                      </div>
                      <p>{order.items.map((item) => `${item.name} × ${item.quantity}`).join(", ")}</p>
                      <dl>
                        <div>
                          <dt>Total</dt>
                          <dd>Rs {(order.totalAmountMinor / 100).toLocaleString("en-LK")}</dd>
                        </div>
                        <div>
                          <dt>Courier</dt>
                          <dd>{order.courier?.name || "Being assigned"}</dd>
                        </div>
                        <div>
                          <dt>Waybill</dt>
                          <dd>{order.waybillNumber || "Pending"}</dd>
                        </div>
                      </dl>
                      <div className="customer-order-progress">
                        <span className="is-complete">Confirmed</span>
                        <span className={["packed", "shipped", "delivered"].includes(order.fulfilmentStatus) ? "is-complete" : ""}>
                          Packed
                        </span>
                        <span className={["shipped", "delivered"].includes(order.fulfilmentStatus) ? "is-complete" : ""}>
                          Shipped
                        </span>
                        <span className={order.fulfilmentStatus === "delivered" ? "is-complete" : ""}>
                          Delivered
                        </span>
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="customer-account-empty">No orders are linked to this account yet.</p>
                )}
              </div>
            )}
            {!isBusy && tab === "chats" && (
              <div className="customer-account-list">
                {chats.length ? (
                  chats.map((chat) => {
                    const chatMessages = Array.isArray(chat?.messages) && chat.messages.length > 0
                      ? chat.messages.slice(-4)
                      : chat?.lastMessage
                      ? [{ id: `${chat.id}-last`, role: chat.lastMessageRole || "assistant", message: chat.lastMessage }]
                      : [];

                    return (
                      <article key={chat.id} className="customer-chat-card">
                        <div className="customer-chat-card__header">
                          <div>
                            <strong>Chat conversation</strong>
                            {chat.updatedAt && (
                              <span className="customer-chat-card__date">
                                {new Date(chat.updatedAt).toLocaleDateString("en-LK", {
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                            )}
                          </div>
                          <span className={`customer-chat-card__badge status--${chat.status || "active"}`}>
                            <Clock3 size={13} /> {readableStatus(chat.status || "active")}
                          </span>
                        </div>
                        <div className="customer-chat-card__messages">
                          {chatMessages.length > 0 ? (
                            chatMessages.map((message) => (
                              <p key={message.id} className="customer-chat-card__msg">
                                <b>{["assistant", "seller"].includes(message.role) ? "Vendly" : "You"}:</b>{" "}
                                {message.message}
                              </p>
                            ))
                          ) : (
                            <p className="customer-chat-card__empty-msg">No messages in this chat yet.</p>
                          )}
                        </div>
                        {onOpenChat && (
                          <button
                            type="button"
                            className="customer-chat-card__resume"
                            onClick={() => {
                              onClose();
                              onOpenChat(chat);
                            }}
                          >
                            <MessageSquareText size={15} /> Resume this chat
                          </button>
                        )}
                      </article>
                    );
                  })
                ) : (
                  <p className="customer-account-empty">No saved chats yet.</p>
                )}
              </div>
            )}
          </div>
        )}
        {error && (
          <p className="customer-account-error" role="alert">
            {error}
          </p>
        )}
      </section>
    </div>
  );
}

export default CustomerAccountModal;
