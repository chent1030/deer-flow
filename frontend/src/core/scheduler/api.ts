import { authFetch } from "@/core/api";

import type {
  ScheduledTask,
  TaskExecution,
  TaskCreateRequest,
  TaskUpdateRequest,
} from "./types";

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json();
}

export async function listTasks(): Promise<ScheduledTask[]> {
  return parseJson<ScheduledTask[]>(await authFetch("/api/scheduler/tasks"));
}

export async function createTask(req: TaskCreateRequest): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(
    await authFetch("/api/scheduler/tasks", {
      method: "POST",
      body: JSON.stringify(req),
    }),
  );
}

export async function getTask(taskId: string): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(await authFetch(`/api/scheduler/tasks/${taskId}`));
}

export async function updateTask(
  taskId: string,
  req: TaskUpdateRequest,
): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(
    await authFetch(`/api/scheduler/tasks/${taskId}`, {
      method: "PUT",
      body: JSON.stringify(req),
    }),
  );
}

export async function deleteTask(taskId: string): Promise<void> {
  const res = await authFetch(`/api/scheduler/tasks/${taskId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(res.statusText);
}

export async function toggleTask(taskId: string): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(
    await authFetch(`/api/scheduler/tasks/${taskId}/toggle`, { method: "POST" }),
  );
}

export async function triggerTask(taskId: string): Promise<TaskExecution> {
  return parseJson<TaskExecution>(
    await authFetch(`/api/scheduler/tasks/${taskId}/trigger`, { method: "POST" }),
  );
}

export async function listExecutions(
  taskId: string,
  limit = 20,
  offset = 0,
): Promise<TaskExecution[]> {
  return parseJson<TaskExecution[]>(
    await authFetch(
      `/api/scheduler/tasks/${taskId}/executions?limit=${limit}&offset=${offset}`,
    ),
  );
}

export async function getExecution(
  taskId: string,
  executionId: string,
): Promise<TaskExecution> {
  return parseJson<TaskExecution>(
    await authFetch(`/api/scheduler/tasks/${taskId}/executions/${executionId}`),
  );
}
