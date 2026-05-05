# SPDX-License-Identifier: MIT

"""识别助手V0.1 - Streamlit主应用入口（可配置页面顺序）"""

import sys
from pathlib import Path

import streamlit as st
from app_meta import APP_NAME, APP_VERSION, PAGE_NAVIGATION

from recognizer.common.config.settings import Settings

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_home() -> None:
    """Render the home page content."""
    st.title(f"📄 {APP_NAME}")
    st.markdown(f"欢迎使用 {APP_NAME}{APP_VERSION}")

    col1, col2 = st.columns(2)
    with col1:
        st.info("请从左侧菜单选择功能页面")

    with col2:
        st.markdown(
            """
        **功能说明:**
        - 发票识别：上传图片/PDF 识别，可查看节点详情、引擎全量结果与一致性验证
        - 调度流程：维护“节点组合与顺序”，支持设置默认流程（不选时自动使用默认）
        - 节点配置：管理识别节点启用/顺序/参数
        - 模板管理：维护模板与字段（用于区域/结构化提取）
        - 数据规则：维护字段提取规则与测试
        - LLM配置：配置大模型节点（可选）
        - 导出配置：管理导出模板与参数，支持 sort 排序决定默认展示
        - 调试日志：查看运行日志与排查问题
        """
        )

    st.markdown("---")
    st.markdown("### API连接状态")

    try:
        import requests

        base_url = str(Settings.get("api.base_url", "http://127.0.0.1:8000")).rstrip(
            "/"
        )
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            st.success("✅ OCR服务已连接")
        else:
            st.warning("⚠️ OCR服务响应异常")
    except Exception:
        base_url = str(Settings.get("api.base_url", "http://127.0.0.1:8000")).rstrip(
            "/"
        )
        st.error(f"❌ 无法连接OCR服务 ({base_url})")
        st.info(
            "请确保OCR服务正在运行: "
            "`uvicorn recognizer.interfaces.api.app:app --host 127.0.0.1 --port 8000`"
        )


def _build_navigation_pages() -> list:
    """Build Streamlit page objects from configuration."""
    # NOTE: We intentionally keep Streamlit's auto-multipage folder disabled by
    # naming it `app_pages` (not `pages`), otherwise Streamlit will render a
    # second default sidebar navigation based on filenames.
    pages_dir = Path(__file__).parent / "app_pages"
    # Home navigation title: hide version, show short name.
    pages = [st.Page(_render_home, title="发票助手", icon="🏠", default=True)]
    required_keys = {"file", "title", "icon", "order"}
    for idx, page in enumerate(PAGE_NAVIGATION):
        missing_keys = required_keys - set(page.keys())
        if missing_keys:
            missing = ", ".join(sorted(missing_keys))
            st.error(f"PAGE_NAVIGATION 第 {idx + 1} 项缺少字段: {missing}")
            st.stop()

    sorted_navigation = sorted(
        PAGE_NAVIGATION,
        key=lambda page: (page["order"], page["title"]),
    )
    for page in sorted_navigation:
        pages.append(
            st.Page(
                str(pages_dir / page["file"]),
                title=page["title"],
                icon=page["icon"],
            )
        )
    return pages


st.markdown(
    """
<style>
  section[data-testid="stSidebar"] { padding-top: 8px; }
  section[data-testid="stSidebar"] .stMarkdown { margin-bottom: 0.25rem; }
</style>
""",
    unsafe_allow_html=True,
)

if not hasattr(st, "Page") or not hasattr(st, "navigation"):
    st.error("当前 Streamlit 版本不支持可配置导航。请升级到较新版本后重试。")
    st.stop()

navigation = st.navigation(_build_navigation_pages(), position="sidebar")
navigation.run()
