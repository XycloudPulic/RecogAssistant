-- RecogAssistant - initial seed data (DML). Run after init_recognition_db.sql.
--
-- 默认票据：电子发票（普通发票）（数电票）。抽取购销方、项目名称（*…*）、合计金额/税额、价税合计、备注、开票人；
-- 不抽取明细列（单价/数量/税率等），不适配出行人附表（另模板处理）。
-- config / runtime_*：TemplateManager + FieldExtractionEngine（code 必须为 cfg_{模板id}）
--
-- 说明：仅升级本文件不会自动重跑种子；若已有库需 UPDATE 模板字段或重建库。

BEGIN;

-- ---------------------------------------------------------------------------
-- schema_migrations
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (2);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (3);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (4);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (5);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (6);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (7);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (8);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (9);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (10);

-- ---------------------------------------------------------------------------
-- rulesets + rule_items（文档特征，可供规则集 UI / 后续 data_field 绑定）
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO rulesets(id, name, description, is_active)
VALUES (
  1,
  '电子发票（普通发票）',
  '数电普票：购销方、项目名称、合计金额与税额、价税合计（大小写）、备注、开票人',
  1
);

INSERT OR IGNORE INTO rule_items(id, ruleset_id, item_type, pattern, config_json, priority, is_active)
VALUES (1, 1, 'keyword', '电子发票（普通发票）', '{}', 100, 1);

INSERT OR IGNORE INTO rule_items(id, ruleset_id, item_type, pattern, config_json, priority, is_active)
VALUES (2, 1, 'keyword', '电子发票', '{}', 80, 1);

INSERT OR IGNORE INTO rule_items(id, ruleset_id, item_type, pattern, config_json, priority, is_active)
VALUES (3, 1, 'keyword', '旅客运输服务', '{}', 40, 1);

INSERT OR IGNORE INTO rule_items(id, ruleset_id, item_type, pattern, config_json, priority, is_active)
VALUES (4, 1, 'keyword', '住宿服务', '{}', 40, 1);

-- ---------------------------------------------------------------------------
-- validators（与 ValidationEngine 类型一致）
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO validators(id, name, validator_type, config_json, is_active)
VALUES (1, '数电发票号码（20位数字）', 'regex', '{"pattern":"^[0-9]{20}$"}', 1);

INSERT OR IGNORE INTO validators(id, name, validator_type, config_json, is_active)
VALUES (2, '统一社会信用代码（18位）', 'regex', '{"pattern":"^[0-9A-Z]{18}$"}', 1);

INSERT OR IGNORE INTO validators(id, name, validator_type, config_json, is_active)
VALUES (3, '金额小数', 'amount', '{}', 1);

INSERT OR IGNORE INTO validators(id, name, validator_type, config_json, is_active)
VALUES (4, '数量（非负整数）', 'number', '{"integer":true,"min":0}', 1);

-- ---------------------------------------------------------------------------
-- data_fields（与模板字段 field_key 对齐）
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (1, 1, 'invoice_number', '发票号码', 'string', 10, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (2, 1, 'issue_date', '开票日期', 'date', 20, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (3, 1, 'buyer_name', '购买方名称', 'string', 30, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (4, 1, 'buyer_tax_id', '购买方纳税人识别号', 'string', 40, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (5, 1, 'seller_name', '销售方名称', 'string', 50, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (6, 1, 'seller_tax_id', '销售方纳税人识别号', 'string', 60, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (7, 1, 'item_name', '项目名称', 'string', 70, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (8, 1, 'subtotal_amount', '合计金额', 'amount', 80, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (9, 1, 'subtotal_tax', '合计税额', 'amount', 90, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (10, 1, 'total_amount_cn', '价税合计（大写）', 'string', 100, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (11, 1, 'total_amount', '价税合计（小写）', 'amount', 110, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (12, 1, 'remark', '备注', 'string', 120, NULL, 1);
INSERT OR IGNORE INTO data_fields(id, ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) VALUES (13, 1, 'issuer', '开票人', 'string', 130, NULL, 1);

-- ---------------------------------------------------------------------------
-- templates（config DB）— engine/parser 与运行期 runtime_templates.engine 一致（paddle）
-- sample_image：可将默认样张放到 data/db/samples/ 后填路径
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO templates(
  id, name, engine, parser, field_count, sample_image, is_active, ruleset_id
) VALUES (
  1,
  '电子发票（普通发票）',
  'paddle',
  'electronic_invoice_general',
  13,
  NULL,
  1,
  1
);

-- 模板匹配规则：keyword 的 rule_value 须为 JSON 数组字符串（见 TemplateManager._match_keywords）
INSERT OR IGNORE INTO template_rules(id, template_id, rule_type, rule_value, priority)
VALUES (1, 1, 'keyword', '["电子发票（普通发票）","电子发票","电子发普通发票","国家税务总局","北京市税务局","旅客运输服务","住宿服务"]', 50);

INSERT OR IGNORE INTO template_rules(id, template_id, rule_type, rule_value, priority)
VALUES (2, 1, 'regex', '发票号码', 5);

-- ---------------------------------------------------------------------------
-- template_fields（config DB）— 合计两行：「合」「计」各占一行或单行「合计」，后为 ¥金额、¥税额
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(1, 1, 'invoice_number', '发票号码', 'string', 'regex', '{"pattern":"发票号码\\s*[：: ]*([0-9]{10,30})","group":1,"source":"full_text"}', NULL, 10, '[1]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(2, 1, 'issue_date', '开票日期', 'string', 'regex', '{"pattern":"开票日期\\s*[：: ]*(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日)","group":1,"source":"full_text"}', NULL, 20, '[]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(3, 1, 'buyer_name', '购买方名称', 'string', 'regex', '{"pattern":"(?m)^名称\\s*[：:]\\s*(.+)$","group":1,"source":"full_text","match_index":0}', NULL, 30, '[]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(4, 1, 'buyer_tax_id', '购买方纳税人识别号', 'string', 'regex', '{"pattern":"(?m)^统(?:一|[-－]{1,3})社会信用代码/纳税人识别号\\s*[：:]\\s*([0-9A-Z]{15,20})\\s*$","group":1,"source":"full_text","match_index":0}', NULL, 40, '[2]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(5, 1, 'seller_name', '销售方名称', 'string', 'regex', '{"pattern":"(?m)^名称\\s*[：:]\\s*(.+)$","group":1,"source":"full_text","match_index":1}', NULL, 50, '[]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(6, 1, 'seller_tax_id', '销售方纳税人识别号', 'string', 'regex', '{"pattern":"(?m)^统(?:一|[-－]{1,3})社会信用代码/纳税人识别号\\s*[：:]\\s*([0-9A-Z]{15,20})\\s*$","group":1,"source":"full_text","match_index":1}', NULL, 60, '[2]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(7, 1, 'item_name', '项目名称', 'string', 'regex', '{"pattern":"(?m)^(\\*[^\\n]+)$","group":1,"source":"full_text","match_index":0}', NULL, 70, '[]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(8, 1, 'subtotal_amount', '合计金额', 'string', 'regex', '{"pattern":"(?m)(?:^合\\s*$\\n^计\\s*$\\n|^合计\\s*$\\n)^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$\\n^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$","group":1,"source":"full_text","match_index":0,"replace_map":{" ": ""}}', NULL, 80, '[3]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(9, 1, 'subtotal_tax', '合计税额', 'string', 'regex', '{"pattern":"(?m)(?:^合\\s*$\\n^计\\s*$\\n|^合计\\s*$\\n)^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$\\n^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$","group":2,"source":"full_text","match_index":0,"replace_map":{" ": ""}}', NULL, 90, '[3]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(10, 1, 'total_amount_cn', '价税合计（大写）', 'string', 'regex', '{"pattern":"(?m)^价税合计\\s*[（(]\\s*大写\\s*[）)]\\s*$\\n^\\s*(.+?)\\s*$","group":1,"source":"full_text","match_index":0,"replace_map":{"ⓧ":"","②":"","①":"","◯":""}}', NULL, 100, '[]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(11, 1, 'total_amount', '价税合计（小写）', 'string', 'regex', '{"pattern":"[（(]\\s*小写\\s*[）)]\\s*[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)","group":1,"source":"full_text","match_index":0}', NULL, 110, '[3]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(12, 1, 'remark', '备注', 'string', 'keyword', '{"keywords":["备注"]}', NULL, 120, '[]', NULL);

INSERT OR IGNORE INTO template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, validation_rule, order_index, validator_ids, rule_item_id) VALUES
(13, 1, 'issuer', '开票人', 'string', 'regex', '{"pattern":"开票人\\s*[：: ]*([^\\n\\r\\s]+)","group":1,"source":"full_text"}', NULL, 130, '[]', NULL);

-- ---------------------------------------------------------------------------
-- llm_configs
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO llm_configs(
  id, name, provider, base_url, model, api_key_ref, system_prompt, response_schema, is_active
) VALUES (
  1,
  '默认LLM（未配置）',
  'openai_compatible',
  NULL,
  'gpt-4o-mini',
  NULL,
  NULL,
  '{}',
  0
);

-- ---------------------------------------------------------------------------
-- nodes（paddle 绑定默认模板+规则集，便于后台展示；运行时仍按 OCR 全文匹配模板）
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO nodes(
  node_name, display_name, description, node_type, enabled, order_index,
  template_id, ruleset_id, llm_config_id, config_json
) VALUES (
  'paddle_ocr',
  'PaddleRecognitionNode',
  '',
  'ocr',
  1,
  10,
  1,
  1,
  NULL,
  '{"module":"recognizer.domain.recognition.nodes.paddle_node","class":"PaddleRecognitionNode","engine":"paddleocr"}'
);

INSERT OR IGNORE INTO nodes(
  node_name, display_name, description, node_type, enabled, order_index,
  template_id, ruleset_id, llm_config_id, config_json
) VALUES (
  'llm_vision',
  'LLMRecognitionNode',
  '',
  'llm',
  0,
  20,
  NULL,
  NULL,
  1,
  '{"module":"recognizer.domain.recognition.nodes.llm_node","class":"LLMRecognitionNode","engine":"unknown"}'
);

UPDATE nodes SET template_id=1, ruleset_id=1 WHERE node_name='paddle_ocr';

-- ---------------------------------------------------------------------------
-- export_configs（与 ExportConfigService.seed_defaults_if_needed 一致）
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO export_configs(name, format, filename_template, sort, options_json, is_active)
VALUES ('默认CSV', 'csv', 'common_result_{date}', 10, '{"delimiter":",","encoding":"utf-8-sig"}', 1);

INSERT OR IGNORE INTO export_configs(name, format, filename_template, sort, options_json, is_active)
VALUES ('默认Excel', 'xlsx', 'common_result_{date}', 20, '{"sheet_name":"common_result"}', 1);

INSERT OR IGNORE INTO export_configs(name, format, filename_template, sort, options_json, is_active)
VALUES ('默认TXT', 'txt', 'common_result_{date}', 30, '{"separator":"\t","encoding":"utf-8"}', 1);

-- ---------------------------------------------------------------------------
-- workflows + workflow_nodes
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO workflows(id, name, description, is_default, is_active)
VALUES (1, '电子发票识别流程', 'PaddleOCR + LLM（LLM 默认关闭）', 1, 1);

INSERT INTO workflow_nodes(workflow_id, node_id, enabled, order_index, config_override_json)
SELECT 1, (SELECT id FROM nodes WHERE node_name='paddle_ocr' LIMIT 1), 1, 10, '{}'
WHERE NOT EXISTS (
  SELECT 1 FROM workflow_nodes wn
  JOIN nodes n ON n.id = wn.node_id AND n.node_name = 'paddle_ocr'
  WHERE wn.workflow_id = 1
);

INSERT INTO workflow_nodes(workflow_id, node_id, enabled, order_index, config_override_json)
SELECT 1, (SELECT id FROM nodes WHERE node_name='llm_vision' LIMIT 1), 1, 20, '{}'
WHERE NOT EXISTS (
  SELECT 1 FROM workflow_nodes wn
  JOIN nodes n ON n.id = wn.node_id AND n.node_name = 'llm_vision'
  WHERE wn.workflow_id = 1
);

-- ---------------------------------------------------------------------------
-- 运行期模板（TemplateManager / FieldExtractionEngine）— code 必须为 cfg_1
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO runtime_templates(id, name, code, engine, category, priority, enabled, description, created_at, updated_at)
VALUES (
  1,
  '电子发票（普通发票）',
  'cfg_1',
  'paddle',
  'electronic_invoice_general',
  10,
  1,
  '种子模板：与 config templates.id=1 对应（购销方+项目名+合计+价税合计）',
  datetime('now'),
  datetime('now')
);

INSERT OR IGNORE INTO runtime_template_rules(id, template_id, rule_type, rule_value, weight)
VALUES (1, 1, 'keyword', '["电子发票（普通发票）","电子发票","电子发普通发票","国家税务总局","北京市税务局","旅客运输服务","住宿服务"]', 50);

INSERT OR IGNORE INTO runtime_template_rules(id, template_id, rule_type, rule_value, weight)
VALUES (2, 1, 'regex', '发票号码', 5);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(1, 1, 'invoice_number', '发票号码', 'string', 'regex', '{"pattern":"发票号码\\s*[：: ]*([0-9]{10,30})","group":1,"source":"full_text"}', 0, NULL, 10);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(2, 1, 'issue_date', '开票日期', 'string', 'regex', '{"pattern":"开票日期\\s*[：: ]*(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日)","group":1,"source":"full_text"}', 0, NULL, 20);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(3, 1, 'buyer_name', '购买方名称', 'string', 'regex', '{"pattern":"(?m)^名称\\s*[：:]\\s*(.+)$","group":1,"source":"full_text","match_index":0}', 0, NULL, 30);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(4, 1, 'buyer_tax_id', '购买方纳税人识别号', 'string', 'regex', '{"pattern":"(?m)^统(?:一|[-－]{1,3})社会信用代码/纳税人识别号\\s*[：:]\\s*([0-9A-Z]{15,20})\\s*$","group":1,"source":"full_text","match_index":0}', 0, NULL, 40);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(5, 1, 'seller_name', '销售方名称', 'string', 'regex', '{"pattern":"(?m)^名称\\s*[：:]\\s*(.+)$","group":1,"source":"full_text","match_index":1}', 0, NULL, 50);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(6, 1, 'seller_tax_id', '销售方纳税人识别号', 'string', 'regex', '{"pattern":"(?m)^统(?:一|[-－]{1,3})社会信用代码/纳税人识别号\\s*[：:]\\s*([0-9A-Z]{15,20})\\s*$","group":1,"source":"full_text","match_index":1}', 0, NULL, 60);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(7, 1, 'item_name', '项目名称', 'string', 'regex', '{"pattern":"(?m)^(\\*[^\\n]+)$","group":1,"source":"full_text","match_index":0}', 0, NULL, 70);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(8, 1, 'subtotal_amount', '合计金额', 'string', 'regex', '{"pattern":"(?m)(?:^合\\s*$\\n^计\\s*$\\n|^合计\\s*$\\n)^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$\\n^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$","group":1,"source":"full_text","match_index":0,"replace_map":{" ": ""}}', 0, NULL, 80);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(9, 1, 'subtotal_tax', '合计税额', 'string', 'regex', '{"pattern":"(?m)(?:^合\\s*$\\n^计\\s*$\\n|^合计\\s*$\\n)^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$\\n^[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)\\s*$","group":2,"source":"full_text","match_index":0,"replace_map":{" ": ""}}', 0, NULL, 90);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(10, 1, 'total_amount_cn', '价税合计（大写）', 'string', 'regex', '{"pattern":"(?m)^价税合计\\s*[（(]\\s*大写\\s*[）)]\\s*$\\n^\\s*(.+?)\\s*$","group":1,"source":"full_text","match_index":0,"replace_map":{"ⓧ":"","②":"","①":"","◯":""}}', 0, NULL, 100);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(11, 1, 'total_amount', '价税合计（小写）', 'string', 'regex', '{"pattern":"[（(]\\s*小写\\s*[）)]\\s*[¥￥]\\s*([0-9]+(?:\\.[0-9]{1,2})?)","group":1,"source":"full_text","match_index":0}', 0, NULL, 110);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(12, 1, 'remark', '备注', 'string', 'keyword', '{"keywords":["备注"]}', 0, NULL, 120);

INSERT OR IGNORE INTO runtime_template_fields(id, template_id, field_name, field_label, field_type, extractor_type, extractor_config, required, validation_rule, order_index) VALUES
(13, 1, 'issuer', '开票人', 'string', 'regex', '{"pattern":"开票人\\s*[：: ]*([^\\n\\r\\s]+)","group":1,"source":"full_text"}', 0, NULL, 130);

-- ---------------------------------------------------------------------------
INSERT OR REPLACE INTO _recog_db_bundle (id, bundle_version) VALUES (1, '2');

COMMIT;
