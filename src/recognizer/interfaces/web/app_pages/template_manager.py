# SPDX-License-Identifier: MIT

"""模板管理页面"""

import json

import streamlit as st
from app_meta import APP_NAME, APP_VERSION
from utils.api_client import OCRAPIClient

api = OCRAPIClient()

st.set_page_config(
    page_title=f"{APP_NAME}{APP_VERSION} · 模板管理",
    page_icon="📋",
    layout="wide",
)

st.title("📋 模板管理")
st.markdown("支持单行弹窗查看/修改、单行删除、勾选多行后批量删除。")

tab_list, tab_add = st.tabs(["📋 模板列表（管理）", "➕ 添加模板"])

try:
    templates = api.get_templates()
except Exception as e:
    st.error(f"加载失败：{e}")
    templates = []

try:
    rulesets = api.list_rulesets(active_only=False)
except Exception:
    rulesets = []

try:
    validators = api.list_validators(active_only=False)
except Exception:
    validators = []


@st.dialog("查看/修改模板")
def _edit_template_dialog(template_id: int) -> None:
    tpl = api.get_template(template_id)
    with st.form(f"edit_template_{template_id}"):
        name = st.text_input("模板名称", value=tpl.get("name", ""))
        # engine/parser are not user-facing (reserved for future multi-engine routing)
        is_active = st.checkbox("启用", value=bool(tpl.get("is_active", True)))
        if not rulesets:
            st.warning("请先在“数据规则”里创建数据集合（必选）。")
            st.stop()
        rs_opts = [f"{r['id']} · {r['name']}" for r in rulesets]
        cur_rs = tpl.get("ruleset_id")
        rs_default = (
            f"{cur_rs} · {next((r['name'] for r in rulesets if int(r['id']) == int(cur_rs)), '')}"
            if cur_rs
            else rs_opts[0]
        )
        rs_index = rs_opts.index(rs_default) if rs_default in rs_opts else 0
        sel_rs = st.selectbox("关联数据规则（必选）", options=rs_opts, index=rs_index)
        ruleset_id = int(sel_rs.split("·")[0].strip())

        rule_items = []
        try:
            rule_items = api.list_rule_items(int(ruleset_id))
        except Exception:
            rule_items = []
        data_fields = []
        try:
            data_fields = api.list_data_fields(int(ruleset_id))
        except Exception:
            data_fields = []

        # Existing validator bindings from template_fields (field_name -> validator_ids)
        existing_fields = tpl.get("fields") or []
        existing_validator_map: dict[str, list[int]] = {}
        for f in existing_fields:
            try:
                fn = str(f.get("field_name") or "")
                if not fn:
                    continue
                v_ids = f.get("validator_ids") or []
                if isinstance(v_ids, list):
                    existing_validator_map[fn] = [
                        int(x) for x in v_ids if x is not None
                    ]
            except Exception:
                continue

        validator_opts = {
            f"{v['id']} · {v.get('validator_type')} · {v.get('name')}": int(v["id"])
            for v in (validators or [])
        }
        validator_labels = list(validator_opts.keys())
        id_to_label = {vid: label for label, vid in validator_opts.items()}

        with st.expander("字段校验绑定（为每个字段选择 validators）", expanded=False):
            if not validator_opts:
                st.info("暂无校验规则，请先在“校验规则”页面创建。")
            elif not data_fields:
                st.info("该数据规则暂无数据项（业务字段）")
            else:
                st.caption(
                    "提示：这里配置的是字段合法性校验（validation），不影响字段抽取规则。"
                )
                for df in data_fields:
                    key = str(df.get("field_key") or "")
                    label = str(df.get("field_label") or key)
                    default_ids = existing_validator_map.get(key, [])
                    default_labels = [
                        id_to_label[i] for i in default_ids if i in id_to_label
                    ]
                    sel = st.multiselect(
                        f"{label}（{key}）",
                        options=validator_labels,
                        default=default_labels,
                        key=f"tmpl_{template_id}_field_{key}_validators",
                    )
                    existing_validator_map[key] = [int(validator_opts[x]) for x in sel]

        with st.expander("查看：该数据规则包含的数据项（业务字段）", expanded=False):
            if not data_fields:
                st.info("该数据规则暂无数据项（业务字段）")
            else:
                st.dataframe(data_fields, use_container_width=True)

        with st.expander("查看：该数据规则包含的提取规则", expanded=False):
            if not rule_items:
                st.info("该数据规则暂无提取规则")
            else:
                st.dataframe(rule_items, use_container_width=True)

        st.caption(
            "说明：下面的“匹配规则”用于自动判定这张票属于哪个模板（模板匹配/类型判断），不是字段提取规则。"
        )
        rules_json = st.text_area(
            "匹配规则（用于判定模板，JSON）",
            value=json.dumps(tpl.get("rules", []), ensure_ascii=False, indent=2),
            height=180,
        )
        if st.form_submit_button("保存单行修改", type="primary"):
            try:
                rules = json.loads(rules_json) if rules_json.strip() else []
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            payload = {
                "name": name,
                "engine": tpl.get("engine", "paddleocr"),
                "parser": tpl.get("parser", "keyword"),
                "sample_image": tpl.get("sample_image"),
                "is_active": is_active,
                "ruleset_id": ruleset_id,
                # Store validator bindings in template_fields even when ruleset_id is used.
                "fields": [
                    {
                        "field_name": str(df.get("field_key") or ""),
                        "field_label": str(
                            df.get("field_label") or df.get("field_key") or ""
                        ),
                        "field_type": str(df.get("field_type") or "string"),
                        "extractor_type": "keyword",
                        "extractor_config": {},
                        "rule_item_id": df.get("rule_item_id"),
                        "validation_rule": None,
                        "validator_ids": existing_validator_map.get(
                            str(df.get("field_key") or ""), []
                        ),
                        "order_index": int(df.get("order_index") or 0),
                    }
                    for df in (data_fields or [])
                    if str(df.get("field_key") or "")
                ],
                "rules": rules,
            }
            try:
                api.update_template(template_id, payload)
                st.success("已更新")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")


with tab_list:
    st.markdown("### 已配置模板")
    selected_ids = [
        int(t["id"])
        for t in templates
        if st.session_state.get(f"template_select_{int(t['id'])}", False)
    ]
    if st.button(
        "✖ 批量删除选中模板",
        type="secondary",
        disabled=not selected_ids,
        key="bulk_delete_templates_btn",
    ):
        deleted = 0
        failed = 0
        for template_id in selected_ids:
            try:
                api.delete_template(template_id)
                st.session_state[f"template_select_{template_id}"] = False
                deleted += 1
            except Exception as e:
                st.error(f"删除模板 {template_id} 失败：{e}")
                failed += 1
        st.success(f"批量删除完成：成功 {deleted}，失败 {failed}")
        st.rerun()

    if not templates:
        st.info("暂无模板")
    else:
        header = st.columns([0.8, 0.8, 2.4, 1.6, 1.0, 1.0, 1.0])
        header[0].markdown("**选中**")
        header[1].markdown("**ID**")
        header[2].markdown("**名称**")
        header[3].markdown("**数据规则**")
        header[4].markdown("**启用**")
        header[5].markdown("**查看/修改**")
        header[6].markdown("**删除**")

        for t in templates:
            template_id = int(t["id"])
            row = st.columns([0.8, 0.8, 2.4, 1.6, 1.0, 1.0, 1.0])
            row[0].checkbox(
                "选择",
                key=f"template_select_{template_id}",
                value=st.session_state.get(f"template_select_{template_id}", False),
                label_visibility="collapsed",
            )
            row[1].write(template_id)
            row[2].write(t.get("name", ""))
            rid = t.get("ruleset_id")
            row[3].write("" if not rid else f"{rid}")
            row[4].write("✅" if bool(t.get("is_active", True)) else "❌")
            if row[5].button(
                "查看/修改",
                key=f"template_edit_btn_{template_id}",
                use_container_width=True,
            ):
                _edit_template_dialog(template_id)
            if row[6].button(
                "删除", key=f"template_del_btn_{template_id}", use_container_width=True
            ):
                try:
                    api.delete_template(template_id)
                    st.success(f"已删除模板 {template_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")


with tab_add:
    st.markdown("### 添加模板")
    with st.form("create_template_form"):
        name = st.text_input("模板名称")
        # engine/parser are not user-facing; use stable defaults
        is_active = st.checkbox("启用", value=True)
        if not rulesets:
            st.warning("请先在“数据规则”里创建数据集合（必选）。")
            st.stop()
        rs_opts = [f"{r['id']} · {r['name']}" for r in rulesets]
        sel_rs = st.selectbox("关联数据规则（必选）", options=rs_opts)
        ruleset_id = int(sel_rs.split("·")[0].strip())

        st.caption(
            "说明：下面的“匹配规则”用于自动判定这张票属于哪个模板（模板匹配/类型判断），不是字段提取规则。"
        )
        rules_json = st.text_area(
            "匹配规则（用于判定模板，JSON）", value="[]", height=180
        )
        if st.form_submit_button("创建模板", type="primary"):
            try:
                rules = json.loads(rules_json) if rules_json.strip() else []
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
                st.stop()
            payload = {
                "name": name,
                "engine": "paddleocr",
                "parser": "keyword",
                "sample_image": None,
                "is_active": is_active,
                "ruleset_id": ruleset_id,
                # fields are derived from data ruleset at runtime; do not manage here.
                "fields": [],
                "rules": rules,
            }
            try:
                api.create_template(payload)
                st.success("已创建")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")
