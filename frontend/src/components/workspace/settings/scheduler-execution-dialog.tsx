"use client";

import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MarkdownContent } from "@/components/workspace/messages/markdown-content";
import { useI18n } from "@/core/i18n/hooks";
import type { TaskExecution, ChatMessage, ContentBlock } from "@/core/scheduler/types";
import { streamdownPlugins } from "@/core/streamdown";

interface SchedulerExecutionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  execution: TaskExecution | null;
}

function extractTextContent(content: string | ContentBlock[]): string {
  if (typeof content === "string") return content;
  return content
    .filter((block) => block.type === "text" && block.text)
    .map((block) => block.text!)
    .join("\n");
}

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "completed":
      return "default";
    case "failed":
      return "destructive";
    case "skipped":
      return "secondary";
    default:
      return "outline";
  }
}

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = seconds % 60;
  return `${minutes}m ${remainSeconds}s`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function ToolMessageBlock({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(false);
  const text = extractTextContent(message.content);
  const maxLen = 300;
  const truncated = !expanded && text.length > maxLen;

  return (
    <div className="rounded-md border bg-muted/50 p-2 text-sm font-mono">
      <div className="flex items-center gap-1 text-muted-foreground">
        <span className="font-sans font-medium">{message.name ?? "tool"}</span>
      </div>
      <pre className="mt-1 whitespace-pre-wrap break-all text-xs">
        {truncated ? text.slice(0, maxLen) + "..." : text}
      </pre>
      {text.length > maxLen && (
        <button
          type="button"
          className="mt-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? (
            <>
              <ChevronUpIcon className="h-3 w-3" />
              Show less
            </>
          ) : (
            <>
              <ChevronDownIcon className="h-3 w-3" />
              Show more
            </>
          )}
        </button>
      )}
    </div>
  );
}

export function SchedulerExecutionDialog({
  open,
  onOpenChange,
  execution,
}: SchedulerExecutionDialogProps) {
  const { t } = useI18n();

  if (!execution) return null;

  const messages = execution.messages ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-w-4xl flex-col" style={{ height: "70vh" }}>
        <DialogHeader>
          <div className="flex items-center gap-3">
            <DialogTitle>{t.scheduler.executionDetail}</DialogTitle>
            <Badge variant={statusVariant(execution.status)}>
              {execution.status}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{formatTime(execution.triggered_at)}</span>
            {execution.completed_at && (
              <>
                <span>·</span>
                <span>
                  {t.scheduler.duration}: {formatDuration(execution.triggered_at, execution.completed_at)}
                </span>
              </>
            )}
          </div>
        </DialogHeader>

        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="flex flex-col gap-3 py-2">
            {messages.length === 0 && (
              <p className="text-center text-sm text-muted-foreground">
                {t.scheduler.noExecutions}
              </p>
            )}
            {messages.map((msg, idx) => {
              if (msg.type === "system") return null;

              if (msg.type === "human") {
                const text = extractTextContent(msg.content);
                return (
                  <div key={msg.id ?? idx} className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-primary-foreground">
                      <p className="whitespace-pre-wrap text-sm">{text}</p>
                    </div>
                  </div>
                );
              }

              if (msg.type === "ai") {
                const text = extractTextContent(msg.content);
                if (!text) return null;
                return (
                  <div key={msg.id ?? idx} className="flex justify-start">
                    <div className="max-w-[80%] rounded-2xl rounded-bl-sm bg-muted px-4 py-2.5">
                      <MarkdownContent
                        content={text}
                        isLoading={false}
                        rehypePlugins={streamdownPlugins.rehypePlugins}
                        className="text-sm"
                      />
                    </div>
                  </div>
                );
              }

              if (msg.type === "tool") {
                return (
                  <div key={msg.id ?? idx} className="mx-auto w-full max-w-[80%]">
                    <ToolMessageBlock message={msg} />
                  </div>
                );
              }

              return null;
            })}

            {execution.error_message && (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                {execution.error_message}
              </div>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
