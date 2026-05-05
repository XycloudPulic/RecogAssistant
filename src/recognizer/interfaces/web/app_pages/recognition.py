# SPDX-License-Identifier: MIT

"""发票识别页面"""

import base64
import hashlib
import json
import os

# 导入组件
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.node_graph import (
    NodeInfo,
    create_default_nodes,
    parse_result_to_nodes,
    render_node_row,
)
from utils.api_client import OCRAPIClient

# 页面标题
st.title("📄 发票识别")
st.markdown("上传发票图片进行**识别流程**编排与结果汇总（支持多张图片顺序识别）")

# Make Streamlit dialogs responsive (near fullscreen) for readability.
st.markdown(
    """
<style>
  /* Dialog container */
  div[role="dialog"] {
    width: 96vw !important;
    max-width: 96vw !important;
  }
  /* Dialog body scrolling */
  div[role="dialog"] > div {
    max-height: 92vh !important;
    overflow: auto !important;
  }
</style>
""",
    unsafe_allow_html=True,
)

if "jobs" not in st.session_state:
    st.session_state.jobs = []  # list[dict]
if "active_job_id" not in st.session_state:
    st.session_state.active_job_id = None
if "active_node_idx" not in st.session_state:
    st.session_state.active_node_idx = 0

api_client = OCRAPIClient()


def _kv_table(data_obj):
    """Render dict/list into a simple key-value table for normal users."""
    try:
        import pandas as pd  # type: ignore
    except Exception:
        pd = None  # type: ignore
    if pd is None:
        st.json(data_obj)
        return

    if data_obj is None:
        st.info("无数据")
        return

    if isinstance(data_obj, dict):
        rows = [
            {"字段": str(k), "值": "" if v is None else str(v)}
            for k, v in data_obj.items()
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return
    if isinstance(data_obj, list):
        # If list of dicts, show as table; otherwise fallback to json.
        if data_obj and all(isinstance(x, dict) for x in data_obj):
            st.dataframe(
                pd.DataFrame(data_obj), use_container_width=True, hide_index=True
            )
            return
        st.json(data_obj)
        return
    st.dataframe(
        pd.DataFrame([{"字段": "value", "值": str(data_obj)}]),
        use_container_width=True,
        hide_index=True,
    )


def _raw_json_expander(data_obj, *, title: str = "查看原始 JSON（可选）") -> None:
    with st.expander(title, expanded=False):
        st.code(json.dumps(data_obj, ensure_ascii=False, indent=2), language="json")


def _render_engine_results_full(
    engine_results: list[dict], *, template_ctx: dict | None = None
) -> None:
    """Render engine_results with an overview + full per-engine JSON.

    Column order: template field order (when template_ctx is available),
    otherwise the union of keys in the order they first appear.
    """
    if not engine_results:
        st.info("无引擎结果")
        return

    try:
        import pandas as pd  # type: ignore

        def _cell(v: object) -> object:
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=False)
            return v

        meta_cols = [
            "id",
            "engine",
            "parser",
            "cost_time",
            "is_valid",
            "invalid_fields",
        ]

        # Collect all keys across all engine_result["result"] dicts.
        all_result_keys: list[str] = []
        seen: set[str] = set()
        for e in engine_results:
            res = e.get("result")
            if isinstance(res, dict):
                for k in res.keys():
                    sk = str(k)
                    if sk not in seen:
                        seen.add(sk)
                        all_result_keys.append(sk)

        # Prefer template field order when provided; otherwise keep insertion order.
        template_fields: list[str] = []
        ctx_fields = (
            (template_ctx or {}).get("fields")
            if isinstance(template_ctx, dict)
            else None
        )
        if isinstance(ctx_fields, list):
            for f in ctx_fields:
                k = str((f or {}).get("field_name") or "")
                if k and k not in template_fields:
                    template_fields.append(k)
        ordered_result_keys = [k for k in template_fields if k in seen] + [
            k for k in all_result_keys if k not in template_fields
        ]

        rows: list[dict] = []
        for e in engine_results:
            row: dict[str, object] = {
                "id": e.get("id"),
                "engine": e.get("engine"),
                "parser": e.get("parser"),
                "cost_time": e.get("cost_time"),
            }
            vres = e.get("validation_result") if isinstance(e, dict) else None
            if isinstance(vres, dict):
                row["is_valid"] = bool(vres.get("is_valid", True))
                row["invalid_fields"] = int(vres.get("invalid_fields", 0) or 0)
            else:
                row["is_valid"] = None
                row["invalid_fields"] = None
            res = e.get("result")
            if isinstance(res, dict):
                for k in ordered_result_keys:
                    row[k] = _cell(res.get(k))
            else:
                for k in ordered_result_keys:
                    row[k] = None
            rows.append(row)

        cols = meta_cols + ordered_result_keys
        df = pd.DataFrame(rows)
        df = df[[c for c in cols if c in df.columns]]
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception:
        # If pandas isn't available or fails, we still render full JSON below.
        pass

    st.caption("完整识别结果（按引擎/解析器展开）")
    for i, e in enumerate(engine_results):
        engine = e.get("engine") or "unknown_engine"
        parser = e.get("parser") or "unknown_parser"
        eid = e.get("id") or f"{engine}:{parser}"
        title = f"[{i + 1}] {eid} ({engine}/{parser})"
        with st.expander(title, expanded=False):
            st.caption(f"cost_time: {e.get('cost_time')} ms")
            st.json(e)

    with st.expander("各引擎校验明细（validation_result）", expanded=False):
        for i, e in enumerate(engine_results):
            if not isinstance(e, dict):
                continue
            eid = e.get("id") or f"{e.get('engine')}:{e.get('parser')}"
            vres = e.get("validation_result")
            st.markdown(f"**[{i + 1}] {eid}**")
            if not isinstance(vres, dict) or not vres:
                st.caption("无校验结果")
            else:
                _render_validation_result(vres, template_ctx)


def _friendly_node_error(err: str) -> str:
    """Hide low-level/vendor details and show actionable message."""
    if not err:
        return ""
    s = str(err)
    low = s.lower()

    # OpenAI region limitation / forbidden
    if "unsupported_country_region_territory" in s or (
        "request_forbidden" in low and "region" in low
    ):
        return (
            "该 LLM 节点调用失败：当前 LLM 服务账号/Key **不支持此区域**（403）。\n\n"
            "建议：在“LLM配置”中更换可用的 Key/服务商，或在“节点配置”里先关闭该节点。"
        )

    if "invalid_api_key" in low or "api key" in low and "invalid" in low:
        return (
            "该 LLM 节点调用失败：API Key 无效或未配置。\n\n"
            "建议：在“LLM配置”中检查 Key 是否正确、是否有权限调用视觉模型。"
        )

    if "rate limit" in low or "too many requests" in low:
        return (
            "该 LLM 节点调用失败：请求过于频繁，触发了限流。\n\n"
            "建议：稍后重试，或降低并发/频率。"
        )

    if "timeout" in low:
        return (
            "该节点调用失败：请求超时。\n\n"
            "建议：稍后重试，或在节点配置中提高超时时间（如有）。"
        )

    # Generic fallback (avoid dumping raw dict / stackish text)
    if len(s) > 220:
        s = s[:220] + "..."
    return f"该节点执行失败：{s}"


def _node_business_view(node: NodeInfo, *, template_ctx: dict | None) -> None:
    """Render *this node's* extracted business result (not raw output, not global common_result)."""
    biz = getattr(node, "business_data", None)
    biz_tctx = getattr(node, "business_template_ctx", None) or template_ctx

    if biz is not None:
        st.caption("该节点提取出的业务数据（来自本节点）")
        _render_business_result_table(biz or {}, template_ctx=biz_tctx)
        _raw_json_expander(biz, title="查看本节点业务结果原始 JSON（可选）")
        return

    st.info("该节点未生成可展示的业务结果（可能执行失败或未启用提取）")
    # Optional: raw output for troubleshooting
    out = node.output_data
    if out is not None:
        _raw_json_expander(out, title="查看本节点原始输出 JSON（可选）")


def _value_from_common(common_result: dict, key: str):
    """Read a field from the (now flat) common_result dict.

    Tolerates legacy persisted runs that still carry an `extra_fields` dict.
    """
    if not isinstance(common_result, dict):
        return ""
    if key in common_result:
        return common_result.get(key, "")
    extra = (
        common_result.get("extra_fields")
        if isinstance(common_result.get("extra_fields"), dict)
        else {}
    )
    return (extra or {}).get(key, "")


def _render_business_result_table(
    common_result: dict, *, template_ctx: dict | None = None
) -> None:
    """Render business fields driven by template_ctx.fields when available.

    Falls back to listing whatever keys the dynamic common_result contains, so
    new document types (e.g. train tickets) display correctly without code changes.
    """
    rows: list[dict] = []
    common_result = common_result or {}

    fields = (
        (template_ctx or {}).get("fields") if isinstance(template_ctx, dict) else None
    )
    if isinstance(fields, list) and fields:
        for f in fields:
            key = f.get("field_name")
            if not key:
                continue
            label = f.get("field_label") or key
            rows.append(
                {
                    "字段": str(label),
                    "key": str(key),
                    "值": _value_from_common(common_result, str(key)),
                }
            )
    else:
        for key, value in common_result.items():
            if key == "extra_fields":
                continue
            rows.append(
                {
                    "字段": str(key),
                    "key": str(key),
                    "值": "" if value is None else str(value),
                }
            )

    try:
        import pandas as pd  # type: ignore

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception:
        _kv_table(common_result)


def _field_label_from_ctx(field_key: str, template_ctx: dict | None) -> str:
    """Resolve a field's display label using template_ctx, fallback to the key."""
    fields = (
        (template_ctx or {}).get("fields") if isinstance(template_ctx, dict) else None
    )
    if isinstance(fields, list):
        for f in fields:
            if str(f.get("field_name") or "") == str(field_key or ""):
                return str(f.get("field_label") or field_key or "")
    return str(field_key or "")


def _render_dblclick_fullscreen_image(
    image_path: str, *, key: str, height_px: int
) -> None:
    """Double-click to toggle fullscreen preview (no buttons).

    Fullscreen uses object-fit: contain so the whole invoice is visible first.
    """
    try:
        img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    except Exception:
        st.info("无法加载图片")
        return

    wrap_id = f"fs_wrap_{key}"
    img_id = f"fs_img_{key}"
    html = f"""
<style>
  #{wrap_id} {{
    width: 100%;
    height: {max(160, height_px - 40)}px;
    overflow: hidden;
    background: #fff;
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.06);
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  #{img_id} {{
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    border-radius: 10px;
    cursor: zoom-in;
    background: #fff;
  }}
  .hint {{
    font-size: 12px;
    color: rgba(0,0,0,0.55);
    margin-top: 6px;
  }}
  /* Fullscreen behavior (fit entire invoice by default) */
  #{img_id}:fullscreen {{
    width: 100vw;
    height: 100vh;
    object-fit: contain;
    background: #000;
    cursor: zoom-out;
    border-radius: 0;
  }}
</style>
<div id="{wrap_id}">
  <img id="{img_id}" src="data:image/jpeg;base64,{img_b64}" alt="invoice" />
</div>
<div class="hint">双击图片：全屏 / 退出全屏</div>
<script>
  (function() {{
    const img = document.getElementById('{img_id}');
    if (!img) return;
    img.addEventListener('dblclick', async function(e) {{
      e.preventDefault();
      try {{
        if (!document.fullscreenElement) {{
          if (img.requestFullscreen) await img.requestFullscreen();
        }} else {{
          if (document.exitFullscreen) await document.exitFullscreen();
        }}
      }} catch (err) {{
        console.warn(err);
      }}
    }});
  }})();
</script>
"""
    components.html(html, height=height_px)


def _render_board_thumbnail(image_path: str, key: str) -> None:
    """Small thumbnail with dblclick fullscreen (no buttons)."""
    _render_dblclick_fullscreen_image(image_path, key=f"board_{key}", height_px=220)


def _render_validation_result(
    validation: dict, template_ctx: dict | None, *, show_raw: bool = True
) -> None:
    if not isinstance(validation, dict) or not validation:
        st.info("无校验结果（该模板未绑定 validators）")
        return
    headline = {
        "是否合规": bool(validation.get("is_valid", True)),
        "字段总数": int(validation.get("total_fields", 0) or 0),
        "合规字段": int(validation.get("valid_fields", 0) or 0),
        "不合规字段": int(validation.get("invalid_fields", 0) or 0),
    }
    _kv_table(headline)

    items = validation.get("items") or []
    if not items:
        st.caption("无字段级校验明细")
        return
    try:
        import pandas as pd  # type: ignore

        rows = []
        for it in items:
            fkey = it.get("field")
            errs = it.get("errors") or []
            msg = "; ".join(
                [
                    str(e.get("message") or "")
                    for e in errs
                    if isinstance(e, dict) and e.get("message")
                ]
            )
            rows.append(
                {
                    "字段": _field_label_from_ctx(str(fkey or ""), template_ctx),
                    "field": fkey,
                    "value": it.get("value"),
                    "is_valid": bool(it.get("is_valid", True)),
                    "errors": msg,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception:
        _kv_table(items)

    if show_raw:
        _raw_json_expander(validation, title="查看原始校验结果（JSON）")


def _render_engine_validation_results(
    engines: list[dict], template_ctx: dict | None
) -> None:
    """Render per-engine validation results (overview + per-field details)."""
    if not engines:
        st.info("无引擎结果")
        return

    try:
        import pandas as pd  # type: ignore

        rows = []
        for e in engines:
            vr = e.get("validation_result") if isinstance(e, dict) else None
            rows.append(
                {
                    "engine": e.get("engine"),
                    "parser": e.get("parser"),
                    "id": e.get("id"),
                    "is_valid": (vr or {}).get("is_valid")
                    if isinstance(vr, dict)
                    else None,
                    "invalid_fields": (vr or {}).get("invalid_fields")
                    if isinstance(vr, dict)
                    else None,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception:
        _kv_table(engines)

    st.markdown("#### 各引擎字段校验明细")
    for e in engines:
        if not isinstance(e, dict):
            continue
        vr = e.get("validation_result")
        title = f"{e.get('engine', '')}:{e.get('parser', '')} · {e.get('id', '')}"
        with st.expander(title, expanded=False):
            if isinstance(vr, dict):
                _render_validation_result(vr, template_ctx=template_ctx, show_raw=False)
            else:
                st.info("该引擎无校验结果（validation_result 为空）")


def _render_total_and_engine_validation(
    *, data: dict, template_ctx: dict | None
) -> None:
    """Validation node: show total validation_result + per-engine validation_result list."""
    total_vr = data.get("validation_result")
    if isinstance(total_vr, dict):
        st.markdown("#### 总校验结果（validation_result）")
        _render_validation_result(total_vr, template_ctx=template_ctx, show_raw=False)
        st.markdown("---")

    engines = data.get("engine_results") or []
    st.markdown("#### 各引擎校验结果（engine_results[].validation_result）")
    _render_engine_validation_results(
        engines if isinstance(engines, list) else [], template_ctx=template_ctx
    )


@st.dialog("节点详情")
def _node_detail_dialog(job: dict, node: NodeInfo) -> None:
    meta = st.columns([3, 2, 2, 2])
    meta[0].markdown(f"**图片**\n\n{job.get('filename', '')}")
    meta[1].markdown(f"**节点**\n\n{node.name}")
    meta[2].markdown(f"**类型**\n\n{node.node_type or '-'}")
    meta[3].markdown(
        f"**耗时(ms)**\n\n{node.cost_time if node.cost_time is not None else 0}"
    )

    if node.error:
        st.error(_friendly_node_error(node.error))

    is_summary = node.name == "summary" or node.node_type == "summary"
    is_validation = node.name == "validation" or node.node_type == "validation"
    if is_summary:
        tab_in, tab_biz, tab_verify, tab_val, tab_engines, tab_raw = st.tabs(
            ["输入", "业务", "一致性", "校验", "引擎", "原始"]
        )
    elif is_validation:
        tab_val, tab_in = st.tabs(["校验", "输入"])
    else:
        tab_in, tab_out, tab_model, tab_rule, tab_biz = st.tabs(
            ["输入", "输出", "模型", "规则", "业务"]
        )

    with tab_in:
        _render_dblclick_fullscreen_image(
            job["image_path"], key=f"node_{job['id']}_{node.name}", height_px=520
        )

    # Only non-summary/non-validation nodes have an "输出" tab.
    if (not is_summary) and (not is_validation):
        with tab_out:
            if node.output_data is None:
                st.info("无输出信息")
            else:
                _kv_table(node.output_data)
                _raw_json_expander(node.output_data)

    # Shared context for the remaining tabs (independent from input/output)
    result = job.get("result") or {}
    data = (result or {}).get("data") or {}
    template_ctx = None
    if isinstance(data.get("debug"), dict):
        template_ctx = (data.get("debug") or {}).get("template_ctx")

    if is_summary:
        with tab_biz:
            # Summary node: only show final business data
            common_result = data.get("common_result") or {}
            _render_business_result_table(common_result, template_ctx=template_ctx)
            _raw_json_expander(common_result)

        with tab_verify:
            verify = data.get("verify_result") or {}
            # Show headline metrics
            headline = {
                "是否一致": bool(verify.get("is_consistent", False)),
                "字段总数": int(verify.get("total_fields", 0) or 0),
                "一致字段": int(verify.get("consistent_fields", 0) or 0),
                "不一致字段": int(verify.get("inconsistent_fields", 0) or 0),
            }
            _kv_table(headline)
            # Show per-field details as table if present
            details = verify.get("diff_details") or []
            if details:
                try:
                    import pandas as pd  # type: ignore

                    rows = []
                    for d in details:
                        vals = d.get("values") or []
                        v0 = (vals[0] or {}).get("value") if vals else ""
                        fkey = d.get("field")
                        rows.append(
                            {
                                "字段": _field_label_from_ctx(
                                    str(fkey or ""), template_ctx
                                ),
                                "field": fkey,
                                "status": d.get("status"),
                                "value": v0,
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(rows), use_container_width=True, hide_index=True
                    )
                except Exception:
                    _kv_table(details)
            _raw_json_expander(verify)

        with tab_val:
            validation = data.get("validation_result") or {}
            _render_validation_result(
                validation if isinstance(validation, dict) else {},
                template_ctx=template_ctx,
            )

        with tab_engines:
            engines = data.get("engine_results") or []
            _render_engine_results_full(
                engines if isinstance(engines, list) else [],
                template_ctx=template_ctx,
            )

        with tab_raw:
            st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")
    elif is_validation:
        with tab_val:
            _render_total_and_engine_validation(
                data=data if isinstance(data, dict) else {}, template_ctx=template_ctx
            )
    else:
        with tab_model:
            model_obj = {
                "node": node.name,
                "type": node.node_type,
                "engine": node.engine,
                "template": (template_ctx or {}).get("template"),
                "fields_count": len((template_ctx or {}).get("fields") or []),
            }
            _kv_table(model_obj)
            if template_ctx and template_ctx.get("template"):
                st.caption("命中模板")
                _kv_table(template_ctx.get("template"))
            _raw_json_expander(template_ctx or {}, title="查看原始模板上下文（可选）")

        with tab_rule:
            extractor_types = []
            if template_ctx and template_ctx.get("fields"):
                extractor_types = sorted(
                    {
                        str(f.get("extractor_type"))
                        for f in template_ctx["fields"]
                        if f.get("extractor_type")
                    }
                )
            _kv_table({"extractor_types": extractor_types})
            _raw_json_expander({"extractor_types": extractor_types})

        with tab_biz:
            # IMPORTANT: For non-summary nodes, only show THIS node's result.
            _node_business_view(node, template_ctx=template_ctx)


def _job_id() -> str:
    # Use uuid to avoid Streamlit widget key collisions.
    return uuid.uuid4().hex


def _normalize_stuck_running_jobs() -> None:
    """Mid-batch navigation can leave jobs ``running`` without ``result``; treat as pending."""
    for j in st.session_state.jobs:
        if j.get("status") == "running" and j.get("result") is None:
            j["status"] = "pending"


def _incomplete_job_count() -> int:
    return sum(
        1
        for j in st.session_state.jobs
        if j.get("status") not in {"success", "failed"}
    )


def _queue_content_shas() -> set[str]:
    return {
        str(j["content_sha256"])
        for j in st.session_state.jobs
        if j.get("content_sha256")
    }


def _apply_recognize_response_to_job(job: dict, res: dict | None) -> None:
    job["result"] = res
    job["nodes"] = parse_result_to_nodes(res or {})
    try:
        job["persisted_job_id"] = (
            ((res or {}).get("data") or {}).get("debug", {}) or {}
        ).get("persisted_job_id")
        job["persisted_run_id"] = (
            ((res or {}).get("data") or {}).get("debug", {}) or {}
        ).get("persisted_run_id")
    except Exception:
        pass
    code = (res or {}).get("code")
    job["status"] = "success" if code == 0 else "failed"


def _run_recognition_queue(api_client: OCRAPIClient, workflow_id: int | None) -> None:
    """Process all jobs that are not terminal (success/failed); skip completed ones."""
    _normalize_stuck_running_jobs()
    progress = st.progress(0)
    total = max(len(st.session_state.jobs), 1)
    for i, job in enumerate(st.session_state.jobs):
        st.session_state.active_job_id = job["id"]
        if job["status"] in {"success", "failed"}:
            progress.progress((i + 1) / total)
            continue
        job["status"] = "running"
        with st.spinner(f"识别中：{job['filename']}"):
            upload_path = job.get("input_path") or job["image_path"]
            res = api_client.recognize(upload_path, workflow_id=workflow_id)
        _apply_recognize_response_to_job(job, res)
        progress.progress((i + 1) / total)
    st.success("队列识别完成")
    st.rerun()


def _rerun_single_job(
    api_client: OCRAPIClient, job: dict, workflow_id: int | None
) -> None:
    """Run recognition once for a single queue job (current workflow)."""
    st.session_state.active_job_id = job["id"]
    job["status"] = "running"
    upload_path = job.get("input_path") or job["image_path"]
    res = api_client.recognize(upload_path, workflow_id=workflow_id)
    _apply_recognize_response_to_job(job, res)


def _rerun_all_jobs(api_client: OCRAPIClient, workflow_id: int | None) -> None:
    """Re-run recognition for every job in the queue (ignores prior success/failed)."""
    _normalize_stuck_running_jobs()
    progress = st.progress(0)
    total = max(len(st.session_state.jobs), 1)
    for i, job in enumerate(st.session_state.jobs):
        st.session_state.active_job_id = job["id"]
        job["status"] = "running"
        with st.spinner(f"识别中 ({i + 1}/{total})：{job.get('filename', '')}"):
            upload_path = job.get("input_path") or job["image_path"]
            res = api_client.recognize(upload_path, workflow_id=workflow_id)
        _apply_recognize_response_to_job(job, res)
        progress.progress((i + 1) / total)
    st.success("已全部重新识别")
    st.rerun()


def _add_jobs(uploaded_files) -> int:
    """Append new files to the queue; skip files whose bytes already exist in queue.

    Returns the number of skipped duplicates (same SHA-256 as an existing job).
    """
    existing = _queue_content_shas()
    skipped = 0
    for uf in uploaded_files:
        raw = uf.getvalue()
        content_sha = hashlib.sha256(raw).hexdigest()
        if content_sha in existing:
            skipped += 1
            continue
        existing.add(content_sha)

        suffix = Path(uf.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            input_path = tmp.name

        preview_path = input_path
        if suffix.lower() == ".pdf":
            try:
                import fitz  # type: ignore

                doc = fitz.open(input_path)
                try:
                    page0 = doc.load_page(0)
                    pix = page0.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".png"
                    ) as tmp_img:
                        preview_path = tmp_img.name
                    pix.save(preview_path)
                finally:
                    doc.close()
            except Exception:
                preview_path = input_path

        st.session_state.jobs.append(
            {
                "id": _job_id(),
                "filename": uf.name,
                "content_sha256": content_sha,
                "image_path": preview_path,
                "input_path": input_path,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "status": "pending",
                "result": None,
                "nodes": create_default_nodes(),
            }
        )
    if st.session_state.active_job_id is None and st.session_state.jobs:
        st.session_state.active_job_id = st.session_state.jobs[0]["id"]
    return skipped


def _find_job(job_id: str):
    for j in st.session_state.jobs:
        if j["id"] == job_id:
            return j
    return None


def _job_result_payload(job: dict) -> tuple[dict, dict, dict | None]:
    """Return (data, common_result, template_ctx) from a queue job's API result."""
    res = job.get("result") or {}
    data = res.get("data") if isinstance(res.get("data"), dict) else {}
    common = (
        data.get("common_result") if isinstance(data.get("common_result"), dict) else {}
    )
    template_ctx = None
    if isinstance(data.get("debug"), dict):
        template_ctx = data.get("debug", {}).get("template_ctx")
    return data, common, template_ctx


def _build_workflow_placeholder_nodes(
    api_client: OCRAPIClient, workflow_id: int | None
) -> list[NodeInfo]:
    """Build placeholder node flow for pending/running jobs.

    This is used to render the full node chain during recognition (before final result arrives),
    so the UI does not fall back to only 2 default nodes.
    """
    if workflow_id is None:
        return create_default_nodes()
    try:
        nodes = api_client.list_nodes()
        wf_nodes = api_client.get_workflow_nodes(int(workflow_id))
    except Exception:
        return create_default_nodes()

    # node_id -> node config
    node_by_id: dict[int, dict] = {}
    for n in nodes if isinstance(nodes, list) else []:
        try:
            node_by_id[int(n.get("id"))] = n
        except Exception:
            continue

    # Sort workflow nodes by order_index
    wf_nodes_sorted = []
    for wn in wf_nodes if isinstance(wf_nodes, list) else []:
        if not isinstance(wn, dict):
            continue
        wf_nodes_sorted.append(wn)
    wf_nodes_sorted.sort(key=lambda x: int(x.get("order_index") or 100))

    out: list[NodeInfo] = []
    for wn in wf_nodes_sorted:
        try:
            node_id = int(wn.get("node_id"))
        except Exception:
            continue
        base = node_by_id.get(node_id) or {}
        enabled = bool(wn.get("enabled", True)) and bool(base.get("enabled", True))
        if not enabled:
            continue
        cfg = (
            base.get("config_json") if isinstance(base.get("config_json"), dict) else {}
        )
        out.append(
            NodeInfo(
                name=str(base.get("node_name") or f"node_{node_id}"),
                status="pending",
                engine=str(cfg.get("engine") or ""),
                node_type=str(base.get("node_type") or ""),
                cost_time=None,
                error=None,
            )
        )

    # Always show virtual validation + final merge/summary nodes as placeholders.
    out.append(
        NodeInfo(
            name="validation",
            status="pending",
            engine="validators",
            node_type="validation",
            output_data=None,
        )
    )
    out.append(
        NodeInfo(
            name="merge_result",
            status="pending",
            engine="merge",
            node_type="summary",
            output_data=None,
        )
    )
    return out or create_default_nodes()


st.markdown("### 1) 上传图片（可多张）")
_upload_skip = st.session_state.pop("_upload_skip_notice", None)
if _upload_skip:
    st.info(_upload_skip)
uploaded_files = st.file_uploader(
    "选择发票图片",
    type=["jpg", "jpeg", "png", "bmp", "pdf"],
    accept_multiple_files=True,
    help="可多选；再次点「加入队列」只追加新文件，与队列中内容相同的文件会自动跳过。",
)
if uploaded_files:
    if st.button("加入队列", type="primary"):
        dup = _add_jobs(uploaded_files)
        if dup:
            st.session_state["_upload_skip_notice"] = (
                f"已跳过 {dup} 个与队列中内容相同的文件（追加时自动去重）。"
            )
        st.rerun()

st.markdown("---")
st.markdown("### 2) 识别队列")
if not st.session_state.jobs:
    st.info("队列为空")
else:
    _normalize_stuck_running_jobs()
    n_incomplete = _incomplete_job_count()
    if n_incomplete:
        st.info(
            f"尚有 {n_incomplete} 条未完成。切到其它页面会中断批量识别；"
            "请点「继续识别」或「开始识别」（均会跳过已成功/失败项，从未完成项接着跑）。"
        )
    n_total = len(st.session_state.jobs)
    stat_line = f"队列 **{n_total}** 张"
    if n_incomplete:
        stat_line += f" · 待处理 **{n_incomplete}** 张"
    st.caption(stat_line)

    sel_row = st.columns([1.45, 1])
    options = [f"{j['filename']} · {j['status']}" for j in st.session_state.jobs]
    ids = [j["id"] for j in st.session_state.jobs]
    idx = (
        ids.index(st.session_state.active_job_id)
        if st.session_state.active_job_id in ids
        else 0
    )
    with sel_row[0]:
        selected = st.selectbox(
            "当前图片",
            options=options,
            index=idx,
            label_visibility="visible",
        )
    st.session_state.active_job_id = ids[options.index(selected)]

    try:
        workflows = api_client.list_workflows(active_only=True)
    except Exception:
        workflows = []
    default_wf_id = None
    try:
        default_wf_id = api_client.get_default_workflow_id()
    except Exception:
        default_wf_id = None

    if default_wf_id is None:
        for w in workflows:
            try:
                if bool(w.get("is_default")):
                    default_wf_id = int(w.get("id"))
                    break
            except Exception:
                continue

    wf_items = [f"{w['id']} · {w['name']}" for w in workflows]
    default_idx = 0
    if default_wf_id is not None:
        for i, it in enumerate(wf_items):
            if str(it).split("·")[0].strip() == str(int(default_wf_id)):
                default_idx = i
                break
    with sel_row[1]:
        wf_sel = st.selectbox(
            "调度流程",
            options=wf_items or ["(none)"],
            index=default_idx,
            label_visibility="visible",
        )
    workflow_id = None
    if wf_sel and wf_sel != "(none)":
        try:
            workflow_id = int(str(wf_sel).split("·")[0].strip())
        except Exception:
            workflow_id = None

    placeholder_nodes = _build_workflow_placeholder_nodes(api_client, workflow_id)
    for j in st.session_state.jobs:
        if j.get("result") is None and j.get("status") in {"pending", "running"}:
            j["nodes"] = [NodeInfo(**n.__dict__) for n in placeholder_nodes]

    st.markdown("**识别操作**")
    st.caption("以下按钮同宽单行排列；鼠标悬停可看完整说明。")
    # Equal-width columns so every button stretches to the same width on one row.
    op_row = st.columns([1, 1, 1, 1, 1])
    if op_row[0].button(
        "开始识别",
        type="primary",
        use_container_width=True,
        help="只处理尚未成功/失败的任务；已完成的会跳过。",
    ):
        _run_recognition_queue(api_client, workflow_id)
    if op_row[1].button(
        "继续识别",
        use_container_width=True,
        help="与「开始识别」相同逻辑：从队列中未完成项接着跑。",
    ):
        if _incomplete_job_count() == 0:
            st.warning("没有待识别的任务（当前均为成功或失败）。")
        else:
            _run_recognition_queue(api_client, workflow_id)
    if op_row[2].button(
        "当前重识",
        use_container_width=True,
        help="仅对上方「当前图片」下拉框选中的那一张，按当前调度流程再识别一次。",
    ):
        job = _find_job(st.session_state.active_job_id)
        if job is None:
            st.error("未找到当前任务。")
        else:
            with st.spinner(f"重新识别：{job.get('filename', '')}"):
                _rerun_single_job(api_client, job, workflow_id)
            st.rerun()
    if op_row[3].button(
        "全部重识",
        use_container_width=True,
        help="对队列中每一张图重新识别（含已成功/失败的），按当前调度流程跑完整队列。",
    ):
        _rerun_all_jobs(api_client, workflow_id)
    if op_row[4].button(
        "清空队列",
        use_container_width=True,
        help="删除队列及本地临时文件。",
    ):
        for j in st.session_state.jobs:
            for k in ("image_path", "input_path"):
                p = j.get(k)
                try:
                    if p and os.path.exists(str(p)):
                        os.unlink(str(p))
                except Exception:
                    pass
        st.session_state.jobs = []
        st.session_state.active_job_id = None
        st.rerun()

    st.session_state["_recognition_workflow_id"] = workflow_id

st.markdown("---")
st.markdown("### 3) 识别记录（分页）")
if not st.session_state.jobs:
    st.info("请先上传图片加入队列")
else:
    pager = st.columns([2, 2, 6])
    page_size = pager[0].selectbox("每页数量", options=[3, 5, 8, 10], index=1)
    total = len(st.session_state.jobs)
    total_pages = max(1, (total + int(page_size) - 1) // int(page_size))
    page = pager[1].number_input(
        "页码", min_value=1, max_value=total_pages, value=1, step=1
    )
    pager[2].caption(
        "每条：左侧为放大原图（双击全屏），右侧为最终识别字段；下方为节点流程，可点节点看详情。"
    )

    start = (int(page) - 1) * int(page_size)
    end = min(total, start + int(page_size))
    jobs_page = st.session_state.jobs[start:end]
    # Save current pagination slice for other sections (e.g. export).
    st.session_state["_jobs_page_slice"] = (start, end)

    wf_for_rerun = st.session_state.get("_recognition_workflow_id")
    # Record list: image taller than old 220px thumbnail so invoice text is readable.
    # components.html height includes image box + hint row; inner box uses height_px-40.
    _RECORD_IMAGE_HEIGHT = 520

    for job in jobs_page:
        _, common_result, template_ctx = _job_result_payload(job)
        res_top = job.get("result") or {}

        with st.container():
            title_row = st.columns([5, 1])
            with title_row[0]:
                st.markdown(
                    f"##### {job.get('filename', '未命名')}\n\n"
                    f"状态：**{job.get('status', '-')}**"
                )
            with title_row[1]:
                if st.button(
                    "重识别",
                    key=f"rerun_row_{job['id']}",
                    help="仅此张再识别一次",
                    use_container_width=True,
                ):
                    with st.spinner(f"识别中：{job.get('filename', '')}"):
                        _rerun_single_job(api_client, job, wf_for_rerun)
                    st.session_state.active_job_id = job["id"]
                    st.rerun()

            img_col, res_col = st.columns([1.05, 0.95])
            with img_col:
                st.caption("原图")
                _render_dblclick_fullscreen_image(
                    job["image_path"],
                    key=f"record_{job['id']}",
                    height_px=_RECORD_IMAGE_HEIGHT,
                )
            with res_col:
                st.caption("识别结果（最终抽取）")
                if job.get("status") in {"pending", "running"}:
                    st.info("尚未完成识别。")
                elif job.get("status") == "failed":
                    st.error(str(res_top.get("msg") or "识别失败"))
                    if common_result:
                        _render_business_result_table(
                            common_result, template_ctx=template_ctx
                        )
                elif not common_result:
                    st.warning("无 common_result，可在节点详情中查看各引擎输出。")
                else:
                    _render_business_result_table(
                        common_result, template_ctx=template_ctx
                    )

            st.caption("识别流程（节点）")
            idx, clicked = render_node_row(job["nodes"], key=f"row_{job['id']}")
            st.session_state.active_job_id = job["id"]
            st.session_state.active_node_idx = idx
            if clicked:
                node = job["nodes"][idx]
                _node_detail_dialog(job, node)

            st.divider()

st.markdown("---")
st.caption(
    "提示：识别记录中左侧原图可双击全屏查看；节点详情弹窗已自适应浏览器大小。"
)

st.markdown("### 4) 识别结果导出")
try:
    export_confs = api_client.list_export_configs(active_only=True)
except Exception as e:
    export_confs = []
    st.warning(f"无法读取导出配置：{e}")

if not export_confs:
    st.info("暂无导出配置，请先在数据库中添加 export_configs 配置。")
else:
    exp_cols = st.columns([3, 3, 2, 2])
    exp_options = [f"{c['name']} ({c['format']})" for c in export_confs]
    default_exp_idx = 0
    try:
        if export_confs:
            best_i = 0
            best_sort = int(export_confs[0].get("sort") or 0)
            for i, c in enumerate(export_confs):
                s = int(c.get("sort") or 0)
                if s < best_sort:
                    best_sort = s
                    best_i = i
            default_exp_idx = best_i
    except Exception:
        default_exp_idx = 0
    exp_idx = exp_cols[0].selectbox(
        "导出模板",
        options=list(range(len(exp_options))),
        index=int(default_exp_idx),
        format_func=lambda i: exp_options[i],
    )
    export_cfg = export_confs[int(exp_idx)]

    _EXPORT_KIND_SUCCESS = "仅识别成功的记录"
    _EXPORT_KIND_FAILED = "仅识别失败的记录"
    _EXPORT_KIND_ALL = "全部记录（成功、失败与未知）"

    export_kind = exp_cols[1].selectbox(
        "导出类型",
        options=[
            _EXPORT_KIND_SUCCESS,
            _EXPORT_KIND_FAILED,
            _EXPORT_KIND_ALL,
        ],
        index=0,
    )
    filename_overwrite = exp_cols[2].text_input("文件名(可选)", value="")
    exp_cols[3].caption(
        "范围：当前队列中**已加入**的全部图片（与分页无关）。"
        "「仅成功」导出模板字段（表头为 field_label）；"
        "「仅失败 / 全部」含列：文件名、状态、说明，成功行另含识别字段。"
    )

    def _export_all_jobs() -> list[dict]:
        return list(st.session_state.jobs)

    def _status_zh(status: str | None) -> str:
        s = status or ""
        if s == "success":
            return "成功"
        if s == "failed":
            return "失败"
        return "未知"

    def _job_detail(job: dict) -> str:
        st_local = job.get("status") or ""
        if st_local == "pending":
            return "等待识别"
        if st_local == "running":
            return "识别中"
        res = job.get("result")
        if isinstance(res, dict):
            return str(res.get("msg") or "").strip() or "—"
        return "—"

    def _collect_export_rows(
        kind: str,
    ) -> tuple[list[dict], dict | None]:
        """Build rows from entire session queue. template_ctx only for success-only."""
        jobs = _export_all_jobs()
        if kind == _EXPORT_KIND_SUCCESS:
            rows: list[dict] = []
            template_ctx: dict | None = None
            for j in jobs:
                if j.get("status") != "success":
                    continue
                data = (j.get("result") or {}).get("data") or {}
                cr = data.get("common_result")
                if not isinstance(cr, dict):
                    continue
                rows.append(dict(cr))
                if template_ctx is None:
                    dbg = data.get("debug") if isinstance(data.get("debug"), dict) else None
                    if dbg and dbg.get("template_ctx"):
                        template_ctx = dbg.get("template_ctx")
            return rows, template_ctx

        if kind == _EXPORT_KIND_FAILED:
            rows = []
            for j in jobs:
                if j.get("status") != "failed":
                    continue
                rows.append(
                    {
                        "文件名": j.get("filename") or "",
                        "状态": "失败",
                        "说明": _job_detail(j),
                    }
                )
            return rows, None

        # 全部：成功行合并 common_result；其余仅文件名/状态/说明（不传 template_ctx）
        rows = []
        for j in jobs:
            base = {
                "文件名": j.get("filename") or "",
                "状态": _status_zh(j.get("status")),
                "说明": _job_detail(j),
            }
            if j.get("status") == "success":
                data = (j.get("result") or {}).get("data") or {}
                cr = data.get("common_result")
                if isinstance(cr, dict):
                    rows.append({**cr, **base})
                else:
                    rows.append(base)
            else:
                rows.append(base)
        return rows, None

    if st.button("导出识别结果", type="primary"):
        try:
            if not st.session_state.jobs:
                st.warning("队列为空，请先加入图片并完成识别后再导出。")
                st.stop()

            rows, template_ctx = _collect_export_rows(export_kind)
            if not rows:
                if export_kind == _EXPORT_KIND_SUCCESS:
                    st.warning("当前没有识别成功的记录可导出（需有 common_result）。")
                elif export_kind == _EXPORT_KIND_FAILED:
                    st.warning("当前没有识别失败的记录可导出。")
                else:
                    st.warning("没有可导出的行。")
                st.stop()

            content = api_client.generate_export(
                export_config_id=int(export_cfg["id"]),
                rows=rows,
                template_ctx=template_ctx,
                filename_overwrite=filename_overwrite.strip() or None,
            )
            ext = str(export_cfg.get("format") or "dat").lower()
            out_name = (
                filename_overwrite.strip()
                if filename_overwrite.strip()
                else export_cfg.get("name", "export")
            ) + f".{ext}"
            st.download_button("点击下载文件", data=content, file_name=out_name)
        except Exception as e:
            st.error(str(e))
