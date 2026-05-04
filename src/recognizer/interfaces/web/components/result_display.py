# SPDX-License-Identifier: MIT

"""结果展示组件（与具体票据类型解耦）。

`common_result` 现在是动态 dict，schema 由命中模板的字段决定。
本组件优先使用 `data.debug.template_ctx.fields` 来排序与显示标签，
缺省时直接展示 dict 的 key/value。
"""

import json
from typing import Any, Dict, List, Optional

import streamlit as st


def _template_ctx(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    data = result.get("data") if isinstance(result.get("data"), dict) else None
    if not isinstance(data, dict):
        return None
    debug = data.get("debug") if isinstance(data.get("debug"), dict) else None
    if not isinstance(debug, dict):
        return None
    ctx = debug.get("template_ctx")
    return ctx if isinstance(ctx, dict) else None


def _ordered_fields(
    common_result: Dict[str, Any], template_ctx: Optional[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Return [{key, label}, ...] in display order."""
    fields: List[Dict[str, str]] = []
    if template_ctx and isinstance(template_ctx.get("fields"), list):
        for f in template_ctx["fields"] or []:
            key = str((f or {}).get("field_name") or "")
            if not key:
                continue
            label = str((f or {}).get("field_label") or key)
            fields.append({"key": key, "label": label})
    if fields:
        return fields
    for key, _ in (common_result or {}).items():
        if key == "extra_fields":
            continue
        fields.append({"key": str(key), "label": str(key)})
    return fields


def display_invoice_result(result: Optional[Dict[str, Any]]) -> None:
    """显示识别结果（兼容旧函数名；现已通用化）。

    - 字段显示按命中模板的 fields；
    - 一致性结果按 verify_result 渲染指标；
    - 引擎原始结果展示在折叠面板中。
    """
    if not result:
        st.info("暂无识别结果")
        return

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    template_ctx = _template_ctx(result)

    common_result = (
        data.get("common_result") if isinstance(data.get("common_result"), dict) else {}
    )
    if common_result:
        st.markdown("### 识别结果")
        rows: List[tuple] = []
        for f in _ordered_fields(common_result, template_ctx):
            value = common_result.get(f["key"], "")
            if value is None:
                value = ""
            rows.append((f["label"], value))

        rendered = False
        for label, value in rows:
            if value == "":
                continue
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"**{label}:**")
            with col2:
                st.write(value)
            rendered = True
        if not rendered:
            st.warning("未能提取到任何字段")

    verify_result = (
        data.get("verify_result") if isinstance(data.get("verify_result"), dict) else {}
    )
    if verify_result:
        st.markdown("### 一致性验证")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总字段数", verify_result.get("total_fields", 0))
        with col2:
            st.metric("一致字段", verify_result.get("consistent_fields", 0))
        with col3:
            st.metric("不一致字段", verify_result.get("inconsistent_fields", 0))

        is_consistent = verify_result.get("is_consistent", False)
        if is_consistent:
            st.success("所有字段一致")
        else:
            st.warning("存在不一致字段")

    engine_results = data.get("engine_results") or []
    if engine_results:
        with st.expander("查看各引擎解析结果"):
            for i, engine_result in enumerate(engine_results):
                st.markdown(
                    f"**引擎 {i + 1}: {engine_result.get('engine', 'unknown')}_{engine_result.get('parser', 'unknown')}**"
                )
                st.json(engine_result.get("result", {}))
                cost_time = engine_result.get("cost_time")
                if cost_time:
                    st.caption(f"耗时: {cost_time}ms")


def display_json_result(result: Optional[Dict[str, Any]]) -> None:
    """以JSON格式显示结果。"""
    if not result:
        st.info("暂无数据")
        return
    st.json(result)


def display_raw_response(result: Optional[Dict[str, Any]]) -> None:
    """显示原始响应。"""
    if not result:
        st.info("暂无数据")
        return
    st.markdown("### 原始响应")
    st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")
