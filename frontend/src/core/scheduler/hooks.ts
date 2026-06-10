import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";
import type { TaskCreateRequest, TaskUpdateRequest } from "./types";

const TASKS_KEY = ["scheduler", "tasks"];

export function useScheduledTasks() {
  return useQuery({ queryKey: TASKS_KEY, queryFn: api.listTasks });
}

export function useTaskExecutions(taskId: string | null) {
  return useQuery({
    queryKey: [...TASKS_KEY, taskId, "executions"],
    queryFn: () => api.listExecutions(taskId!),
    enabled: !!taskId,
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: TaskCreateRequest) => api.createTask(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...req }: { id: string } & TaskUpdateRequest) =>
      api.updateTask(id, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useToggleTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.toggleTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useTriggerTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.triggerTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}
