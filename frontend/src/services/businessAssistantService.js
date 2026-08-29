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

/** Upload a browser microphone recording for server-side Groq transcription. */
export async function transcribeBusinessAssistantAudio(
  businessId,
  audioBlob,
  { filename = "business-assistant.webm", language = "" } = {},
) {
  const formData = new FormData();
  formData.append("audio", audioBlob, filename);
  if (language) formData.append("language", language);

  const response = await apiRequest(
    `/businesses/${businessId}/assistant/transcriptions`,
    {
      method: "POST",
      body: formData,
    },
  );

  return response.transcription;
}
