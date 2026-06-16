"use client";

import { Eye, EyeOff, LockKeyhole, Sparkles, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AnimatedLoginCharacters } from "@/components/auth/animated-login-characters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { localizeErrorMessage } from "@/core/errors/localize";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [focusedField, setFocusedField] = useState<"username" | "password" | null>(
    null,
  );
  const router = useRouter();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(localizeErrorMessage(data.detail, "登录失败"));
        return;
      }
      router.push("/workspace");
    } catch {
      setError("网络错误，请重试");
    } finally {
      setLoading(false);
    }
  };

  const isTyping = focusedField !== null;

  return (
    <main className="grid min-h-dvh bg-[#fff7ed] text-[#22160f] lg:grid-cols-[minmax(0,1.08fr)_minmax(440px,0.92fr)]">
      <section className="relative hidden min-h-dvh overflow-hidden bg-[#f97316] px-10 py-10 text-white lg:flex lg:flex-col lg:justify-between xl:px-14">
        <div className="relative z-10 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg border border-white/20 bg-white/15">
            <Sparkles className="size-5" />
          </div>
          <div>
            <div className="text-base font-semibold">芯工坊</div>
            <div className="text-xs text-white/70">企业级智能体协作平台</div>
          </div>
        </div>

        <div className="relative z-10 flex flex-1 flex-col justify-center">
          <div className="mb-8 max-w-xl">
            <p className="mb-3 text-sm font-medium text-white/75">
              Welcome back
            </p>
            <h1 className="text-5xl leading-tight font-bold">
              让智能体继续接手你的工作流
            </h1>
            <p className="mt-5 max-w-md text-base leading-7 text-white/78">
              登录后进入工作台，管理对话、文件、技能和自动化任务。
            </p>
          </div>

          <div className="flex justify-center">
            <AnimatedLoginCharacters
              isTyping={isTyping}
              passwordLength={password.length}
              showPassword={showPassword}
            />
          </div>
        </div>
      </section>

      <section className="flex min-h-dvh items-center justify-center px-6 py-10 sm:px-8">
        <div className="w-full max-w-[420px]">
          <div className="mb-10 flex items-center justify-center gap-3 lg:hidden">
            <div className="flex size-10 items-center justify-center rounded-lg bg-[#f97316] text-white">
              <Sparkles className="size-5" />
            </div>
            <div>
              <div className="text-base font-semibold">Clerk Flow</div>
              <div className="text-xs text-muted-foreground">
                企业级智能体协作平台
              </div>
            </div>
          </div>

          <div className="mb-9">
            <p className="mb-3 text-sm font-medium text-[#9a3412]">
              账号登录
            </p>
            <h2 className="text-3xl font-bold">欢迎回来</h2>
            <p className="mt-3 text-sm leading-6 text-[#7c5b47]">
              使用管理员分配的账号进入工作台。
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <div className="relative">
                <UserRound className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-[#9a6a4a]" />
                <Input
                  id="username"
                  type="text"
                  value={username}
                  autoComplete="username"
                  onChange={(event) => setUsername(event.target.value)}
                  onFocus={() => setFocusedField("username")}
                  onBlur={() => setFocusedField(null)}
                  className="h-12 rounded-lg border-[#e8c7a9] bg-white/80 pl-10 text-[#22160f] shadow-none focus-visible:border-[#f97316] focus-visible:ring-[#f97316]/20"
                  placeholder="请输入用户名"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <div className="relative">
                <LockKeyhole className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-[#9a6a4a]" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  autoComplete="current-password"
                  onChange={(event) => setPassword(event.target.value)}
                  onFocus={() => setFocusedField("password")}
                  onBlur={() => setFocusedField(null)}
                  className="h-12 rounded-lg border-[#e8c7a9] bg-white/80 px-10 text-[#22160f] shadow-none focus-visible:border-[#f97316] focus-visible:ring-[#f97316]/20"
                  placeholder="请输入密码"
                  required
                />
                <button
                  type="button"
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                  onClick={() => setShowPassword((value) => !value)}
                  className={cn(
                    "absolute top-1/2 right-2 flex size-9 -translate-y-1/2 items-center justify-center rounded-md text-[#8a5b3d] transition-colors hover:bg-[#ffedd5] hover:text-[#7c2d12] focus-visible:ring-2 focus-visible:ring-[#f97316]/40 focus-visible:outline-none",
                  )}
                >
                  {showPassword ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </button>
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="h-12 w-full rounded-lg bg-[#111827] text-base font-medium text-white hover:bg-[#0f172a]"
              disabled={loading}
            >
              {loading ? "登录中..." : "登录"}
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
}
