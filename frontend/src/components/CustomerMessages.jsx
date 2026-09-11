import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Bot,
  Languages,
  MessageCircle,
  PhoneCall,
  Search,
  Send,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from "lucide-react";

import {
  getChatMessages,
  getChatSessions,
  deleteChatSession,
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
  if (Number.isNaN(date.getTime())) return "";

  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const yesterday = new Date();
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();

  const timeStr = date.toLocaleTimeString("en-LK", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  if (isToday) return timeStr;
  if (isYesterday) return `Yesterday, ${timeStr}`;
  return date.toLocaleDateString("en-LK", {
    month: "short",
    day: "numeric",
  }) + `, ${timeStr}`;
}

function formatBubbleTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("en-LK", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export default function CustomerMessages({
  businessId,
  onSummaryChange,
  initialSessionId = "",
}) {
  const [sessions, setSessions] = useState([]);
  const [chatCursor, setChatCursor] = useState(null);
  const [hasMoreChats, setHasMoreChats] = useState(false);
  const [isLoadingMoreChats, setIsLoadingMoreChats] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [conversation, setConversation] = useState(null);
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isUpdatingAi, setIsUpdatingAi] = useState(false);
  const [error, setError] = useState("");

  const messagesEndRef = useRef(null);

  const loadSessions = useCallback(async () => {
    if (!businessId) return;
    try {
      const result = await getChatSessions(businessId);
      const rows = result.sessions;
      setSessions(rows);
      setChatCursor(result.nextCursor || null);
      setHasMoreChats(Boolean(result.hasMore));
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

  async function loadMoreChats() {
    if (!chatCursor || isLoadingMoreChats) return;
    setIsLoadingMoreChats(true);
    try {
      const result = await getChatSessions(businessId, { before: chatCursor });
      setSessions((current) => [...current, ...(result.sessions || [])]);
      setChatCursor(result.nextCursor || null);
      setHasMoreChats(Boolean(result.hasMore));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoadingMoreChats(false);
    }
  }

  useEffect(() => {
    if (initialSessionId) setSelectedId(initialSessionId);
  }, [initialSessionId]);

  useEffect(() => {
    loadSessions();
    return undefined;
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
    return () => {
      isCurrent = false;
    };
  }, [businessId, selectedId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages]);

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

  async function handleDeleteChat() {
    if (!selectedId || !window.confirm("Delete this conversation and all its messages permanently?")) return;
    try {
      await deleteChatSession(businessId, selectedId);
      const remaining = sessions.filter((session) => session.id !== selectedId);
      setSessions(remaining);
      setConversation(null);
      setSelectedId(remaining[0]?.id || "");
      setChatCursor(null);
      setHasMoreChats(false);
    } catch (requestError) {
      setError(requestError.message);
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
        <div className="customer-messages__search-box">
          <div className="customer-messages__search">
            <Search size={15} aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search conversations..."
            />
            {search && (
              <button
                type="button"
                className="customer-messages__search-clear"
                onClick={() => setSearch("")}
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="customer-messages__conversation-list">
          {visibleSessions.map((session) => {
            const isActive = session.id === selectedId;
            return (
              <button
                key={session.id}
                type="button"
                className={`customer-messages__conversation ${isActive ? "is-active" : ""}`}
                onClick={() => setSelectedId(session.id)}
              >
                <span className="customer-messages__avatar">
                  {initials(session.customer?.name)}
                </span>
                <span className="customer-messages__conversation-copy">
                  <span className="customer-messages__conversation-name-row">
                    <strong>{session.customer?.name || "Guest customer"}</strong>
                    <time>{formatTime(session.lastMessageAt)}</time>
                  </span>
                  <small>{session.customer?.phoneNumber || "Storefront visitor"}</small>
                  <span className="customer-messages__snippet">{session.lastMessage || "No messages yet"}</span>
                </span>
                {session.unreadCount > 0 && (
                  <span className="customer-messages__unread-badge">{session.unreadCount}</span>
                )}
              </button>
            );
          })}
          {!isLoading && visibleSessions.length === 0 && (
            <div className="customer-messages__empty-sidebar">
              <MessageCircle size={28} />
              <p>No conversations found</p>
            </div>
          )}
          {hasMoreChats && !search.trim() && (
            <button
              className="customer-messages__load-more"
              type="button"
              onClick={loadMoreChats}
              disabled={isLoadingMoreChats}
            >
              {isLoadingMoreChats ? "Loading..." : "Show more chats"}
            </button>
          )}
        </div>
      </aside>

      <div className="customer-messages__chat">
        {selectedId && customer ? (
          <>
            <header className="customer-messages__header">
              <button
                className="customer-messages__back"
                type="button"
                onClick={() => setSelectedId("")}
                aria-label="Back to conversations"
              >
                <ArrowLeft size={18} />
              </button>

              <div className="customer-messages__header-profile">
                <span className="customer-messages__avatar is-header">
                  {initials(customer.name)}
                </span>
                <div className="customer-messages__header-info">
                  <strong>{customer.name || "Guest customer"}</strong>
                  <span>{customer.phoneNumber || customer.email || "Storefront visitor"}</span>
                </div>
              </div>

              <div className="customer-messages__header-actions">
                <button
                  className={`customer-messages__ai-toggle ${isAiPaused ? "is-paused" : "is-active"}`}
                  type="button"
                  onClick={handleAiToggle}
                  disabled={isUpdatingAi}
                  aria-pressed={!isAiPaused}
                  title={isAiPaused ? "Resume AI chatbot responses" : "Pause AI chatbot responses"}
                >
                  <span className={`customer-messages__ai-dot ${isAiPaused ? "is-paused" : "is-active"}`} />
                  <Bot size={14} />
                  <span>{isAiPaused ? "Resume AI" : "Pause AI"}</span>
                </button>

                {callPhone && (
                  <a
                    className="customer-messages__call"
                    href={`tel:${callPhone}`}
                    aria-label={`Call ${customer.name || "customer"}`}
                    title={`Call ${customer.phoneNumber}`}
                  >
                    <PhoneCall size={14} />
                  </a>
                )}

                <span className="customer-messages__channel">
                  <Sparkles size={13} />
                  <span>Chatbot</span>
                </span>

                <button
                  className="customer-messages__delete"
                  type="button"
                  onClick={handleDeleteChat}
                  title="Delete chat"
                >
                  <Trash2 size={14} />
                  <span>Delete</span>
                </button>
              </div>
            </header>

            <div className="customer-messages__messages" aria-live="polite">
              {conversation?.hasMore && (
                <button
                  className="customer-messages__load-history"
                  type="button"
                  onClick={async () => {
                    const older = await getChatMessages(businessId, selectedId, {
                      before: conversation.nextCursor,
                    });
                    setConversation((current) => ({
                      ...current,
                      messages: [...older.messages, ...(current?.messages || [])],
                      nextCursor: older.nextCursor,
                      hasMore: older.hasMore,
                    }));
                  }}
                >
                  Load older messages
                </button>
              )}

              {(conversation?.messages || []).map((message) => {
                const outgoing = ["seller", "assistant"].includes(message.role);
                const isAi = message.role === "assistant";
                return (
                  <div
                    key={message.id}
                    className={`customer-messages__bubble-row ${outgoing ? "is-outgoing" : "is-incoming"}`}
                  >
                    <article className={`customer-messages__bubble ${outgoing ? "is-outgoing" : "is-incoming"}`}>
                      {outgoing && (
                        <div className="customer-messages__bubble-sender">
                          {isAi ? (
                            <span className="customer-messages__role-tag is-ai">
                              <Bot size={11} /> AI Assistant
                            </span>
                          ) : (
                            <span className="customer-messages__role-tag is-seller">
                              <UserRound size={11} /> Store Team
                            </span>
                          )}
                        </div>
                      )}

                      {message.metadata?.imageUrl && (
                        <a
                          className="customer-messages__image"
                          href={message.metadata.imageUrl}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <img src={message.metadata.imageUrl} alt="Sent attachment" />
                        </a>
                      )}

                      <p>{message.sellerMessage || message.message}</p>

                      {message.metadata?.translated && (
                        <small className="customer-messages__translated">
                          <Languages size={12} aria-hidden="true" />
                          Sent in {LANGUAGE_NAMES[message.metadata.language] || message.metadata.language}:
                          {" "}{message.message}
                        </small>
                      )}

                      <div className="customer-messages__bubble-footer">
                        <time>{formatBubbleTime(message.createdAt)}</time>
                      </div>
                    </article>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            <footer className="customer-messages__composer-footer">
              <form className="customer-messages__composer" onSubmit={handleSubmit}>
                <input
                  value={reply}
                  onChange={(event) => setReply(event.target.value)}
                  placeholder="Type a reply to customer..."
                  aria-label="Reply message"
                />
                <button
                  type="submit"
                  disabled={!reply.trim() || isSending}
                  aria-label="Send reply"
                >
                  <Send size={16} />
                </button>
              </form>
            </footer>
          </>
        ) : (
          <div className="customer-messages__placeholder">
            <div className="customer-messages__placeholder-icon">
              <MessageCircle size={36} />
            </div>
            <strong>Select a conversation</strong>
            <span>Customer chatbot messages and inquiries will appear here.</span>
          </div>
        )}
        {error && <p className="customer-messages__error" role="alert">{error}</p>}
      </div>
    </section>
  );
}
