import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

import {
  changeCurrentAccountPassword,
  fetchCurrentAccount,
  formatAccountRole,
} from "@/core/auth/account";
import { fetch as fetcher } from "@/core/api/fetcher";

const mockedFetch = vi.mocked(fetcher);

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("account auth helpers", () => {
  test("loads the current admin account through the cookie-backed auth-check route", async () => {
    const user = {
      id: "user-1",
      username: "admin",
      display_name: "Admin",
      email: "",
      role: "super_admin",
      department_id: null,
      status: "active",
    };
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, { authenticated: true, user }),
    );

    await expect(fetchCurrentAccount()).resolves.toEqual(user);

    expect(mockedFetch).toHaveBeenCalledWith("/api/auth-check");
  });

  test("returns null when auth-check reports an unauthenticated session", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, { authenticated: false }),
    );

    await expect(fetchCurrentAccount()).resolves.toBeNull();
  });

  test("changes the current account password through the Next.js cookie-to-Bearer proxy", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(200, { message: "ok" }));

    await changeCurrentAccountPassword("admin123", "Newpass123!");

    expect(mockedFetch).toHaveBeenCalledWith("/api/account/password", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: "admin123",
        new_password: "Newpass123!",
      }),
    });
  });

  test("formats admin role values for display", () => {
    expect(formatAccountRole("super_admin")).toBe("super admin");
  });
});
