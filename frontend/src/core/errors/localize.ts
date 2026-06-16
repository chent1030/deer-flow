export function localizeErrorMessage(message: unknown, fallback = "操作失败"): string {
  if (typeof message !== "string" || !message.trim()) {
    return fallback;
  }

  const text = message.trim();
  const rules: Array<[RegExp, string]> = [
    [/^Unauthorized$/, "请先登录"],
    [/^Authentication failed$/, "认证失败"],
    [/^Login failed$/, "登录失败"],
    [/^Could not reach the DeerFlow backend\.$/, "无法连接到 DeerFlow 后端。"],
    [/^Failed to check agent name: /, "检查智能体名称失败："],
    [/^Failed to load agents: /, "加载智能体失败："],
    [/^Failed to create agent: /, "创建智能体失败："],
    [/^Failed to update agent: /, "更新智能体失败："],
    [/^Failed to delete agent: /, "删除智能体失败："],
    [/^Failed to share agent: /, "分享智能体失败："],
    [/^Failed to load users: /, "加载用户失败："],
    [/^Failed to list uploaded files$/, "加载已上传文件失败"],
    [/^Failed to delete file$/, "删除文件失败"],
    [/^Upload failed$/, "上传失败"],
    [/^Agent '(.+)' not found$/, "智能体“$1”不存在"],
    [/^Invalid agent name '(.+)'.*$/, "智能体名称“$1”无效，只能包含字母、数字和连字符。"],
    [/^Custom-agent management API is disabled\..*$/, "自定义智能体管理接口未启用。"],
    [/^CSRF token missing\. Include X-CSRF-Token header\.$/, "缺少 CSRF 令牌，请携带 X-CSRF-Token 请求头。"],
    [/^CSRF token mismatch\.$/, "CSRF 令牌不匹配。"],
    [/^Cross-site auth request denied\.$/, "跨站认证请求已被拒绝。"],
    [/^Invalid credentials$/, "用户名或密码错误"],
    [/^User is disabled$/, "用户已被禁用"],
    [/^Old password is incorrect$/, "当前密码不正确"],
    [/^Target user not found$/, "目标用户不存在"],
    [/^Cannot share an agent to self$/, "不能将智能体分享给自己"],
    [/^Target user is disabled$/, "目标用户已被禁用"],
  ];

  for (const [pattern, replacement] of rules) {
    if (pattern.test(text)) {
      return text.replace(pattern, replacement);
    }
  }
  return text;
}
