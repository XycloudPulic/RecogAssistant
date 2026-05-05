# SPDX-License-Identifier: MIT

"""LLM配置页面"""

import json

import streamlit as st
from utils.api_client import OCRAPIClient

api = OCRAPIClient()

st.title("🤖 LLM配置")
st.markdown("支持单行弹窗查看/修改、单行删除、勾选多行后批量删除。")

tab_list, tab_add = st.tabs(["📋 配置列表（管理）", "➕ 添加配置"])

try:
    llms = api.list_llm_configs()
except Exception as e:
    st.error(f"加载失败：{e}")
    llms = []


@st.dialog("查看/修改LLM配置")
def _edit_llm_dialog(llm: dict) -> None:
    with st.form(f"edit_llm_{llm['id']}"):
        name = st.text_input("名称", value=llm.get("name", ""))
        provider = st.selectbox(
            "provider",
            options=["openai", "ollama"],
            index=0 if llm.get("provider") == "openai" else 1,
        )
        base_url = st.text_input("base_url", value=llm.get("base_url") or "")
        model = st.text_input("model", value=llm.get("model") or "")
        api_key_ref = st.text_input("api_key_ref", value=llm.get("api_key_ref") or "")
        system_prompt = st.text_area(
            "system_prompt", value=llm.get("system_prompt") or "", height=140
        )
        schema_json = st.text_area(
            "response_schema（JSON）",
            value=json.dumps(
                llm.get("response_schema") or {}, ensure_ascii=False, indent=2
            ),
            height=180,
        )
        is_active = st.checkbox("启用", value=bool(llm.get("is_active", True)))
        if st.form_submit_button("保存单行修改", type="primary"):
            try:
                response_schema = json.loads(schema_json) if schema_json.strip() else {}
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            payload = {
                "name": name,
                "provider": provider,
                "base_url": base_url or None,
                "model": model,
                "api_key_ref": api_key_ref or None,
                "system_prompt": system_prompt or None,
                "response_schema": response_schema,
                "is_active": is_active,
            }
            try:
                api.update_llm_config(int(llm["id"]), payload)
                st.success("已更新")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")


with tab_list:
    st.markdown("### 已配置LLM")
    selected_ids = [
        int(c["id"])
        for c in llms
        if st.session_state.get(f"llm_select_{int(c['id'])}", False)
    ]
    if st.button(
        "✖ 批量删除选中配置",
        type="secondary",
        disabled=not selected_ids,
        key="bulk_delete_llm_btn",
    ):
        deleted = 0
        failed = 0
        for llm_id in selected_ids:
            try:
                api.delete_llm_config(llm_id)
                st.session_state[f"llm_select_{llm_id}"] = False
                deleted += 1
            except Exception as e:
                st.error(f"删除配置 {llm_id} 失败：{e}")
                failed += 1
        st.success(f"批量删除完成：成功 {deleted}，失败 {failed}")
        st.rerun()

    if not llms:
        st.info("暂无配置")
    else:
        header = st.columns([0.8, 0.8, 2.0, 1.2, 2.0, 1.0, 1.0, 1.0])
        header[0].markdown("**选中**")
        header[1].markdown("**ID**")
        header[2].markdown("**名称**")
        header[3].markdown("**provider**")
        header[4].markdown("**model**")
        header[5].markdown("**启用**")
        header[6].markdown("**查看/修改**")
        header[7].markdown("**删除**")

        for c in llms:
            llm_id = int(c["id"])
            row = st.columns([0.8, 0.8, 2.0, 1.2, 2.0, 1.0, 1.0, 1.0])
            row[0].checkbox(
                "选择",
                key=f"llm_select_{llm_id}",
                value=st.session_state.get(f"llm_select_{llm_id}", False),
                label_visibility="collapsed",
            )
            row[1].write(llm_id)
            row[2].write(c.get("name", ""))
            row[3].write(c.get("provider", ""))
            row[4].write(c.get("model", ""))
            row[5].write("✅" if bool(c.get("is_active", True)) else "❌")
            if row[6].button(
                "查看/修改", key=f"llm_edit_btn_{llm_id}", use_container_width=True
            ):
                _edit_llm_dialog(c)
            if row[7].button(
                "删除", key=f"llm_del_btn_{llm_id}", use_container_width=True
            ):
                try:
                    api.delete_llm_config(llm_id)
                    st.success(f"已删除配置 {llm_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")


with tab_add:
    st.markdown("### 添加LLM配置")
    with st.form("create_llm_form"):
        name = st.text_input("名称")
        provider = st.selectbox("provider", options=["openai", "ollama"])
        base_url = st.text_input("base_url", value="https://api.openai.com/v1")
        model = st.text_input("model", value="gpt-4o-mini")
        api_key_ref = st.text_input("api_key_ref")
        system_prompt = st.text_area("system_prompt", height=140)
        schema_json = st.text_area("response_schema（JSON）", value="{}", height=180)
        is_active = st.checkbox("启用", value=True)
        if st.form_submit_button("创建配置", type="primary"):
            try:
                response_schema = json.loads(schema_json) if schema_json.strip() else {}
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            payload = {
                "name": name,
                "provider": provider,
                "base_url": base_url or None,
                "model": model,
                "api_key_ref": api_key_ref or None,
                "system_prompt": system_prompt or None,
                "response_schema": response_schema,
                "is_active": is_active,
            }
            try:
                api.create_llm_config(payload)
                st.success("已创建")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")
