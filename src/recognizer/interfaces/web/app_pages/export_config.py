# SPDX-License-Identifier: MIT

"""导出配置页面"""

import json

import streamlit as st
from app_meta import APP_NAME, APP_VERSION
from utils.api_client import OCRAPIClient

api = OCRAPIClient()

st.set_page_config(
    page_title=f"{APP_NAME}{APP_VERSION} · 导出配置",
    page_icon="📤",
    layout="wide",
)

st.title("📤 导出配置")
st.markdown("支持单行弹窗查看/修改、单行删除、勾选多行后批量删除。")

tab_list, tab_add = st.tabs(["📋 配置列表（管理）", "➕ 添加配置"])

try:
    rows = api.list_export_configs(active_only=False)
except Exception as e:
    st.error(f"加载失败：{e}")
    rows = []


@st.dialog("查看/修改导出配置")
def _edit_export_dialog(cfg: dict) -> None:
    with st.form(f"edit_export_cfg_{cfg['id']}"):
        name = st.text_input("name", value=cfg.get("name", ""))
        formats = ["csv", "xlsx", "txt", "pdf"]
        fmt = st.selectbox(
            "format",
            options=formats,
            index=formats.index(cfg.get("format", "csv"))
            if cfg.get("format", "csv") in formats
            else 0,
        )
        filename_template = st.text_input(
            "filename_template",
            value=cfg.get("filename_template") or "common_result_{date}",
        )
        sort = st.number_input(
            "sort（越小越靠前/默认）",
            min_value=0,
            max_value=100000,
            value=int(cfg.get("sort") or 0),
            step=1,
        )
        is_active = st.checkbox("is_active", value=bool(cfg.get("is_active", True)))
        options_json = st.text_area(
            "options_json（JSON）",
            value=json.dumps(
                cfg.get("options_json") or {}, ensure_ascii=False, indent=2
            ),
            height=180,
        )
        if st.form_submit_button("保存单行修改", type="primary"):
            try:
                opts = json.loads(options_json) if options_json.strip() else {}
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            payload = {
                "name": name,
                "format": fmt,
                "filename_template": filename_template,
                "sort": int(sort),
                "options_json": opts,
                "is_active": is_active,
            }
            try:
                api.update_export_config(int(cfg["id"]), payload)
                st.success("已更新")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")


with tab_list:
    st.markdown("### 已配置导出项")
    selected_ids = [
        int(r["id"])
        for r in rows
        if st.session_state.get(f"export_select_{int(r['id'])}", False)
    ]
    if st.button(
        "✖ 批量删除选中配置",
        type="secondary",
        disabled=not selected_ids,
        key="bulk_delete_exports_btn",
    ):
        deleted = 0
        failed = 0
        for export_id in selected_ids:
            try:
                api.delete_export_config(export_id)
                st.session_state[f"export_select_{export_id}"] = False
                deleted += 1
            except Exception as e:
                st.error(f"删除配置 {export_id} 失败：{e}")
                failed += 1
        st.success(f"批量删除完成：成功 {deleted}，失败 {failed}")
        st.rerun()

    if not rows:
        st.info("暂无导出配置")
    else:
        header = st.columns([0.8, 0.8, 1.0, 2.0, 1.2, 2.0, 1.0, 1.0, 1.0])
        header[0].markdown("**选中**")
        header[1].markdown("**ID**")
        header[2].markdown("**sort**")
        header[3].markdown("**名称**")
        header[4].markdown("**格式**")
        header[5].markdown("**文件名模板**")
        header[6].markdown("**启用**")
        header[7].markdown("**查看/修改**")
        header[8].markdown("**删除**")

        for r in rows:
            export_id = int(r["id"])
            row = st.columns([0.8, 0.8, 1.0, 2.0, 1.2, 2.0, 1.0, 1.0, 1.0])
            row[0].checkbox(
                "选择",
                key=f"export_select_{export_id}",
                value=st.session_state.get(f"export_select_{export_id}", False),
                label_visibility="collapsed",
            )
            row[1].write(export_id)
            row[2].write(int(r.get("sort") or 0))
            row[3].write(r.get("name", ""))
            row[4].write(r.get("format", ""))
            row[5].write(r.get("filename_template", ""))
            row[6].write("✅" if bool(r.get("is_active", True)) else "❌")
            if row[7].button(
                "查看/修改",
                key=f"export_edit_btn_{export_id}",
                use_container_width=True,
            ):
                _edit_export_dialog(r)
            if row[8].button(
                "删除", key=f"export_del_btn_{export_id}", use_container_width=True
            ):
                try:
                    api.delete_export_config(export_id)
                    st.success(f"已删除配置 {export_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")


with tab_add:
    st.markdown("### 添加导出配置")
    with st.form("create_export_cfg_form"):
        name = st.text_input("name（唯一）")
        fmt = st.selectbox("format", options=["csv", "xlsx", "txt", "pdf"])
        filename_template = st.text_input(
            "filename_template", value="common_result_{date}"
        )
        sort = st.number_input(
            "sort（越小越靠前/默认）", min_value=0, max_value=100000, value=0, step=1
        )
        is_active = st.checkbox("is_active", value=True)
        options_json = st.text_area("options_json（JSON）", value="{}", height=180)
        if st.form_submit_button("创建配置", type="primary"):
            try:
                opts = json.loads(options_json) if options_json.strip() else {}
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            payload = {
                "name": name,
                "format": fmt,
                "filename_template": filename_template,
                "sort": int(sort),
                "options_json": opts,
                "is_active": is_active,
            }
            try:
                api.create_export_config(payload)
                st.success("已创建")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")
