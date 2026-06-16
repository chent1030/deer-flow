import { fetch } from "@/core/api/fetcher";

export interface AdminAccount {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: string;
  department_id: string | null;
  status: string;
}

interface AuthCheckResponse {
  authenticated: boolean;
  user?: AdminAccount;
}

export function formatAccountRole(role: string): string {
  return role.replaceAll("_", " ");
}

export async function fetchCurrentAccount(): Promise<AdminAccount | null> {
  try {
    const res = await fetch("/api/auth-check");
    if (!res.ok) {
      return null;
    }

    const data = (await res.json()) as AuthCheckResponse;
    return data.authenticated ? (data.user ?? null) : null;
  } catch {
    return null;
  }
}

export async function changeCurrentAccountPassword(
  currentPassword: string,
  newPassword: string,
): Promise<Response> {
  return fetch("/api/account/password", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}
