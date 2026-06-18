import { afterEach, describe, expect, it, vi } from "vitest";

import { authFetch } from "@/core/api/auth-fetch";

describe("authFetch", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    Reflect.deleteProperty(globalThis, "document");
  });

  it("adds the csrf header for state-changing requests", async () => {
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: { cookie: "csrf_token=test-csrf-token" },
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}", { status: 200 }));

    await authFetch("/api/example", { method: "POST", body: "{}" });

    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    const [, init] = call!;
    const headers = new Headers(init?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("test-csrf-token");
  });
});
