import { useEffect, useState } from "react";
import { Clock3, LogIn, LogOut, MessageSquareText, PackageSearch, UserRound, X } from "lucide-react";
import {
  loginAsGuest,
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
} from "../services/authService";
import { getCustomerChats, getCustomerOrders } from "../services/publicService";
import "./CustomerAccountModal.css";

function readableStatus(value = "") {
  return value.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function CustomerAccountModal({ isOpen, onClose, user, storeCode }) {
  const [mode, setMode] = useState("login");
  const [tab, setTab] = useState("orders");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [orders, setOrders] = useState([]);
  const [chats, setChats] = useState([]);
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    if (!isOpen || !user || !storeCode) return;
    let active = true;
    setIsBusy(true);
    Promise.all([getCustomerOrders(storeCode), getCustomerChats(storeCode)])
      .then(([orderResponse, chatResponse]) => {
        if (!active) return;
        setOrders(orderResponse.orders ?? []);
        setChats(chatResponse.chats ?? []);
        setError("");
      })
      .catch((requestError) => active && setError(requestError.message))
      .finally(() => active && setIsBusy(false));
    return () => { active = false; };
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
    try { await action(); } catch (authError) { setError(authError.message); }
    finally { setIsBusy(false); }
  }

  return (
    <div className="customer-account-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="customer-account-modal" role="dialog" aria-modal="true" aria-label="Customer account">
        <header><div><UserRound size={20} /><div><strong>{user ? "My account" : "Customer login"}</strong><small>Save chats, orders and tracking details</small></div></div><button type="button" onClick={onClose} aria-label="Close"><X size={19} /></button></header>

        {!user ? (
          <div className="customer-account-auth">
            <div className="customer-account-switch"><button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => setMode("login")}>Log in</button><button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => setMode("register")}>Create account</button></div>
            <form onSubmit={submit}>
              {mode === "register" && <label>Name<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>}
              <label>Email<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label>
              <label>Password<input type="password" minLength={6} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
              <button className="customer-account-primary" disabled={isBusy}><LogIn size={17} />{mode === "login" ? "Log in" : "Create account"}</button>
            </form>
            <div className="customer-account-divider"><span>or</span></div>
            <button type="button" onClick={() => authenticate(loginWithGoogle)} disabled={isBusy}>Continue with Google</button>
            <button type="button" onClick={() => authenticate(loginAsGuest)} disabled={isBusy}>Continue as guest</button>
            <small className="customer-account-hint">Guest history remains available on this browser. Create an account to use it across devices.</small>
          </div>
        ) : (
          <div className="customer-account-portal">
            <div className="customer-account-identity"><span>{user.isAnonymous ? "G" : (user.displayName || user.email || "C").charAt(0).toUpperCase()}</span><div><strong>{user.isAnonymous ? "Guest customer" : user.displayName || "Customer"}</strong><small>{user.isAnonymous ? "History saved on this device" : user.email}</small></div><button type="button" onClick={() => authenticate(logoutUser)}><LogOut size={16} /> Log out</button></div>
            <nav><button className={tab === "orders" ? "is-active" : ""} type="button" onClick={() => setTab("orders")}><PackageSearch size={16} /> Orders</button><button className={tab === "chats" ? "is-active" : ""} type="button" onClick={() => setTab("chats")}><MessageSquareText size={16} /> Chats</button></nav>
            {isBusy && <p className="customer-account-empty">Loading history…</p>}
            {!isBusy && tab === "orders" && <div className="customer-account-list">{orders.length ? orders.map((order) => <article key={order.id}><div><strong>{order.orderNumber}</strong><span className={`customer-order-status customer-order-status--${order.fulfilmentStatus}`}>{readableStatus(order.fulfilmentStatus)}</span></div><p>{order.items.map((item) => `${item.name} × ${item.quantity}`).join(", ")}</p><dl><div><dt>Total</dt><dd>Rs {(order.totalAmountMinor / 100).toLocaleString("en-LK")}</dd></div><div><dt>Courier</dt><dd>{order.courier?.name || "Being assigned"}</dd></div><div><dt>Waybill</dt><dd>{order.waybillNumber || "Pending"}</dd></div></dl><div className="customer-order-progress"><span className="is-complete">Confirmed</span><span className={["packed", "shipped", "delivered"].includes(order.fulfilmentStatus) ? "is-complete" : ""}>Packed</span><span className={["shipped", "delivered"].includes(order.fulfilmentStatus) ? "is-complete" : ""}>Shipped</span><span className={order.fulfilmentStatus === "delivered" ? "is-complete" : ""}>Delivered</span></div></article>) : <p className="customer-account-empty">No orders are linked to this account yet.</p>}</div>}
            {!isBusy && tab === "chats" && <div className="customer-account-list">{chats.length ? chats.map((chat) => <article key={chat.id}><div><strong>Chat conversation</strong><span><Clock3 size={13} /> {chat.status}</span></div>{chat.messages.slice(-4).map((message) => <p key={message.id}><b>{message.role === "assistant" ? "Vendly" : "You"}:</b> {message.message}</p>)}</article>) : <p className="customer-account-empty">No saved chats yet.</p>}</div>}
          </div>
        )}
        {error && <p className="customer-account-error" role="alert">{error}</p>}
      </section>
    </div>
  );
}

export default CustomerAccountModal;
