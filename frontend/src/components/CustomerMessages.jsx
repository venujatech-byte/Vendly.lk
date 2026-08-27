import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Bot,
  Languages,
  MessageCircle,
  PhoneCall,
  Search,
  Send,
  UserRound,
} from "lucide-react";

import {
  getChatMessages,
  getChatSessions,
  markChatRead,
  sendSellerMessage,
  setChatAiPaused,
} from "../services/messageService";

import "./CustomerMessages.css";

// The customer reads their own language; the seller sees both so they
// know what was actually delivered on their behalf.
const LANGUAGE_NAMES = { en: "English", si: "Sinhala", ta: "Tamil" };

function initials(name) {
  return String(name || "Guest")
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("en-LK", { dateStyle: "medium", timeStyle: "short" });
}

export default function CustomerMessages({
  businessId,
  onSummaryChange,
  initialSessionId = "",
}) {
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [conversation, setConversation] = useState(null);
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isUpdatingAi, setIsUpdatingAi] = useState(false);
  const [error, setError] = useState("");

  const loadSessions = useCallback(async () => {
    if (!businessId) return;
    try {
      const rows = await getChatSessions(businessId);
      setSessions(rows);
      onSummaryChange?.({
        count: rows.length,
        unread: rows.reduce((sum, row) => sum + (row.unreadCount || 0), 0),
      });
      setSelectedId((current) =>
        current ||
        (initialSessionId && rows.some((row) => row.id === initialSessionId)
          ? initialSessionId
          : rows[0]?.id || ""),
      );
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }, [businessId, initialSessionId, onSummaryChange]);

  useEffect(() => {
    if (initialSessionId) setSelectedId(initialSessionId);
  }, [initialSessionId]);

  useEffect(() => {
    loadSessions();
    const timer = window.setInterval(loadSessions, 8000);
    return () => window.clearInterval(timer);
  }, [loadSessions]);

  useEffect(() => {
    if (!businessId || !selectedId) {
      setConversation(null);
      return;
    }
    let isCurrent = true;
    async function loadConversation() {
      try {
        const result = await getChatMessages(businessId, selectedId);
        if (!isCurrent) return;
        setConversation(result);
        await markChatRead(businessId, selectedId);
        if (!isCurrent) return;
        setSessions((current) =>
          current.map((item) =>
            item.id === selectedId ? { ...item, unreadCount: 0 } : item,
          ),
        );
      } catch (requestError) {
        if (isCurrent) setError(requestError.message);
      }
    }
    loadConversation();
    const timer = window.setInterval(loadConversation, 5000);
    return () => {
      isCurrent = false;
      window.clearInterval(timer);
    };
  }, [businessId, selectedId]);

  const visibleSessions = useMemo(() => {
    const value = search.trim().toLowerCase();
    if (!value) return sessions;
    return sessions.filter((session) =>
      [session.customer?.name, session.customer?.phoneNumber, session.lastMessage]
        .some((field) => String(field || "").toLowerCase().includes(value)),
    );
  }, [search, sessions]);

  async function handleSubmit(event) {
    event.preventDefault();
    const message = reply.trim();
    if (!message || !selectedId || isSending) return;
    setIsSending(true);
    setError("");
    try {
      const savedMessage = await sendSellerMessage(businessId, selectedId, message);
      setConversation((current) => ({
        ...current,
        messages: [...(current?.messages || []), savedMessage],
      }));
      setReply("");
      await loadSessions();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSending(false);
    }
  }

  async function handleAiToggle() {
    if (!selectedId || isUpdatingAi) return;
    const nextPaused = !(
      conversation?.session?.aiPaused ?? selectedSession?.aiPaused
    );
    setIsUpdatingAi(true);
    setError("");
    try {
      await setChatAiPaused(businessId, selectedId, nextPaused);
      setConversation((current) => ({
        ...current,
        session: { ...current?.session, aiPaused: nextPaused },
      }));
      setSessions((current) =>
        current.map((session) =>
          session.id === selectedId
            ? { ...session, aiPaused: nextPaused }
            : session,
        ),
      );
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsUpdatingAi(false);
    }
  }

  const selectedSession = sessions.find((session) => session.id === selectedId);
  const customer = conversation?.session?.customer || selectedSession?.customer;
  const isAiPaused = Boolean(
    conversation?.session?.aiPaused ?? selectedSession?.aiPaused,
  );
  const callPhone = String(customer?.phoneNumber || "").replace(/[^+\d]/g, "");

  return (
    <section className={`customer-messages ${selectedId ? "customer-messages--selected" : ""}`}>
      <aside className="customer-messages__sidebar">
        <label className="customer-messages__search">
          <Search size={16} aria-hidden="true" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search conversations..."
          />
        </label>

        <div className="customer-messages__conversation-list">
          {visibleSessions.map((session) => (
            <button
              key={session.id}
              type="button"
              className={`customer-messages__conversation ${session.id === selectedId ? "is-active" : ""}`}
              onClick={() => setSelectedId(session.id)}
            >
              <span className="customer-messages__avatar">{initials(session.customer?.name)}</span>
              <span className="customer-messages__conversation-copy">
                <strong>{session.customer?.name || "Guest customer"}</strong>
                <small>{session.customer?.phoneNumber || "Storefront visitor"}</small>
                <span>{session.lastMessage}</span>
              </span>
              <span className="customer-messages__conversation-meta">
                <time>{formatTime(session.lastMessageAt)}</time>
                {session.unreadCount > 0 && <b>{session.unreadCount}</b>}
              </span>
            </button>
          ))}
          {!isLoading && visibleSessions.length === 0 && (
            <p className="customer-messages__empty">No chatbot conversations yet.</p>
          )}
        </div>
      </aside>

      <div className="customer-messages__chat">
        {selectedId && customer ? (
          <>
            <header className="customer-messages__header">
              <button className="customer-messages__back" type="button" onClick={() => setSelectedId("")} aria-label="Back to conversations">
                <ArrowLeft size={18} />
              </button>
              <span className="customer-messages__avatar">{initials(customer.name)}</span>
              <div>
                <strong>{customer.name || "Guest customer"}</strong>
                <span>{customer.phoneNumber || customer.email || "Storefront visitor"}</span>
              </div>
              <div className="customer-messages__header-actions">
                <button
                  className={`customer-messages__ai-toggle ${isAiPaused ? "is-paused" : ""}`}
                  type="button"
                  onClick={handleAiToggle}
                  disabled={isUpdatingAi}
                  aria-pressed={isAiPaused}
                  title={isAiPaused ? "Resume automatic replies" : "Pause automatic replies"}
                >
                  <Bot size={15} />
                  {isAiPaused ? "Resume AI" : "Pause AI"}
                </button>
                {callPhone && (
                  <a
                    className="customer-messages__call"
                    href={`tel:${callPhone}`}
                    aria-label={`Call ${customer.name || "customer"}`}
                    title={`Call ${customer.phoneNumber}`}
                  >
                    <PhoneCall size={16} />
                  </a>
                )}
                <span className="customer-messages__channel"><MessageCircle size={15} /> Chatbot</span>
              </div>
            </header>

            <div className="customer-messages__messages" aria-live="polite">
              {(conversation?.messages || []).map((message) => {
                const outgoing = ["seller", "assistant"].includes(message.role);
                return (
                  <article key={message.id} className={`customer-messages__bubble ${outgoing ? "is-outgoing" : "is-incoming"}`}>
                    {/* A seller's own reply is shown back in the words they
                        typed; `message` holds the version the customer read. */}
                    <p>{message.sellerMessage || message.message}</p>
                    {message.metadata?.translated && (
                      <small className="customer-messages__translated">
                        <Languages size={12} aria-hidden="true" />
                        Sent in {LANGUAGE_NAMES[message.metadata.language] || message.metadata.language}:
                        {" "}{message.message}
                      </small>
                    )}
                    <time>{formatTime(message.createdAt)}</time>
                  </article>
                );
              })}
            </div>

            <form className="customer-messages__composer" onSubmit={handleSubmit}>
              <input value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Type a reply..." aria-label="Reply message" />
              <button  type="submit" disabled={!reply.trim() || isSending} aria-label="Send reply">
                <Send size={18} />
              </button>
            </form>
          </>
        ) : (
          <div className="customer-messages__placeholder">
            <UserRound size={35} />
            <strong>Select a conversation</strong>
            <span>Customer chatbot messages will appear here.</span>
          </div>
        )}
        {error && <p className="customer-messages__error" role="alert">{error}</p>}
      </div>
    </section>
  );
}
