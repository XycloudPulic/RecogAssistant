# SPDX-License-Identifier: MIT

"""Node config CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter

from recognizer.application.services.node_config_service import NodeConfigService
from recognizer.interfaces.api.schemas.config_models import NodeConfigIn, NodeConfigOut

router = APIRouter(prefix="/nodes", tags=["nodes"])
node_service = NodeConfigService()


@router.on_event("startup")
def _startup() -> None:
    node_service.bootstrap_nodes()


@router.get("", response_model=list[NodeConfigOut])
def list_nodes() -> list[NodeConfigOut]:
    return node_service.list_nodes()


@router.post("", response_model=NodeConfigOut)
def create_node(payload: NodeConfigIn) -> NodeConfigOut:
    return node_service.create_node(payload)


@router.put("/{node_id}", response_model=NodeConfigOut)
def update_node(node_id: int, payload: NodeConfigIn) -> NodeConfigOut:
    return node_service.update_node(node_id, payload)


@router.delete("/{node_id}")
def delete_node(node_id: int) -> dict:
    return node_service.delete_node(node_id)
