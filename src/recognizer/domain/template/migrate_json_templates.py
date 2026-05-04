# SPDX-License-Identifier: MIT

"""JSON模板迁移到SQLite脚本"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent))

from recognizer.template.database import (
    get_db_connection,
    init_database,
)

# JSON模板目录
JSON_DIR = Path(__file__).parent.parent / "parsers" / "paddleocr" / "template" / "data"


def migrate_json_templates():
    """迁移JSON模板到SQLite"""

    # 初始化数据库
    init_database()

    conn = get_db_connection()
    cursor = conn.cursor()

    migrated_count = 0

    # 遍历所有JSON文件
    for json_file in JSON_DIR.glob("*.json"):
        print(f"\n处理模板: {json_file.name}")

        # 读取JSON数据
        with open(json_file, "r", encoding="utf-8") as f:
            template_data = json.load(f)

        # 检查是否已存在
        cursor.execute(
            "SELECT id FROM invoice_templates WHERE name = ?",
            (template_data.get("template_name"),),
        )
        existing = cursor.fetchone()

        if existing:
            print(f"  ⚠️  模板已存在，跳过: {template_data.get('template_name')}")
            continue

        # 插入模板主表
        cursor.execute(
            """
            INSERT INTO invoice_templates (name, engine, parser, field_count, is_active)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                template_data.get("template_name"),
                "paddleocr",
                "coordinate",  # JSON模板使用坐标解析
                len(template_data.get("fields", {})),
                1,
            ),
        )

        template_db_id = cursor.lastrowid

        # 插入识别规则（match_keywords）
        match_keywords = template_data.get("match_keywords", [])
        if match_keywords:
            cursor.execute(
                """
                INSERT INTO template_rules (template_id, rule_type, rule_value, priority)
                VALUES (?, ?, ?, ?)
            """,
                (template_db_id, "keyword", json.dumps(match_keywords), 1),
            )
            print(f"  ✅ 添加识别规则: {match_keywords}")

        # 插入字段配置
        fields = template_data.get("fields", {})
        for field_name, field_config in fields.items():
            # 坐标配置
            parser_config = {
                "type": "coordinate",
                "x1": field_config.get("x1", 0),
                "y1": field_config.get("y1", 0),
                "x2": field_config.get("x2", 0),
                "y2": field_config.get("y2", 0),
                "image_width": template_data.get("image_width", 1430),
                "image_height": template_data.get("image_height", 881),
            }

            # 字段标签映射
            field_labels = {
                "invoice_number": "发票号码",
                "date": "开票日期",
                "buyer": "购买方名称",
                "buyer_tax_id": "购买方税号",
                "seller": "销售方名称",
                "seller_tax_id": "销售方税号",
                "item_name": "货物名称",
                "amount": "金额",
                "tax": "税额",
                "total_amount": "价税合计",
            }

            cursor.execute(
                """
                INSERT INTO template_fields
                (template_id, field_name, field_label, field_type, parser_config, order_index)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    template_db_id,
                    field_name,
                    field_labels.get(field_name, field_name),
                    "string",
                    json.dumps(parser_config),
                    list(fields.keys()).index(field_name),
                ),
            )

        migrated_count += 1
        print(
            f"  ✅ 模板迁移成功: {template_data.get('template_name')} (ID: {template_db_id})"
        )
        print(f"     字段数: {len(fields)}")

    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"迁移完成! 共迁移 {migrated_count} 个模板")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    migrate_json_templates()
