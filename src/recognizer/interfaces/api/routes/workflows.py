# SPDX-License-Identifier: MIT

"""Workflow (node composition) CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter

from recognizer.application.services.workflow_config_service import (
    WorkflowConfigService,
)
from recognizer.interfaces.api.schemas.config_models import (
    WorkflowIn,
    WorkflowNodeIn,
    WorkflowNodeOut,
    WorkflowOut,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])
workflow_service = WorkflowConfigService()


@router.on_event("startup")
def _startup() -> None:
    workflow_service.seed_default_workflow_if_needed()
    workflow_service.ensure_default_workflow_if_missing()


@router.get("", response_model=list[WorkflowOut])
def list_workflows(active_only: bool = True) -> list[WorkflowOut]:
    return workflow_service.list_workflows(active_only=active_only)


@router.post("", response_model=WorkflowOut)
def create_workflow(payload: WorkflowIn) -> WorkflowOut:
    return workflow_service.create_workflow(payload)


@router.put("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(workflow_id: int, payload: WorkflowIn) -> WorkflowOut:
    return workflow_service.update_workflow(workflow_id, payload)


@router.put("/{workflow_id}/default")
def set_default_workflow(workflow_id: int) -> dict:
    """Set one workflow as the default workflow (unset others)."""
    return workflow_service.set_default_workflow(workflow_id)


@router.get("/default")
def get_default_workflow() -> dict:
    """Get current default workflow id (active)."""
    return {
        "default_workflow_id": workflow_service.get_default_workflow_id(
            active_only=True
        )
    }


@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: int) -> dict:
    return workflow_service.delete_workflow(workflow_id)


@router.get("/{workflow_id}/nodes", response_model=list[WorkflowNodeOut])
def list_workflow_nodes(workflow_id: int) -> list[WorkflowNodeOut]:
    return workflow_service.list_workflow_nodes(workflow_id)


@router.put("/{workflow_id}/nodes")
def replace_workflow_nodes(workflow_id: int, payload: list[WorkflowNodeIn]) -> dict:
    return workflow_service.replace_workflow_nodes(workflow_id, payload)
