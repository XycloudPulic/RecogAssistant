# SPDX-License-Identifier: MIT

"""版本信息页面"""

import streamlit as st
from app_meta import APP_NAME, APP_VERSION

# 页面配置
st.set_page_config(page_title="关于", page_icon="ℹ️", layout="wide")

st.title("ℹ️ 关于")
st.markdown("---")

st.markdown(f"""
### 📄 名称
{APP_NAME}

### 版本
{APP_VERSION}
""")

st.markdown("""
### 功能特性清单

- ✅ 发票图片/PDF 识别：多引擎并行识别、字段一致性验证、节点详情可视化
- ✅ 调度流程（Workflow）：维护节点组合与执行顺序，支持设置默认流程
- ✅ 节点配置：节点启用/顺序/参数管理（可扩展新增节点）
- ✅ 模板管理：模板与字段维护，用于区域/结构化提取
- ✅ 数据规则：字段提取规则维护与测试
- ✅ LLM 配置：可选的大模型解析节点配置
- ✅ 导出配置：导出模板与参数管理，支持 sort 排序决定默认展示
- ✅ 识别记录：本地 jobs/runs 保存与 rerun（如已启用）
""")
