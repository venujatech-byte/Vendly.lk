import { apiRequest } from "./apiClient";

export async function getChatSessions(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/chat-sessions`);
  return response.sessions;
}

export async function getChatMessages(businessId, sessionId) {
  return apiRequest(
    `/businesses/${businessId}/chat-sessions/${sessionId}/messages`,
  );
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
