"""REST API for scheduled tasks."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.admin.deps import get_current_user, get_db
from app.admin.models.user import User
from app.admin.services import scheduler_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class TaskCreateRequest(BaseModel):
    agent_description: str = Field(default="", description="Agent description")
    agent_soul: str = Field(default="", description="Agent soul content")
    skill_name: str = Field(..., description="Skill to execute")
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    custom_variables: dict | None = Field(default=None, description="Custom variables")


class TaskUpdateRequest(BaseModel):
    agent_description: str | None = Field(default=None, description="Agent description")
    agent_soul: str | None = Field(default=None, description="Agent soul content")
    skill_name: str | None = Field(default=None, description="Skill to execute")
    cron_expression: str | None = Field(default=None, description="Cron expression")
    custom_variables: dict | None = Field(default=None, description="Custom variables")


class TaskResponse(BaseModel):
    id: str
    agent_name: str
    agent_description: str
    agent_soul: str
    skill_name: str
    cron_expression: str
    custom_variables: dict | None
    is_enabled: bool
    status: str
    last_execution_at: str | None
    next_execution_at: str | None
    error_message: str | None


class ExecutionResponse(BaseModel):
    id: str
    task_id: str
    status: str
    triggered_at: str
    completed_at: str | None
    thread_id: str | None
    messages: list | None
    error_message: str | None
    token_usage: dict | None


def _task_to_response(task) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        agent_name=task.agent_name,
        agent_description=task.agent_description,
        agent_soul=task.agent_soul,
        skill_name=task.skill_name,
        cron_expression=task.cron_expression,
        custom_variables=task.custom_variables,
        is_enabled=task.is_enabled,
        status=task.status.value if hasattr(task.status, "value") else task.status,
        last_execution_at=task.last_execution_at,
        next_execution_at=task.next_execution_at,
        error_message=task.error_message,
    )


def _exec_to_response(exec_obj) -> ExecutionResponse:
    return ExecutionResponse(
        id=str(exec_obj.id),
        task_id=str(exec_obj.task_id),
        status=exec_obj.status.value if hasattr(exec_obj.status, "value") else exec_obj.status,
        triggered_at=exec_obj.triggered_at,
        completed_at=exec_obj.completed_at,
        thread_id=exec_obj.thread_id,
        messages=exec_obj.messages,
        error_message=exec_obj.error_message,
        token_usage=exec_obj.token_usage,
    )


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    tasks = await scheduler_service.list_tasks(db, user.id)
    return [_task_to_response(t) for t in tasks]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    request: TaskCreateRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        task = await scheduler_service.create_task(
            db,
            user.id,
            agent_description=request.agent_description,
            agent_soul=request.agent_soul,
            skill_name=request.skill_name,
            cron_expression=request.cron_expression,
            custom_variables=request.custom_variables,
        )
        return _task_to_response(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        task = await scheduler_service.get_task(db, uuid.UUID(task_id), user.id)
        return _task_to_response(task)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        task = await scheduler_service.update_task(
            db,
            uuid.UUID(task_id),
            user.id,
            **request.model_dump(exclude_none=True),
        )
        return _task_to_response(task)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        await scheduler_service.delete_task(db, uuid.UUID(task_id), user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/toggle", response_model=TaskResponse)
async def toggle_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        task = await scheduler_service.toggle_task(db, uuid.UUID(task_id), user.id)
        return _task_to_response(task)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/trigger", response_model=ExecutionResponse)
async def trigger_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        execution = await scheduler_service.trigger_task(db, uuid.UUID(task_id), user.id)
        return _exec_to_response(execution)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/tasks/{task_id}/executions", response_model=list[ExecutionResponse])
async def list_executions(
    task_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        executions = await scheduler_service.list_executions(db, uuid.UUID(task_id), user.id, limit=limit, offset=offset)
        return [_exec_to_response(e) for e in executions]
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/tasks/{task_id}/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    task_id: str,
    execution_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        execution = await scheduler_service.get_execution(db, uuid.UUID(execution_id), user.id)
        return _exec_to_response(execution)
    except ValueError:
        raise HTTPException(status_code=404, detail="Execution not found")
