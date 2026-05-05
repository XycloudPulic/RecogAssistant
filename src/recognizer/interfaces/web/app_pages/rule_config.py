# SPDX-License-Identifier: MIT

"""规则配置页面"""

import json

import streamlit as st
from utils.api_client import OCRAPIClient

api = OCRAPIClient()

st.title("📐 数据规则")
st.markdown("数据规则支持单行弹窗查看/修改、单行删除、勾选多行后批量删除。")

tab_rulesets, tab_fields, tab_items, tab_test = st.tabs(
    ["📚 数据集合", "🧾 数据项", "🧩 提取规则", "🧪 正则测试"]
)

try:
    rulesets = api.list_rulesets()
except Exception as e:
    st.error(f"加载失败：{e}")
    rulesets = []

if "active_ruleset_id" not in st.session_state:
    st.session_state.active_ruleset_id = int(rulesets[0]["id"]) if rulesets else None


@st.dialog("查看/修改数据规则")
def _edit_ruleset_dialog(ruleset: dict) -> None:
    with st.form(f"edit_ruleset_{ruleset['id']}"):
        name = st.text_input("名称", value=ruleset.get("name", ""))
        description = st.text_area(
            "描述", value=ruleset.get("description", ""), height=100
        )
        is_active = st.checkbox("启用", value=bool(ruleset.get("is_active", True)))
        if st.form_submit_button("保存单行修改", type="primary"):
            try:
                api.update_ruleset(
                    int(ruleset["id"]),
                    {"name": name, "description": description, "is_active": is_active},
                )
                st.success("已更新")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")


@st.dialog("添加数据规则")
def _create_ruleset_dialog() -> None:
    with st.form("create_ruleset_dialog_form"):
        create_name = st.text_input("名称")
        create_desc = st.text_area("描述", height=100)
        create_active = st.checkbox("启用", value=True)
        if st.form_submit_button("创建数据规则", type="primary"):
            try:
                api.create_ruleset(
                    {
                        "name": create_name,
                        "description": create_desc,
                        "is_active": create_active,
                    }
                )
                st.success("已创建")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")


with tab_rulesets:
    st.markdown("### 已配置数据集合")
    if not rulesets:
        st.info("暂无数据集合")
    else:
        header = st.columns([0.8, 0.8, 2.2, 3.0, 1.0, 1.0, 1.0])
        header[0].markdown("**选中**")
        header[1].markdown("**ID**")
        header[2].markdown("**名称（数据集合）**")
        header[3].markdown("**描述**")
        header[4].markdown("**启用**")
        header[5].markdown("**查看/修改**")
        header[6].markdown("**删除**")

        for r in rulesets:
            rid = int(r["id"])
            row = st.columns([0.8, 0.8, 2.2, 3.0, 1.0, 1.0, 1.0])
            row[0].checkbox(
                "选择",
                key=f"ruleset_select_{rid}",
                value=st.session_state.get(f"ruleset_select_{rid}", False),
                label_visibility="collapsed",
            )
            row[1].write(rid)
            row[2].write(r.get("name", ""))
            row[3].write(r.get("description", ""))
            row[4].write("✅" if bool(r.get("is_active", True)) else "❌")
            if row[5].button(
                "查看/修改", key=f"ruleset_edit_btn_{rid}", use_container_width=True
            ):
                _edit_ruleset_dialog(r)
            if row[6].button(
                "删除", key=f"ruleset_del_btn_{rid}", use_container_width=True
            ):
                try:
                    api.delete_ruleset(rid)
                    st.success(f"已删除数据集合 {rid}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")

    selected_ids = [
        int(r["id"])
        for r in rulesets
        if st.session_state.get(f"ruleset_select_{int(r['id'])}", False)
    ]
    c_add, c_bulk = st.columns([1, 2])
    if c_add.button("➕ 添加数据集合", type="primary", use_container_width=True):
        _create_ruleset_dialog()
    if c_bulk.button(
        "✖ 批量删除选中数据集合",
        type="secondary",
        disabled=not selected_ids,
        use_container_width=True,
        key="bulk_delete_rulesets_btn",
    ):
        deleted = 0
        failed = 0
        for ruleset_id in selected_ids:
            try:
                api.delete_ruleset(ruleset_id)
                st.session_state[f"ruleset_select_{ruleset_id}"] = False
                deleted += 1
            except Exception as e:
                st.error(f"删除数据集合 {ruleset_id} 失败：{e}")
                failed += 1
        st.success(f"批量删除完成：成功 {deleted}，失败 {failed}")
        st.rerun()


with tab_fields:
    st.markdown("### 数据项（业务字段定义）")
    ruleset_opts = [f"{r['id']} · {r['name']}" for r in rulesets] or ["(none)"]
    sel = st.selectbox(
        "选择数据集合", options=ruleset_opts, key="ruleset_fields_selectbox"
    )
    if sel == "(none)":
        st.info("请先在“数据集合”里添加数据集合")
        st.stop()
    rid = int(sel.split("·")[0].strip())
    st.caption(f"当前数据集合 ID: {rid}")

    try:
        fields = api.list_data_fields(rid)
    except Exception as e:
        st.error(f"加载失败：{e}")
        fields = []

    try:
        items = api.list_rule_items(rid)
    except Exception:
        items = []
    item_opts = ["(none)"] + [
        f"{int(it['id'])} · {it.get('item_type', '')} · {it.get('pattern') or ''}"
        for it in items
    ]

    def _opt_from_id(x):
        if not x:
            return "(none)"
        for it in items:
            if int(it.get("id")) == int(x):
                return f"{int(it['id'])} · {it.get('item_type', '')} · {it.get('pattern') or ''}"
        return "(none)"

    st.caption(
        "这里定义的是“业务字段集合”里的每个字段（例如：发票号码/开票日期/金额…）。模板只关联集合，不在模板里重复维护字段定义。"
    )
    if fields:
        # Attach human-friendly extractor selection display.
        rows = []
        for f in fields:
            rows.append(
                {
                    "id": f.get("id"),
                    "field_key": f.get("field_key"),
                    "field_label": f.get("field_label"),
                    "field_type": f.get("field_type"),
                    "order_index": f.get("order_index"),
                    "rule_item_id": f.get("rule_item_id"),
                    "提取规则(数据项)": _opt_from_id(f.get("rule_item_id")),
                    "is_active": f.get("is_active"),
                }
            )
        st.dataframe(rows, use_container_width=True)
    else:
        st.dataframe(fields, use_container_width=True)

    with st.form("data_field_form"):
        st.markdown("#### 添加/更新数据项（业务字段）")
        field_key = st.text_input("field_key（唯一键，例如 invoice_number）", value="")
        field_label = st.text_input("field_label（显示名，例如 发票号码）", value="")
        field_type = st.selectbox(
            "field_type", options=["string", "number", "date"], index=0
        )
        order_index = st.number_input(
            "order_index", value=0, step=1, min_value=0, max_value=10_000
        )
        sel_item = st.selectbox(
            "字段提取规则（选择一个已创建的提取规则）",
            options=item_opts,
            index=0,
            help="先去“提取规则”里添加好规则，再回来为字段选择。",
        )
        rule_item_id = (
            None if sel_item == "(none)" else int(sel_item.split("·")[0].strip())
        )
        is_active = st.checkbox("启用", value=True)

        c1, c2, c3 = st.columns(3)
        add = c1.form_submit_button("添加字段", type="primary")
        update = c2.form_submit_button("更新字段（按 field_id）")
        delete = c3.form_submit_button("删除字段（按 field_id）")
        field_id = st.number_input(
            "field_id（用于更新/删除）", value=0, step=1, min_value=0
        )

        payload = {
            "field_key": str(field_key or "").strip(),
            "field_label": str(field_label or "").strip(),
            "field_type": str(field_type or "string"),
            "order_index": int(order_index),
            "rule_item_id": rule_item_id,
            "is_active": bool(is_active),
        }

        if add:
            try:
                api.create_data_field(rid, payload)
                st.success("已添加字段")
                st.rerun()
            except Exception as e:
                st.error(f"添加失败：{e}")
        if update:
            try:
                api.update_data_field(rid, int(field_id), payload)
                st.success("已更新字段")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")
        if delete:
            try:
                api.delete_data_field(rid, int(field_id))
                st.success("已删除字段")
                st.rerun()
            except Exception as e:
                st.error(f"删除失败：{e}")


with tab_items:
    st.markdown("### 提取规则（Data items）")
    ruleset_opts = [f"{r['id']} · {r['name']}" for r in rulesets] or ["(none)"]
    sel = st.selectbox(
        "选择数据集合", options=ruleset_opts, key="ruleset_items_selectbox"
    )
    if sel == "(none)":
        st.info("请先在“数据集合”里添加数据集合")
        st.stop()
    rid = int(sel.split("·")[0].strip())
    st.session_state.active_ruleset_id = rid

    st.caption(f"当前数据集合 ID: {rid}")
    try:
        items = api.list_rule_items(rid)
    except Exception as e:
        st.error(f"加载失败：{e}")
        items = []

    st.caption(
        "提取规则类型（item_type）：regex / keyword / key_value / region / script"
    )
    st.dataframe(items, use_container_width=True)

    with st.form("rule_item_form"):
        item_type = st.selectbox(
            "提取规则类型（item_type）",
            options=["regex", "keyword", "key_value", "region", "script"],
        )
        pattern = st.text_input("pattern（regex/keyword 等；script 可留空）", value="")
        priority = st.number_input("priority（优先级）", value=0, step=1)
        script_ref = ""
        entrypoint = "extract"
        timeout_ms = 800
        input_mode = "full_text"
        if item_type == "script":
            st.markdown("#### Script 数据项（方案B：脚本存文件）")
            c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
            script_ref = c1.text_input(
                "script_ref（相对 scripts/extractors/ 的 .py 文件）",
                value="example_invoice_number.py",
                help="示例：example_invoice_number.py（对应 scripts/extractors/example_invoice_number.py）",
            )
            entrypoint = c2.text_input("entrypoint（函数名）", value="extract")
            timeout_ms = c3.number_input(
                "timeout_ms（毫秒）", value=800, step=50, min_value=50, max_value=10_000
            )
            input_mode = st.selectbox(
                "input（传给脚本的输入）", options=["full_text", "line"], index=0
            )
            st.caption(
                "脚本函数签名：def extract(ctx) -> str，其中 ctx.full_text / ctx.raw_data / ctx.config 可用。"
            )

            derived_config = {
                "script_ref": script_ref,
                "entrypoint": entrypoint,
                "timeout_ms": int(timeout_ms),
                "input": input_mode,
            }
            with st.expander("高级：config_json（可选覆盖）", expanded=False):
                config_json = st.text_area(
                    "config_json（JSON）",
                    value=json.dumps(derived_config, ensure_ascii=False),
                    height=140,
                )
        else:
            config_json = st.text_area("config_json（JSON）", value="{}", height=120)

        c1, c2, c3 = st.columns(3)
        add = c1.form_submit_button("添加数据项", type="primary")
        update = c2.form_submit_button("更新数据项（按 item_id）")
        delete = c3.form_submit_button("删除数据项（按 item_id）")
        item_id = st.number_input("item_id（用于更新/删除）", value=0, step=1)

        if add:
            try:
                api.create_rule_item(
                    rid,
                    {
                        "item_type": item_type,
                        "pattern": pattern or None,
                        "priority": int(priority),
                        "config_json": json.loads(config_json or "{}"),
                    },
                )
                st.success("已添加数据项")
                st.rerun()
            except Exception as e:
                st.error(f"添加失败：{e}")
        if update:
            try:
                api.update_rule_item(
                    rid,
                    int(item_id),
                    {
                        "item_type": item_type,
                        "pattern": pattern or None,
                        "priority": int(priority),
                        "config_json": json.loads(config_json or "{}"),
                    },
                )
                st.success("已更新数据项")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败：{e}")
        if delete:
            try:
                api.delete_rule_item(rid, int(item_id))
                st.success("已删除数据项")
                st.rerun()
            except Exception as e:
                st.error(f"删除失败：{e}")


with tab_test:
    st.markdown("### 正则表达式测试")
    test_text = st.text_area(
        "测试文本",
        value="发票号码：26112000000827373241\n开票日期：2026年03月04日\n金额：¥105.31\n税额：13.69",
        height=150,
    )
    test_pattern = st.text_input("正则表达式", value=r"发票号码[：:]\s*([A-Z0-9]{20})")
    if st.button("测试匹配", type="primary"):
        try:
            out = api.regex_test(test_pattern, test_text)
            if out.get("matched"):
                st.success(f"匹配成功：groups={out.get('groups')}")
                st.code(out.get("match") or "")
            else:
                st.warning("未匹配到内容")
        except Exception as e:
            st.error(str(e))
