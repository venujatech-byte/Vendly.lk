import { useState } from "react";
import {
  ArrowRight,
  Bot,
  CreditCard,
  HelpCircle,
  PackageCheck,
  ShoppingBag,
  Sparkles,
  Truck,
  X,
} from "lucide-react";
import "./StorefrontInstructionsModal.css";

function StorefrontInstructionsModal({
  isOpen,
  onClose,
  businessName,
  onOpenChat,
}) {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  if (!isOpen) return null;

  function handleDismiss() {
    if (dontShowAgain) {
      try {
        localStorage.setItem("vendly_storefront_guide_dismissed", "true");
      } catch (e) {
        // ignore
      }
    }
    // Also save in sessionStorage so it doesn't pop up again in the current session
    try {
      sessionStorage.setItem("vendly_storefront_guide_session", "true");
    } catch (e) {
      // ignore
    }
    onClose();
  }

  function handleStartChat() {
    handleDismiss();
    if (onOpenChat) onOpenChat();
  }

  return (
    <div
      className="sf-instructions-backdrop"
      role="presentation"
      onMouseDown={(e) => e.target === e.currentTarget && handleDismiss()}
    >
      <section
        className="sf-instructions-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sf-instructions-title"
      >
        <header className="sf-instructions-modal__header">
          <div className="sf-instructions-modal__badge">
            <Sparkles size={14} /> Quick Customer Guide
          </div>
          <button
            type="button"
            className="sf-instructions-modal__close"
            onClick={handleDismiss}
            aria-label="Close instructions"
          >
            <X size={18} />
          </button>
        </header>

        <div className="sf-instructions-modal__hero">
          <h2 id="sf-instructions-title">
            Welcome to {businessName || "our storefront"}!
          </h2>
          <p>Here are a few quick tips to help you get the best shopping experience:</p>
        </div>

        <div className="sf-instructions-modal__grid">
          <article className="sf-guide-card">
            <div className="sf-guide-card__icon sf-guide-card__icon--blue">
              <ShoppingBag size={20} />
            </div>
            <div className="sf-guide-card__content">
              <h3>1. Browse & Filter Items</h3>
              <p>
                Browse catalog products, sort by price or availability, and click any item to see full-size images and options.
              </p>
            </div>
          </article>

          <article className="sf-guide-card">
            <div className="sf-guide-card__icon sf-guide-card__icon--purple">
              <Bot size={20} />
            </div>
            <div className="sf-guide-card__content">
              <h3>2. 24/7 AI Shopping Assistant</h3>
              <p>
                Have questions or need recommendations? Tap the <b>Chatbot</b>. Our AI checks stock and can build your order directly in chat!
              </p>
            </div>
          </article>

          <article className="sf-guide-card">
            <div className="sf-guide-card__icon sf-guide-card__icon--emerald">
              <CreditCard size={20} />
            </div>
            <div className="sf-guide-card__content">
              <h3>3. Fast & Safe Checkout</h3>
              <p>
                Add items to cart, enter your delivery address, and choose between Cash on Delivery (COD) or Card payment.
              </p>
            </div>
          </article>

          <article className="sf-guide-card">
            <div className="sf-guide-card__icon sf-guide-card__icon--amber">
              <Truck size={20} />
            </div>
            <div className="sf-guide-card__content">
              <h3>4. Track Order & Delivery</h3>
              <p>
                Track parcel packaging, dispatch status, and courier waybill numbers anytime under <b>My Orders</b>.
              </p>
            </div>
          </article>
        </div>

        <footer className="sf-instructions-modal__footer">
          <label className="sf-instructions-modal__checkbox">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            <span>Don't show this guide on startup again</span>
          </label>

          <div className="sf-instructions-modal__actions">
            {onOpenChat && (
              <button
                type="button"
                className="sf-instructions-btn sf-instructions-btn--secondary"
                onClick={handleStartChat}
              >
                <Bot size={16} /> Chat with AI
              </button>
            )}
            <button
              type="button"
              className="sf-instructions-btn sf-instructions-btn--primary"
              onClick={handleDismiss}
            >
              <span>Explore Store</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}

export default StorefrontInstructionsModal;
