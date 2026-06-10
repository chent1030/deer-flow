import { getBackendBaseURL } from "../config";

let isRedirecting = false;

function redirectOn401(response: Response): void {
  if (response.status === 401 && !isRedirecting && typeof window !== "undefined") {
    isRedirecting = true;
    fetch("/api/logout", { method: "POST" }).catch(() => undefined);
    window.location.href = "/";
  }
}

export async function authFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = input.startsWith("/") ? input : `${getBackendBaseURL()}${input}`;
  const { headers: customHeaders, ...rest } = init;
  const headers = customHeaders instanceof Headers
    ? customHeaders
    : new Headers(customHeaders as Record<string, string>);

  if (!headers.has("Content-Type") && !(rest.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...rest,
    credentials: "include",
    headers,
  });

  redirectOn401(response);
  return response;
}
