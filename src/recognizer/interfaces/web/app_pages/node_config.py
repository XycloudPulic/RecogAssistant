# SPDX-License-Identifier: MIT

"""节点配置页面"""

import json

import streamlit as st
from app_meta import APP_NAME, APP_VERSION
from utils.api_client import OCRAPIClient

api = OCRAPIClient()

st.set_page_config(
    page_title=f"{APP_NAME}{APP_VERSION} · 节点配置",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ 节点配置")
st.markdown("支持单行弹窗查看/修改、单行删除、勾选多行后批量删除。")

tab_list, tab_add = st.tabs(["📋 节点列表（管理）", "➕ 添加节点"])

try:
    nodes = api.list_nodes()
except Exception as e:
    st.error(f"加载节点失败：{e}")
    nodes = []


def _load_reference_data():
    try:
        templates = api.get_templates()
    except Exception:
        templates = []
    try:
        rulesets = api.list_rulesets()
    except Exception:
        rulesets = []
    try:
        llms = api.list_llm_configs()
    except Exception:
        llms = []
    return templates, rulesets, llms


@st.dialog("查看/修改节点")
def _edit_node_dialog(node: dict) -> None:
    templates, rulesets, llms = _load_reference_data()

    with st.form(f"edit_node_form_{node['id']}"):
        node_name = st.text_input("node_name（唯一）", value=node.get("node_name", ""))
        display_name = st.text_input("display_name", value=node.get("display_name", ""))
        description = st.text_area("description", value=node.get("description", ""))
        node_type = st.selectbox(
            "node_type",
            options=["ocr", "llm"],
            index=0 if node.get("node_type") == "ocr" else 1,
        )
        enabled = st.checkbox("enabled", value=bool(node.get("enabled", True)))
        order_index = st.number_input(
            "order_index",
            value=int(node.get("order_index", 100)),
            min_value=0,
            max_value=1000,
            step=10,
        )

        template_id = None
        ruleset_id = None
        llm_config_id = None
        if node_type == "ocr":
            tpl_opts = ["(none)"] + [f"{t['id']} · {t['name']}" for t in templates]
            cur_tpl = node.get("template_id")
            tpl_default = (
                f"{cur_tpl} · {next((t['name'] for t in templates if int(t['id']) == int(cur_tpl)), '')}"
                if cur_tpl
                else "(none)"
            )
            tpl_index = tpl_opts.index(tpl_default) if tpl_default in tpl_opts else 0
            sel_tpl = st.selectbox(
                "template（可选）", options=tpl_opts, index=tpl_index
            )
            if sel_tpl != "(none)":
                template_id = int(sel_tpl.split("·")[0].strip())

            # ruleset is derived from template (preferred UX for normal users)
            derived_ruleset_id = None
            if template_id is not None:
                tpl = next(
                    (t for t in templates if int(t.get("id")) == int(template_id)), None
                )
                if tpl:
                    derived_ruleset_id = tpl.get("ruleset_id")
            derived_ruleset_name = ""
            if derived_ruleset_id:
                derived_ruleset_name = next(
                    (
                        r.get("name", "")
                        for r in rulesets
                        if int(r.get("id")) == int(derived_ruleset_id)
                    ),
                    "",
                )
            st.caption(
                f"数据规则：{'(none)' if not derived_ruleset_id else str(derived_ruleset_id) + ' · ' + derived_ruleset_name}（从模板自动继承）"
            )

            with st.expander("高级：覆盖数据规则（可选）", expanded=False):
                rs_opts = ["(inherit from template)"] + [
                    f"{r['id']} · {r['name']}" for r in rulesets
                ]
                cur_rs = node.get("ruleset_id")
                rs_default = (
                    f"{cur_rs} · {next((r['name'] for r in rulesets if int(r['id']) == int(cur_rs)), '')}"
                    if cur_rs
                    else "(inherit from template)"
                )
                rs_index = rs_opts.index(rs_default) if rs_default in rs_opts else 0
                sel_rs = st.selectbox("数据规则覆盖", options=rs_opts, index=rs_index)
                if sel_rs != "(inherit from template)":
                    ruleset_id = int(sel_rs.split("·")[0].strip())
        else:
            llm_opts = [f"{c['id']} · {c['name']}" for c in llms] or ["(no llm config)"]
            cur_llm = node.get("llm_config_id")
            llm_default = (
                f"{cur_llm} · {next((c['name'] for c in llms if int(c['id']) == int(cur_llm)), '')}"
                if cur_llm
                else "(no llm config)"
            )
            llm_index = llm_opts.index(llm_default) if llm_default in llm_opts else 0
            sel_llm = st.selectbox(
                "llm_config（必选）", options=llm_opts, index=llm_index
            )
            if sel_llm != "(no llm config)":
                llm_config_id = int(sel_llm.split("·")[0].strip())

        config_json = st.text_area(
            "config_json（JSON）",
            value=json.dumps(node.get("config_json", {}), ensure_ascii=False, indent=2),
            height=140,
        )

        if st.form_submit_button("保存单行修改", type="primary"):
            try:
                cfg = json.loads(config_json) if config_json.strip() else {}
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()

            payload = {
                "node_name": node_name,
                "display_name": display_name,
                "description": description,
                "node_type": node_type,
                "enabled": enabled,
                "order_index": int(order_index),
                "template_id": template_id,
                "ruleset_id": ruleset_id,
                "llm_config_id": llm_config_id,
                "config_json": cfg,
            }
            try:
                api.update_node(int(node["id"]), payload)
                st.success("已更新")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")


with tab_list:
    st.markdown("### 已配置节点")
    selected_ids = [
        int(n["id"])
        for n in nodes
        if st.session_state.get(f"node_select_{int(n['id'])}", False)
    ]
    if st.button(
        "✖ 批量删除选中节点",
        type="secondary",
        disabled=not selected_ids,
        key="bulk_delete_nodes_in_list_btn",
    ):
        deleted = 0
        failed = 0
        for node_id in selected_ids:
            try:
                api.delete_node(node_id)
                st.session_state[f"node_select_{node_id}"] = False
                deleted += 1
            except Exception:
                failed += 1
        st.success(f"批量删除完成：成功 {deleted}，失败 {failed}")
        st.rerun()

    if not nodes:
        st.info("暂无节点配置")
    else:
        header = st.columns([0.8, 0.8, 1.6, 1.6, 1.0, 1.0, 1.0, 1.0])
        header[0].markdown("**选中**")
        header[1].markdown("**ID**")
        header[2].markdown("**节点名**")
        header[3].markdown("**显示名**")
        header[4].markdown("**类型**")
        header[5].markdown("**启用**")
        header[6].markdown("**查看/修改**")
        header[7].markdown("**删除**")

        for n in nodes:
            node_id = int(n["id"])
            row = st.columns([0.8, 0.8, 1.6, 1.6, 1.0, 1.0, 1.0, 1.0])
            row[0].checkbox(
                "选择",
                key=f"node_select_{node_id}",
                value=st.session_state.get(f"node_select_{node_id}", False),
                label_visibility="collapsed",
            )
            row[1].write(node_id)
            row[2].write(n.get("node_name", ""))
            row[3].write(n.get("display_name", ""))
            row[4].write(n.get("node_type", ""))
            row[5].write("✅" if bool(n.get("enabled", False)) else "❌")
            if row[6].button(
                "查看/修改", key=f"node_edit_btn_{node_id}", use_container_width=True
            ):
                _edit_node_dialog(n)
            if row[7].button(
                "删除", key=f"node_del_btn_{node_id}", use_container_width=True
            ):
                try:
                    api.delete_node(node_id)
                    st.success(f"已删除节点 {node_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")

with tab_add:
    st.markdown("### 新增节点")
    templates, rulesets, llms = _load_reference_data()

    with st.form("create_node_form"):
        node_name = st.text_input("node_name（唯一）", placeholder="e.g. paddle_ocr")
        display_name = st.text_input("display_name", placeholder="e.g. Paddle OCR")
        description = st.text_area("description", placeholder="节点功能描述...")
        node_type = st.selectbox("node_type", options=["ocr", "llm"])
        enabled = st.checkbox("enabled", value=True)
        order_index = st.number_input(
            "order_index", value=100, min_value=0, max_value=1000, step=10
        )

        template_id = None
        ruleset_id = None
        llm_config_id = None
        if node_type == "ocr":
            tpl_opts = ["(none)"] + [f"{t['id']} · {t['name']}" for t in templates]
            sel_tpl = st.selectbox("template（可选）", options=tpl_opts)
            if sel_tpl != "(none)":
                template_id = int(sel_tpl.split("·")[0].strip())

            derived_ruleset_id = None
            if template_id is not None:
                tpl = next(
                    (t for t in templates if int(t.get("id")) == int(template_id)), None
                )
                if tpl:
                    derived_ruleset_id = tpl.get("ruleset_id")
            derived_ruleset_name = ""
            if derived_ruleset_id:
                derived_ruleset_name = next(
                    (
                        r.get("name", "")
                        for r in rulesets
                        if int(r.get("id")) == int(derived_ruleset_id)
                    ),
                    "",
                )
            st.caption(
                f"规则集：{'(none)' if not derived_ruleset_id else str(derived_ruleset_id) + ' · ' + derived_ruleset_name}（从模板自动继承）"
            )

            with st.expander("高级：覆盖规则集（可选）", expanded=False):
                rs_opts = ["(inherit from template)"] + [
                    f"{r['id']} · {r['name']}" for r in rulesets
                ]
                sel_rs = st.selectbox("ruleset 覆盖", options=rs_opts)
                if sel_rs != "(inherit from template)":
                    ruleset_id = int(sel_rs.split("·")[0].strip())
        else:
            llm_opts = [f"{c['id']} · {c['name']}" for c in llms] or ["(no llm config)"]
            sel_llm = st.selectbox("llm_config（必选）", options=llm_opts)
            if sel_llm != "(no llm config)":
                llm_config_id = int(sel_llm.split("·")[0].strip())

        config_json = st.text_area("config_json（JSON）", value="{}", height=140)
        if st.form_submit_button("创建节点", type="primary"):
            try:
                cfg = json.loads(config_json) if config_json.strip() else {}
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            payload = {
                "node_name": node_name,
                "display_name": display_name,
                "description": description,
                "node_type": node_type,
                "enabled": enabled,
                "order_index": int(order_index),
                "template_id": template_id,
                "ruleset_id": ruleset_id,
                "llm_config_id": llm_config_id,
                "config_json": cfg,
            }
            try:
                api.create_node(payload)
                st.success("已创建")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")
