import {
  Bell,
  Check,
  CreditCard,
  Mail,
  Palette,
  Phone,
  Settings,
  ShieldCheck,
  Sparkles,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../context/authContextValue";
import {
  createPayHereCheckout,
  getBusinessBilling,
  redirectToPayHere,
} from "../services/billingService";
import { updatePublicContact } from "../services/businessService";
import ModalShell from "./ModalShell";
import StaffSettings from "./StaffSettings";

import "./SettingsModal.css";


const sections = [
  { id: "general", label: "General", icon: Settings },
  { id: "staff", label: "Staff & permissions", icon: UsersRound },
  { id: "plan", label: "Current plan", icon: Sparkles },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "preferences", label: "Preferences", icon: Palette },
];


function formatMoney(amountMinor = 0) {
  if (!amountMinor) return "Free";
  return `LKR ${(amountMinor / 100).toLocaleString("en-LK")}`;
}


function readablePaymentStatus(status = "") {
  const labels = {
    initiated: "Waiting for checkout",
    pending: "Payment pending",
    paid: "Payment completed",
    cancelled: "Payment cancelled",
    failed: "Payment failed",
    chargedback: "Payment charged back",
  };
  return labels[status] || "No payment yet";
}


function SettingsModal({
  isOpen,
  initialSection = "general",
  onClose,
  onOpenProfile,
  theme,
  onToggleTheme,
}) {
  const {
    user,
    sellerProfile,
    business,
    membership,
    refreshSellerProfile,
  } = useAuth();
  const [activeSection, setActiveSection] = useState(initialSection);
  const [billing, setBilling] = useState(null);
  const [billingError, setBillingError] = useState("");
  const [isBillingLoading, setIsBillingLoading] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState("seller");
  const [checkoutWorking, setCheckoutWorking] = useState(false);
  const [contactDetails, setContactDetails] = useState({ phone: "", email: "" });
  const [contactError, setContactError] = useState("");
  const [contactMessage, setContactMessage] = useState("");
  const [isContactSaving, setIsContactSaving] = useState(false);
  const [billingDetails, setBillingDetails] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    city: "",
  });

  useEffect(() => {
    if (isOpen) setActiveSection(initialSection);
  }, [initialSection, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    setBillingDetails((current) => ({
      ...current,
      name: current.name || user?.displayName || sellerProfile?.ownerName || "",
      email: current.email || user?.email || business?.email || "",
      phone: current.phone || business?.phone || "",
      address:
        current.address ||
        business?.address?.line1 ||
        business?.address?.street ||
        "",
      city: current.city || business?.address?.city || "",
    }));
  }, [business, isOpen, sellerProfile?.ownerName, user?.displayName, user?.email]);

  useEffect(() => {
    if (!isOpen) return;
    setContactDetails({
      phone: business?.publicPhone || "",
      email: business?.publicEmail || "",
    });
    setContactError("");
    setContactMessage("");
  }, [business?.publicEmail, business?.publicPhone, isOpen]);

  useEffect(() => {
    let requestIsCurrent = true;
    if (!isOpen || !business?.id) return undefined;

    setIsBillingLoading(true);
    setBillingError("");
    getBusinessBilling(business.id)
      .then((result) => {
        if (!requestIsCurrent) return;
        setBilling(result);
        const paidPlan = result.currentPlan?.id;
        if (paidPlan && paidPlan !== "early_access") setSelectedPlanId(paidPlan);
      })
      .catch((error) => {
        if (requestIsCurrent) setBillingError(error.message);
      })
      .finally(() => {
        if (requestIsCurrent) setIsBillingLoading(false);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id, isOpen]);

  const selectedPlan = useMemo(
    () => billing?.plans?.find((plan) => plan.id === selectedPlanId),
    [billing?.plans, selectedPlanId],
  );
  const isOwner = membership?.role === "owner";
  const canManageBusiness = ["owner", "admin"].includes(membership?.role);

  function choosePlan(planId) {
    setSelectedPlanId(planId);
    setActiveSection("billing");
  }

  function updateBillingDetail(event) {
    setBillingDetails((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function updateContactDetail(event) {
    setContactDetails((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
    setContactError("");
    setContactMessage("");
  }

  async function savePublicContact(event) {
    event.preventDefault();
    if (!business?.id || !canManageBusiness) return;

    setIsContactSaving(true);
    setContactError("");
    setContactMessage("");

    try {
      await updatePublicContact(business.id, contactDetails);
      await refreshSellerProfile();
      setContactMessage("Storefront contact details saved.");
    } catch (error) {
      setContactError(error.message);
    } finally {
      setIsContactSaving(false);
    }
  }

  async function startCheckout(event) {
    event.preventDefault();
    if (!business?.id || !selectedPlan) return;

    setCheckoutWorking(true);
    setBillingError("");
    try {
      const checkout = await createPayHereCheckout(business.id, {
        planId: selectedPlan.id,
        ...billingDetails,
      });
      redirectToPayHere(checkout);
    } catch (error) {
      setBillingError(error.message);
      setCheckoutWorking(false);
    }
  }

  function renderGeneral() {
    return (
      <div className="settings-modal__stack">
        <section className="settings-modal__card settings-modal__identity">
          <span className="settings-modal__avatar">
            {(sellerProfile?.businessName || "VB").slice(0, 2).toUpperCase()}
          </span>
          <div>
            <small>Business workspace</small>
            <h3>{sellerProfile?.businessName || business?.name || "Your Business"}</h3>
            <p>{user?.email}</p>
          </div>
          <span className="settings-modal__role">{membership?.role || "viewer"}</span>
        </section>

        <section className="settings-modal__card">
          <div className="settings-modal__section-heading">
            <UserRound size={20} />
            <div><h3>Account & security</h3><p>Manage your email, sign-in method and password.</p></div>
          </div>
          <button className="settings-modal__outline-button" type="button" onClick={onOpenProfile}>
            Open My Profile
          </button>
        </section>

        <form className="settings-modal__card" onSubmit={savePublicContact}>
          <div className="settings-modal__section-heading">
            <Phone size={20} />
            <div>
              <h3>Storefront contact details</h3>
              <p>These details appear on the Contact page customers can open from your store link.</p>
            </div>
          </div>

          <div className="settings-modal__contact-grid">
            <label>
              <span><Phone size={14} /> Contact number</span>
              <input
                name="phone"
                value={contactDetails.phone}
                onChange={updateContactDetail}
                placeholder="Example: +94 77 123 4567"
                autoComplete="tel"
                disabled={!canManageBusiness || isContactSaving}
              />
            </label>
            <label>
              <span><Mail size={14} /> Contact email</span>
              <input
                name="email"
                type="email"
                value={contactDetails.email}
                onChange={updateContactDetail}
                placeholder="Example: support@yourstore.lk"
                autoComplete="email"
                disabled={!canManageBusiness || isContactSaving}
              />
            </label>
          </div>

          {contactError && <p className="settings-modal__error" role="alert">{contactError}</p>}
          {contactMessage && <p className="settings-modal__success" role="status">{contactMessage}</p>}

          <div className="settings-modal__contact-footer">
            <small>Leave a field empty if you do not want to publish it.</small>
            <button type="submit" disabled={!canManageBusiness || isContactSaving}>
              {isContactSaving ? "Saving..." : "Save contact details"}
            </button>
          </div>
          {!canManageBusiness && (
            <p className="settings-modal__notice">Only an owner or admin can change public contact details.</p>
          )}
        </form>

        <section className="settings-modal__card settings-modal__details-grid">
          <div><span>Currency</span><strong>{business?.currency || "LKR"}</strong></div>
          <div><span>Timezone</span><strong>{business?.timezone || "Asia/Colombo"}</strong></div>
          <div><span>Workspace ID</span><strong>{business?.id || "-"}</strong></div>
          <div><span>Store code</span><strong>{business?.shortCode || "-"}</strong></div>
        </section>
      </div>
    );
  }

  function renderPlan() {
    if (isBillingLoading) return <p className="settings-modal__empty">Loading plans...</p>;
    return (
      <div className="settings-modal__stack">
        <section className="settings-modal__current-plan">
          <div>
            <span>Current plan</span>
            <h3>{billing?.currentPlan?.name || "Early access"}</h3>
            <p>{billing?.currentPlan?.description}</p>
          </div>
          <strong>{formatMoney(billing?.currentPlan?.amountMinor)}{billing?.currentPlan?.amountMinor ? "/month" : ""}</strong>
        </section>

        <div className="settings-modal__plans">
          {(billing?.plans || []).map((plan) => (
            <article
              className={`settings-modal__plan ${plan.id === billing?.currentPlan?.id ? "settings-modal__plan--current" : ""}`}
              key={plan.id}
            >
              {plan.id === billing?.currentPlan?.id && <span className="settings-modal__plan-badge">Current</span>}
              <h3>{plan.name}</h3>
              <strong>{formatMoney(plan.amountMinor)}{plan.amountMinor ? <small>/month</small> : null}</strong>
              <p>{plan.description}</p>
              <ul>{plan.features.map((feature) => <li key={feature}><Check size={14} />{feature}</li>)}</ul>
              {plan.amountMinor > 0 && plan.id !== billing?.currentPlan?.id && (
                <button type="button" onClick={() => choosePlan(plan.id)} disabled={!isOwner}>
                  {isOwner ? `Choose ${plan.name}` : "Owner access required"}
                </button>
              )}
            </article>
          ))}
        </div>
      </div>
    );
  }

  function renderBilling() {
    return (
      <form className="settings-modal__billing" onSubmit={startCheckout}>
        <section className="settings-modal__checkout-summary">
          <div><span>Selected plan</span><strong>{selectedPlan?.name || "Seller plan"}</strong></div>
          <strong>{formatMoney(selectedPlan?.amountMinor)}<small>/month</small></strong>
        </section>

        {billing?.lastPayment && (
          <section className="settings-modal__payment-status" aria-live="polite">
            <div>
              <span>Latest PayHere payment</span>
              <strong>{readablePaymentStatus(billing.lastPayment.status)}</strong>
            </div>
            <div>
              <span>Reference</span>
              <strong>{billing.lastPayment.orderId}</strong>
            </div>
            <span className={`settings-modal__payment-pill settings-modal__payment-pill--${billing.lastPayment.status || "initiated"}`}>
              {billing.lastPayment.status || "initiated"}
            </span>
          </section>
        )}

        <section className="settings-modal__card">
          <div className="settings-modal__section-heading">
            <CreditCard size={20} />
            <div><h3>PayHere sandbox checkout</h3><p>No real money is charged while sandbox mode is enabled.</p></div>
          </div>
          <div className="settings-modal__billing-grid">
            <label>Billing name<input name="name" value={billingDetails.name} onChange={updateBillingDetail} required /></label>
            <label>Email<input name="email" type="email" value={billingDetails.email} onChange={updateBillingDetail} required /></label>
            <label>Phone<input name="phone" value={billingDetails.phone} onChange={updateBillingDetail} required /></label>
            <label>City<input name="city" value={billingDetails.city} onChange={updateBillingDetail} required /></label>
            <label className="settings-modal__billing-address">Address<input name="address" value={billingDetails.address} onChange={updateBillingDetail} required /></label>
          </div>
        </section>

        {!billing?.payhere?.configured && (
          <p className="settings-modal__notice" role="status">
            Add PAYHERE_MERCHANT_ID and PAYHERE_MERCHANT_SECRET to the Flask environment to enable sandbox checkout.
          </p>
        )}
        {billingError && <p className="settings-modal__error" role="alert">{billingError}</p>}

        <div className="settings-modal__billing-footer">
          <div>
            <ShieldCheck size={17} />
            <span>Checkout is handled securely by PayHere.</span>
          </div>
          <button type="submit" disabled={!isOwner || !billing?.payhere?.configured || checkoutWorking}>
            {checkoutWorking ? "Opening PayHere..." : `Pay ${formatMoney(selectedPlan?.amountMinor)} in sandbox`}
          </button>
        </div>
      </form>
    );
  }

  function renderPreferences() {
    return (
      <div className="settings-modal__stack">
        <section className="settings-modal__card settings-modal__preference">
          <div className="settings-modal__section-heading">
            <Palette size={20} />
            <div><h3>Appearance</h3><p>Choose how the Vendly dashboard looks on this device.</p></div>
          </div>
          <button type="button" onClick={onToggleTheme}>Use {theme === "dark" ? "light" : "dark"} theme</button>
        </section>
        <section className="settings-modal__card settings-modal__preference">
          <div className="settings-modal__section-heading">
            <Bell size={20} />
            <div><h3>Device notifications</h3><p>Browser notification permission is controlled by this device.</p></div>
          </div>
          <button
            type="button"
            onClick={() => "Notification" in window && window.Notification.requestPermission()}
          >
            Enable notifications
          </button>
        </section>
      </div>
    );
  }

  return (
    <ModalShell
      isOpen={isOpen}
      onClose={onClose}
      title="Settings"
      description="Manage your workspace, team and Vendly plan."
      size="full"
    >
      <div className="settings-modal">
        <nav className="settings-modal__navigation" aria-label="Settings sections">
          {sections.map((section) => {
            const Icon = section.icon;
            return (
              <button
                className={activeSection === section.id ? "is-active" : ""}
                key={section.id}
                type="button"
                onClick={() => setActiveSection(section.id)}
              >
                <Icon size={18} />
                <span>{section.label}</span>
              </button>
            );
          })}
        </nav>

        <main className="settings-modal__content">
          <header className="settings-modal__content-heading">
            <span>{sections.find((section) => section.id === activeSection)?.label}</span>
          </header>
          {activeSection === "general" && renderGeneral()}
          {activeSection === "staff" && <StaffSettings businessId={business?.id} currentRole={membership?.role} />}
          {activeSection === "plan" && renderPlan()}
          {activeSection === "billing" && renderBilling()}
          {activeSection === "preferences" && renderPreferences()}
        </main>
      </div>
    </ModalShell>
  );
}

export default SettingsModal;
