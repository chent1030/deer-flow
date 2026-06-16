import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  Agent,
  CreateAgentRequest,
  ShareAgentRequest,
  ShareAgentResponse,
  ShareUser,
  UpdateAgentRequest,
} from "./types";

const BACKEND_UNAVAILABLE_STATUSES = new Set([502, 503, 504]);

function localizeErrorDetail(detail: string): string {
  const map: Array<[RegExp, string]> = [
    [/^Could not reach the DeerFlow backend\.$/, "无法连接到 DeerFlow 后端。"],
    [/^Failed to load agents: /, "加载智能体失败："],
    [/^Agent '(.+)' not found$/, "智能体“$1”不存在"],
    [/^Failed to create agent: /, "创建智能体失败："],
    [/^Failed to update agent: /, "更新智能体失败："],
    [/^Failed to delete agent: /, "删除智能体失败："],
    [/^Failed to share agent: /, "分享智能体失败："],
    [/^Failed to load users: /, "加载用户失败："],
    [/^Invalid agent name '(.+)'.*$/, "智能体名称“$1”无效，只能包含字母、数字和连字符。"],
    [/^Custom-agent management API is disabled\..*$/, "自定义智能体管理接口未启用。"],
  ];
  for (const [pattern, replacement] of map) {
    if (pattern.test(detail)) {
      return detail.replace(pattern, replacement);
    }
  }
  return detail;
}

export class AgentNameCheckError extends Error {
  constructor(
    message: string,
    public readonly reason: "backend_unreachable" | "request_failed",
    /**
     * Raw backend `detail` string when the failure came from a backend
     * response carrying one. `null` when no detail was provided (e.g.
     * network-layer failure, empty response body, unparseable body) — in
     * which case `message` is a generated fallback like "Failed to check
     * agent name: Bad Gateway" and the UI should prefer its own localized
     * fallback instead of surfacing the generated string.
     */
    public readonly detail: string | null = null,
  ) {
    super(message);
    this.name = "AgentNameCheckError";
  }
}

export class AgentsApiDisabledError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AgentsApiDisabledError";
  }
}

function isAgentsApiDisabledDetail(detail: string | undefined): boolean {
  return typeof detail === "string" && detail.includes("agents_api.enabled");
}

export async function listAgents(): Promise<Agent[]> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents`);
  if (!res.ok) throw new Error(`Failed to load agents: ${res.statusText}`);
  const data = (await res.json()) as { agents: Agent[] };
  return data.agents;
}

export async function getAgent(name: string): Promise<Agent> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}`);
  if (!res.ok) throw new Error(`Agent '${name}' not found`);
  return res.json() as Promise<Agent>;
}

export async function createAgent(request: CreateAgentRequest): Promise<Agent> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    if (isAgentsApiDisabledDetail(err.detail)) {
      throw new AgentsApiDisabledError("自定义智能体管理接口未启用。");
    }
    throw new Error(localizeErrorDetail(err.detail ?? `Failed to create agent: ${res.statusText}`));
  }
  return res.json() as Promise<Agent>;
}

export async function updateAgent(
  name: string,
  request: UpdateAgentRequest,
): Promise<Agent> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(localizeErrorDetail(err.detail ?? `Failed to update agent: ${res.statusText}`));
  }
  return res.json() as Promise<Agent>;
}

export async function deleteAgent(name: string): Promise<void> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(localizeErrorDetail(`Failed to delete agent: ${res.statusText}`));
}

export async function shareAgent(
  name: string,
  request: ShareAgentRequest,
): Promise<ShareAgentResponse> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(localizeErrorDetail(err.detail ?? `Failed to share agent: ${res.statusText}`));
  }
  return res.json() as Promise<ShareAgentResponse>;
}

export async function searchShareUsers(search: string): Promise<ShareUser[]> {
  const params = new URLSearchParams();
  if (search.trim()) params.set("search", search.trim());
  const query = params.toString();
  const res = await fetch(
    `${getBackendBaseURL()}/api/users/search${query ? `?${query}` : ""}`,
  );
  if (!res.ok) throw new Error(localizeErrorDetail(`Failed to load users: ${res.statusText}`));
  const data = (await res.json()) as { users: ShareUser[] };
  return data.users;
}

export async function checkAgentName(
  name: string,
): Promise<{ available: boolean; name: string }> {
  let res: Response;
  try {
    res = await fetch(
      `${getBackendBaseURL()}/api/agents/check?name=${encodeURIComponent(name)}`,
    );
  } catch {
    throw new AgentNameCheckError(
      "Could not reach the DeerFlow backend.",
      "backend_unreachable",
    );
  }

  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    if (isAgentsApiDisabledDetail(err.detail)) {
      throw new AgentsApiDisabledError("自定义智能体管理接口未启用。");
    }
    if (BACKEND_UNAVAILABLE_STATUSES.has(res.status)) {
      throw new AgentNameCheckError(
        "Could not reach the DeerFlow backend.",
        "backend_unreachable",
      );
    }
    const backendDetail = typeof err.detail === "string" ? err.detail : null;
    throw new AgentNameCheckError(
      localizeErrorDetail(backendDetail ?? `Failed to check agent name: ${res.statusText}`),
      "request_failed",
      backendDetail,
    );
  }
  return res.json() as Promise<{ available: boolean; name: string }>;
}
