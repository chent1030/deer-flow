import { fetch } from "@/core/api/fetcher";
import { parseJsonOrThrow } from "@/core/api/response";
import { getBackendBaseURL } from "@/core/config";

import type { MCPConfig } from "./types";

export async function loadMCPConfig() {
  const response = await fetch(`${getBackendBaseURL()}/api/mcp/config`);
  return parseJsonOrThrow<MCPConfig>(response, "加载工具配置失败");
}

export async function updateMCPConfig(config: MCPConfig) {
  const response = await fetch(`${getBackendBaseURL()}/api/mcp/config`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(config),
  });
  return parseJsonOrThrow<MCPConfig>(response, "更新工具配置失败");
}
