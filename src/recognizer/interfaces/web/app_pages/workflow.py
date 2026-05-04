# SPDX-License-Identifier: MIT

"""调度流程配置页面"""

import json

import requests
import streamlit as st
from app_meta import APP_NAME, APP_VERSION
from utils.api_client import OCRAPIClient

api = OCRAPIClient()

st.set_page_config(
    page_title=f"{APP_NAME}{APP_VERSION} · 调度流程",
    page_icon="🧩",
    layout="wide",
)

st.title("🧩 调度流程（Workflow）")
st.markdown("支持单行弹窗查看/修改、单行删除、勾选多行后批量删除；节点组合独立维护。")

tab_list, tab_add, tab_nodes = st.tabs(
    ["📋 流程列表（管理）", "➕ 添加流程", "🧩 节点组合"]
)

try:
    workflows = api.list_workflows(active_only=False)
except Exception as e:
    st.error(f"加载失败：{e}")
    workflows = []


@st.dialog("查看/修改流程")
def _edit_workflow_dialog(workflow: dict) -> None:
    with st.form(f"edit_workflow_{workflow['id']}"):
        name = st.text_input("流程名称", value=workflow.get("name", ""))
        description = st.text_area("描述", value=workflow.get("description") or "")
        is_active = st.checkbox("启用", value=bool(workflow.get("is_active", True)))
        if st.form_submit_button("保存单行修改", type="primary"):
            try:
                api.update_workflow(
                    int(workflow["id"]),
                    {"name": name, "description": description, "is_active": is_active},
                )
                st.success("已更新")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")


with tab_list:
    st.markdown("### 已配置流程")
    default_workflow_id = None
    try:
        default_workflow_id = api.get_default_workflow_id()
    except Exception:
        default_workflow_id = None
    selected_ids = [
        int(w["id"])
        for w in workflows
        if st.session_state.get(f"workflow_select_{int(w['id'])}", False)
    ]
    if st.button(
        "✖ 批量删除选中流程",
        type="secondary",
        disabled=not selected_ids,
        key="bulk_delete_workflows_btn",
    ):
        deleted = 0
        failed = 0
        for workflow_id in selected_ids:
            try:
                api.delete_workflow(workflow_id)
                st.session_state[f"workflow_select_{workflow_id}"] = False
                deleted += 1
            except Exception as e:
                st.error(f"删除流程 {workflow_id} 失败：{e}")
                failed += 1
        st.success(f"批量删除完成：成功 {deleted}，失败 {failed}")
        st.rerun()

    if not workflows:
        st.info("暂无流程配置")
    else:
        header = st.columns([0.8, 0.8, 1.0, 2.2, 2.2, 1.0, 1.0, 1.0])
        header[0].markdown("**选中**")
        header[1].markdown("**ID**")
        header[2].markdown("**默认**")
        header[3].markdown("**名称**")
        header[4].markdown("**描述**")
        header[5].markdown("**启用**")
        header[6].markdown("**查看/修改**")
        header[7].markdown("**删除**")

        for w in workflows:
            workflow_id = int(w["id"])
            row = st.columns([0.8, 0.8, 1.0, 2.2, 2.2, 1.0, 1.0, 1.0])
            row[0].checkbox(
                "选择",
                key=f"workflow_select_{workflow_id}",
                value=st.session_state.get(f"workflow_select_{workflow_id}", False),
                label_visibility="collapsed",
            )
            row[1].write(workflow_id)
            is_default = (
                default_workflow_id is not None
                and int(default_workflow_id) == workflow_id
            ) or bool(w.get("is_default", False))
            if is_default:
                row[2].write("⭐ 默认")
            else:
                if row[2].button(
                    "设为默认",
                    key=f"workflow_set_default_btn_{workflow_id}",
                    use_container_width=True,
                ):
                    try:
                        api.set_default_workflow(workflow_id)
                        st.success(f"已设置默认流程：{workflow_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"设置默认失败：{e}")

            row[3].write(w.get("name", ""))
            row[4].write(w.get("description", ""))
            row[5].write("✅" if bool(w.get("is_active", True)) else "❌")
            if row[6].button(
                "查看/修改",
                key=f"workflow_edit_btn_{workflow_id}",
                use_container_width=True,
            ):
                _edit_workflow_dialog(w)
            if row[7].button(
                "删除", key=f"workflow_del_btn_{workflow_id}", use_container_width=True
            ):
                try:
                    api.delete_workflow(workflow_id)
                    st.success(f"已删除流程 {workflow_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")


with tab_add:
    st.markdown("### 添加流程")
    with st.form("create_workflow_form"):
        name = st.text_input("流程名称")
        description = st.text_area("描述", value="默认识别调度：按节点顺序执行启用节点")
        is_active = st.checkbox("启用", value=True)
        if st.form_submit_button("创建流程", type="primary"):
            try:
                api.create_workflow(
                    {"name": name, "description": description, "is_active": is_active}
                )
                st.success("已创建")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")


with tab_nodes:
    st.markdown("### 编辑流程节点组合")
    active_workflows = api.list_workflows(active_only=False)
    wf_opts = [f"{w['id']} · {w['name']}" for w in active_workflows] or ["(none)"]
    sel = st.selectbox("选择流程", options=wf_opts)
    if sel == "(none)":
        st.info("请先创建流程")
        st.stop()
    wf_id = int(sel.split("·")[0].strip())

    try:
        nodes = api.list_nodes()
    except Exception:
        nodes = []

    try:
        wf_nodes = api.get_workflow_nodes(wf_id)
    except Exception:
        wf_nodes = []

    wf_nodes_by_node_id = {int(x["node_id"]): x for x in (wf_nodes or [])}

    st.caption(
        "提示：这里配置的是“某个流程里要跑哪些节点、按什么顺序跑”。不需要写 JSON。"
    )
    show_all = st.checkbox("显示全部节点（包含节点配置里未启用的）", value=False)

    def _to_row(n: dict) -> dict:
        node_id = int(n["id"])
        in_wf = wf_nodes_by_node_id.get(node_id)
        return {
            # IMPORTANT: Whether a node is included in a workflow should ONLY depend on workflow_nodes.
            # Otherwise, removing it from workflow will appear to "not work" after refresh
            # because globally-enabled nodes would be auto-checked again.
            "纳入流程": bool(in_wf["enabled"]) if in_wf is not None else False,
            "节点全局启用": bool(n.get("enabled", False)),
            "顺序": int(in_wf["order_index"])
            if in_wf is not None
            else int(n.get("order_index") or 100),
            "节点ID": node_id,
            "节点名": n.get("node_name", ""),
            "显示名": n.get("display_name", ""),
            "类型": n.get("node_type", ""),
        }

    display_nodes = (
        nodes if show_all else [n for n in nodes if bool(n.get("enabled", False))]
    )
    rows = [_to_row(n) for n in display_nodes]
    rows.sort(key=lambda r: (0 if r["纳入流程"] else 1, int(r["顺序"]), r["节点名"]))

    try:
        import pandas as pd  # type: ignore
    except Exception:
        pd = None  # type: ignore

    if pd is None:
        st.warning(
            "当前环境缺少 pandas，暂时无法使用表格编辑器。请使用下方“高级 JSON”方式保存。"
        )
        edited_rows = rows
    else:
        df = pd.DataFrame(rows)
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            disabled=["节点全局启用", "节点ID", "节点名", "显示名", "类型"],
            column_config={
                "纳入流程": st.column_config.CheckboxColumn(
                    "纳入流程", help="勾选表示该节点会在此流程中执行"
                ),
                "顺序": st.column_config.NumberColumn(
                    "顺序", min_value=0, max_value=1000, step=10
                ),
            },
        )
        edited_rows = edited_df.to_dict(orient="records")

    payload = []
    for r in edited_rows:
        if not bool(r.get("纳入流程")):
            continue
        payload.append(
            {
                "node_id": int(r["节点ID"]),
                "enabled": True,
                "order_index": int(r.get("顺序") or 100),
                "config_override_json": wf_nodes_by_node_id.get(
                    int(r["节点ID"]), {}
                ).get("config_override_json")
                or {},
            }
        )
    payload.sort(key=lambda x: int(x.get("order_index") or 0))

    c1, c2 = st.columns([1, 1])
    if c1.button("保存节点组合", type="primary", use_container_width=True):
        resp = requests.put(
            f"{api.base_url}/workflows/{wf_id}/nodes", json=payload, timeout=20
        )
        if resp.status_code >= 400:
            st.error(resp.text)
        else:
            st.success("已保存")
            st.rerun()

    with st.expander("高级：查看/编辑 JSON（可选）", expanded=False):
        txt = st.text_area(
            "workflow_nodes（JSON）",
            value=json.dumps(payload, ensure_ascii=False, indent=2),
            height=260,
        )
        if c2.button(
            "按 JSON 保存（高级）", type="secondary", use_container_width=True
        ):
            try:
                payload2 = json.loads(txt) if txt.strip() else []
                assert isinstance(payload2, list)
            except Exception as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            resp2 = requests.put(
                f"{api.base_url}/workflows/{wf_id}/nodes", json=payload2, timeout=20
            )
            if resp2.status_code >= 400:
                st.error(resp2.text)
            else:
                st.success("已保存")
                st.rerun()
