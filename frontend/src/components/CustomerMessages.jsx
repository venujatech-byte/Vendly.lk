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
import { ref, onValue, query, limitToLast } from "firebase/database";
import { rtdb } from "../firebase/firebase";

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

  const messagesContainerRef = useRef(null);
  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;
  const isUserNearBottomRef = useRef(true);
  const lastSelectedIdRef = useRef(selectedId);
  const previousMessagesCountRef = useRef(0);
  const isLoadingOlderRef = useRef(false);
  const conversationCacheRef = useRef(new Map());

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
    const interval = setInterval(loadSessions, 20000);
    return () => clearInterval(interval);
  }, [loadSessions]);

  useEffect(() => {
    if (!businessId || !selectedId) {
      setConversation(null);
      return;
    }
    // Restore from in-memory cache immediately if available
    if (conversationCacheRef.current.has(selectedId)) {
      setConversation(conversationCacheRef.current.get(selectedId));
    }
    markChatRead(businessId, selectedId).catch(() => {});
    setSessions((current) =>
      current.map((item) =>
        item.id === selectedId ? { ...item, unreadCount: 0 } : item,
      ),
    );
  }, [businessId, selectedId]);

  function handleScroll(event) {
    const element = event.currentTarget;
    const distanceToBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    isUserNearBottomRef.current = distanceToBottom < 80;
  }

  // Real-time listener on RTDB for instant message sync with 0 Firestore reads
  useEffect(() => {
    if (!selectedId) return undefined;

    const chatQuery = query(
      ref(rtdb, `chatMessages/${selectedId}`),
      limitToLast(10),
    );
    const unsubscribe = onValue(
      chatQuery,
      (snapshot) => {
        const val = snapshot.val();
        if (!val) {
          setConversation((current) => {
            if (current) return current;
            const sessionMeta = sessionsRef.current.find((s) => s.id === selectedId);
            const emptyConv = {
              session: {
                id: selectedId,
                customer: sessionMeta?.customer,
                orderId: sessionMeta?.orderId,
                state: sessionMeta?.state || "browsing",
                status: sessionMeta?.status || "active",
                aiPaused: sessionMeta?.aiPaused || false,
                needsSellerAttention: sessionMeta?.needsSellerAttention || false,
              },
              messages: [],
              hasMore: false,
            };
            conversationCacheRef.current.set(selectedId, emptyConv);
            return emptyConv;
          });
          return;
        }

        const rtdbMessages = Object.entries(val).map(([id, item]) => ({
          id,
          ...item,
        }));
        rtdbMessages.sort(
          (a, b) => new Date(a.createdAt || 0) - new Date(b.createdAt || 0),
        );

        setConversation((current) => {
          const prev = current?.messages || [];
          // Preserve older messages if user paginated backwards
          const rtdbIds = new Set(rtdbMessages.map((m) => m.id));
          const olderLoaded = prev.filter((m) => !rtdbIds.has(m.id));
          const combined = [...olderLoaded, ...rtdbMessages];
          combined.sort(
            (a, b) => new Date(a.createdAt || 0) - new Date(b.createdAt || 0),
          );

          // If identical messages are already rendered, bail out to avoid re-render and scroll triggers
          if (
            prev.length === combined.length &&
            prev[prev.length - 1]?.id === combined[combined.length - 1]?.id &&
            prev[0]?.id === combined[0]?.id
          ) {
            return current;
          }

          const sessionMeta = sessionsRef.current.find((s) => s.id === selectedId);
          const updated = {
            session: current?.session || {
              id: selectedId,
              customer: sessionMeta?.customer,
              orderId: sessionMeta?.orderId,
              state: sessionMeta?.state || "browsing",
              status: sessionMeta?.status || "active",
              aiPaused: sessionMeta?.aiPaused || false,
              needsSellerAttention: sessionMeta?.needsSellerAttention || false,
            },
            messages: combined,
            hasMore: current?.hasMore ?? (rtdbMessages.length >= 10),
          };
          conversationCacheRef.current.set(selectedId, updated);
          return updated;
        });

        if (rtdbMessages.length > 0) {
          const last = rtdbMessages[rtdbMessages.length - 1];
          setSessions((current) =>
            current.map((item) =>
              item.id === selectedId
                ? {
                    ...item,
                    lastMessage: last.message || last.sellerMessage || item.lastMessage,
                    lastMessageRole: last.role || item.lastMessageRole,
                    lastMessageAt: last.createdAt || item.lastMessageAt,
                  }
                : item,
            ),
          );
        }
      },
      (err) => {
        console.error("RTDB onValue error in CustomerMessages:", err);
      },
    );

    return () => {
      unsubscribe();
    };
  }, [selectedId]);

  // Reset scroll tracker whenever user switches to a different conversation
  useEffect(() => {
    if (selectedId !== lastSelectedIdRef.current) {
      lastSelectedIdRef.current = selectedId;
      isUserNearBottomRef.current = true;
      previousMessagesCountRef.current = 0;
    }
  }, [selectedId]);

  // User-friendly scrolling: never force-scroll if the user scrolled up to read history
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const currentCount = conversation?.messages?.length || 0;
    const prevCount = previousMessagesCountRef.current;
    previousMessagesCountRef.current = currentCount;

    if (isLoadingOlderRef.current) {
      isLoadingOlderRef.current = false;
      return;
    }

    // Initial conversation open: scroll down to the newest message
    if (prevCount === 0 && currentCount > 0) {
      requestAnimationFrame(() => {
        if (messagesContainerRef.current) {
          messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
        }
      });
      return;
    }

    // New incoming message: only auto-scroll if the user is already near the bottom
    if (currentCount > prevCount && isUserNearBottomRef.current) {
      requestAnimationFrame(() => {
        if (messagesContainerRef.current) {
          messagesContainerRef.current.scrollTo({
            top: messagesContainerRef.current.scrollHeight,
            behavior: "smooth",
          });
        }
      });
    }
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
      isUserNearBottomRef.current = true;
      setConversation((current) => {
        if (!current) return current;
        const exists = (current.messages || []).some((m) => m.id === savedMessage.id);
        return {
          ...current,
          messages: exists ? current.messages : [...(current.messages || []), savedMessage],
        };
      });
      setReply("");
      requestAnimationFrame(() => {
        const container = messagesContainerRef.current;
        if (container) {
          container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
        }
      });
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

            <div
              ref={messagesContainerRef}
              onScroll={handleScroll}
              className="customer-messages__messages"
              aria-live="polite"
            >
              {conversation?.hasMore && (
                <button
                  className="customer-messages__load-history"
                  type="button"
                  onClick={async () => {
                    const container = messagesContainerRef.current;
                    const prevScrollHeight = container ? container.scrollHeight : 0;
                    const prevScrollTop = container ? container.scrollTop : 0;
                    isLoadingOlderRef.current = true;
                    try {
                      const earliestId = conversation?.messages?.[0]?.id;
                      const older = await getChatMessages(businessId, selectedId, {
                        before: earliestId || conversation?.nextCursor,
                        limit: 10,
                      });
                      setConversation((current) => {
                        const prev = current?.messages || [];
                        const existingIds = new Set(prev.map((m) => m.id));
                        const newOlder = (older.messages || []).filter((m) => !existingIds.has(m.id));
                        const updated = {
                          ...current,
                          messages: [...newOlder, ...prev],
                          nextCursor: older.nextCursor,
                          hasMore: Boolean(older.hasMore),
                        };
                        conversationCacheRef.current.set(selectedId, updated);
                        return updated;
                      });
                      requestAnimationFrame(() => {
                        if (container) {
                          const delta = container.scrollHeight - prevScrollHeight;
                          container.scrollTop = prevScrollTop + delta;
                        }
                      });
                    } catch (e) {
                      isLoadingOlderRef.current = false;
                    }
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
