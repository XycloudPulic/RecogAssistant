-- RecogAssistant - SQLite initialization script
-- Version: V0.1.0 (schema derived from current codebase)
--
-- Usage:
--   sqlite3 data/db/recognition.db < data/db/scripts/init_recognition_db.sql
--   Or: service.bat init   (runs pip + this script + insert_recognition_db.sql)
--
-- Notes:
-- - This script creates BOTH:
--   1) config tables (nodes/workflows/templates/validators/...) used by admin pages
--   2) runtime tables (recognition history + runtime templates) used during recognition
-- - SQLite JSON is stored as TEXT/JSON; application treats these columns as JSON.

PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

BEGIN;

-- =========================================================
-- Admin configuration schema (persisted under persistence.admin_configuration)
-- =========================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Templates (config)
CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  engine TEXT NOT NULL,
  parser TEXT NOT NULL,
  field_count INTEGER NOT NULL DEFAULT 0,
  sample_image TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  ruleset_id INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS template_fields (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  field_name TEXT NOT NULL,
  field_label TEXT NOT NULL,
  field_type TEXT NOT NULL DEFAULT 'string',
  extractor_type TEXT NOT NULL DEFAULT 'keyword',
  extractor_config TEXT NOT NULL DEFAULT '{}',
  validation_rule TEXT,
  order_index INTEGER NOT NULL DEFAULT 0,
  -- V0.1.0: validator ids (JSON array string), used for reusable validators binding
  validator_ids TEXT NOT NULL DEFAULT '[]',
  rule_item_id INTEGER,
  FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS template_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  rule_type TEXT NOT NULL,
  rule_value TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_templates_engine_parser ON templates(engine, parser);
CREATE INDEX IF NOT EXISTS idx_templates_ruleset ON templates(ruleset_id);
CREATE INDEX IF NOT EXISTS idx_template_fields_template ON template_fields(template_id);
CREATE INDEX IF NOT EXISTS idx_template_fields_rule_item ON template_fields(rule_item_id);
CREATE INDEX IF NOT EXISTS idx_template_rules_template ON template_rules(template_id);

-- Rule sets (general-purpose)
CREATE TABLE IF NOT EXISTS rulesets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rule_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ruleset_id INTEGER NOT NULL,
  item_type TEXT NOT NULL,
  pattern TEXT,
  config_json TEXT NOT NULL DEFAULT '{}',
  priority INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (ruleset_id) REFERENCES rulesets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rule_items_ruleset ON rule_items(ruleset_id);

-- Data fields (field definitions under a ruleset)
CREATE TABLE IF NOT EXISTS data_fields (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ruleset_id INTEGER NOT NULL,
  field_key TEXT NOT NULL,
  field_label TEXT NOT NULL,
  field_type TEXT NOT NULL DEFAULT 'string',
  order_index INTEGER NOT NULL DEFAULT 0,
  rule_item_id INTEGER,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (ruleset_id) REFERENCES rulesets(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_data_fields_ruleset_key ON data_fields(ruleset_id, field_key);
CREATE INDEX IF NOT EXISTS idx_data_fields_ruleset ON data_fields(ruleset_id, order_index);
CREATE INDEX IF NOT EXISTS idx_data_fields_rule_item ON data_fields(rule_item_id);

-- LLM configs (matches LLMConfigRepository)
CREATE TABLE IF NOT EXISTS llm_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  provider TEXT NOT NULL,
  base_url TEXT,
  model TEXT NOT NULL,
  api_key_ref TEXT,
  system_prompt TEXT,
  response_schema TEXT NOT NULL DEFAULT '{}',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Nodes (global node registry; matches NodeConfigRepository / node_autoregister)
CREATE TABLE IF NOT EXISTS nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_name TEXT NOT NULL UNIQUE,
  display_name TEXT,
  description TEXT,
  node_type TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  order_index INTEGER NOT NULL DEFAULT 100,
  template_id INTEGER,
  ruleset_id INTEGER,
  llm_config_id INTEGER,
  config_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL,
  FOREIGN KEY (ruleset_id) REFERENCES rulesets(id) ON DELETE SET NULL,
  FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_order ON nodes(order_index);

-- Export configs (matches ExportConfigRepository)
CREATE TABLE IF NOT EXISTS export_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  format TEXT NOT NULL,
  filename_template TEXT NOT NULL DEFAULT 'export_{date}',
  options_json TEXT NOT NULL DEFAULT '{}',
  sort INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_export_configs_sort ON export_configs(sort);

-- Workflows + nodes in workflow
CREATE TABLE IF NOT EXISTS workflows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  is_default INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_workflows_default ON workflows(is_default);

CREATE TABLE IF NOT EXISTS workflow_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id INTEGER NOT NULL,
  node_id INTEGER NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  order_index INTEGER NOT NULL DEFAULT 100,
  config_override_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
  FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workflow ON workflow_nodes(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_nodes_order ON workflow_nodes(workflow_id, order_index);

-- Validators (reusable field validation rules)
CREATE TABLE IF NOT EXISTS validators (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  validator_type TEXT NOT NULL,
  config_json TEXT NOT NULL DEFAULT '{}',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_validators_type ON validators(validator_type);
CREATE INDEX IF NOT EXISTS idx_validators_active ON validators(is_active);

-- =========================================================
-- Runtime DB schema (src/recognizer/infrastructure/persistence)
-- =========================================================

-- Runtime templates (used by recognition runtime)
CREATE TABLE IF NOT EXISTS runtime_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(100) NOT NULL,
  code VARCHAR(50) NOT NULL UNIQUE,
  engine VARCHAR(50) NOT NULL,
  category VARCHAR(50),
  priority INTEGER DEFAULT 100,
  enabled BOOLEAN DEFAULT 1,
  description TEXT,
  created_at DATETIME,
  updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS runtime_template_fields (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  field_name VARCHAR(50) NOT NULL,
  field_label VARCHAR(100),
  field_type VARCHAR(20),
  extractor_type VARCHAR(20) NOT NULL,
  extractor_config JSON NOT NULL,
  required BOOLEAN,
  validation_rule VARCHAR(200),
  order_index INTEGER,
  FOREIGN KEY(template_id) REFERENCES runtime_templates (id)
);

CREATE TABLE IF NOT EXISTS runtime_template_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  rule_type VARCHAR(20) NOT NULL,
  rule_value TEXT NOT NULL,
  weight INTEGER,
  FOREIGN KEY(template_id) REFERENCES runtime_templates (id)
);

-- Recognition history
CREATE TABLE IF NOT EXISTS runtime_recognition_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  original_filename VARCHAR(255),
  image_sha256 VARCHAR(64) NOT NULL,
  image_path TEXT,
  is_active BOOLEAN NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runtime_recognition_jobs_sha ON runtime_recognition_jobs(image_sha256);

CREATE TABLE IF NOT EXISTS runtime_recognition_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'success',
  cost_time_ms INTEGER NOT NULL DEFAULT 0,
  orchestrator_config JSON,
  node_config_snapshot JSON,
  common_result JSON,
  verify_result JSON,
  engine_results JSON,
  raw_response JSON,
  template_ctx JSON,
  created_at DATETIME NOT NULL,
  FOREIGN KEY(job_id) REFERENCES runtime_recognition_jobs (id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_recognition_runs_job ON runtime_recognition_runs(job_id);

CREATE TABLE IF NOT EXISTS runtime_node_run_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  node_name VARCHAR(100) NOT NULL,
  node_type VARCHAR(20),
  engine VARCHAR(50),
  status VARCHAR(20) NOT NULL DEFAULT 'success',
  cost_time_ms INTEGER NOT NULL DEFAULT 0,
  output_json JSON,
  error TEXT,
  FOREIGN KEY(run_id) REFERENCES runtime_recognition_runs (id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_node_run_results_run ON runtime_node_run_results(run_id);

-- Marks successful application of bundled DDL+DML (see insert_recognition_db.sql)
CREATE TABLE IF NOT EXISTS _recog_db_bundle (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  bundle_version TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

COMMIT;

