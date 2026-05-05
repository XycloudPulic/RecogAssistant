# SPDX-License-Identifier: MIT

"""校验规则配置页面（validators）。"""

import json

import streamlit as st
from utils.api_client import OCRAPIClient

api = OCRAPIClient()

st.title("🛡️ 校验规则")
st.markdown(
    "校验规则可复用并可绑定到模板字段（`validator_ids`）。支持在线测试单个值是否通过。"
)

tab_list, tab_test = st.tabs(["📚 规则列表", "🧪 规则测试"])


@st.dialog("查看/修改校验规则")
def _edit_validator_dialog(v: dict) -> None:
    with st.form(f"edit_validator_{v['id']}"):
        name = st.text_input("名称", value=v.get("name", ""))
        validator_type = st.text_input(
            "类型（required/regex/amount/number/date/length/enum）",
            value=v.get("validator_type", ""),
        )
        cfg_text = st.text_area(
            "配置（JSON）",
            value=json.dumps(v.get("config_json") or {}, ensure_ascii=False, indent=2),
            height=180,
        )
        is_active = st.checkbox("启用", value=bool(v.get("is_active", True)))
        if st.form_submit_button("保存修改", type="primary"):
            try:
                cfg = json.loads(cfg_text or "{}")
            except Exception as e:
                st.error(f"配置 JSON 无效：{e}")
                return
            try:
                api.update_validator(
                    int(v["id"]),
                    {
                        "name": name,
                        "validator_type": validator_type,
                        "config_json": cfg,
                        "is_active": is_active,
                    },
                )
                st.success("已更新")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")


@st.dialog("添加校验规则")
def _create_validator_dialog() -> None:
    with st.form("create_validator_form"):
        name = st.text_input("名称")
        validator_type = st.selectbox(
            "类型",
            [
                "required",
                "regex",
                "amount",
                "number",
                "date",
                "length",
                "enum",
                "range",
            ],
            index=0,
        )
        cfg_text = st.text_area("配置（JSON）", value="{}", height=180)
        is_active = st.checkbox("启用", value=True)
        if st.form_submit_button("创建", type="primary"):
            try:
                cfg = json.loads(cfg_text or "{}")
            except Exception as e:
                st.error(f"配置 JSON 无效：{e}")
                return
            try:
                api.create_validator(
                    {
                        "name": name,
                        "validator_type": validator_type,
                        "config_json": cfg,
                        "is_active": is_active,
                    }
                )
                st.success("已创建")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")


with tab_list:
    cols = st.columns([1, 1, 1, 6])
    active_only = cols[0].checkbox("仅看启用", value=False)
    if cols[1].button("刷新"):
        st.rerun()
    if cols[2].button("新增", type="primary"):
        _create_validator_dialog()

    try:
        validators = api.list_validators(active_only=active_only)
    except Exception as e:
        st.error(f"加载失败：{e}")
        validators = []

    if not validators:
        st.info("暂无校验规则")
    else:
        header = st.columns([0.8, 0.8, 1.6, 4.0, 0.9, 1.4])
        header[0].markdown("**ID**")
        header[1].markdown("**启用**")
        header[2].markdown("**类型**")
        header[3].markdown("**名称**")
        header[4].markdown("**编辑**")
        header[5].markdown("**删除**")

        for v in validators:
            row = st.columns([0.8, 0.8, 1.6, 4.0, 0.9, 1.4])
            row[0].write(v.get("id"))
            row[1].write("✅" if v.get("is_active") else "—")
            row[2].code(str(v.get("validator_type") or ""), language=None)
            row[3].write(v.get("name") or "")
            if row[4].button("编辑", key=f"edit_{v['id']}"):
                _edit_validator_dialog(v)
            if row[5].button("删除", key=f"del_{v['id']}"):
                try:
                    api.delete_validator(int(v["id"]))
                    st.success("已删除")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")


with tab_test:
    st.markdown("### 单值测试")
    try:
        validators = api.list_validators(active_only=False)
    except Exception:
        validators = []
    opts = {
        f"{v['id']} · {v.get('validator_type')} · {v.get('name')}": int(v["id"])
        for v in validators
    }
    if not opts:
        st.info("暂无可测试的校验规则，请先在“规则列表”中创建。")
    else:
        sel = st.selectbox("选择规则", list(opts.keys()))
        value = st.text_input("待校验的值", value="")
        if st.button("运行测试", type="primary"):
            try:
                out = api.test_validator(
                    {"validator_id": int(opts[sel]), "value": value}
                )
                st.json(out)
            except Exception as e:
                st.error(f"测试失败：{e}")
