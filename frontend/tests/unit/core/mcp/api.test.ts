import { afterEach, describe, expect, it, vi } from "vitest";

import { loadMCPConfig } from "@/core/mcp/api";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: () => "http://backend.local",
}));

describe("MCP API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reports plain-text server errors without json parse failures", async () => {
    const { fetch } = await import("@/core/api/fetcher");
    vi.mocked(fetch).mockResolvedValue(
      new Response("Internal Server Error", {
        status: 500,
        statusText: "Internal Server Error",
      }),
    );

    await expect(loadMCPConfig()).rejects.toThrow("Internal Server Error");
  });
});
