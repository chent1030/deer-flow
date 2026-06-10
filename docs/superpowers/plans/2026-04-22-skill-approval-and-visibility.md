# Skill 审批生效 + 权限运行时过滤 实现计划

> **给智能体工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务执行本计划。步骤使用复选框（`- [ ]`）语法进行追踪。

**目标：** 修复管理端 skill 审批后不生效的 bug，并实现按用户权限在 agent 运行时过滤 skill 列表。

**架构：** 两层改动——第一层修复审批链路（从 MinIO 下载 ZIP → 解压到 `skills/custom/` → 刷新缓存）；第二层在 agent 调用时查询 admin DB 的 skill 可见性规则，按当前用户过滤 `available_skills`，权限被收回后下次对话自动不显示。

**技术栈：** Python 3.12（FastAPI、SQLAlchemy、LangGraph）

---

## 需要修改的文件

| 文件 | 职责 |
|------|------|
| `backend/app/admin/routers/skills.py` | 修复审批提取、删除清理、添加按用户可见 skill 列表端点 |
| `backend/app/admin/services/skill_service.py` | 添加按用户查询可见 skill 列表 |
| `backend/app/admin/schemas/skill.py` | 添加可见 skill 响应 schema |
| `backend/packages/harness/deerflow/skills/loader.py` | 添加按 skill 名过滤函数 |
| `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` | `get_skills_prompt_section` 接受按用户过滤后的 skill 列表 |
| `backend/packages/harness/deerflow/agents/lead_agent/agent.py` | 从 configurable metadata 取用户可见 skill 列表 |
| `backend/app/gateway/routers/skills.py` | 添加认证，按用户过滤 skill 列表 |
| `backend/tests/test_admin/test_skill_api.py` | 更新审批测试验证文件系统 |

---

### 任务 1：修复审批链路——审批时从 MinIO 下载 ZIP 并解压到 skills/custom/

**文件：**
- 修改：`backend/app/admin/routers/skills.py` — `review_skill` 端点（约第 219-230 行）

当前代码（第 219-230 行）：
```python
@router.post("/{skill_id}/review", response_model=SkillResponse)
async def review_skill(
    skill_id: uuid.UUID,
    req: SkillReviewRequest,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    updated = await skill_service.review_skill(db, skill, user.id, req.action, req.comment)
    if req.action == "approve":
        _extract_skill_to_custom(updated.name)
    return _skill_to_response(updated)
```

- [ ] **步骤 1：替换审批逻辑**

将 `if req.action == "approve":` 块改为：
```python
    if req.action == "approve":
        minio_client = _get_minio_client()
        zip_data = minio_client.download(updated.minio_object_key)
        _extract_zip_to_skills(zip_data, updated.name)
        try:
            from deerflow.agents.lead_agent.prompt import refresh_skills_system_prompt_cache_async
            await refresh_skills_system_prompt_cache_async()
        except Exception:
            pass
```

- [ ] **步骤 2：验证** — 从 `backend/` 运行：
```bash
PYTHONPATH=. uv run python -c "from app.admin.routers.skills import review_skill; print('OK')"
```
预期输出：`OK`

---

### 任务 2：修复删除链路——删除/拒绝时清理 skills/custom/ 目录

**文件：**
- 修改：`backend/app/admin/routers/skills.py` — `delete_skill` 端点

- [ ] **步骤 1：在 `delete_skill` 端点中添加文件系统清理**

找到 `delete_skill` 端点（约第 233-248 行），在 `minio_client.delete` 之后添加文件系统清理：

```python
@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if skill.author_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or super admin can delete")
    deleted = await skill_service.delete_skill(db, skill_id)
    try:
        minio_client = _get_minio_client()
        minio_client.delete(deleted.minio_object_key)
    except Exception:
        pass
    if deleted.status == SkillStatus.APPROVED:
        _remove_skill_from_custom(deleted.name)
    return {"message": "Skill deleted"}
```

- [ ] **步骤 2：添加 `_remove_skill_from_custom` 辅助函数**

在文件顶部辅助函数区域（`_extract_zip_to_skills` 之后）添加：

```python
def _remove_skill_from_custom(skill_name: str) -> None:
    skill_path = os.path.join(SKILLS_ROOT, skill_name)
    if os.path.exists(skill_path):
        shutil.rmtree(skill_path)
```

注意：`shutil` 和 `os` 已经被导入。

- [ ] **步骤 3：验证** — 从 `backend/` 运行：
```bash
PYTHONPATH=. uv run python -c "from app.admin.routers.skills import delete_skill; print('OK')"
```

---

### 任务 3：添加按用户查询可见 skill 列表的服务函数

**文件：**
- 修改：`backend/app/admin/services/skill_service.py`

- [ ] **步骤 1：添加 `list_visible_skills_for_user` 函数**

在文件末尾添加：

```python
async def list_visible_skills_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_role: str,
    department_id: uuid.UUID | None,
) -> list[str]:
    query = select(Skill).where(Skill.status == SkillStatus.APPROVED)
    skills_result = await db.execute(query)
    all_skills = list(skills_result.scalars().all())

    visible_names = []
    for skill in all_skills:
        if skill.visibility == SkillVisibility.COMPANY:
            visible_names.append(skill.name)
        elif skill.visibility == SkillVisibility.DEPARTMENT:
            if user_role in ("super_admin", "dept_admin") or skill.department_id == department_id:
                visible_names.append(skill.name)
        elif skill.visibility == SkillVisibility.SPECIFIC_USERS:
            if user_role == "super_admin":
                visible_names.append(skill.name)
                continue
            result = await db.execute(
                select(SkillVisibleUser).where(
                    SkillVisibleUser.skill_id == skill.id,
                    SkillVisibleUser.user_id == user_id,
                )
            )
            if result.scalar_one_or_none():
                visible_names.append(skill.name)
        elif skill.visibility == SkillVisibility.PRIVATE:
            if skill.author_id == user_id or user_role == "super_admin":
                visible_names.append(skill.name)

    return visible_names
```

- [ ] **步骤 2：验证** — 从 `backend/` 运行：
```bash
PYTHONPATH=. uv run python -c "from app.admin.services.skill_service import list_visible_skills_for_user; print('OK')"
```

---

### 任务 4：添加按用户可见 skill 列表的 API 端点

**文件：**
- 修改：`backend/app/admin/routers/skills.py`
- 修改：`backend/app/admin/schemas/skill.py`

- [ ] **步骤 1：在 schemas 中添加响应类型**

在 `backend/app/admin/schemas/skill.py` 末尾添加：

```python
class VisibleSkillsResponse(BaseModel):
    skill_names: list[str]
```

- [ ] **步骤 2：在 admin skill router 中添加端点**

在 `backend/app/admin/routers/skills.py` 中添加新端点（在 `list_skills` 之后）：

```python
from app.admin.schemas.skill import SkillListResponse, SkillResponse, SkillReviewRequest, SkillUpdate, SkillVisibilityUpdate, VisibleSkillsResponse

@router.get("/visible", response_model=VisibleSkillsResponse)
async def list_visible_skills(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    names = await skill_service.list_visible_skills_for_user(
        db, user.id, user.role.value, user.department_id,
    )
    return VisibleSkillsResponse(skill_names=names)
```

**注意：** 这个端点必须放在 `@router.get("/{skill_id}")` 之前（FastAPI 按注册顺序匹配路由，否则 `/visible` 会被 `/{skill_id}` 捕获）。

- [ ] **步骤 3：验证** — 从 `backend/` 运行：
```bash
PYTHONPATH=. uv run python -c "from app.admin.routers.skills import list_visible_skills; print('OK')"
```

---

### 任务 5：为 Gateway skills 路由添加认证和按用户过滤

**文件：**
- 修改：`backend/app/gateway/routers/skills.py`

- [ ] **步骤 1：添加导入和认证依赖**

在文件顶部添加：
```python
from app.admin.deps import get_current_user
from app.admin.models.user import User
```

- [ ] **步骤 2：为 `list_skills` 端点添加认证和过滤**

找到 `async def list_skills() -> SkillsListResponse:` 改为：

```python
@router.get(
    "/skills",
    response_model=SkillsListResponse,
    summary="List All Skills",
    description="Retrieve a list of all available skills filtered by user visibility.",
)
async def list_skills(current_user: User = Depends(get_current_user)) -> SkillsListResponse:
    try:
        from app.admin.services import skill_service as admin_skill_service
        from app.admin.models.skill import SkillStatus, SkillVisibility
        from sqlalchemy import select
        from app.admin.deps import get_db
        from app.admin.models.skill import Skill as AdminSkill, SkillVisibleUser

        all_skills = load_skills(enabled_only=True)

        try:
            from app.gateway.app import get_app
            app = get_app()
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
            async with async_sessionmaker(app.state.db_engine)() as db:
                visible_names = await admin_skill_service.list_visible_skills_for_user(
                    db, current_user.id, current_user.role.value, current_user.department_id,
                )
        except Exception:
            visible_names = [s.name for s in all_skills]

        if visible_names is not None:
            all_skills = [s for s in all_skills if s.name in visible_names]

        return SkillsListResponse(skills=[_skill_to_response(skill) for skill in all_skills])
    except Exception as e:
        logger.error(f"Failed to load skills: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load skills: {str(e)}")
```

**注意：** 这需要 gateway app 的 `db_engine` 在 `app.state` 上可用。检查 `app/gateway/app.py` 确认。如果不可用，改用 `get_app_config().admin.database_url` 创建临时 session。

- [ ] **步骤 3：验证** — 从 `backend/` 运行：
```bash
PYTHONPATH=. uv run python -c "from app.gateway.routers.skills import list_skills; print('OK')"
```

---

### 任务 6：在 agent 运行时按用户过滤 skill 列表

**文件：**
- 修改：`backend/packages/harness/deerflow/agents/lead_agent/prompt.py`
- 修改：`backend/packages/harness/deerflow/agents/lead_agent/agent.py`

这是权限隔离的核心——让 agent 在构建 system prompt 时只包含当前用户可见的 skill。

- [ ] **步骤 1：修改 `get_skills_prompt_section` 接受可选的用户可见 skill 名列表**

在 `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` 中，找到 `get_skills_prompt_section`（约第 571 行）：

```python
def get_skills_prompt_section(available_skills: set[str] | None = None) -> str:
```

改为：
```python
def get_skills_prompt_section(available_skills: set[str] | None = None, visible_skill_names: set[str] | None = None) -> str:
```

在 `skills = _get_enabled_skills()` 之后，添加过滤逻辑：
```python
    if visible_skill_names is not None:
        skills = [s for s in skills if s.name in visible_skill_names]
```

- [ ] **步骤 2：修改 `apply_prompt_template` 传递 `visible_skill_names`**

找到 `apply_prompt_template`（约第 674 行），添加 `visible_skill_names` 参数：

```python
def apply_prompt_template(subagent_enabled: bool = False, max_concurrent_subagents: int = 3, *, agent_name: str | None = None, available_skills: set[str] | None = None, visible_skill_names: set[str] | None = None, username: str | None = None) -> str:
```

将 `get_skills_prompt_section(available_skills)` 改为 `get_skills_prompt_section(available_skills, visible_skill_names=visible_skill_names)`。

- [ ] **步骤 3：在 agent.py 中从 configurable metadata 提取可见 skill 列表**

在 `backend/packages/harness/deerflow/agents/lead_agent/agent.py` 中，找到 `apply_prompt_template(` 调用（约第 346-348 行）：

```python
        system_prompt=apply_prompt_template(
            subagent_enabled=subagent_enabled, max_concurrent_subagents=max_concurrent_subagents, agent_name=agent_name, available_skills=set(agent_config.skills) if agent_config and agent_config.skills is not None else None
        ),
```

改为：
```python
        config_data = get_config()
        visible_skills = config_data.get("configurable", {}).get("visible_skills")
        visible_skill_names = set(visible_skills) if visible_skills else None
        system_prompt=apply_prompt_template(
            subagent_enabled=subagent_enabled, max_concurrent_subagents=max_concurrent_subagents, agent_name=agent_name, available_skills=set(agent_config.skills) if agent_config and agent_config.skills is not None else None, visible_skill_names=visible_skill_names, username=config_data.get("configurable", {}).get("username"),
        ),
```

确保 `get_config` 已被导入（检查文件顶部的 import，应该已有 `from langgraph.config import get_config`）。

- [ ] **步骤 4：验证** — 从 `backend/` 运行：
```bash
PYTHONPATH=. uv run python -c "from deerflow.agents.lead_agent.prompt import apply_prompt_template; result = apply_prompt_template(visible_skill_names={'data-analysis'}); print('OK, length:', len(result))"
```

---

### 任务 7：在 Gateway 创建线程时注入用户可见 skill 列表

**文件：**
- 修改：`backend/app/gateway/routers/threads.py`（或 thread_runs.py）

这是把 `visible_skills` 和 `username` 注入 LangGraph configurable metadata 的地方。当用户通过 Gateway 创建或运行线程时，从 JWT 中提取用户身份，查询可见 skill 列表，注入到 configurable 中。

- [ ] **步骤 1：找到线程创建/运行入口**

搜索 Gateway 中调用 LangGraph client 创建线程或运行 agent 的代码。找到 `configurable` 字典被构建的位置。

- [ ] **步骤 2：注入 `username` 和 `visible_skills`**

在 configurable 构建处添加：
```python
from app.admin.deps import get_current_user
from app.admin.services import skill_service as admin_skill_service

# 在已有的 configurable 字典中添加：
configurable["username"] = current_user.username
# 查询可见 skill 列表
visible_names = await admin_skill_service.list_visible_skills_for_user(
    db, current_user.id, current_user.role.value, current_user.department_id,
)
configurable["visible_skills"] = visible_names
```

**注意：** 具体实现取决于线程创建/运行的代码结构。需要先阅读相关文件。

---

### 任务 8：更新测试

**文件：**
- 修改：`backend/tests/test_admin/test_skill_api.py`

- [ ] **步骤 1：验证审批测试中 zip 被解压**

添加一个测试用例验证审批后文件存在于 `skills/custom/`：
```python
@pytest.mark.asyncio
async def test_review_approve_extracts_to_custom(client, auth_headers, seed_data, tmp_path):
    zip_bytes = _make_zip_bytes("approve-extract-skill")
    resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "approve-extract-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", zip_bytes, "application/zip")},
    )
    skill_id = resp.json()["id"]
    resp = await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["super_admin"],
        json={"action": "approve", "comment": "OK"},
    )
    assert resp.status_code == 200
```

- [ ] **步骤 2：添加可见 skill 列表测试**

```python
@pytest.mark.asyncio
async def test_list_visible_skills(client, auth_headers, seed_data):
    resp = await client.get("/api/admin/skills/visible", headers=auth_headers["super_admin"])
    assert resp.status_code == 200
    assert "skill_names" in resp.json()
```

- [ ] **步骤 3：运行所有测试** — 从 `backend/` 运行：
```bash
PYTHONPATH=. uv run pytest tests/test_admin/ tests/test_memory_*.py --tb=short -v
```

---

### 任务 9：最终验证

- [ ] **步骤 1：运行后端 lint** — `PYTHONPATH=. uv run ruff check app/ packages/ tests/`
- [ ] **步骤 2：运行所有后端测试** — `PYTHONPATH=. uv run pytest tests/ --tb=short`
- [ ] **步骤 3：运行前端类型检查** — `node_modules/.bin/tsc --noEmit`
- [ ] **步骤 4：运行管理端类型检查** — `node_modules/.bin/tsc --noEmit`
