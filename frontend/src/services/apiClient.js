import { getCurrentUserToken } from "./authService";

const configuredApiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:5000/api/v1"
).replace(/\/$/, "");

// During development, use the same hostname that opened the Vite page.
// localhost therefore calls localhost:5000, while a phone using the PC's
// Wi-Fi address calls that same Wi-Fi address on port 5000.
function developmentApiBaseUrl(configuredUrl) {
  if (!import.meta.env.DEV || typeof window === "undefined") return configuredUrl;

  try {
    const url = new URL(configuredUrl);
    url.hostname = window.location.hostname;
    return url.toString().replace(/\/$/, "");
  } catch {
    return configuredUrl;
  }
}

const apiBaseUrl = developmentApiBaseUrl(configuredApiBaseUrl);

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

  const requestUrl = `${apiBaseUrl}/${path.replace(/^\//, "")}`;

  async function sendRequest() {
    const response = await fetch(requestUrl, {
      method,
      headers: requestHeaders,
      body: requestBody,
      signal,
    });
    const responseType = response.headers.get("content-type") ?? "";
    const responseData = responseType.includes("application/json")
      ? await response.json()
      : null;

    return { response, responseData };
  }

  let { response, responseData } = await sendRequest();

  // Immediately after Firebase sign-in, its cached token can briefly be the
  // token from the previous auth state. Refresh it once and repeat only the
  // request that the backend explicitly rejected as an invalid token.
  if (
    requiresAuthentication &&
    response.status === 401 &&
    responseData?.error?.code === "invalid_authentication_token"
  ) {
    const refreshedToken = await getCurrentUserToken(true);

    if (refreshedToken) {
      requestHeaders.set("Authorization", `Bearer ${refreshedToken}`);
      ({ response, responseData } = await sendRequest());
    }
       setTimeout(() => {
    console.log("This runs after 2 seconds");
    window.location.reload();
  }, 1000);

  }

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
