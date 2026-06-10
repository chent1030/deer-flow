export type TaskStatus = "active" | "paused" | "error";
export type ExecutionStatus = "running" | "completed" | "failed" | "skipped";

export interface ScheduledTask {
  id: string;
  agent_name: string;
  agent_description: string;
  agent_soul: string;
  skill_name: string;
  cron_expression: string;
  custom_variables: Record<string, string> | null;
  is_enabled: boolean;
  status: TaskStatus;
  last_execution_at: string | null;
  next_execution_at: string | null;
  error_message: string | null;
}

export interface TaskExecution {
  id: string;
  task_id: string;
  status: ExecutionStatus;
  triggered_at: string;
  completed_at: string | null;
  thread_id: string | null;
  messages: ChatMessage[] | null;
  error_message: string | null;
  token_usage: Record<string, unknown> | null;
}

export interface ChatMessage {
  type: string;
  content: string | ContentBlock[];
  name?: string;
  id?: string;
  additional_kwargs?: Record<string, unknown>;
}

export interface ContentBlock {
  type: string;
  text?: string;
  [key: string]: unknown;
}

export interface TaskCreateRequest {
  agent_description: string;
  agent_soul: string;
  skill_name: string;
  cron_expression: string;
  custom_variables?: Record<string, string>;
}

export interface TaskUpdateRequest {
  agent_description?: string;
  agent_soul?: string;
  skill_name?: string;
  cron_expression?: string;
  custom_variables?: Record<string, string>;
}
