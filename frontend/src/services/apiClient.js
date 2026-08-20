import { getCurrentUserToken } from "./authService";

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:5000/api/v1"
).replace(/\/$/, "");

/**
 * Send one request to the Vendly Flask API.
 *
 * Firebase owns the login session. This helper reads its current ID token and
 * sends that token to Flask, where it is verified before business data is read
 * or changed.
 */
export async function apiRequest(
  path,
  {
    method = "GET",
    body,
    headers = {},
    requiresAuthentication = true,
    signal,
  } = {},
) {
  const requestHeaders = new Headers(headers);

  if (requiresAuthentication) {
    const idToken = await getCurrentUserToken();

    if (!idToken && requiresAuthentication !== "optional") {
      throw new Error("You must be logged in to complete this request.");
    }

    if (idToken) requestHeaders.set("Authorization", `Bearer ${idToken}`);
  }

  let requestBody = body;

  if (body !== undefined && !(body instanceof FormData)) {
    requestHeaders.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(
    `${apiBaseUrl}/${path.replace(/^\//, "")}`,
    {
      method,
      headers: requestHeaders,
      body: requestBody,
      signal,
    },
  );

  const responseType = response.headers.get("content-type") ?? "";
  const responseData = responseType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok) {
    const error = new Error(
      responseData?.error?.message ??
        `The API request failed with status ${response.status}.`,
    );

    error.status = response.status;
    error.code = responseData?.error?.code ?? "api_request_failed";
    error.details = responseData?.error?.details;

    throw error;
  }

  return responseData;
}

/** Download an authenticated file from the API without treating it as JSON. */
export async function apiFileRequest(path) {
  const idToken = await getCurrentUserToken();

  if (!idToken) {
    throw new Error("You must be logged in to complete this request.");
  }

  const response = await fetch(`${apiBaseUrl}/${path.replace(/^\//, "")}`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });

  if (!response.ok) {
    const responseType = response.headers.get("content-type") ?? "";
    const responseData = responseType.includes("application/json")
      ? await response.json()
      : null;
    throw new Error(
      responseData?.error?.message ??
        `The file download failed with status ${response.status}.`,
    );
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);

  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] ?? "vendly-download",
  };
}
