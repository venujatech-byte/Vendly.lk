import { apiRequest } from "./apiClient";

export function getPublicStore(storeCode) {
  return apiRequest(`/public/stores/${storeCode}`, {
    requiresAuthentication: false,
  });
}

export function getPublicProduct(productCode) {
  return apiRequest(`/public/products/${productCode}`, {
    requiresAuthentication: false,
  });
}

export function createPublicChatSession({ storeCode, productCode }) {
  return apiRequest("/public/chat/sessions", {
    method: "POST",
    body: { storeCode, productCode },
    requiresAuthentication: "optional",
  });
}

export function claimPublicChatSession(sessionId, sessionToken) {
  return apiRequest(`/public/chat/sessions/${sessionId}/claim`, {
    method: "POST",
    headers: { "X-Chat-Session-Token": sessionToken },
  });
}

export function getCustomerOrders(storeCode) {
  return apiRequest(`/public/stores/${storeCode}/customer/orders`);
}

export function getCustomerChats(storeCode) {
  return apiRequest(`/public/stores/${storeCode}/customer/chats`);
}

export function sendPublicChatMessage(sessionId, sessionToken, message, orderDraft = {}) {
  return apiRequest(`/public/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    body: { message, ...orderDraft },
    headers: { "X-Chat-Session-Token": sessionToken },
    requiresAuthentication: false,
  });
}

export function getPublicChatMessages(sessionId, sessionToken) {
  return apiRequest(`/public/chat/sessions/${sessionId}/messages`, {
    headers: { "X-Chat-Session-Token": sessionToken },
    requiresAuthentication: false,
  });
}

export function createPublicChatOrder(sessionId, sessionToken, orderData) {
  return apiRequest(`/public/chat/sessions/${sessionId}/orders`, {
    method: "POST",
    body: orderData,
    headers: { "X-Chat-Session-Token": sessionToken },
    requiresAuthentication: "optional",
  });
}

export function getPublicProductReviews(productCode) {
  return apiRequest(`/public/products/${productCode}/reviews`, {
    requiresAuthentication: false,
  });
}

export function submitPublicReview(storeCode, reviewData) {
  return apiRequest(`/public/stores/${storeCode}/reviews`, {
    method: "POST",
    body: reviewData,
    requiresAuthentication: false,
  });
}
