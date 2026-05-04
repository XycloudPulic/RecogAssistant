# SPDX-License-Identifier: MIT

APP_NAME = "发票识别助手"
APP_VERSION = "V0.1"

# Sidebar page order and display metadata.
# Update this list to change navigation order without renaming files.
PAGE_NAVIGATION = [
    {"file": "recognition.py", "title": "发票识别", "icon": "📄", "order": 10},
    {"file": "node_config.py", "title": "节点配置", "icon": "⚙️", "order": 20},
    {"file": "template_manager.py", "title": "模板管理", "icon": "📋", "order": 30},
    {"file": "validator_config.py", "title": "校验规则", "icon": "🛡️", "order": 35},
    {"file": "rule_config.py", "title": "数据规则", "icon": "📐", "order": 40},
    {"file": "llm_config.py", "title": "LLM配置", "icon": "🤖", "order": 50},
    {"file": "export_config.py", "title": "导出配置", "icon": "📤", "order": 60},
    {"file": "workflow.py", "title": "调度流程", "icon": "🧩", "order": 15},
    {"file": "debug_log.py", "title": "调试日志", "icon": "📝", "order": 80},
    {"file": "about.py", "title": "关于", "icon": "ℹ️", "order": 90},
]
