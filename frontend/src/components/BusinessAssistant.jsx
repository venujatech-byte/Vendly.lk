import {
  Bot,
  Check,
  Mic,
  MicOff,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import { sendBusinessAssistantMessage } from "../services/businessAssistantService";
import { downloadOrderExport, printWaybill } from "../services/operationService";
import { downloadInventoryCsv, getProducts } from "../services/productService";
import { downloadCustomersCsv, getCustomers } from "../services/customerService";
import { getShopSales } from "../services/shopSaleService";
import { downloadReceiptPdf } from "../services/receiptService";
import "./BusinessAssistant.css";

const starterMessage = {
  id: "assistant-welcome",
  role: "assistant",
  text: "Hello! I can summarize your business, search and filter records, open dashboard tools and settings, export data, and safely prepare status or stock updates.",
  suggestions: ["Today's summary", "Filter packed orders", "Open customer messages", "Add a new order"],
};

function messageId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function friendlyError(error) {
  return error?.message || "The business assistant could not complete that request.";
}

function isResetFilterCommand(message) {
  const normalizedMessage = String(message || "").trim().toLowerCase();

  return (
    /\b(reset|clear|remove)\b.*\b(filters?|search)\b/.test(normalizedMessage)
    || /\b(filters?|search)\b.*\b(reset|clear|remove)\b/.test(normalizedMessage)
    || /\bshow\s+(all|everything)(\s+records?)?\b/.test(normalizedMessage)
  );
}

function downloadShopSalesCsv(sales) {
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const headings = ["Sale number", "Customer", "Phone", "Items", "Subtotal", "Discount", "Total", "Date"];
  const rows = sales.filter((sale) => sale.status !== "voided").map((sale) => [
    sale.saleNumber,
    sale.customerName || "Walk-in customer",
    sale.phoneNumber || "",
    (sale.items || []).map((item) => `${item.name} x ${item.quantity}`).join("; "),
    (sale.subtotalMinor || 0) / 100,
    (sale.discountTotalMinor || 0) / 100,
    (sale.totalAmountMinor || 0) / 100,
    String(sale.createdAt || "").slice(0, 10),
  ]);
  const csv = [headings, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `vendly-shop-sales-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function BusinessAssistant({ isOpen, onToggle, onClose }) {
  const navigate = useNavigate();
  const { business } = useAuth();
  const [messages, setMessages] = useState([starterMessage]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const [voiceLanguage, setVoiceLanguage] = useState("en-LK");
  const messageListRef = useRef(null);
  const recognitionRef = useRef(null);
  const voiceHoldTimerRef = useRef(null);
  const skipNextAssistantClickRef = useRef(false);
  const voiceStopRequestedRef = useRef(false);
  const [isHoldingVoiceButton, setIsHoldingVoiceButton] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState("");

  useEffect(() => {
    if (!isOpen || !messageListRef.current) return;
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [isOpen, messages, isSending]);

  useEffect(() => () => {
    window.clearTimeout(voiceHoldTimerRef.current);
    recognitionRef.current?.abort();
    window.speechSynthesis?.cancel();
  }, []);

  function speak(text) {
    if (!speechEnabled || !window.speechSynthesis || !text) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = voiceLanguage;
    utterance.rate = 1;
    window.speechSynthesis.speak(utterance);
  }

  function appendAssistantResponse(response) {
    const assistantMessage = {
      id: messageId("assistant"),
      role: "assistant",
      text: response?.message || "I could not prepare a response.",
      cards: response?.cards || [],
      suggestions: response?.suggestions || [],
      pendingAction: response?.pendingAction || null,
    };

    setMessages((current) => [...current, assistantMessage]);
    speak(assistantMessage.text);
  }

  async function executeResponseAction(response) {
    const action = response?.clientAction;

    if (action?.type === "export_orders") {
      await downloadOrderExport(business.id, {
        dateFrom: action.dateFrom || "",
        dateTo: action.dateTo || "",
        status: action.status || "",
      });
      return;
    }

    if (action?.type === "export_sales") {
      const sales = await getShopSales(business.id, {
        dateFrom: action.dateFrom || "",
        dateTo: action.dateTo || "",
      });
      downloadShopSalesCsv(sales);
      return;
    }

    if (action?.type === "print_waybills") {
      action.orders?.forEach((order) => printWaybill(order));
      return;
    }

    if (action?.type === "print_receipts") {
      action.sales?.forEach((sale) => downloadReceiptPdf(business, {
        ...sale,
        orderNumber: sale.saleNumber,
        deliveryFeeMinor: 0,
        taxTotalMinor: 0,
        deliveryAddress: {},
        paymentMethod: "paid",
      }));
      return;
    }

    if (action?.type === "set_theme") {
      window.dispatchEvent(new CustomEvent("vendly:set-theme", { detail: { theme: action.theme } }));
      return;
    }

    if (action?.type === "export_inventory") {
      const products = await getProducts(business.id);
      downloadInventoryCsv(products);
      return;
    }

    if (action?.type === "export_customers") {
      const customers = await getCustomers(business.id);
      downloadCustomersCsv(customers);
      return;
    }

    if (action?.type === "open_settings") {
      window.dispatchEvent(new CustomEvent("vendly:open-settings", {
        detail: { section: action.section || "general" },
      }));
      return;
    }

    if (action?.type === "reset_filters") {
      window.dispatchEvent(new CustomEvent("vendly:reset-filters"));
      return;
    }

    if (response?.navigateTo) {
      // Assistant filtering is intentionally replace-not-additive. Reset the
      // previous page's filter state before opening the requested filtered view.
      if (/[?&](search|status|dateFrom|dateTo|stockStatus|sortBy)=/.test(response.navigateTo)) {
        window.dispatchEvent(new CustomEvent("vendly:reset-filters"));
      }
      navigate(response.navigateTo);
    }
  }

  async function sendMessage(text) {
    const cleanMessage = text.trim();
    if (!cleanMessage || isSending) return;

    setMessages((current) => [
      ...current,
      { id: messageId("user"), role: "user", text: cleanMessage },
    ]);
    setDraft("");
    setIsSending(true);

    // Resetting filters is a local dashboard command. Handle it before the API
    // call so an AI provider can never reinterpret it as the previous filter.
    if (isResetFilterCommand(cleanMessage)) {
      window.dispatchEvent(new CustomEvent("vendly:reset-filters"));
      appendAssistantResponse({
        message: "Filters cleared. Showing all records again.",
      });
      setIsSending(false);
      return;
    }

    try {
      if (!business?.id) {
        throw new Error("Your business account is still loading. Please try again.");
      }

      const response = await sendBusinessAssistantMessage(business.id, {
        message: cleanMessage,
      });
      appendAssistantResponse(response);
      await executeResponseAction(response);
    } catch (error) {
      appendAssistantResponse({ message: friendlyError(error) });
    } finally {
      setIsSending(false);
    }
  }

  async function confirmAction(action, sourceMessageId) {
    if (isSending) return;
    setIsSending(true);
    setMessages((current) => current.map((message) => (
      message.id === sourceMessageId
        ? { ...message, pendingAction: null, actionState: "confirmed" }
        : message
    )));

    try {
      const response = await sendBusinessAssistantMessage(business.id, {
        confirmedAction: action,
      });
      appendAssistantResponse(response);
      await executeResponseAction(response);
    } catch (error) {
      appendAssistantResponse({ message: friendlyError(error) });
    } finally {
      setIsSending(false);
    }
  }

  function cancelAction(sourceMessageId) {
    setMessages((current) => current.map((message) => (
      message.id === sourceMessageId
        ? { ...message, pendingAction: null, actionState: "cancelled" }
        : message
    )));
  }

  function startVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      appendAssistantResponse({
        message: "Voice input is not supported by this browser. Try Chrome on HTTPS or localhost.",
      });
      return;
    }

    recognitionRef.current?.abort();
    voiceStopRequestedRef.current = false;
    setVoiceTranscript("");
    const recognition = new SpeechRecognition();
    recognition.lang = voiceLanguage;
    // Interim text lets the Siri-style overlay show the words while the
    // browser is still listening, before the final command is submitted.
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => {
      setIsListening(false);
      // Releasing the hold button can intentionally end recognition before a
      // phrase is detected. Do not present that normal action as an error.
      if (voiceStopRequestedRef.current) return;
      appendAssistantResponse({
        message: "I could not hear that clearly. Please try again or type your request.",
      });
    };
    recognition.onresult = (event) => {
      let transcript = "";
      let finalTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const phrase = event.results[index]?.[0]?.transcript || "";
        transcript += phrase;
        if (event.results[index].isFinal) finalTranscript += phrase;
      }

      setVoiceTranscript(transcript.trim());
      if (finalTranscript.trim()) {
        setDraft(finalTranscript.trim());
        sendMessage(finalTranscript.trim());
      }
    };

    recognition.start();
  }

  function stopVoiceInput() {
    voiceStopRequestedRef.current = true;
    recognitionRef.current?.stop();
    setIsListening(false);
  }

  function startHeldVoiceCommand(event) {
    if (event.button !== undefined && event.button !== 0) return;

    skipNextAssistantClickRef.current = false;
    window.clearTimeout(voiceHoldTimerRef.current);
    voiceHoldTimerRef.current = window.setTimeout(() => {
      skipNextAssistantClickRef.current = true;
      setIsHoldingVoiceButton(true);
      startVoiceInput();
    }, 280);
  }

  function finishHeldVoiceCommand() {
    window.clearTimeout(voiceHoldTimerRef.current);
    if (!skipNextAssistantClickRef.current) return;

    setIsHoldingVoiceButton(false);
    stopVoiceInput();
  }

  function cancelHeldVoiceCommand() {
    finishHeldVoiceCommand();
    // Pointer cancellation/leave does not dispatch the normal click that
    // pointer-up does, so do not suppress the seller's next ordinary click.
    skipNextAssistantClickRef.current = false;
  }

  function handleAssistantButtonClick() {
    if (skipNextAssistantClickRef.current) {
      skipNextAssistantClickRef.current = false;
      return;
    }
    onToggle();
  }

  return (
    <>
      <button
        className={`floating-assistant-button ${isListening || isHoldingVoiceButton ? "is-listening" : ""}`}
        type="button"
        onClick={handleAssistantButtonClick}
        onPointerDown={startHeldVoiceCommand}
        onPointerUp={finishHeldVoiceCommand}
        onPointerLeave={cancelHeldVoiceCommand}
        onPointerCancel={cancelHeldVoiceCommand}
        aria-label={isListening || isHoldingVoiceButton ? "Listening for a voice command" : isOpen ? "Close business assistant" : "Open business assistant"}
        aria-expanded={isOpen}
        title="Click to open. Press and hold to speak."
      >
        {isListening || isHoldingVoiceButton ? <Mic aria-hidden="true" /> : isOpen ? <X aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
      </button>

      {(isListening || isHoldingVoiceButton) && (
        <div className="business-assistant__voice-overlay" aria-live="polite">
          <div className="business-assistant__voice-orb"><Mic aria-hidden="true" /></div>
          <p className="business-assistant__voice-label">Listening…</p>
          <p className="business-assistant__voice-transcript">
            {voiceTranscript || "Speak your dashboard command"}
          </p>
          <p className="business-assistant__voice-hint">Release to finish</p>
        </div>
      )}

      {isOpen && (
        <section
          className="business-assistant"
          role="dialog"
          aria-label="Business Assistant"
        >
          <header className="business-assistant__header">
            <span className="business-assistant__identity">
              <span className="business-assistant__logo"><Bot aria-hidden="true" /></span>
              <span>
                <strong>Business Assistant</strong>
                <small>Permission-aware AI</small>
              </span>
            </span>

            <span className="business-assistant__header-actions">
              <button
                type="button"
                className="business-assistant__language"
                onClick={() => setVoiceLanguage((current) => current === "en-LK" ? "si-LK" : "en-LK")}
                title="Change voice language"
              >
                {voiceLanguage === "en-LK" ? "EN" : "සිං"}
              </button>
              <button
                type="button"
                className="business-assistant__icon-button"
                onClick={() => setSpeechEnabled((current) => !current)}
                aria-label={speechEnabled ? "Turn spoken replies off" : "Turn spoken replies on"}
                aria-pressed={speechEnabled}
              >
                {speechEnabled ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
              </button>
              <button
                type="button"
                className="business-assistant__icon-button"
                onClick={onClose}
                aria-label="Close assistant"
              >
                <X aria-hidden="true" />
              </button>
            </span>
          </header>

          <div
            className="business-assistant__messages"
            ref={messageListRef}
            aria-live="polite"
          >
            {messages.map((message) => (
              <article
                className={`business-assistant__message business-assistant__message--${message.role}`}
                key={message.id}
              >
                <p>{message.text}</p>

                {message.cards?.length > 0 && (
                  <div className="business-assistant__cards">
                    {message.cards.map((card, index) => (
                      <button
                        className="business-assistant__card"
                        type="button"
                        key={`${message.id}-${card.id || index}`}
                        onClick={() => card.navigateTo && navigate(card.navigateTo)}
                        disabled={!card.navigateTo}
                      >
                        <span>
                          <strong>{card.title}</strong>
                          {card.subtitle && <small>{card.subtitle}</small>}
                        </span>
                        <span className="business-assistant__card-value">{card.value}</span>
                      </button>
                    ))}
                  </div>
                )}

                {message.pendingAction && (
                  <div className="business-assistant__confirmation">
                    <strong>Confirmation required</strong>
                    <span>{message.pendingAction.label}</span>
                    <div>
                      <button
                        type="button"
                        className="business-assistant__confirm"
                        onClick={() => confirmAction(message.pendingAction, message.id)}
                        disabled={isSending}
                      >
                        <Check aria-hidden="true" /> Confirm
                      </button>
                      <button
                        type="button"
                        onClick={() => cancelAction(message.id)}
                        disabled={isSending}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {message.actionState && (
                  <small className="business-assistant__action-state">
                    Action {message.actionState}.
                  </small>
                )}

                {message.suggestions?.length > 0 && (
                  <div className="business-assistant__suggestions">
                    {message.suggestions.map((suggestion) => (
                      <button
                        type="button"
                        key={`${message.id}-${suggestion}`}
                        onClick={() => sendMessage(suggestion)}
                        disabled={isSending}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}

            {isSending && (
              <div className="business-assistant__thinking" aria-label="Assistant is thinking">
                <span /> <span /> <span />
              </div>
            )}
          </div>

          <form
            className="business-assistant__composer"
            onSubmit={(event) => {
              event.preventDefault();
              sendMessage(draft);
            }}
          >
            <button
              type="button"
              className={`business-assistant__voice ${isListening ? "is-listening" : ""}`}
              onClick={isListening ? stopVoiceInput : startVoiceInput}
              aria-label={isListening ? "Stop listening" : "Use voice input"}
            >
              {isListening ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}
            </button>
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask about your business..."
              aria-label="Assistant request"
              disabled={isSending}
              autoComplete="off"
            />
            <button
              type="submit"
              className="business-assistant__send"
              aria-label="Send request"
              disabled={isSending || !draft.trim()}
            >
              <Send aria-hidden="true" />
            </button>
          </form>
        </section>
      )}
    </>
  );
}

export default BusinessAssistant;
