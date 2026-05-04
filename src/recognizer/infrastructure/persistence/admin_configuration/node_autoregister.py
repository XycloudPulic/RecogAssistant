# SPDX-License-Identifier: MIT

"""Auto-register recognition node classes into config DB.

Goal: when developers add a new node class under `recognizer.domain.recognition.nodes`,
it appears automatically in the Node Config UI without manually inserting DB rows.

This follows OCP:
- new node -> new class -> discovered and upserted
- no changes required in the main registration logic
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import pkgutil
from dataclasses import dataclass
from typing import Any, Optional, Type

from recognizer.domain.recognition.nodes.base_node import BaseRecognitionNode
from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeDescriptor:
    node_name: str
    node_type: str
    engine: str
    order_index: int
    module: str
    class_name: str
    display_name: str
    description: str
    enabled_default: bool


def _safe_str(v: Any) -> str:
    return (v or "").strip()


def _describe_node(
    cls: Type[BaseRecognitionNode], module_name: str
) -> Optional[NodeDescriptor]:
    # Prefer class-level constants to avoid heavy __init__ during discovery.
    node_name = _safe_str(getattr(cls, "NODE_NAME", "")) or _safe_str(
        getattr(cls, "node_name", "")
    )
    node_type = _safe_str(getattr(cls, "NODE_TYPE", "")) or _safe_str(
        getattr(cls, "node_type_name", "")
    )
    engine = _safe_str(getattr(cls, "ENGINE_NAME", "")) or _safe_str(
        getattr(cls, "engine", "")
    )

    # Fallback to instantiation (best-effort) if not provided.
    if not (node_name and node_type and engine):
        try:
            inst = cls()  # type: ignore[call-arg]
            node_name = node_name or _safe_str(getattr(inst, "name", ""))
            node_type = node_type or _safe_str(getattr(inst, "node_type", ""))
            engine = engine or _safe_str(getattr(inst, "engine_name", ""))
        except Exception as e:
            logger.warning(
                "Skip node %s.%s: cannot instantiate (%s)", module_name, cls.__name__, e
            )
            return None

    if not node_name:
        return None

    order_index = int(getattr(cls, "order", 100) or 100)
    enabled_default = node_name in {"paddle_ocr"}
    return NodeDescriptor(
        node_name=node_name,
        node_type=node_type or "ocr",
        engine=engine or "",
        order_index=order_index,
        module=module_name,
        class_name=cls.__name__,
        display_name=cls.__name__,
        description=(inspect.getdoc(cls) or "").strip(),
        enabled_default=enabled_default,
    )


def discover_node_descriptors(
    package: str = "recognizer.domain.recognition.nodes",
) -> list[NodeDescriptor]:
    """Discover node classes in a package."""
    descriptors: list[NodeDescriptor] = []
    pkg = importlib.import_module(package)

    for _, mod_name, is_pkg in pkgutil.walk_packages(pkg.__path__, package + "."):
        if is_pkg:
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            logger.warning("Skip importing %s: %s", mod_name, e)
            continue

        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj is BaseRecognitionNode:
                continue
            if not issubclass(obj, BaseRecognitionNode):
                continue
            desc = _describe_node(obj, mod_name)
            if desc:
                descriptors.append(desc)

    # Unique by node_name (last one wins)
    by_name: dict[str, NodeDescriptor] = {d.node_name: d for d in descriptors}
    return list(by_name.values())


def upsert_nodes(descriptors: list[NodeDescriptor]) -> int:
    """Upsert discovered nodes into config DB. Returns affected count (best-effort)."""
    if not descriptors:
        return 0

    init_config_db()
    conn = get_connection()
    changed = 0
    try:
        for d in descriptors:
            cfg_json = json.dumps(
                {"module": d.module, "class": d.class_name, "engine": d.engine},
                ensure_ascii=False,
            )
            # Insert if missing
            conn.execute(
                """
                INSERT OR IGNORE INTO nodes(
                  node_name, display_name, description, node_type, enabled, order_index,
                  template_id, ruleset_id, llm_config_id, config_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    d.node_name,
                    d.display_name,
                    d.description,
                    d.node_type,
                    1 if d.enabled_default else 0,
                    d.order_index,
                    None,
                    None,
                    None,
                    cfg_json,
                ),
            )
            # Update dynamic fields on every startup (keeps doc/order in sync with code)
            cur = conn.execute(
                """
                UPDATE nodes SET
                  display_name=?,
                  description=?,
                  node_type=?,
                  order_index=?,
                  config_json=?,
                  updated_at=datetime('now')
                WHERE node_name=?
                """,
                (
                    d.display_name,
                    d.description,
                    d.node_type,
                    d.order_index,
                    cfg_json,
                    d.node_name,
                ),
            )
            changed += int(cur.rowcount or 0)
        conn.commit()
    finally:
        conn.close()
    return changed


def auto_register_nodes() -> int:
    """Convenience function for app startup."""
    desc = discover_node_descriptors()
    return upsert_nodes(desc)
