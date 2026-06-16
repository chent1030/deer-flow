"use client";

import { CheckIcon, Loader2Icon, SearchIcon, XIcon } from "lucide-react";
import { useMemo, useState } from "react";

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
import { ScrollArea } from "@/components/ui/scroll-area";
import { useShareAgent, useShareUsers } from "@/core/agents";
import type { Agent, ShareAgentResult, ShareUser } from "@/core/agents";
import { localizeErrorMessage } from "@/core/errors/localize";
import { useI18n } from "@/core/i18n/hooks";

interface AgentShareDialogProps {
  agent: Agent;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function userLabel(user: ShareUser): string {
  return user.display_name ? `${user.display_name} (${user.username})` : user.username;
}

function localizedShareResult(result: ShareAgentResult): string {
  if (result.status === "created") {
    return result.target_agent_name ? `已创建为 ${result.target_agent_name}` : "已创建";
  }
  return localizeErrorMessage(result.error_message, "分享失败");
}

export function AgentShareDialog({
  agent,
  open,
  onOpenChange,
}: AgentShareDialogProps) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ShareUser[]>([]);
  const [results, setResults] = useState<ShareAgentResult[] | null>(null);
  const usersQuery = useShareUsers(search);
  const shareMutation = useShareAgent();
  const selectedIds = useMemo(() => new Set(selected.map((u) => u.id)), [selected]);

  function toggleUser(user: ShareUser) {
    setResults(null);
    setSelected((current) =>
      current.some((item) => item.id === user.id)
        ? current.filter((item) => item.id !== user.id)
        : [...current, user],
    );
  }

  async function submit() {
    const response = await shareMutation.mutateAsync({
      name: agent.name,
      userIds: selected.map((u) => u.id),
    });
    setResults(response.results);
  }

  function close(nextOpen: boolean) {
    onOpenChange(nextOpen);
    if (!nextOpen) {
      setSearch("");
      setSelected([]);
      setResults(null);
      shareMutation.reset();
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.agents.shareTitle}</DialogTitle>
          <DialogDescription>{t.agents.shareDescription}</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="relative">
            <SearchIcon className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.agents.shareSearchPlaceholder}
              className="pl-8"
            />
          </div>

          {selected.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {selected.map((user) => (
                <Badge key={user.id} variant="secondary" className="gap-1">
                  {userLabel(user)}
                  <button type="button" onClick={() => toggleUser(user)}>
                    <XIcon className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}

          <ScrollArea className="h-48 rounded-md border">
            <div className="p-2">
              {usersQuery.isLoading ? (
                <div className="text-muted-foreground p-3 text-sm">
                  {t.common.loading}
                </div>
              ) : usersQuery.data?.length ? (
                usersQuery.data.map((user) => {
                  const checked = selectedIds.has(user.id);
                  return (
                    <button
                      key={user.id}
                      type="button"
                      onClick={() => toggleUser(user)}
                      className="hover:bg-muted flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm"
                    >
                      <span>{userLabel(user)}</span>
                      {checked && <CheckIcon className="text-primary h-4 w-4" />}
                    </button>
                  );
                })
              ) : (
                <div className="text-muted-foreground p-3 text-sm">
                  {t.agents.shareNoUsers}
                </div>
              )}
            </div>
          </ScrollArea>

          {results && (
            <div className="space-y-1 rounded-md border p-2 text-sm">
              {results.map((result) => (
                <div
                  key={result.target_user_id}
                  className="flex items-center justify-between gap-2"
                >
                  <span>{result.target_username ?? result.target_user_id}</span>
                  <span
                    className={
                      result.status === "created"
                        ? "text-green-600"
                        : "text-destructive"
                    }
                  >
                    {localizedShareResult(result)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            {t.common.cancel}
          </Button>
          <Button
            onClick={submit}
            disabled={selected.length === 0 || shareMutation.isPending}
          >
            {shareMutation.isPending && (
              <Loader2Icon className="mr-1.5 h-4 w-4 animate-spin" />
            )}
            {t.agents.share}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
