export interface Agent {
  name: string;
  description: string;
  model: string | null;
  tool_groups: string[] | null;
  skills: string[] | null;
  soul?: string | null;
}

export interface CreateAgentRequest {
  name: string;
  description?: string;
  model?: string | null;
  tool_groups?: string[] | null;
  skills?: string[] | null;
  soul?: string;
}

export interface UpdateAgentRequest {
  description?: string | null;
  model?: string | null;
  tool_groups?: string[] | null;
  skills?: string[] | null;
  soul?: string | null;
}

export interface ShareUser {
  id: string;
  username: string;
  display_name: string;
}

export interface ShareAgentRequest {
  user_ids: string[];
}

export interface ShareAgentResult {
  target_user_id: string;
  target_username: string | null;
  target_agent_name: string | null;
  status: "created" | "failed";
  error_message: string | null;
}

export interface ShareAgentResponse {
  results: ShareAgentResult[];
}
