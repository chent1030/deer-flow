import { authFetch } from "../api/auth-fetch";

export type AuthUser = {
  username: string;
};

type AuthCheckResponse = {
  authenticated?: boolean;
  user?: {
    username?: unknown;
  };
};

export function readUsernameFromAuthCheck(data: unknown): string | undefined {
  if (!data || typeof data !== "object") {
    return undefined;
  }

  const authData = data as AuthCheckResponse;
  if (authData.authenticated !== true) {
    return undefined;
  }

  const username = authData.user?.username;
  if (typeof username !== "string") {
    return undefined;
  }

  const trimmed = username.trim();
  return trimmed || undefined;
}

export async function loadCurrentUsername(): Promise<string | undefined> {
  const response = await authFetch("/api/auth-check", { method: "GET" });
  if (!response.ok) {
    return undefined;
  }

  try {
    return readUsernameFromAuthCheck(await response.json());
  } catch {
    return undefined;
  }
}
