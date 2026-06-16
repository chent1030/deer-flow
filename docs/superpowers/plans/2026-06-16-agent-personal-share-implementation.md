# Agent Personal Share Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add personal agent sharing where sharing creates independent per-recipient agent copies and the admin panel shows read-only share records.

**Architecture:** Implement a backend share service around the existing user-scoped filesystem agent storage, backed by an audit table. The workspace UI calls a new share endpoint from each agent card, while the admin UI reads share records through a read-only admin endpoint.

**Tech Stack:** FastAPI, SQLAlchemy async models/services, Alembic, pytest, Next.js/React, TanStack Query, Vite admin React app.

---

### Task 1: Backend Model, Migration, And Share Service Tests

**Files:**
- Create: `backend/app/admin/models/agent_share.py`
- Modify: `backend/app/admin/models/__init__.py`
- Create: `backend/alembic/versions/e2f3a4b5c6d7_add_agent_share_records.py`
- Create: `backend/app/admin/services/agent_share_service.py`
- Create: `backend/tests/test_agent_share_service.py`

- [ ] Write tests for target name collision, successful copy, self-share failure, per-target failure isolation, and audit record creation.
- [ ] Run `uv run pytest tests/test_agent_share_service.py -q` from `backend`; expect import or missing implementation failures.
- [ ] Add `AgentShareRecord` model and Alembic migration.
- [ ] Add `agent_share_service.share_agent_to_users`.
- [ ] Re-run `uv run pytest tests/test_agent_share_service.py -q`; expect pass.

### Task 2: Workspace Share API

**Files:**
- Modify: `backend/app/gateway/routers/agents.py`
- Add tests to existing or new backend gateway API test file.

- [ ] Add `AgentShareRequest`, `AgentShareResult`, and `AgentShareResponse` schemas.
- [ ] Add `POST /api/agents/{name}/share`.
- [ ] Require agents API enabled.
- [ ] Resolve current user via existing auth context and reject sharing non-owned agents.
- [ ] Delegate copy/audit behavior to `agent_share_service`.
- [ ] Run targeted backend tests.

### Task 3: Admin Share Records API

**Files:**
- Create: `backend/app/admin/routers/agent_share_records.py`
- Modify: `backend/app/gateway/app.py`
- Add backend API tests.

- [ ] Add read-only paginated endpoint `GET /api/admin/agent-share-records`.
- [ ] Support filters for source owner, target user, source agent, target agent, status, and created time range.
- [ ] Include source/target username/display name fields.
- [ ] Mount router in gateway app.
- [ ] Run targeted backend tests.

### Task 4: Workspace Share UI

**Files:**
- Modify: `frontend/src/core/agents/types.ts`
- Modify: `frontend/src/core/agents/api.ts`
- Modify: `frontend/src/core/agents/hooks.ts`
- Create: `frontend/src/components/workspace/agents/agent-share-dialog.tsx`
- Modify: `frontend/src/components/workspace/agents/agent-card.tsx`
- Modify i18n locale files as needed.

- [ ] Add frontend API function for `POST /api/agents/{name}/share`.
- [ ] Add share mutation hook.
- [ ] Build share dialog with user multi-select, explanatory copy, submit, and per-target result display.
- [ ] Add share button to agent cards.
- [ ] Run `pnpm.cmd typecheck`.

### Task 5: Admin Share Records Page

**Files:**
- Add admin API client functions/types.
- Add admin route/page/component.
- Modify admin sidebar/menu routing.

- [ ] Find existing admin page patterns for users/skills/audit pages.
- [ ] Add read-only table page named `智能体分享记录`.
- [ ] Add filters for source user, target user, source agent, target agent, status, and time range where existing UI controls make this practical.
- [ ] Do not add distribute, revoke, delete, or sync actions.
- [ ] Run admin build/typecheck command used by the repo.

### Task 6: Verification

**Files:**
- No new files expected.

- [ ] Run targeted backend tests.
- [ ] Run broader relevant backend tests if time allows.
- [ ] Run `pnpm.cmd typecheck` in `frontend`.
- [ ] Run frontend production build.
- [ ] Run admin build.
- [ ] Report exact commands, pass/fail status, and any residual warnings.
