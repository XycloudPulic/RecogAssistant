# SPDX-License-Identifier: MIT

"""Application service for workflow configuration use-cases."""

from __future__ import annotations

import json

from recognizer.application.errors import NotFoundError
from recognizer.infrastructure.persistence.admin_configuration.repositories.workflow_config_repository import (
    WorkflowConfigRepository,
)
from recognizer.interfaces.api.schemas.config_models import (
    WorkflowIn,
    WorkflowNodeIn,
    WorkflowNodeOut,
    WorkflowOut,
)


class WorkflowConfigService:
    """Workflow CRUD/business orchestration service."""

    def __init__(self, repository: WorkflowConfigRepository | None = None) -> None:
        self._repository = repository or WorkflowConfigRepository()

    def seed_default_workflow_if_needed(self) -> None:
        if self._repository.has_any_workflow():
            return
        wf_id = self._repository.create_workflow(
            "默认流程", "默认识别调度：按节点顺序执行启用节点", True
        )
        # First workflow is the default workflow by definition.
        try:
            self._repository.set_default_workflow(int(wf_id))
        except Exception:
            # Best-effort: default flag is optional for older DBs.
            pass
        for node in self._repository.list_enabled_nodes():
            if int(node.get("enabled") or 0) != 1:
                continue
            self._repository.create_workflow_node(
                workflow_id=wf_id,
                node_id=int(node["id"]),
                enabled=True,
                order_index=int(node.get("order_index") or 100),
                config_override_json="{}",
            )

    def ensure_default_workflow_if_missing(self) -> None:
        """If workflows exist but none is marked default, pick the newest active one."""
        try:
            current = self._repository.get_default_workflow_id(active_only=True)
        except Exception:
            current = None
        if current is not None:
            return
        rows = self._repository.list_workflows(active_only=True)
        if not rows:
            return
        wf_id = int(rows[0]["id"])
        try:
            self._repository.set_default_workflow(wf_id)
        except Exception:
            pass

    def list_workflows(self, *, active_only: bool) -> list[WorkflowOut]:
        rows = self._repository.list_workflows(active_only=active_only)
        out: list[WorkflowOut] = []
        for row in rows:
            row["is_active"] = bool(row["is_active"])
            row["is_default"] = bool(row.get("is_default", 0))
            out.append(WorkflowOut(**row))
        return out

    def create_workflow(self, payload: WorkflowIn) -> WorkflowOut:
        try:
            workflow_id = self._repository.create_workflow(
                payload.name, payload.description, payload.is_active
            )
        except Exception as exc:
            if not self._repository.is_unique_conflict(exc):
                raise
            workflow_id = self._repository.get_workflow_id_by_name(payload.name)
            if workflow_id is None:
                raise
            self._repository.update_workflow(
                workflow_id,
                name=payload.name,
                description=payload.description,
                is_active=payload.is_active,
            )
        row = self._repository.get_workflow_by_id(workflow_id)
        if not row:
            raise NotFoundError("workflow not found")
        row["is_active"] = bool(row["is_active"])
        row["is_default"] = bool(row.get("is_default", 0))
        return WorkflowOut(**row)

    def update_workflow(self, workflow_id: int, payload: WorkflowIn) -> WorkflowOut:
        updated = self._repository.update_workflow(
            workflow_id,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
        )
        if updated <= 0:
            raise NotFoundError("workflow not found")
        row = self._repository.get_workflow_by_id(workflow_id)
        if not row:
            raise NotFoundError("workflow not found")
        row["is_active"] = bool(row["is_active"])
        row["is_default"] = bool(row.get("is_default", 0))
        return WorkflowOut(**row)

    def set_default_workflow(self, workflow_id: int) -> dict:
        row = self._repository.get_workflow_by_id(workflow_id)
        if not row:
            raise NotFoundError("workflow not found")
        self._repository.set_default_workflow(int(workflow_id))
        return {"ok": True, "default_workflow_id": int(workflow_id)}

    def get_default_workflow_id(self, *, active_only: bool = True) -> int | None:
        return self._repository.get_default_workflow_id(active_only=active_only)

    def delete_workflow(self, workflow_id: int) -> dict:
        deleted = self._repository.hard_delete_workflow(workflow_id)
        if deleted <= 0:
            raise NotFoundError("workflow not found")
        return {"ok": True}

    def list_workflow_nodes(self, workflow_id: int) -> list[WorkflowNodeOut]:
        rows = self._repository.list_workflow_nodes(workflow_id)
        out: list[WorkflowNodeOut] = []
        for row in rows:
            row["enabled"] = bool(row["enabled"])
            try:
                row["config_override_json"] = json.loads(
                    row.get("config_override_json") or "{}"
                )
            except Exception:
                row["config_override_json"] = {}
            out.append(WorkflowNodeOut(**row))
        return out

    def replace_workflow_nodes(
        self, workflow_id: int, payload: list[WorkflowNodeIn]
    ) -> dict:
        row = self._repository.get_workflow_by_id(workflow_id)
        if not row:
            raise NotFoundError("workflow not found")
        items = [
            {
                "node_id": int(n.node_id),
                "enabled": bool(n.enabled),
                "order_index": int(n.order_index),
                "config_override_json": json.dumps(
                    n.config_override_json, ensure_ascii=False
                ),
            }
            for n in payload
        ]
        self._repository.replace_workflow_nodes(workflow_id, items)
        return {"ok": True}
