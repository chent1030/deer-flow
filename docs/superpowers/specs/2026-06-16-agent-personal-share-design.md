# Agent Personal Share Design

## Goal

Add personal agent sharing for the workspace. A user can share one of their agents with selected users. Sharing creates an independent copy for each recipient. After the copy is created, edits by either side do not affect the other side.

The admin panel only shows an audit page for share records. Admins do not distribute agents, revoke shares, or synchronize copies.

## Scope

Included:

- Share an existing custom agent to one or more individual users.
- Copy the agent into each recipient's user-scoped agent directory.
- Auto-generate a non-conflicting target agent name if the recipient already has an agent with the same name.
- Record each attempted share in an audit table.
- Add a workspace share dialog on agent cards.
- Add a read-only admin page for agent share records.

Excluded:

- Department sharing.
- Persistent shared access permissions.
- Collaborative editing of one shared agent.
- Revoking a share after the copy is created.
- Synchronizing future changes from source to copies.
- Copying chat history, memory, scheduled tasks, or execution history.
- Admin-initiated distribution.

## Behavior

Sharing is a copy operation, not an authorization operation.

When user A shares `sales-agent` with user B:

- The backend reads A's `sales-agent` files.
- The backend creates a new agent directory under B's user-scoped agent directory.
- The copied agent becomes B's own agent.
- B can edit, delete, use, and later share the copied agent.
- A's original agent is unchanged.
- Later edits to A's original do not update B's copy.
- Later edits to B's copy do not update A's original.

## Copied Data

Copy:

- `config.yaml`
- `SOUL.md`
- Description
- Model override
- Tool group whitelist
- Skill whitelist
- Any other files required for the custom agent definition inside the agent directory

Do not copy:

- Chat threads
- Messages
- User memory
- Scheduled tasks
- Scheduled task executions
- Share records from the source

## Name Collision

If the recipient already has the same agent name, generate a copy name:

- `sales-agent`
- `sales-agent-copy`
- `sales-agent-copy-2`
- `sales-agent-copy-3`

The response and audit record must store the actual target agent name.

## Data Model

Add `agent_share_records`.

Fields:

- `id`: UUID primary key
- `source_owner_id`: UUID, user who initiated sharing
- `source_agent_name`: string
- `target_user_id`: UUID
- `target_agent_name`: string nullable when failed before target name generation
- `status`: enum/string, `created` or `failed`
- `error_message`: text nullable
- `created_at`: timestamp

This table is for audit only. It does not grant access.

## Workspace API

Add:

```text
POST /api/agents/{name}/share
```

Request:

```json
{
  "user_ids": ["..."]
}
```

Response:

```json
{
  "results": [
    {
      "target_user_id": "...",
      "target_username": "zhangsan",
      "target_agent_name": "sales-agent-copy",
      "status": "created",
      "error_message": null
    }
  ]
}
```

Rules:

- Only the current user's own agent can be shared.
- The source agent must exist in the current user's user-scoped agent directory.
- Sharing to self should be rejected with a per-target failure.
- Missing, disabled, or invalid target users should be returned as per-target failures.
- One failed recipient must not prevent other recipients from receiving their copies.
- Each target result must be recorded in `agent_share_records`.

## Admin API

Add a read-only endpoint under the admin API, for example:

```text
GET /api/admin/agent-share-records
```

Filters:

- `source_owner_id`
- `target_user_id`
- `source_agent_name`
- `target_agent_name`
- `status`
- `created_from`
- `created_to`
- `page`
- `page_size`

Response includes source user display fields and target user display fields where available.

## Workspace UI

Add a share action on each agent card.

Dialog:

- Search/select one or more users.
- Show fixed explanatory text: sharing creates independent copies and later edits do not sync.
- Submit to `POST /api/agents/{name}/share`.
- Show per-user results after completion.

The dialog should not include departments or permission levels.

## Admin UI

Add a read-only page named `Agent Share Records`. The localized Chinese UI label should be `智能体分享记录`.

Columns:

- Share time
- Source user
- Source agent name
- Target user
- Target agent name
- Status
- Error message

Filters:

- Source user
- Target user
- Source agent name
- Target agent name
- Status
- Time range

No actions:

- No distribute button
- No revoke button
- No delete copied agent button
- No sync/update button

## Implementation Notes

The current agent system is filesystem-backed and user-scoped. The share service should reuse the existing path helpers instead of introducing a second storage location.

The copy should run through a small service function so the API route, audit writes, collision handling, and tests all use one implementation.

Use transactional audit writes where practical, but do not roll back a successfully copied recipient because another recipient failed.

## Verification

Backend:

- Unit test name collision generation.
- Unit test sharing to one valid user.
- Unit test sharing to multiple users where one fails and others succeed.
- Unit test self-share failure.
- Unit test share record creation for success and failure.

Frontend:

- Typecheck.
- Build.
- Share dialog can select users and display per-recipient results.

Manual:

- Create an agent as user A.
- Share to user B.
- Log in as B and verify copied agent appears.
- Edit B's copy and verify A's original is unchanged.
- Verify admin share record appears.
