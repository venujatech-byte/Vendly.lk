import { apiRequest } from "./apiClient";

export async function getChatSessions(businessId, { before = "", limit = 10 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (before) params.set("before", before);
  return apiRequest(`/businesses/${businessId}/chat-sessions?${params}`);
}

export async function getChatMessages(businessId, sessionId, { before = "", limit = 20 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (before) params.set("before", before);
  return apiRequest(`/businesses/${businessId}/chat-sessions/${sessionId}/messages?${params}`);
}

export function deleteChatSession(businessId, sessionId) {
  return apiRequest(`/businesses/${businessId}/chat-sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function sendSellerMessage(businessId, sessionId, message) {
  const response = await apiRequest(
    `/businesses/${businessId}/chat-sessions/${sessionId}/messages`,
    { method: "POST", body: { message } },
  );
  return response.message;
}

export async function markChatRead(businessId, sessionId) {
  return apiRequest(
    `/businesses/${businessId}/chat-sessions/${sessionId}/read`,
    { method: "PATCH" },
  );
}

export async function setChatAiPaused(businessId, sessionId, paused) {
  return apiRequest(
    `/businesses/${businessId}/chat-sessions/${sessionId}/ai`,
    { method: "PATCH", body: { paused } },
  );
}
