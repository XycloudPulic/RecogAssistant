# SPDX-License-Identifier: MIT

"""Application service for node config use-cases."""

from __future__ import annotations

from recognizer.application.errors import NotFoundError, ValidationError
from recognizer.infrastructure.persistence.admin_configuration.node_autoregister import (
    auto_register_nodes,
)
from recognizer.infrastructure.persistence.admin_configuration.repositories.node_config_repository import (
    NodeConfigRepository,
)
from recognizer.interfaces.api.schemas.config_models import NodeConfigIn, NodeConfigOut


class NodeConfigService:
    """Node CRUD/business orchestration service."""

    def __init__(self, repository: NodeConfigRepository | None = None) -> None:
        self._repository = repository or NodeConfigRepository()

    def bootstrap_nodes(self) -> None:
        # Auto-register node classes into config DB (OCP).
        try:
            auto_register_nodes()
        except Exception:
            import logging

            logging.getLogger(__name__).exception("node auto-registration failed")

        self._seed_default_nodes()

    def _seed_default_nodes(self) -> None:
        if self._repository.get_node_id_by_name("paddle_ocr") is None:
            self._repository.create_node(
                {
                    "node_name": "paddle_ocr",
                    "display_name": "Paddle OCR",
                    "description": "Default OCR node (PaddleOCR).",
                    "node_type": "ocr",
                    "enabled": True,
                    "order_index": 10,
                    "template_id": None,
                    "ruleset_id": None,
                    "llm_config_id": None,
                    "config_json": {
                        "module": "recognizer.domain.recognition.nodes.paddle_node",
                        "class": "PaddleRecognitionNode",
                        "engine": "paddleocr",
                    },
                }
            )

        if self._repository.get_node_id_by_name("llm_recognition") is None:
            self._repository.create_node(
                {
                    "node_name": "llm_recognition",
                    "display_name": "LLM Recognition",
                    "description": "Optional LLM node (disabled by default).",
                    "node_type": "llm",
                    "enabled": False,
                    "order_index": 20,
                    "template_id": None,
                    "ruleset_id": None,
                    "llm_config_id": None,
                    "config_json": {
                        "module": "recognizer.domain.recognition.nodes.llm_node",
                        "class": "LLMRecognitionNode",
                        "engine": "llm",
                    },
                }
            )

    @staticmethod
    def _validate_payload(payload: NodeConfigIn) -> None:
        if payload.node_type not in {"ocr", "llm"}:
            raise ValidationError("node_type must be 'ocr' or 'llm'")
        if payload.node_type == "llm" and not payload.llm_config_id:
            raise ValidationError("LLM node requires llm_config_id")

    @staticmethod
    def _to_out(row: dict) -> NodeConfigOut:
        row["enabled"] = bool(row["enabled"])
        # Pydantic will validate config_json as dict; repository stores JSON string already parsed in routes before.
        return NodeConfigOut(**row)

    def list_nodes(self) -> list[NodeConfigOut]:
        rows = self._repository.list_nodes()
        out: list[NodeConfigOut] = []
        import json

        for row in rows:
            try:
                row["config_json"] = json.loads(row.get("config_json") or "{}")
            except Exception:
                row["config_json"] = {}
            out.append(self._to_out(row))
        return out

    def create_node(self, payload: NodeConfigIn) -> NodeConfigOut:
        self._validate_payload(payload)
        node_id = self._repository.create_node(payload.model_dump())
        row = self._repository.get_node_by_id(node_id)
        if not row:
            raise NotFoundError("Node not found")
        import json

        row["config_json"] = json.loads(row.get("config_json") or "{}")
        return self._to_out(row)

    def update_node(self, node_id: int, payload: NodeConfigIn) -> NodeConfigOut:
        self._validate_payload(payload)
        updated = self._repository.update_node(node_id, payload.model_dump())
        if updated <= 0:
            raise NotFoundError("Node not found")
        row = self._repository.get_node_by_id(node_id)
        if not row:
            raise NotFoundError("Node not found")
        import json

        row["config_json"] = json.loads(row.get("config_json") or "{}")
        return self._to_out(row)

    def delete_node(self, node_id: int) -> dict:
        deleted = self._repository.delete_node(node_id)
        if deleted <= 0:
            raise NotFoundError("Node not found")
        return {"ok": True}
