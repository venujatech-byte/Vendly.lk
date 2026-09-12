import {
  ArrowRight,
  Bell,
  Building2,
  Check,
  Copy,
  CreditCard,
  Landmark,
  Mail,
  MapPin,
  MessageCircleQuestion,
  Moon,
  Palette,
  Phone,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  Sun,
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
import { SRI_LANKA_DISTRICTS } from "../data/districts";
import { updatePublicContact } from "../services/businessService";
import ModalShell from "./ModalShell";
import StaffSettings from "./StaffSettings";

import "./SettingsModal.css";

const sections = [
  {
    id: "general",
    label: "General",
    icon: Settings,
    description: "Manage your business workspace, storefront contact details and policies.",
  },
  {
    id: "staff",
    label: "Staff & permissions",
    icon: UsersRound,
    description: "Invite team members and configure role-based access control.",
  },
  {
    id: "plan",
    label: "Current plan",
    icon: Sparkles,
    description: "Review your active subscription features and explore upgrade tiers.",
  },
  {
    id: "billing",
    label: "Billing",
    icon: CreditCard,
    description: "Manage your PayHere sandbox payment credentials and checkout tests.",
  },
  {
    id: "preferences",
    label: "Preferences",
    icon: Palette,
    description: "Customize appearance themes, smooth animations and device notifications.",
  },
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
  animationsEnabled = true,
  onToggleAnimations,
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
  const [copiedKey, setCopiedKey] = useState(null);

  const [contactDetails, setContactDetails] = useState({
    phone: "",
    email: "",
    storefrontFaq: "",
  });

  const [bankDetails, setBankDetails] = useState({
    bankName: "",
    branch: "",
    accountName: "",
    accountNumber: "",
    instructions: "",
  });

  const [storeLocation, setStoreLocation] = useState({
    isOnlineOnly: true,
    addressLine: "",
    city: "",
    district: "",
    openingHours: "",
    mapUrl: "",
  });

  const [contactError, setContactError] = useState("");
  const [contactMessage, setContactMessage] = useState("");
  const [isContactSaving, setIsContactSaving] = useState(false);

  const [billingDetails, setBillingDetails] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    city: "Colombo",
    country: "Sri Lanka",
  });

  const isOwner = membership?.role === "owner";
  const canManageBusiness = ["owner", "admin"].includes(membership?.role);

  useEffect(() => {
    setActiveSection(initialSection);
  }, [initialSection]);

  useEffect(() => {
    let requestIsCurrent = true;

    if (!isOpen || !business?.id) {
      return undefined;
    }

    setIsBillingLoading(true);
    setBillingError("");

    getBusinessBilling(business.id)
      .then((records) => {
        if (!requestIsCurrent) return;
        setBilling(records);
        setSelectedPlanId(records.currentPlan?.id || "seller");
      })
      .catch((error) => {
        if (!requestIsCurrent) return;
        setBillingError(error.message);
      })
      .finally(() => {
        if (requestIsCurrent) {
          setIsBillingLoading(false);
        }
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [isOpen, business?.id]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const businessName =
      sellerProfile?.businessName || business?.name || "";
    const email = user?.email || "";
    const phone =
      sellerProfile?.phone ||
      sellerProfile?.publicContact?.phone ||
      business?.phone ||
      "";
    const address =
      sellerProfile?.address ||
      sellerProfile?.publicContact?.address ||
      business?.address ||
      "";
    const city =
      sellerProfile?.city ||
      sellerProfile?.publicContact?.city ||
      business?.city ||
      "Colombo";

    setBillingDetails((currentDetails) => ({
      ...currentDetails,
      name: currentDetails.name || businessName,
      email: currentDetails.email || email,
      phone: currentDetails.phone || phone,
      address: currentDetails.address || address,
      city: currentDetails.city || city,
    }));
  }, [isOpen, sellerProfile, business, user]);

  useEffect(() => {
    if (!isOpen) return;
    const pub = sellerProfile?.publicContact;
    setContactDetails({
      phone: pub?.phone || "",
      email: pub?.email || "",
      storefrontFaq: pub?.storefrontFaq || "",
    });
    setBankDetails({
      bankName: pub?.bankDetails?.bankName || "",
      branch: pub?.bankDetails?.branch || "",
      accountName: pub?.bankDetails?.accountName || "",
      accountNumber: pub?.bankDetails?.accountNumber || "",
      instructions: pub?.bankDetails?.instructions || "",
    });
    setStoreLocation({
      isOnlineOnly: pub?.storeLocation?.isOnlineOnly ?? true,
      addressLine: pub?.storeLocation?.addressLine || "",
      city: pub?.storeLocation?.city || "",
      district: pub?.storeLocation?.district || "",
      openingHours: pub?.storeLocation?.openingHours || "",
      mapUrl: pub?.storeLocation?.mapUrl || "",
    });
    setContactError("");
    setContactMessage("");
  }, [isOpen, sellerProfile]);

  const selectedPlan = useMemo(() => {
    return (
      billing?.plans?.find((plan) => plan.id === selectedPlanId) ||
      billing?.currentPlan ||
      null
    );
  }, [billing, selectedPlanId]);

  function updateBillingDetail(event) {
    const { name, value } = event.target;
    setBillingDetails((currentDetails) => ({
      ...currentDetails,
      [name]: value,
    }));
  }

  function updateContactDetail(event) {
    const { name, value } = event.target;
    setContactDetails((current) => ({ ...current, [name]: value }));
  }

  function updateBankDetail(event) {
    const { name, value } = event.target;
    setBankDetails((current) => ({ ...current, [name]: value }));
  }

  function updateStoreLocation(event) {
    const { name, value } = event.target;
    setStoreLocation((current) => ({ ...current, [name]: value }));
  }

  function handleCopy(key, text) {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey(null), 2000);
  }

  function choosePlan(planId) {
    setSelectedPlanId(planId);
    setActiveSection("billing");
  }

  async function savePublicContact(event) {
    event.preventDefault();
    if (!business?.id) return;
    setIsContactSaving(true);
    setContactError("");
    setContactMessage("");

    try {
      await updatePublicContact(business.id, {
        ...contactDetails,
        bankDetails,
        storeLocation,
      });
      await refreshSellerProfile();
      setContactMessage("Storefront contact details and policies saved successfully.");
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
        {/* Workspace banner */}
        <section className="settings-modal__card settings-modal__identity">
          <div className="settings-modal__avatar">
            {(sellerProfile?.businessName || business?.name || "VB").slice(0, 2).toUpperCase()}
          </div>
          <div className="settings-modal__identity-info">
            <div className="settings-modal__identity-top">
              <span className="settings-modal__subtext">Business Workspace</span>
              <span className={`settings-modal__role settings-modal__role--${membership?.role || "viewer"}`}>
                <Shield size={12} strokeWidth={2.5} />
                {membership?.role || "viewer"}
              </span>
            </div>
            <h3>{sellerProfile?.businessName || business?.name || "Your Business"}</h3>
            <p className="settings-modal__identity-meta">
              <span>{user?.email}</span>
              {business?.shortCode && (
                <>
                  <span className="settings-modal__dot">·</span>
                  <span>Store code: <strong>{business.shortCode}</strong></span>
                </>
              )}
            </p>
          </div>
        </section>

        {/* Profile shortcut */}
        <section
          className="settings-modal__card settings-modal__account-row"
          onClick={onOpenProfile}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onOpenProfile();
            }
          }}
        >
          <div className="settings-modal__section-heading">
            <div className="settings-modal__icon-squircle">
              <UserRound size={18} strokeWidth={2.4} />
            </div>
            <div>
              <h3>Account & security credentials</h3>
              <p>Manage your account email, sign-in methods, and personal profile security.</p>
            </div>
          </div>
          <div className="settings-modal__row-action">
            <span>Manage profile</span>
            <ArrowRight size={16} strokeWidth={2.4} />
          </div>
        </section>

        {/* Storefront Contact & Policies */}
        <form className="settings-modal__card settings-modal__form-card" onSubmit={savePublicContact}>
          <div className="settings-modal__section-heading">
            <div className="settings-modal__icon-squircle">
              <Phone size={18} strokeWidth={2.4} />
            </div>
            <div>
              <h3>Storefront contact & policies</h3>
              <p>
                Displayed on your public store and used by the Business Assistant to answer customer questions automatically.
              </p>
            </div>
          </div>

          <div className="settings-modal__contact-grid">
            <label className="settings-modal__field">
              <span><Phone size={14} /> Contact phone number</span>
              <input
                name="phone"
                value={contactDetails.phone}
                onChange={updateContactDetail}
                placeholder="e.g. +94 77 123 4567"
                autoComplete="tel"
                disabled={!canManageBusiness || isContactSaving}
              />
            </label>
            <label className="settings-modal__field">
              <span><Mail size={14} /> Public contact email</span>
              <input
                name="email"
                type="email"
                value={contactDetails.email}
                onChange={updateContactDetail}
                placeholder="e.g. support@yourstore.lk"
                autoComplete="email"
                disabled={!canManageBusiness || isContactSaving}
              />
            </label>
          </div>

          {/* Policies & FAQ textarea */}
          <label className="settings-modal__faq">
            <div className="settings-modal__faq-label-row">
              <span><MessageCircleQuestion size={14} /> Store policies & FAQ</span>
              <small className="settings-modal__char-counter">
                {contactDetails.storefrontFaq.length} / 4000
              </small>
            </div>
            <textarea
              name="storefrontFaq"
              value={contactDetails.storefrontFaq}
              onChange={updateContactDetail}
              rows={7}
              maxLength={4000}
              placeholder={`Write how your shop works in your own words. The chatbot answers customer queries strictly from this text.

Returns: Unused items can be returned within 7 days. Customer pays return delivery.
Exchange: Size exchanges are free within 14 days.
Payment: Cash on delivery island-wide. Bank transfer also accepted.
Delivery time: 2-3 working days to Colombo, 3-5 days elsewhere.
Opening hours: Monday to Saturday, 9am to 6pm.`}
              disabled={!canManageBusiness || isContactSaving}
            />
            <small className="settings-modal__hint-text">
              The chatbot answers questions strictly using your policies and will not guess unstated rules.
            </small>
          </label>

          {/* Shop Location Subcard */}
          <div className="settings-modal__subcard">
            <div className="settings-modal__subcard-header">
              <div className="settings-modal__subcard-title">
                <MapPin size={16} />
                <h4>Physical shop location</h4>
              </div>
              <p className="settings-modal__subcard-hint">
                Customers asking "where are you located?" receive this location.
              </p>
            </div>

            <label className="settings-modal__toggle-row">
              <input
                type="checkbox"
                checked={storeLocation.isOnlineOnly}
                onChange={(event) =>
                  setStoreLocation((current) => ({
                    ...current,
                    isOnlineOnly: event.target.checked,
                  }))
                }
                disabled={!canManageBusiness || isContactSaving}
              />
              <span className="settings-modal__toggle-track">
                <span className="settings-modal__toggle-thumb" />
              </span>
              <span className="settings-modal__toggle-text">We are online only — no physical shop to visit</span>
            </label>

            {!storeLocation.isOnlineOnly && (
              <div className="settings-modal__subcard-body">
                <div className="settings-modal__contact-grid">
                  <label className="settings-modal__field">
                    <span>Street address</span>
                    <input
                      name="addressLine"
                      value={storeLocation.addressLine}
                      onChange={updateStoreLocation}
                      placeholder="No. 45 Galle Road"
                      disabled={!canManageBusiness || isContactSaving}
                    />
                  </label>
                  <label className="settings-modal__field">
                    <span>City</span>
                    <input
                      name="city"
                      value={storeLocation.city}
                      onChange={updateStoreLocation}
                      placeholder="Nugegoda"
                      disabled={!canManageBusiness || isContactSaving}
                    />
                  </label>
                  <label className="settings-modal__field">
                    <span>District</span>
                    <select
                      name="district"
                      value={storeLocation.district}
                      onChange={updateStoreLocation}
                      disabled={!canManageBusiness || isContactSaving}
                    >
                      <option value="">Select a district</option>
                      {SRI_LANKA_DISTRICTS.map((district) => (
                        <option key={district} value={district}>{district}</option>
                      ))}
                    </select>
                  </label>
                  <label className="settings-modal__field">
                    <span>Opening hours</span>
                    <input
                      name="openingHours"
                      value={storeLocation.openingHours}
                      onChange={updateStoreLocation}
                      placeholder="Mon-Sat, 9am to 6pm"
                      disabled={!canManageBusiness || isContactSaving}
                    />
                  </label>
                </div>
                <label className="settings-modal__field settings-modal__field-full">
                  <span>Google Maps link (optional)</span>
                  <input
                    name="mapUrl"
                    value={storeLocation.mapUrl}
                    onChange={updateStoreLocation}
                    placeholder="https://maps.app.goo.gl/..."
                    disabled={!canManageBusiness || isContactSaving}
                  />
                </label>
              </div>
            )}
          </div>

          {/* Bank Details Subcard */}
          <div className="settings-modal__subcard">
            <div className="settings-modal__subcard-header">
              <div className="settings-modal__subcard-title">
                <Landmark size={16} />
                <h4>Bank details for direct deposits</h4>
              </div>
              <p className="settings-modal__subcard-hint">
                Sent to a customer only when they choose to pay by bank transfer. Leave blank if you only offer cash on delivery.
              </p>
            </div>
            <div className="settings-modal__contact-grid">
              <label className="settings-modal__field">
                <span>Bank name</span>
                <input
                  name="bankName"
                  value={bankDetails.bankName}
                  onChange={updateBankDetail}
                  placeholder="Commercial Bank"
                  disabled={!canManageBusiness || isContactSaving}
                />
              </label>
              <label className="settings-modal__field">
                <span>Branch</span>
                <input
                  name="branch"
                  value={bankDetails.branch}
                  onChange={updateBankDetail}
                  placeholder="Nugegoda"
                  disabled={!canManageBusiness || isContactSaving}
                />
              </label>
              <label className="settings-modal__field">
                <span>Account name</span>
                <input
                  name="accountName"
                  value={bankDetails.accountName}
                  onChange={updateBankDetail}
                  placeholder="V S Tech Store (Pvt) Ltd"
                  disabled={!canManageBusiness || isContactSaving}
                />
              </label>
              <label className="settings-modal__field">
                <span>Account number</span>
                <input
                  name="accountNumber"
                  value={bankDetails.accountNumber}
                  onChange={updateBankDetail}
                  placeholder="8001234567"
                  disabled={!canManageBusiness || isContactSaving}
                />
              </label>
            </div>
            <label className="settings-modal__field settings-modal__field-full">
              <span>Payment instructions (optional)</span>
              <textarea
                name="instructions"
                value={bankDetails.instructions}
                onChange={updateBankDetail}
                rows={2}
                maxLength={500}
                placeholder="e.g. Send transfer slip to 077 123 4567 on WhatsApp after transferring."
                disabled={!canManageBusiness || isContactSaving}
              />
            </label>
          </div>

          {contactError && <p className="settings-modal__error" role="alert">{contactError}</p>}
          {contactMessage && <p className="settings-modal__success" role="status">{contactMessage}</p>}

          <div className="settings-modal__contact-footer">
            <small>Changes apply to your public store and chatbot immediately.</small>
            <button
              className="settings-modal__save-btn"
              type="submit"
              disabled={!canManageBusiness || isContactSaving}
            >
              {isContactSaving ? "Saving details..." : "Save contact details"}
            </button>
          </div>
          {!canManageBusiness && (
            <p className="settings-modal__notice">Only workspace owners and admins can update public details.</p>
          )}
        </form>

        {/* Technical details chips */}
        <section className="settings-modal__card">
          <div className="settings-modal__section-heading">
            <div className="settings-modal__icon-squircle">
              <Building2 size={18} strokeWidth={2.4} />
            </div>
            <div>
              <h3>Workspace identifiers & regional settings</h3>
              <p>System configuration keys for external integrations and API routing.</p>
            </div>
          </div>

          <div className="settings-modal__chips-grid">
            <div className="settings-modal__chip">
              <span className="settings-modal__chip-label">Currency</span>
              <strong className="settings-modal__chip-val">{business?.currency || "LKR"}</strong>
            </div>
            <div className="settings-modal__chip">
              <span className="settings-modal__chip-label">Timezone</span>
              <strong className="settings-modal__chip-val">{business?.timezone || "Asia/Colombo"}</strong>
            </div>
            <div className="settings-modal__chip">
              <span className="settings-modal__chip-label">Workspace ID</span>
              <div className="settings-modal__chip-actionable">
                <code>{business?.id || "—"}</code>
                {business?.id && (
                  <button
                    type="button"
                    onClick={() => handleCopy("id", business.id)}
                    title="Copy Workspace ID"
                    aria-label="Copy Workspace ID"
                  >
                    {copiedKey === "id" ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                  </button>
                )}
              </div>
            </div>
            <div className="settings-modal__chip">
              <span className="settings-modal__chip-label">Store code</span>
              <div className="settings-modal__chip-actionable">
                <code>{business?.shortCode || "—"}</code>
                {business?.shortCode && (
                  <button
                    type="button"
                    onClick={() => handleCopy("code", business.shortCode)}
                    title="Copy Store code"
                    aria-label="Copy Store code"
                  >
                    {copiedKey === "code" ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>
    );
  }

  function renderPlan() {
    if (isBillingLoading) return <p className="settings-modal__empty">Loading subscription plans...</p>;
    return (
      <div className="settings-modal__stack">
        {/* Active plan header banner */}
        <section className="settings-modal__current-plan">
          <div className="settings-modal__current-plan-left">
            <span className="settings-modal__pill-badge">Active subscription</span>
            <h3>{billing?.currentPlan?.name || "Early Access"}</h3>
            <p>{billing?.currentPlan?.description || "Access to all core e-commerce management features."}</p>
          </div>
          <div className="settings-modal__current-plan-price">
            <strong>{formatMoney(billing?.currentPlan?.amountMinor)}</strong>
            <span>{billing?.currentPlan?.amountMinor ? "/ month" : "free tier"}</span>
          </div>
        </section>

        {/* Plan tiers */}
        <div className="settings-modal__plans">
          {(billing?.plans || []).map((plan) => {
            const isCurrent = plan.id === billing?.currentPlan?.id;
            const isPopular = plan.id === "seller" || plan.id === "pro";
            return (
              <article
                className={`settings-modal__plan ${isCurrent ? "settings-modal__plan--current" : ""} ${isPopular && !isCurrent ? "settings-modal__plan--popular" : ""}`}
                key={plan.id}
              >
                {isCurrent && <span className="settings-modal__plan-badge">Current plan</span>}
                {isPopular && !isCurrent && <span className="settings-modal__plan-badge settings-modal__plan-badge--popular">Recommended</span>}

                <div className="settings-modal__plan-top">
                  <h3>{plan.name}</h3>
                  <p>{plan.description}</p>
                </div>

                <div className="settings-modal__plan-pricing">
                  <strong>{formatMoney(plan.amountMinor)}</strong>
                  {plan.amountMinor ? <small>/ month</small> : <small>free forever</small>}
                </div>

                <ul className="settings-modal__plan-features">
                  {plan.features.map((feature) => (
                    <li key={feature}>
                      <span className="settings-modal__check-badge">
                        <Check size={13} strokeWidth={2.6} />
                      </span>
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                {plan.amountMinor > 0 && !isCurrent && (
                  <button
                    type="button"
                    className="settings-modal__plan-btn"
                    onClick={() => choosePlan(plan.id)}
                    disabled={!isOwner}
                  >
                    {isOwner ? `Upgrade to ${plan.name}` : "Owner access required"}
                  </button>
                )}

                {isCurrent && (
                  <div className="settings-modal__plan-active-label">
                    <Check size={14} strokeWidth={2.4} /> Active on this store
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
    );
  }

  function renderBilling() {
    return (
      <form className="settings-modal__billing" onSubmit={startCheckout}>
        <section className="settings-modal__checkout-summary">
          <div>
            <span className="settings-modal__pill-badge">Selected Subscription</span>
            <h3>{selectedPlan?.name || "Seller plan"}</h3>
          </div>
          <div className="settings-modal__current-plan-price">
            <strong>{formatMoney(selectedPlan?.amountMinor)}</strong>
            <small>/ month</small>
          </div>
        </section>

        {billing?.lastPayment && (
          <section className="settings-modal__payment-status" aria-live="polite">
            <div>
              <span>Latest PayHere transaction</span>
              <strong>{readablePaymentStatus(billing.lastPayment.status)}</strong>
            </div>
            <div>
              <span>Transaction order ID</span>
              <code>{billing.lastPayment.orderId}</code>
            </div>
            <span className={`settings-modal__payment-pill settings-modal__payment-pill--${billing.lastPayment.status || "initiated"}`}>
              {billing.lastPayment.status || "initiated"}
            </span>
          </section>
        )}

        <section className="settings-modal__card">
          <div className="settings-modal__section-heading">
            <div className="settings-modal__icon-squircle">
              <CreditCard size={18} strokeWidth={2.4} />
            </div>
            <div>
              <h3>PayHere sandbox checkout simulation</h3>
              <p>No real funds are charged while sandbox mode is enabled. Use test credentials to test checkout.</p>
            </div>
          </div>

          <div className="settings-modal__billing-grid">
            <label className="settings-modal__field">
              <span>Full legal name</span>
              <input name="name" value={billingDetails.name} onChange={updateBillingDetail} placeholder="John Doe" required />
            </label>
            <label className="settings-modal__field">
              <span>Billing email</span>
              <input name="email" type="email" value={billingDetails.email} onChange={updateBillingDetail} placeholder="billing@example.com" required />
            </label>
            <label className="settings-modal__field">
              <span>Phone number</span>
              <input name="phone" value={billingDetails.phone} onChange={updateBillingDetail} placeholder="+94 77 123 4567" required />
            </label>
            <label className="settings-modal__field">
              <span>City</span>
              <input name="city" value={billingDetails.city} onChange={updateBillingDetail} placeholder="Colombo" required />
            </label>
            <label className="settings-modal__field settings-modal__billing-address">
              <span>Street address</span>
              <input name="address" value={billingDetails.address} onChange={updateBillingDetail} placeholder="123 Galle Road" required />
            </label>
          </div>
        </section>

        {!billing?.payhere?.configured && (
          <p className="settings-modal__notice" role="status">
            Add <code>PAYHERE_MERCHANT_ID</code> and <code>PAYHERE_MERCHANT_SECRET</code> to your backend configuration to enable sandbox checkout.
          </p>
        )}
        {billingError && <p className="settings-modal__error" role="alert">{billingError}</p>}

        <div className="settings-modal__billing-footer">
          <div className="settings-modal__billing-security">
            <ShieldCheck size={18} strokeWidth={2.4} />
            <span>Encrypted checkout processed through PayHere payment gateway.</span>
          </div>
          <button
            className="settings-modal__checkout-btn"
            type="submit"
            disabled={!isOwner || !billing?.payhere?.configured || checkoutWorking}
          >
            {checkoutWorking ? "Redirecting to PayHere..." : `Test Pay ${formatMoney(selectedPlan?.amountMinor)} in sandbox`}
          </button>
        </div>
      </form>
    );
  }

  function renderPreferences() {
    return (
      <div className="settings-modal__stack">
        {/* Visual Theme Selection */}
        <section className="settings-modal__card">
          <div className="settings-modal__section-heading">
            <div className="settings-modal__icon-squircle">
              <Palette size={18} strokeWidth={2.4} />
            </div>
            <div>
              <h3>Appearance theme</h3>
              <p>Choose your preferred interface theme for this device.</p>
            </div>
          </div>

          <div className="settings-modal__theme-grid">
            <button
              type="button"
              className={`settings-modal__theme-card ${theme === "light" ? "is-active" : ""}`}
              onClick={() => theme !== "light" && onToggleTheme()}
            >
              <div className="settings-modal__theme-preview settings-modal__theme-preview--light">
                <div className="preview-nav" />
                <div className="preview-content">
                  <div className="preview-bar" />
                  <div className="preview-row" />
                  <div className="preview-row" />
                </div>
              </div>
              <div className="settings-modal__theme-info">
                <div className="settings-modal__theme-title">
                  <Sun size={17} strokeWidth={2.2} />
                  <span>Light theme</span>
                </div>
                {theme === "light" && (
                  <span className="settings-modal__theme-check">
                    <Check size={14} strokeWidth={2.8} />
                  </span>
                )}
              </div>
            </button>

            <button
              type="button"
              className={`settings-modal__theme-card ${theme === "dark" ? "is-active" : ""}`}
              onClick={() => theme !== "dark" && onToggleTheme()}
            >
              <div className="settings-modal__theme-preview settings-modal__theme-preview--dark">
                <div className="preview-nav" />
                <div className="preview-content">
                  <div className="preview-bar" />
                  <div className="preview-row" />
                  <div className="preview-row" />
                </div>
              </div>
              <div className="settings-modal__theme-info">
                <div className="settings-modal__theme-title">
                  <Moon size={17} strokeWidth={2.2} />
                  <span>Dark theme</span>
                </div>
                {theme === "dark" && (
                  <span className="settings-modal__theme-check">
                    <Check size={14} strokeWidth={2.8} />
                  </span>
                )}
              </div>
            </button>
          </div>
        </section>

        {/* Page animations toggle */}
        <section className="settings-modal__card settings-modal__preference-row">
          <div className="settings-modal__section-heading">
            <div className="settings-modal__icon-squircle">
              <Sparkles size={18} strokeWidth={2.4} />
            </div>
            <div>
              <h3>Fluid page animations</h3>
              <p>Smoothly reveal statistics, cards, and charts with transitions.</p>
            </div>
          </div>
          <button
            className={`settings-modal__switch ${animationsEnabled ? "is-enabled" : ""}`}
            type="button"
            role="switch"
            aria-checked={animationsEnabled}
            aria-label="Toggle page animations"
            onClick={onToggleAnimations}
          >
            <span aria-hidden="true" />
            <strong>{animationsEnabled ? "Enabled" : "Disabled"}</strong>
          </button>
        </section>

        {/* Device notifications */}
        <section className="settings-modal__card settings-modal__preference-row">
          <div className="settings-modal__section-heading">
            <div className="settings-modal__icon-squircle">
              <Bell size={18} strokeWidth={2.4} />
            </div>
            <div>
              <h3>Browser notifications</h3>
              <p>Receive immediate alerts on desktop when new orders or claims arrive.</p>
            </div>
          </div>
          <button
            type="button"
            className="settings-modal__action-btn"
            onClick={() => "Notification" in window && window.Notification.requestPermission()}
          >
            Request permission
          </button>
        </section>
      </div>
    );
  }

  const currentSection = sections.find((section) => section.id === activeSection);

  return (
    <ModalShell
      isOpen={isOpen}
      onClose={onClose}
      title="Settings"
      description="Manage your business workspace, team members, subscription and device preferences."
      icon={Settings}
      size="full"
    >
      <div className="settings-modal">
        <nav className="settings-modal__navigation" aria-label="Settings sections">
          {sections.map((section) => {
            const Icon = section.icon;
            const isActive = activeSection === section.id;
            return (
              <button
                className={`settings-modal__nav-item ${isActive ? "is-active" : ""}`}
                key={section.id}
                type="button"
                onClick={() => setActiveSection(section.id)}
              >
                <Icon size={18} strokeWidth={isActive ? 2.5 : 2} />
                <span>{section.label}</span>
              </button>
            );
          })}
        </nav>

        <main className="settings-modal__content">
          <header className="settings-modal__content-heading">
            <div>
              <h3>{currentSection?.label}</h3>
              <p>{currentSection?.description}</p>
            </div>
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
