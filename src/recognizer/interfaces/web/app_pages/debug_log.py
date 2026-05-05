# SPDX-License-Identifier: MIT

"""调试日志页面"""

import time

import streamlit as st
from utils.api_client import OCRAPIClient

st.title("📝 调试日志")
st.markdown("查看 `logs/app.log` 的最新内容，支持按行数 tail、自动刷新、清空、导出。")

api = OCRAPIClient()

top = st.columns([1, 1, 1, 2])
lines = top[0].number_input(
    "显示最新行数 X", value=200, min_value=10, max_value=5000, step=10
)
refresh_sec = top[1].number_input(
    "自动刷新间隔 Y(s)", value=2, min_value=1, max_value=60, step=1
)
auto = top[2].checkbox("自动刷新", value=True)
keyword = top[3].text_input("过滤关键字（可选）", value="")

tool_cols = st.columns(3)
if tool_cols[0].button("清空日志", use_container_width=True):
    try:
        api_resp = __import__("requests").post(f"{api.base_url}/logs/clear", timeout=10)
        api_resp.raise_for_status()
        st.success("已清空")
    except Exception as e:
        st.error(str(e))

if tool_cols[1].button("导出日志", use_container_width=True):
    try:
        import requests

        r = requests.get(f"{api.base_url}/logs/download", timeout=20)
        r.raise_for_status()
        st.download_button(
            "下载日志", r.content, file_name="app.log", mime="text/plain"
        )
    except Exception as e:
        st.error(str(e))

if tool_cols[2].button("手动刷新", use_container_width=True):
    st.rerun()

st.markdown("---")
st.markdown("### 日志内容")


def _fetch_tail() -> str:
    import requests

    r = requests.get(
        f"{api.base_url}/logs/tail", params={"lines": int(lines)}, timeout=10
    )
    r.raise_for_status()
    return r.text or ""


try:
    text = _fetch_tail()
except Exception as e:
    st.error(f"无法读取日志：{e}")
    text = ""

if keyword.strip():
    filtered = []
    for ln in text.splitlines():
        if keyword in ln:
            filtered.append(ln)
    text = "\n".join(filtered)

st.text_area("app.log (tail)", value=text, height=520)

if auto:
    time.sleep(float(refresh_sec))
    st.rerun()
