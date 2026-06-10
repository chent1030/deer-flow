"use client";

import {
  Plus,
  Play,
  Pause,
  Trash2,
  Pencil,
  Clock,
  ChevronRight,
  ChevronDown,
  Eye,
  Loader2,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { CronBuilder, cronToHuman } from "@/components/workspace/settings/cron-builder";
import { SettingsSection } from "@/components/workspace/settings/settings-section";
import { authFetch } from "@/core/api";
import { useI18n } from "@/core/i18n/hooks";
import {
  useScheduledTasks,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
  useToggleTask,
  useTriggerTask,
  useTaskExecutions,
} from "@/core/scheduler/hooks";
import type {
  ScheduledTask,
  TaskCreateRequest,
  TaskUpdateRequest,
} from "@/core/scheduler/types";

const statusVariant = {
  active: "default" as const,
  paused: "secondary" as const,
  error: "destructive" as const,
};

const executionStatusIcon: Record<string, React.ReactNode> = {
  running: <Loader2 className="size-3 animate-spin text-blue-500" />,
  completed: <span className="text-green-500">&#10003;</span>,
  failed: <span className="text-red-500">&#10007;</span>,
  skipped: <span className="text-gray-400">&mdash;</span>,
};

function formatTime(iso: string | null): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function formatDuration(start: string, end: string | null): string {
  if (!end) return "...";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

export function SchedulerSettingsPage() {
  const { t } = useI18n();
  const { data: tasks, isLoading, error } = useScheduledTasks();
  const createMutation = useCreateTask();
  const updateMutation = useUpdateTask();
  const deleteMutation = useDeleteTask();
  const toggleMutation = useToggleTask();
  const triggerMutation = useTriggerTask();

  const [editingTask, setEditingTask] = useState<ScheduledTask | "new" | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ScheduledTask | null>(null);
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [selectedExecutionTaskId, setSelectedExecutionTaskId] = useState<string | null>(null);

  const handleEdit = (task: ScheduledTask) => {
    setEditingTask(task);
  };

  const handleNew = () => {
    setEditingTask("new");
  };

  const handleCancel = () => {
    setEditingTask(null);
  };

  const handleDeleteConfirm = () => {
    if (deleteTarget) {
      deleteMutation.mutate(deleteTarget.id, {
        onSettled: () => setDeleteTarget(null),
      });
    }
  };

  const handleTrigger = (id: string) => {
    triggerMutation.mutate(id);
  };

  const handleToggle = (id: string) => {
    toggleMutation.mutate(id);
  };

  return (
    <SettingsSection title={t.scheduler.title} description={t.scheduler.description}>
      {editingTask !== null ? (
        <TaskForm
          task={editingTask === "new" ? null : editingTask}
          onSave={(req) => {
            if (editingTask === "new") {
              createMutation.mutate(req as TaskCreateRequest, {
                onSuccess: () => setEditingTask(null),
              });
            } else {
              updateMutation.mutate(
                { id: editingTask.id, ...req },
                {
                  onSuccess: () => setEditingTask(null),
                },
              );
            }
          }}
          onCancel={handleCancel}
          isSaving={createMutation.isPending || updateMutation.isPending}
          t={t}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex justify-end">
            <Button onClick={handleNew} size="sm">
              <Plus className="mr-1 size-4" />
              {t.scheduler.createTask}
            </Button>
          </div>

          {isLoading && (
            <div className="text-muted-foreground text-sm">{t.common.loading}</div>
          )}
          {error && (
            <div className="text-destructive text-sm">{error.message}</div>
          )}
          {tasks?.length === 0 && (
            <div className="text-muted-foreground text-sm">{t.scheduler.noTasks}</div>
          )}
          {tasks?.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              isToggling={toggleMutation.isPending}
              isTriggering={triggerMutation.variables === task.id && triggerMutation.isPending}
              onToggle={() => handleToggle(task.id)}
              onTrigger={() => handleTrigger(task.id)}
              onEdit={() => handleEdit(task)}
              onDelete={() => setDeleteTarget(task)}
              isExpanded={expandedTaskId === task.id}
              onToggleExpand={() =>
                setExpandedTaskId(expandedTaskId === task.id ? null : task.id)
              }
              onViewExecution={(executionId) => {
                setSelectedExecutionId(executionId);
                setSelectedExecutionTaskId(task.id);
              }}
              t={t}
            />
          ))}
        </div>
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{t.scheduler.deleteConfirm}</DialogTitle>
            <DialogDescription>{t.scheduler.deleteConfirmDescription}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && <Loader2 className="mr-1 size-4 animate-spin" />}
              {t.scheduler.deleteTask}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {selectedExecutionId && selectedExecutionTaskId && (
        <ExecutionDetailDialogOpener
          taskId={selectedExecutionTaskId}
          executionId={selectedExecutionId}
          onClose={() => {
            setSelectedExecutionId(null);
            setSelectedExecutionTaskId(null);
          }}
        />
      )}
    </SettingsSection>
  );
}

interface TaskFormProps {
  task: ScheduledTask | null;
  onSave: (req: TaskCreateRequest | TaskUpdateRequest) => void;
  onCancel: () => void;
  isSaving: boolean;
  t: ReturnType<typeof useI18n>["t"];
}

function TaskForm({ task, onSave, onCancel, isSaving, t }: TaskFormProps) {
  const isEdit = !!task;
  const [name, setName] = useState(task?.agent_description ?? "");
  const [prompt, setPrompt] = useState(task?.agent_soul ?? "");
  const [skillName, setSkillName] = useState(task?.skill_name ?? "");
  const [cronExpression, setCronExpression] = useState(task?.cron_expression ?? "* * * * *");
  const [variables, setVariables] = useState<{ key: string; value: string }[]>(() => {
    const cv = task?.custom_variables;
    if (!cv) return [];
    return Object.entries(cv).map(([key, value]) => ({ key, value }));
  });
  const [skills, setSkills] = useState<string[]>([]);

  useEffect(() => {
    authFetch("/api/skills")
      .then((r) => r.json())
      .then((data) => {
        const names = data.skills?.map((s: { name: string }) => s.name) ?? [];
        setSkills(names);
      })
      .catch(() => undefined);
  }, []);

  const handleSave = () => {
    const custom_variables: Record<string, string> = {};
    for (const v of variables) {
      if (v.key.trim()) custom_variables[v.key.trim()] = v.value;
    }
    const req = {
      agent_description: name,
      agent_soul: prompt,
      skill_name: skillName,
      cron_expression: cronExpression,
      custom_variables: Object.keys(custom_variables).length > 0 ? custom_variables : undefined,
    };
    onSave(req);
  };

  const addVariable = () => setVariables([...variables, { key: "", value: "" }]);
  const removeVariable = (idx: number) => setVariables(variables.filter((_, i) => i !== idx));
  const updateVariable = (idx: number, field: "key" | "value", val: string) => {
    const next = [...variables];
    next[idx] = { ...next[idx], [field]: val } as { key: string; value: string };
    setVariables(next);
  };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium">{t.scheduler.taskName}</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t.scheduler.taskNamePlaceholder}
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">{t.scheduler.prompt}</label>
        <Textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={t.scheduler.promptPlaceholder}
          rows={5}
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">{t.scheduler.skill}</label>
        <Select value={skillName} onValueChange={setSkillName}>
          <SelectTrigger>
            <SelectValue placeholder={t.scheduler.skillPlaceholder} />
          </SelectTrigger>
          <SelectContent>
            {skills.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">{t.scheduler.cronExpression}</label>
        <CronBuilder value={cronExpression} onChange={setCronExpression} />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">{t.scheduler.customVariables}</label>
        {variables.map((v, idx) => (
          <div key={idx} className="mb-2 flex gap-2">
            <Input
              value={v.key}
              onChange={(e) => updateVariable(idx, "key", e.target.value)}
              placeholder={t.scheduler.variableKey}
              className="w-1/3"
            />
            <Input
              value={v.value}
              onChange={(e) => updateVariable(idx, "value", e.target.value)}
              placeholder={t.scheduler.variableValue}
              className="flex-1"
            />
            <Button variant="ghost" size="sm" onClick={() => removeVariable(idx)}>
              <Trash2 className="size-4" />
            </Button>
          </div>
        ))}
        <Button variant="outline" size="sm" onClick={addVariable}>
          <Plus className="mr-1 size-4" />
          {t.scheduler.addVariable}
        </Button>
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSave} disabled={isSaving || !name || !prompt || !skillName || !cronExpression}>
          {isSaving && <Loader2 className="mr-1 size-4 animate-spin" />}
          {isEdit ? t.scheduler.save : t.scheduler.createTask}
        </Button>
        <Button variant="outline" onClick={onCancel}>
          {t.common.cancel}
        </Button>
      </div>
    </div>
  );
}

interface TaskCardProps {
  task: ScheduledTask;
  isToggling: boolean;
  isTriggering: boolean;
  onToggle: () => void;
  onTrigger: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onViewExecution: (executionId: string) => void;
  t: ReturnType<typeof useI18n>["t"];
}

function TaskCard({
  task,
  isToggling,
  isTriggering,
  onToggle,
  onTrigger,
  onEdit,
  onDelete,
  isExpanded,
  onToggleExpand,
  onViewExecution,
  t,
}: TaskCardProps) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{task.agent_description}</span>
            {task.skill_name && <Badge variant="outline">{task.skill_name}</Badge>}
            <Badge variant={statusVariant[task.status]}>
              {task.status}
            </Badge>
          </div>
          <div className="text-muted-foreground mt-1 flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1">
              <Clock className="size-3" />
              {cronToHuman(task.cron_expression)}
            </span>
            <span>
              {t.scheduler.lastExecution}: {formatTime(task.last_execution_at)}
            </span>
            <span>
              {t.scheduler.nextExecution}: {formatTime(task.next_execution_at)}
            </span>
          </div>
          {task.error_message && (
            <div className="mt-1 text-destructive text-xs">{task.error_message}</div>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            disabled={isToggling}
            title={task.is_enabled ? t.scheduler.toggleDisable : t.scheduler.toggleEnable}
          >
            {task.is_enabled ? <Pause className="size-4" /> : <Play className="size-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onTrigger}
            disabled={isTriggering}
            title={t.scheduler.triggerNow}
          >
            {isTriggering ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Play className="size-4" />
            )}
          </Button>
          <Button variant="ghost" size="icon" onClick={onEdit} title={t.scheduler.editTask}>
            <Pencil className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={onDelete} title={t.scheduler.deleteTask}>
            <Trash2 className="size-4 text-destructive" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleExpand}
            title={t.scheduler.executionHistory}
          >
            {isExpanded ? (
              <ChevronDown className="size-4" />
            ) : (
              <ChevronRight className="size-4" />
            )}
          </Button>
        </div>
      </div>

      {isExpanded && (
        <ExecutionHistoryList taskId={task.id} onViewExecution={onViewExecution} t={t} />
      )}
    </div>
  );
}

interface ExecutionHistoryListProps {
  taskId: string;
  onViewExecution: (executionId: string) => void;
  t: ReturnType<typeof useI18n>["t"];
}

function ExecutionHistoryList({ taskId, onViewExecution, t }: ExecutionHistoryListProps) {
  const { data: executions, isLoading, error } = useTaskExecutions(taskId);

  if (isLoading) {
    return (
      <div className="mt-3 border-t pt-3">
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-3 border-t pt-3">
        <div className="text-destructive text-sm">{error.message}</div>
      </div>
    );
  }

  return (
    <div className="mt-3 border-t pt-3">
      <div className="mb-2 text-sm font-medium">{t.scheduler.executionHistory}</div>
      {!executions || executions.length === 0 ? (
        <div className="text-muted-foreground text-sm">{t.scheduler.noExecutions}</div>
      ) : (
        <div className="flex flex-col gap-1">
          {executions.map((exec) => (
            <div
              key={exec.id}
              className="flex items-center justify-between rounded-md px-2 py-1 text-sm hover:bg-muted/50"
            >
              <div className="flex items-center gap-3">
                <span>{executionStatusIcon[exec.status] ?? exec.status}</span>
                <span>{formatTime(exec.triggered_at)}</span>
                <span className="text-muted-foreground">
                  {t.scheduler.duration}: {formatDuration(exec.triggered_at, exec.completed_at)}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onViewExecution(exec.id)}
              >
                <Eye className="mr-1 size-3" />
                {t.scheduler.viewDetail}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ExecutionDetailDialogOpener({
  taskId,
  executionId,
  onClose,
}: {
  taskId: string;
  executionId: string;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const { data: execution, isLoading } = useTaskExecutions(taskId);

  const exec = execution?.find((e) => e.id === executionId);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.scheduler.executionDetail}</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="text-muted-foreground text-sm">{t.common.loading}</div>
        ) : exec ? (
          <div className="flex flex-col gap-2 text-sm">
            <div>
              <span className="font-medium">{t.scheduler.status}:</span>{" "}
              <span className="flex items-center gap-1">
                {executionStatusIcon[exec.status]}
                {exec.status}
              </span>
            </div>
            <div>
              <span className="font-medium">{t.scheduler.lastExecution}:</span>{" "}
              {formatTime(exec.triggered_at)}
            </div>
            {exec.completed_at && (
              <div>
                <span className="font-medium">{t.scheduler.duration}:</span>{" "}
                {formatDuration(exec.triggered_at, exec.completed_at)}
              </div>
            )}
            {exec.error_message && (
              <div className="text-destructive">{exec.error_message}</div>
            )}
            {exec.messages && exec.messages.length > 0 && (
              <div>
                <div className="mb-1 font-medium">{t.scheduler.messages}:</div>
                <div className="max-h-60 overflow-y-auto rounded border bg-muted/30 p-2">
                  {exec.messages.map((msg, idx) => (
                    <div key={msg.id ?? idx} className="border-b last:border-b-0 py-1">
                      {typeof msg.content === "string"
                        ? msg.content
                        : Array.isArray(msg.content)
                          ? msg.content
                              .filter((b): b is { type: string; text?: string } => b.type === "text")
                              .map((b, i) => <span key={i}>{b.text}</span>)
                          : null}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-muted-foreground text-sm">Not found</div>
        )}
      </DialogContent>
    </Dialog>
  );
}
