# SPDX-License-Identifier: MIT

"""Repository for workflow runtime loading from config DB."""

from __future__ import annotations

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class WorkflowRepository:
    """Read workflow and workflow-node composition from config DB."""

    def __init__(self) -> None:
        init_config_db()

    def exists_active_workflow(self, workflow_id: int) -> bool:
        """Return True when workflow exists and is active."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM workflows WHERE id=? AND is_active=1",
                (int(workflow_id),),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def get_default_workflow_id(self) -> int | None:
        """Return the active default workflow id if set."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM workflows WHERE is_default=1 AND is_active=1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def list_enabled_nodes_for_workflow(self, workflow_id: int) -> list[dict]:
        """Return enabled workflow node rows joined with node base config."""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT wn.*, n.node_name, n.node_type, n.order_index as node_order, n.config_json "
                "FROM workflow_nodes wn JOIN nodes n ON wn.node_id=n.id "
                # IMPORTANT: A node disabled in global Node Config must never run,
                # even if it was previously added into a workflow composition.
                "WHERE wn.workflow_id=? AND wn.enabled=1 AND n.enabled=1 "
                "ORDER BY wn.order_index ASC",
                (int(workflow_id),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
