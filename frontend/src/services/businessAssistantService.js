import { apiRequest } from "./apiClient";

/**
 * Send a natural-language request, or a previously prepared action, to the
 * permission-aware business assistant endpoint.
 */
export async function sendBusinessAssistantMessage(
  businessId,
  { message = "", confirmedAction = null } = {},
) {
  const response = await apiRequest(
    `/businesses/${businessId}/assistant/messages`,
    {
      method: "POST",
      body: confirmedAction ? { confirmedAction } : { message },
    },
  );

  return response.assistant;
}

export async function transcribeBusinessAssistantAudio(
  businessId,
  audio,
  filename,
  language,
) {
  const body = new FormData();
  body.append("audio", audio, filename);
  body.append("language", language);

  const response = await apiRequest(
    `/businesses/${businessId}/assistant/transcriptions`,
    { method: "POST", body },
  );
  return response.transcript;
}
