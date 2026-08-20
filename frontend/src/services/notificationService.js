import { apiRequest } from "./apiClient";


export async function getNotifications(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/notifications`);
  return response.notifications;
}


export async function markNotificationRead(businessId, notificationId) {
  const response = await apiRequest(
    `/businesses/${businessId}/notifications/${notificationId}/read`,
    { method: "PATCH" },
  );
  return response.notification;
}
