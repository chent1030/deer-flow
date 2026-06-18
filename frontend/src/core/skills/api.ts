import { authFetch } from "@/core/api/auth-fetch";
import { parseJsonOrThrow } from "@/core/api/response";

import type { Skill } from "./type";

export async function loadSkills() {
  const skills = await authFetch("/api/skills");
  const json = await parseJsonOrThrow<{ skills: Skill[] }>(
    skills,
    "加载技能失败",
  );
  return json.skills as Skill[];
}

export async function loadVisibleSkillNames(): Promise<string[]> {
  try {
    const skills = await loadSkills();
    return skills.map((s) => s.name);
  } catch {
    return [];
  }
}

export async function enableSkill(skillName: string, enabled: boolean) {
  const response = await authFetch(`/api/skills/${skillName}`, {
    method: "PUT",
    body: JSON.stringify({
      enabled,
    }),
  });
  return parseJsonOrThrow<Skill>(
    response,
    `更新技能 ${skillName} 失败`,
  );
}

export interface InstallSkillRequest {
  thread_id: string;
  path: string;
}

export interface InstallSkillResponse {
  success: boolean;
  skill_name: string;
  message: string;
}

export async function installSkill(
  request: InstallSkillRequest,
): Promise<InstallSkillResponse> {
  const response = await authFetch("/api/skills/install", {
    method: "POST",
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let errorMessage = "安装技能失败";
    try {
      await parseJsonOrThrow<unknown>(response, errorMessage);
    } catch (error) {
      if (error instanceof Error) errorMessage = error.message;
      else if (typeof error === "string") errorMessage = error;
    }
    return {
      success: false,
      skill_name: "",
      message: errorMessage,
    };
  }

  return parseJsonOrThrow<InstallSkillResponse>(response, "安装技能失败");
}
