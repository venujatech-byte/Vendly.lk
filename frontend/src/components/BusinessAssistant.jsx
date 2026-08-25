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
import { downloadOrderExport } from "../services/operationService";
import { downloadInventoryCsv, getProducts } from "../services/productService";
import { downloadCustomersCsv, getCustomers } from "../services/customerService";
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

  useEffect(() => {
    if (!isOpen || !messageListRef.current) return;
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [isOpen, messages, isSending]);

  useEffect(() => () => {
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
      await downloadOrderExport(business.id);
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

    if (response?.navigateTo) navigate(response.navigateTo);
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
    const recognition = new SpeechRecognition();
    recognition.lang = voiceLanguage;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => {
      setIsListening(false);
      appendAssistantResponse({
        message: "I could not hear that clearly. Please try again or type your request.",
      });
    };
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim() || "";
      setDraft(transcript);
      if (transcript) sendMessage(transcript);
    };

    recognition.start();
  }

  function stopVoiceInput() {
    recognitionRef.current?.stop();
    setIsListening(false);
  }

  return (
    <>
      <button
        className="floating-assistant-button"
        type="button"
        onClick={onToggle}
        aria-label={isOpen ? "Close business assistant" : "Open business assistant"}
        aria-expanded={isOpen}
        title="Business Assistant"
      >
        {isOpen ? <X aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
      </button>

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
