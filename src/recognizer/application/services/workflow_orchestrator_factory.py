# SPDX-License-Identifier: MIT

"""Application service that builds runtime orchestrator from workflow config."""

from __future__ import annotations

import json

from recognizer.application.errors import NotFoundError
from recognizer.application.workflows.recognition_orchestrator import (
    RecognitionOrchestrator,
)
from recognizer.infrastructure.persistence.admin_configuration.repositories.workflow_repository import (
    WorkflowRepository,
)


class WorkflowOrchestratorFactory:
    """Build a RecognitionOrchestrator instance from workflow configuration."""

    def __init__(self, repository: WorkflowRepository | None = None) -> None:
        self._repository = repository or WorkflowRepository()

    def create(self, workflow_id: int) -> RecognitionOrchestrator:
        """Create orchestrator using workflow node composition from DB."""
        if not self._repository.exists_active_workflow(workflow_id):
            raise NotFoundError("workflow not found")

        rows = self._repository.list_enabled_nodes_for_workflow(workflow_id)
        node_configs: list[dict] = []
        for row in rows:
            base_cfg = self._safe_json_loads(row.get("config_json"))
            override_cfg = self._safe_json_loads(row.get("config_override_json"))
            node_configs.append(
                {
                    "name": row.get("node_name"),
                    "module": override_cfg.get("module") or base_cfg.get("module"),
                    "class": override_cfg.get("class") or base_cfg.get("class"),
                    "order": int(
                        row.get("order_index") or row.get("node_order") or 100
                    ),
                    "enabled": True,
                }
            )

        return RecognitionOrchestrator(
            config={
                "nodes": node_configs,
                "parallel": False,
                "extraction": {"enabled": True},
                # IMPORTANT: keep workflow composition authoritative
                "auto_reload_nodes": False,
                "use_config_db_nodes": False,
            }
        )

    def create_default(self) -> RecognitionOrchestrator | None:
        """Create orchestrator using the active default workflow if set."""
        default_id = self._repository.get_default_workflow_id()
        if default_id is None:
            return None
        return self.create(int(default_id))

    def get_default_workflow_id(self) -> int | None:
        return self._repository.get_default_workflow_id()

    @staticmethod
    def _safe_json_loads(raw: str | None) -> dict:
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}
