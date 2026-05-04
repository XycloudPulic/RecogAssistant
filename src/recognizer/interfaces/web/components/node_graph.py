# SPDX-License-Identifier: MIT

"""Node flow UI for recognition pipeline (Streamlit).

This component renders a horizontal node flow. Users can click a node to inspect
its details (status, timing, input/output payloads).
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st


class NodeInfo:
    """节点信息"""

    def __init__(
        self,
        name: str,
        status: str = "pending",  # pending, running, success, failed
        engine: Optional[str] = None,
        node_type: Optional[str] = None,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        business_data: Optional[Any] = None,
        business_template_ctx: Optional[Any] = None,
        cost_time: Optional[int] = None,
        error: Optional[str] = None,
    ):
        self.name = name
        self.status = status
        self.engine = engine
        self.node_type = node_type
        self.input_data = input_data
        self.output_data = output_data
        self.business_data = business_data
        self.business_template_ctx = business_template_ctx
        self.cost_time = cost_time
        self.error = error


def render_node_flow(nodes: list[NodeInfo], key: str) -> None:
    """Render clickable node flow and a detail panel.

    `key` is used to namespace Streamlit widget keys for multi-image flows.
    """
    if not nodes:
        st.info("暂无节点数据")
        return

    status_badge = {
        "pending": "⏳ pending",
        "running": "▶ running",
        "success": "✅ success",
        "failed": "❌ failed",
    }

    selected_key = f"{key}__selected_node_idx"
    if selected_key not in st.session_state:
        st.session_state[selected_key] = 0

    cols = st.columns(len(nodes))
    for i, (node, col) in enumerate(zip(nodes, cols)):
        with col:
            label = node.name
            if node.engine:
                label = f"{label}\n({node.engine})"

            if st.button(label, key=f"{key}__node_btn_{i}", use_container_width=True):
                st.session_state[selected_key] = i

            st.caption(status_badge.get(node.status, node.status))
            if node.cost_time is not None:
                st.caption(f"{node.cost_time} ms")

            if i < len(nodes) - 1:
                st.markdown("**→**")

    idx = int(st.session_state[selected_key])
    idx = max(0, min(idx, len(nodes) - 1))
    node = nodes[idx]

    st.markdown("---")
    st.markdown("### 节点详情")

    meta_cols = st.columns(4)
    meta_cols[0].metric("名称", node.name)
    meta_cols[1].metric("状态", node.status)
    meta_cols[2].metric("类型", node.node_type or "-")
    meta_cols[3].metric("耗时(ms)", node.cost_time if node.cost_time is not None else 0)

    if node.error:
        st.error(node.error)

    tab_in, tab_out = st.tabs(["输入", "输出"])
    with tab_in:
        if node.input_data is None:
            st.info("无输入信息")
        else:
            if isinstance(node.input_data, str) and len(node.input_data) > 2000:
                st.text_area("input (truncated)", node.input_data, height=200)
            else:
                st.json(node.input_data)
    with tab_out:
        if node.output_data is None:
            st.info("无输出信息")
        else:
            st.json(node.output_data)


def render_node_row(nodes: list[NodeInfo], key: str) -> tuple[int, bool]:
    """Render a compact row of node buttons.

    Returns (selected_node_index, clicked_now).
    """
    if not nodes:
        st.caption("无节点")
        return 0, False

    status_badge = {
        "pending": "⏳",
        "running": "▶",
        "success": "✅",
        "failed": "❌",
    }

    selected_key = f"{key}__selected_node_idx"
    if selected_key not in st.session_state:
        st.session_state[selected_key] = 0

    clicked = False
    cols = st.columns(len(nodes))
    for i, (node, col) in enumerate(zip(nodes, cols)):
        with col:
            badge = status_badge.get(node.status, "")
            parts = [f"{badge} {node.name}"]
            meta = []
            if node.node_type:
                meta.append(str(node.node_type))
            if node.cost_time is not None:
                meta.append(f"{node.cost_time}ms")
            if meta:
                parts.append(" ".join(meta))
            label = "\n".join(parts)
            if st.button(label, key=f"{key}__row_btn_{i}", use_container_width=True):
                st.session_state[selected_key] = i
                clicked = True
            # cost_time already shown on button label for quick scanning

    idx = int(st.session_state[selected_key])
    return max(0, min(idx, len(nodes) - 1)), clicked


def parse_result_to_nodes(result: dict) -> list[NodeInfo]:
    """从API结果解析节点信息

    Args:
        result: API响应数据

    Returns:
        节点信息列表
    """
    nodes: list[NodeInfo] = []

    data = result.get("data", {}) if result else {}
    debug_nodes = (data.get("debug") or {}).get("nodes", [])
    template_ctx = (
        (data.get("debug") or {}).get("template_ctx")
        if isinstance(data.get("debug"), dict)
        else None
    )

    # Prefer debug-provided node timeline when available (more detailed).
    if debug_nodes:
        for dn in debug_nodes:
            nodes.append(
                NodeInfo(
                    name=dn.get("node_name") or dn.get("engine", "node"),
                    status=dn.get("status", "pending"),
                    engine=dn.get("engine"),
                    node_type=dn.get("node_type"),
                    input_data=None,  # input image is shown from file, not Base64 text
                    output_data=dn.get("output_json"),
                    business_data=dn.get("business_result"),
                    business_template_ctx=dn.get("business_template_ctx"),
                    cost_time=dn.get("cost_time"),
                    error=dn.get("error"),
                )
            )
    else:
        # Fallback: engine_results only (no debug timeline)
        engine_results = data.get("engine_results", [])
        for engine_result in engine_results:
            engine_dict = (
                engine_result.get("result", {})
                if isinstance(engine_result, dict)
                else {}
            )
            nodes.append(
                NodeInfo(
                    name=f"{engine_result.get('engine', 'ocr')}_{engine_result.get('parser', 'parser')}",
                    status="success" if engine_dict else "failed",
                    engine=engine_result.get("engine"),
                    node_type="engine",
                    # Raw output is only available when backend returns debug payload.
                    output_data=None,
                    # Show extracted business fields (engine_results[].result) in the "业务" tab.
                    business_data=engine_dict,
                    cost_time=engine_result.get("cost_time"),
                )
            )

    # Always append validation + summary when present in response data.
    common_result = data.get("common_result")
    verify_result = data.get("verify_result")
    validation_result = data.get("validation_result")

    if validation_result is not None:
        is_valid = bool((validation_result or {}).get("is_valid", True))
        nodes.append(
            NodeInfo(
                name="validation",
                status="success" if is_valid else "failed",
                engine="validators",
                node_type="validation",
                input_data=None,
                output_data={"validation_result": validation_result},
                cost_time=None,
                error=None,
            )
        )

    if (
        common_result is not None
        or verify_result is not None
        or validation_result is not None
    ):
        # Keep historical naming:
        # - with debug timeline: show `summary`
        # - without debug timeline: show `merge_result`
        summary_name = "summary" if debug_nodes else "merge_result"
        nodes.append(
            NodeInfo(
                name=summary_name,
                status="success" if common_result else "failed",
                engine="merge",
                node_type="summary",
                input_data=None,
                output_data={
                    "template_ctx": template_ctx,
                    "common_result": common_result,
                    "verify_result": verify_result,
                    "validation_result": validation_result,
                },
                cost_time=None,
                error=None,
            )
        )

    return nodes


def create_default_nodes() -> list[NodeInfo]:
    """创建默认节点列表"""
    return [
        NodeInfo(
            name="paddle_ocr", status="pending", node_type="ocr", engine="paddleocr"
        ),
        NodeInfo(name="merge_result", status="pending"),
    ]
