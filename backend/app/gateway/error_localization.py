from __future__ import annotations

import re
from typing import Any


_STRING_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^Authentication required$"), "请先登录"),
    (re.compile(r"^Not authenticated$"), "请先登录"),
    (re.compile(r"^Invalid token$"), "登录状态无效，请重新登录"),
    (re.compile(r"^Invalid token type$"), "令牌类型无效"),
    (re.compile(r"^Invalid token payload$"), "令牌内容无效"),
    (re.compile(r"^Token expired$"), "登录状态已过期，请重新登录"),
    (re.compile(r"^Token invalid$"), "登录状态无效，请重新登录"),
    (re.compile(r"^Token revoked \(password changed\)$"), "登录状态已失效，请重新登录"),
    (re.compile(r"^User not found$"), "用户不存在"),
    (re.compile(r"^User is disabled$"), "用户已被禁用"),
    (re.compile(r"^Insufficient permissions$"), "权限不足"),
    (re.compile(r"^Configuration not available$"), "配置不可用"),
    (re.compile(r"^Thread metadata store not available$"), "对话元数据存储不可用"),
    (re.compile(r"^Admin session factory not available$"), "管理端会话服务不可用"),
    (re.compile(r"^Invalid credentials$"), "用户名或密码错误"),
    (re.compile(r"^Invalid refresh token$"), "刷新令牌无效"),
    (re.compile(r"^User not available$"), "用户不可用"),
    (re.compile(r"^Old password is incorrect$"), "当前密码不正确"),
    (re.compile(r"^Cross-site auth request denied\.$"), "跨站认证请求已被拒绝。"),
    (re.compile(r"^CSRF token missing\. Include X-CSRF-Token header\.$"), "缺少 CSRF 令牌，请携带 X-CSRF-Token 请求头。"),
    (re.compile(r"^CSRF token mismatch\.$"), "CSRF 令牌不匹配。"),
    (re.compile(r"^Too many login attempts\. Try again later\.$"), "登录尝试过多，请稍后再试。"),
    (re.compile(r"^Incorrect email or password$"), "用户名或密码错误"),
    (re.compile(r"^Email already registered$"), "邮箱已注册"),
    (re.compile(r"^OAuth users cannot change password$"), "OAuth 用户不能修改密码"),
    (re.compile(r"^Current password is incorrect$"), "当前密码不正确"),
    (re.compile(r"^Email already in use$"), "邮箱已被使用"),
    (re.compile(r"^System already initialized$"), "系统已完成初始化"),
    (re.compile(r"^Task not found$"), "定时任务不存在"),
    (re.compile(r"^Execution not found$"), "执行记录不存在"),
    (re.compile(r"^Task not found or access denied$"), "定时任务不存在或无权访问"),
    (re.compile(r"^Access denied$"), "无权访问"),
    (re.compile(r"^Department not found$"), "部门不存在"),
    (re.compile(r"^Department cannot be its own parent$"), "部门不能设置为自己的上级部门"),
    (re.compile(r"^Department has child departments$"), "该部门下仍有子部门"),
    (re.compile(r"^Department has users$"), "该部门下仍有用户"),
    (re.compile(r"^Cannot access other department$"), "不能访问其他部门"),
    (re.compile(r"^Cannot access user in other department$"), "不能访问其他部门的用户"),
    (re.compile(r"^Cannot update user in other department$"), "不能修改其他部门的用户"),
    (re.compile(r"^Username already exists$"), "用户名已存在"),
    (re.compile(r"^Department admin can only reset regular user passwords$"), "部门管理员只能重置普通用户密码"),
    (re.compile(r"^Cannot reset user password outside your department$"), "不能重置其他部门用户的密码"),
    (re.compile(r"^File must be a zip archive$"), "文件必须是 zip 压缩包"),
    (re.compile(r"^Skill not found$"), "Skill 不存在"),
    (re.compile(r"^You do not have access to this skill$"), "你无权访问该 Skill"),
    (re.compile(r"^Only the author or super admin can download$"), "只有作者或超级管理员可以下载"),
    (re.compile(r"^Only the author or super admin can edit$"), "只有作者或超级管理员可以编辑"),
    (re.compile(r"^Only the author can set visibility$"), "只有作者可以设置可见性"),
    (re.compile(r"^Visibility can only be set on approved skills$"), "只有已通过审核的 Skill 才能设置可见性"),
    (re.compile(r"^Only the author can submit$"), "只有作者可以提交"),
    (re.compile(r"^Only the author can withdraw$"), "只有作者可以撤回"),
    (re.compile(r"^Skill is not pending review$"), "Skill 不在待审核状态"),
    (re.compile(r"^Only the author or super admin can delete$"), "只有作者或超级管理员可以删除"),
    (re.compile(r"^Skill must be withdrawn or rejected to resubmit$"), "只有已撤回或已驳回的 Skill 可以重新提交"),
    (re.compile(r"^Only pending review skills can be withdrawn$"), "只有待审核的 Skill 可以撤回"),
    (re.compile(r"^Thread not found$"), "对话不存在"),
    (re.compile(r"^Thread ([^ ]+) not found$"), "对话 $1 不存在"),
    (re.compile(r"^Run ([^ ]+) not found$"), "运行记录 $1 不存在"),
    (re.compile(r"^No feedback found for this run$"), "该运行记录没有反馈"),
    (re.compile(r"^Feedback ([^ ]+) not found$"), "反馈 $1 不存在"),
    (re.compile(r"^rating must be \+1 or -1$"), "评分只能是 +1 或 -1"),
    (re.compile(r"^Model '(.+)' not found$"), "模型“$1”不存在"),
    (re.compile(r"^Channel service is not running$"), "消息通道服务未运行"),
    (re.compile(r"^No files provided$"), "未提供文件"),
    (re.compile(r"^Total upload size too large$"), "上传文件总大小过大"),
    (re.compile(r"^File too large: (.+)$"), "文件过大：$1"),
    (re.compile(r"^Too many files: maximum is (.+)$"), "文件数量过多，最多允许 $1 个"),
    (re.compile(r"^File not found: (.+)$"), "文件不存在：$1"),
    (re.compile(r"^Invalid path$"), "路径无效"),
    (re.compile(r"^Upload failed$"), "上传失败"),
)


def localize_error_message(message: str) -> str:
    for pattern, replacement in _STRING_RULES:
        if pattern.search(message):
            return pattern.sub(replacement, message)
    return message


def localize_error_detail(detail: Any) -> Any:
    if isinstance(detail, str):
        return localize_error_message(detail)
    if isinstance(detail, list):
        return [localize_error_detail(item) for item in detail]
    if isinstance(detail, dict):
        localized = dict(detail)
        message = localized.get("message")
        if isinstance(message, str):
            localized["message"] = localize_error_message(message)
        detail_value = localized.get("detail")
        if detail_value is not None:
            localized["detail"] = localize_error_detail(detail_value)
        msg = localized.get("msg")
        if isinstance(msg, str):
            localized["msg"] = localize_error_message(msg)
        return localized
    return detail
