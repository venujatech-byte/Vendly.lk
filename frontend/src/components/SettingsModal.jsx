import {
  Bell,
  Check,
  CreditCard,
  Landmark,
  Mail,
  MapPin,
  MessageCircleQuestion,
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
import { SRI_LANKA_DISTRICTS } from "../data/districts";
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
  const [contactDetails, setContactDetails] = useState({
    phone: "",
    email: "",
    storefrontFaq: "",
  });
  // Given to a customer who chooses to pay by transfer. Never published with
  // the rest of the storefront details.
  const [bankDetails, setBankDetails] = useState({
    bankName: "",
    branch: "",
    accountName: "",
    accountNumber: "",
    instructions: "",
  });
  // Either a shop customers can walk into, or an explicit "online only" so
  // the chatbot can say so rather than leaving the question unanswered.
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
      storefrontFaq: business?.storefrontFaq || "",
    });
    setBankDetails({
      bankName: business?.bankDetails?.bankName || "",
      branch: business?.bankDetails?.branch || "",
      accountName: business?.bankDetails?.accountName || "",
      accountNumber: business?.bankDetails?.accountNumber || "",
      instructions: business?.bankDetails?.instructions || "",
    });
    setStoreLocation({
      isOnlineOnly: business?.storeLocation?.isOnlineOnly ?? true,
      addressLine: business?.storeLocation?.addressLine || "",
      city: business?.storeLocation?.city || "",
      district: business?.storeLocation?.district || "",
      openingHours: business?.storeLocation?.openingHours || "",
      mapUrl: business?.storeLocation?.mapUrl || "",
    });
    setContactError("");
    setContactMessage("");
  }, [
    business?.bankDetails,
    business?.storeLocation,
    business?.publicEmail,
    business?.publicPhone,
    business?.storefrontFaq,
    isOpen,
  ]);

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

  function updateStoreLocation(event) {
    setStoreLocation((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
    setContactError("");
    setContactMessage("");
  }

  function updateBankDetail(event) {
    setBankDetails((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
    setContactError("");
    setContactMessage("");
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
      await updatePublicContact(business.id, {
        ...contactDetails,
        bankDetails,
        storeLocation,
      });
      await refreshSellerProfile();
      setContactMessage("Storefront contact details and policies saved.");
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
              <h3>Storefront contact &amp; policies</h3>
              <p>Shown on the Contact page customers open from your store link. The chatbot answers policy questions from what you write here.</p>
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

          <label className="settings-modal__faq">
            <span><MessageCircleQuestion size={14} /> Store policies &amp; FAQ</span>
            <textarea
              name="storefrontFaq"
              value={contactDetails.storefrontFaq}
              onChange={updateContactDetail}
              rows={8}
              maxLength={4000}
              placeholder={`Write how your shop works, in your own words. The chatbot answers customers from this text and never invents a policy.

Returns: Unused items can be returned within 7 days. Customer pays return delivery.
Exchange: Size exchanges are free within 14 days.
Payment: Cash on delivery island-wide. Bank transfer also accepted.
Delivery time: 2-3 working days to Colombo, 3-5 days elsewhere.
Opening hours: Monday to Saturday, 9am to 6pm.`}
              disabled={!canManageBusiness || isContactSaving}
            />
            <small>
              {contactDetails.storefrontFaq.length}/4000 characters. Anything you
              leave out, the chatbot will say the seller has not stated it rather
              than guess.
            </small>
          </label>

          <fieldset className="settings-modal__bank">
            <legend><MapPin size={14} /> Shop location</legend>
            <p className="settings-modal__bank-hint">
              A customer who asks "where are you?" gets this answer. Say you are
              online only rather than leaving the question unanswered.
            </p>
            <label className="settings-modal__online-toggle">
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
              <span>We are online only — there is no shop to visit</span>
            </label>

            {!storeLocation.isOnlineOnly && (
              <>
                <div className="settings-modal__contact-grid">
                  <label>
                    <span>Street address</span>
                    <input name="addressLine" value={storeLocation.addressLine} onChange={updateStoreLocation} placeholder="No. 45 Galle Road" disabled={!canManageBusiness || isContactSaving} />
                  </label>
                  <label>
                    <span>City</span>
                    <input name="city" value={storeLocation.city} onChange={updateStoreLocation} placeholder="Nugegoda" disabled={!canManageBusiness || isContactSaving} />
                  </label>
                  <label>
                    <span>District</span>
                    <select name="district" value={storeLocation.district} onChange={updateStoreLocation} disabled={!canManageBusiness || isContactSaving}>
                      <option value="">Select a district</option>
                      {SRI_LANKA_DISTRICTS.map((district) => (
                        <option key={district} value={district}>{district}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Opening hours</span>
                    <input name="openingHours" value={storeLocation.openingHours} onChange={updateStoreLocation} placeholder="Mon-Sat, 9am to 6pm" disabled={!canManageBusiness || isContactSaving} />
                  </label>
                </div>
                <label className="settings-modal__bank-note">
                  <span>Map link (optional)</span>
                  <input name="mapUrl" value={storeLocation.mapUrl} onChange={updateStoreLocation} placeholder="https://maps.app.goo.gl/..." disabled={!canManageBusiness || isContactSaving} />
                </label>
              </>
            )}
          </fieldset>

          <fieldset className="settings-modal__bank">
            <legend><Landmark size={14} /> Bank details for deposits</legend>
            <p className="settings-modal__bank-hint">
              Sent to a customer only when they choose to pay by transfer. Leave
              blank if you take cash on delivery only.
            </p>
            <div className="settings-modal__contact-grid">
              <label>
                <span>Bank</span>
                <input name="bankName" value={bankDetails.bankName} onChange={updateBankDetail} placeholder="Commercial Bank" disabled={!canManageBusiness || isContactSaving} />
              </label>
              <label>
                <span>Branch</span>
                <input name="branch" value={bankDetails.branch} onChange={updateBankDetail} placeholder="Nugegoda" disabled={!canManageBusiness || isContactSaving} />
              </label>
              <label>
                <span>Account name</span>
                <input name="accountName" value={bankDetails.accountName} onChange={updateBankDetail} placeholder="V S Tech Store (Pvt) Ltd" disabled={!canManageBusiness || isContactSaving} />
              </label>
              <label>
                <span>Account number</span>
                <input name="accountNumber" value={bankDetails.accountNumber} onChange={updateBankDetail} placeholder="8001234567" disabled={!canManageBusiness || isContactSaving} />
              </label>
            </div>
            <label className="settings-modal__bank-note">
              <span>Payment instructions (optional)</span>
              <textarea
                name="instructions"
                value={bankDetails.instructions}
                onChange={updateBankDetail}
                rows={2}
                maxLength={500}
                placeholder="Send the slip to 077 123 4567 on WhatsApp after transferring."
                disabled={!canManageBusiness || isContactSaving}
              />
            </label>
          </fieldset>

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
