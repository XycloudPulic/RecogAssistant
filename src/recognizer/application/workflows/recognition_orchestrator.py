# SPDX-License-Identifier: MIT

"""识别工作流编排器（通用，与具体票据类型解耦）。

核心调度器：负责管理识别节点、执行识别流程、合并识别结果。

架构（三层正交）：
1. Orchestrator（编排器）：调度多个 Workflow（工作流）
2. Workflow（工作流）：由多个 Node（节点）按序组成
3. Node（节点）：单一职责、可复用、可独立测试的基础处理单元

返回值（动态 schema）：
- common_result / engine_results[].result 均为 dict（field_name -> value），
  schema 由命中模板字段决定，可同时承载发票/火车票/其他票据。
"""

from __future__ import annotations

import base64
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from recognizer.domain.extraction.engine import FieldExtractionEngine
from recognizer.domain.extraction.template_manager import TemplateManager
from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    DiffDetail,
    EngineResultItem,
    FieldValueGroup,
    RecognitionResponse,
    RecognitionResponseData,
    RecognitionResult,
    ValidationResult,
    VerifyResult,
)

logger = logging.getLogger(__name__)


class RecognitionOrchestrator:
    """识别工作流编排器。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        # Load default orchestrator config from settings.yaml (NOT hardcoded).
        # Node/workflow runtime config is primarily maintained in config DB; settings.yaml acts as a safe fallback.
        if config is None:
            from recognizer.common.config.settings import Settings

            cfg = Settings.get("orchestrator")
            if not isinstance(cfg, dict) or not cfg:
                raise ValueError(
                    "Missing orchestrator config. Please configure `orchestrator` in config/settings.yaml."
                )
            config = cfg

        self.config: Dict[str, Any] = dict(config)
        # 是否在每次执行前从 config DB 重新加载节点。
        # 对于 workflow 构建出的编排器，必须关闭以避免覆盖工作流节点组合。
        self._auto_reload_nodes = bool(self.config.get("auto_reload_nodes", True))
        # 是否使用后台配置域（admin_configuration）里 ``nodes`` 表的全局节点（workflow 编排器需关闭）。
        # 配置键仍名 ``use_config_db_nodes``，与历史 YAML/工作流 JSON 兼容。
        self._use_admin_configuration_nodes = bool(
            self.config.get("use_config_db_nodes", True)
        )

        self.nodes: List[Any] = []
        self.extraction_engine = FieldExtractionEngine()
        self.template_manager = TemplateManager()

        if self._use_admin_configuration_nodes:
            self._override_nodes_from_admin_configuration_if_present()
        self._load_nodes()

        logger.info(
            "RecognitionOrchestrator initialized with %d nodes", len(self.nodes)
        )

    # ------------------------------------------------------------------
    # Node loading
    # ------------------------------------------------------------------

    def _get_default_config(self) -> Dict[str, Any]:
        # Kept only as a last-resort fallback. Prefer config/settings.yaml + config DB.
        return {}

    def _override_nodes_from_admin_configuration_if_present(self) -> None:
        """若后台配置域（nodes 表）中有节点配置则覆盖默认值。"""
        try:
            from recognizer.infrastructure.persistence.admin_configuration.connection import (
                get_connection,
                init_config_db,
            )

            init_config_db()
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM nodes ORDER BY order_index ASC"
                ).fetchall()
            finally:
                conn.close()
            if not rows:
                return

            import json

            node_configs: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                cfg = {}
                try:
                    cfg = json.loads(d.get("config_json") or "{}")
                except Exception:
                    cfg = {}
                node_configs.append(
                    {
                        "name": d.get("node_name"),
                        "module": cfg.get("module"),
                        "class": cfg.get("class"),
                        "order": int(d.get("order_index") or 100),
                        "enabled": bool(d.get("enabled")),
                        "node_type": d.get("node_type"),
                        "engine": cfg.get("engine"),
                    }
                )

            if any(n.get("module") and n.get("class") for n in node_configs):
                self.config["nodes"] = node_configs
        except Exception:
            logger.exception(
                "Failed to load nodes from admin_configuration; falling back to Settings"
            )

    def _load_nodes(self) -> None:
        node_configs = self.config.get("nodes", [])
        for node_config in node_configs:
            if not node_config.get("enabled", True):
                logger.info("Node '%s' is disabled, skipping", node_config.get("name"))
                continue

            module_path = node_config.get("module")
            class_name = node_config.get("class")
            if not module_path or not class_name:
                logger.warning("Node config missing module or class: %s", node_config)
                continue

            try:
                import importlib

                module = importlib.import_module(module_path)
                node_class: Type = getattr(module, class_name)

                try:
                    node = node_class(configured_name=node_config.get("name"))
                except TypeError:
                    node = node_class()

                node.order = node_config.get("order", node.order)
                self.nodes.append(node)
                logger.info("Loaded node: %s (order=%d)", node.name, node.order)
            except Exception as exc:
                logger.error(
                    "Failed to load node '%s': %s",
                    node_config.get("name"),
                    exc,
                    exc_info=True,
                )

        self.nodes.sort(key=lambda n: n.order)
        logger.info("Total %d nodes loaded", len(self.nodes))

    def reload_nodes(self) -> None:
        """从后台配置域 / settings 重新加载节点列表。"""
        self.nodes = []
        if self._use_admin_configuration_nodes:
            self._override_nodes_from_admin_configuration_if_present()
        self._load_nodes()

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(
        self,
        image_path: str,
        category: Optional[str] = None,
        debug: bool = False,
        **kwargs: Any,
    ) -> RecognitionResponse:
        """执行识别工作流（不绑定具体票据类型）。"""
        start_time = time.time()

        logger.info("=" * 60)
        logger.info("[ORCHESTRATOR START]")
        logger.info("=" * 60)
        logger.info("  Image: %s", image_path)
        logger.info("  Category: %s", category or "(auto)")
        logger.info("  Nodes: %d", len(self.nodes))
        logger.info("  Parallel: %s", self.config.get("parallel", False))
        logger.info("-" * 60)

        try:
            if self._auto_reload_nodes:
                self.reload_nodes()

            self._validate_input(image_path)
            recognition_results = self._execute_nodes(image_path, **kwargs)
            merged_result = self._merge_results(recognition_results)

            common_result, field_confidence, template_ctx = self._extract_fields(
                merged_result, category
            )

            verify_result = self._verify_data(common_result, template_ctx)
            validation_result = self._validate_data(common_result, template_ctx)

            cost_time = int((time.time() - start_time) * 1000)
            response = self._build_response(
                common_result,
                field_confidence,
                recognition_results,
                verify_result,
                validation_result,
                template_ctx,
                cost_time,
                debug_payload=self._build_debug_payload(
                    image_path=image_path,
                    recognition_results=recognition_results,
                    template_ctx=template_ctx,
                    enabled=debug,
                ),
            )

            logger.info("-" * 60)
            logger.info("[ORCHESTRATOR END] SUCCESS")
            logger.info("  Cost time: %dms", cost_time)
            logger.info("  Fields extracted: %d", len(common_result or {}))
            logger.info("=" * 60)
            return response
        except Exception as exc:
            cost_time = int((time.time() - start_time) * 1000)
            logger.error("=" * 60)
            logger.error("[ORCHESTRATOR END] ERROR")
            logger.error("  Error: %s", str(exc))
            logger.error("  Cost time: %dms", cost_time)
            logger.error("=" * 60, exc_info=True)
            return RecognitionResponse(code=1, msg=str(exc), data=None)

    def _validate_input(self, image_path: str) -> None:
        if not image_path:
            raise ValueError("image_path is required")
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

    def _execute_nodes(self, image_path: str, **kwargs: Any) -> List[RecognitionResult]:
        parallel = self.config.get("parallel", False)
        if parallel and len(self.nodes) > 1:
            logger.info("Executing nodes in parallel...")
            return self._execute_parallel(image_path, **kwargs)
        logger.info("Executing nodes sequentially...")
        return self._execute_sequential(image_path, **kwargs)

    def _execute_sequential(
        self, image_path: str, **kwargs: Any
    ) -> List[RecognitionResult]:
        results: List[RecognitionResult] = []
        for node in self.nodes:
            logger.info("Executing node: %s (order=%d)", node.name, node.order)
            result = node.execute(image_path, **kwargs)
            results.append(result)
            logger.info(
                "Node '%s' completed: engine=%s, cost=%dms",
                node.name,
                result.engine,
                result.cost_time,
            )
        return results

    def _execute_parallel(
        self, image_path: str, **kwargs: Any
    ) -> List[RecognitionResult]:
        results: List[RecognitionResult] = []
        with ThreadPoolExecutor(max_workers=len(self.nodes)) as executor:
            future_to_node = {
                executor.submit(node.execute, image_path, **kwargs): node
                for node in self.nodes
            }
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(
                        "Node '%s' completed: engine=%s, cost=%dms",
                        node.name,
                        result.engine,
                        result.cost_time,
                    )
                except Exception as exc:
                    logger.error("Node '%s' failed: %s", node.name, exc, exc_info=True)

        results.sort(
            key=lambda r: next(
                (n.order for n in self.nodes if n.engine_name == r.engine), 999
            )
        )
        return results

    # ------------------------------------------------------------------
    # Merge / extract / verify / build response
    # ------------------------------------------------------------------

    def _merge_results(self, results: List[RecognitionResult]) -> RecognitionResult:
        """合并多个识别结果（当前选择第一个成功的；后续可换为多数投票）。"""
        if not results:
            raise ValueError("No recognition results to merge")
        for result in results:
            if result.raw_data is not None:
                logger.info("Selected result from: %s", result.engine)
                return result
        logger.warning("All recognition results failed, using first one")
        return results[0]

    def _extract_fields(
        self,
        recognition_result: RecognitionResult,
        category: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, float], Optional[Dict[str, Any]]]:
        """根据命中模板字段抽取动态 schema。"""
        extraction_config = self.config.get("extraction", {})
        if not extraction_config.get("enabled", True):
            logger.info("Extraction is disabled, returning empty data")
            return {}, {}, None

        template = self.template_manager.detect_template(
            recognition_result.raw_data,
            category or extraction_config.get("category"),
        )
        if not template:
            logger.warning("No template matched, returning empty data")
            return {}, {}, None

        logger.info("Using template: %s", template.name)

        fields = self.template_manager.get_template_fields(template.id)
        if not fields:
            logger.warning("Template '%s' has no fields", template.name)
            return (
                {},
                {},
                {
                    "template": {"id": template.id, "name": template.name},
                    "fields": [],
                },
            )

        result, confidence = self.extraction_engine.extract(
            recognition_result.raw_data, fields
        )
        template_ctx = {
            "template": {
                "id": template.id,
                "name": template.name,
                "code": getattr(template, "code", None),
            },
            "fields": [
                {
                    "field_name": f.field_name,
                    "field_label": f.field_label,
                    "field_type": getattr(f, "field_type", None),
                    "extractor_type": getattr(f, "extractor_type", None),
                    "extractor_config": getattr(f, "extractor_config", None),
                    "validation_rule": getattr(f, "validation_rule", None),
                    "order_index": getattr(f, "order_index", None),
                }
                for f in fields
            ],
        }

        # Enrich with config-db validator_ids if runtime template code is cfg_{id}.
        try:
            tmpl_code = str(getattr(template, "code", "") or "")
            cfg_id: int | None = None
            if tmpl_code.startswith("cfg_"):
                cfg_id = int(tmpl_code.split("_", 1)[1])
            if cfg_id:
                from recognizer.infrastructure.persistence.admin_configuration.repositories.template_config_repository import (
                    TemplateConfigRepository,
                )

                cfg_repo = TemplateConfigRepository()
                cfg_fields = cfg_repo.list_fields(int(cfg_id))
                vmap: dict[str, list[int]] = {}
                for row in cfg_fields:
                    fn = str(row.get("field_name") or "")
                    if not fn:
                        continue
                    try:
                        v_ids = json.loads(row.get("validator_ids") or "[]")
                        vmap[fn] = [int(x) for x in v_ids if x is not None]
                    except Exception:
                        vmap[fn] = []
                for item in template_ctx.get("fields") or []:
                    key = str(item.get("field_name") or "")
                    item["validator_ids"] = vmap.get(key, [])
        except Exception:
            pass

        return result, confidence, template_ctx

    def _verify_data(
        self,
        common_result: Dict[str, Any],
        template_ctx: Optional[Dict[str, Any]] = None,
    ) -> VerifyResult:
        """按命中模板字段做完整性校验，不绑定特定票据类型。"""
        verify_result = VerifyResult()
        common_result = common_result or {}

        fields_to_check: List[str] = []
        if template_ctx and isinstance(template_ctx.get("fields"), list):
            for f in template_ctx.get("fields") or []:
                key = f.get("field_name")
                if key and key not in fields_to_check:
                    fields_to_check.append(str(key))
        if not fields_to_check:
            fields_to_check = [str(k) for k in (common_result.keys() or [])]

        verify_result.total_fields = len(fields_to_check)
        consistent_count = 0
        diff_details: List[DiffDetail] = []

        for field_name in fields_to_check:
            value = common_result.get(field_name, "")
            if value:
                consistent_count += 1
                diff_details.append(
                    DiffDetail(
                        field=field_name,
                        values=[
                            FieldValueGroup(
                                value=str(value), count=1, sources=["current"]
                            )
                        ],
                        status="consistent",
                    )
                )
            else:
                diff_details.append(
                    DiffDetail(field=field_name, values=[], status="missing")
                )

        verify_result.consistent_fields = consistent_count
        verify_result.inconsistent_fields = (
            verify_result.total_fields - consistent_count
        )
        verify_result.is_consistent = verify_result.inconsistent_fields == 0
        verify_result.diff_details = diff_details

        # 通用校验：amount + tax 与 total_amount 的关系（仅当三个字段都存在时执行）
        amount = common_result.get("amount")
        tax = common_result.get("tax")
        total_amount = common_result.get("total_amount")
        if amount and tax and total_amount:
            try:
                if abs(float(amount) + float(tax) - float(total_amount)) > 0.01:
                    logger.warning(
                        "Amount verification failed: %s + %s != %s",
                        amount,
                        tax,
                        total_amount,
                    )
            except (TypeError, ValueError) as exc:
                logger.warning("Amount verification error: %s", exc)

        return verify_result

    def _validate_data(
        self,
        common_result: Dict[str, Any],
        template_ctx: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult | None:
        """字段合法性校验（validators + template_fields.validator_ids）。"""
        if not template_ctx or not isinstance(template_ctx.get("fields"), list):
            return None

        fields = template_ctx.get("fields") or []
        has_any_validator = any(
            bool((f or {}).get("validator_ids")) for f in fields if isinstance(f, dict)
        )
        if not has_any_validator:
            return None

        referenced_ids: set[int] = set()
        for f in fields:
            if not isinstance(f, dict):
                continue
            v_ids = f.get("validator_ids") or []
            if isinstance(v_ids, list):
                for vid in v_ids:
                    try:
                        referenced_ids.add(int(vid))
                    except Exception:
                        continue

        validators_by_id: dict[int, dict[str, Any]] = {}
        if referenced_ids:
            try:
                from recognizer.infrastructure.persistence.admin_configuration.repositories.validator_repository import (
                    ValidatorRepository,
                )

                repo = ValidatorRepository()
                for row in repo.list_validators(active_only=False):
                    try:
                        vid = int(row.get("id") or 0)
                    except Exception:
                        continue
                    if vid not in referenced_ids:
                        continue
                    try:
                        cfg = json.loads(row.get("config_json") or "{}")
                    except Exception:
                        cfg = {}
                    validators_by_id[vid] = {
                        "validator_type": row.get("validator_type"),
                        "config": cfg,
                        "name": row.get("name"),
                    }
            except Exception:
                validators_by_id = {}

        from recognizer.domain.validation.engine import ValidationEngine

        raw = ValidationEngine().validate(
            common_result=common_result or {},
            fields=fields,
            validators_by_id=validators_by_id,
        )
        return ValidationResult(**raw)

    def _validate_dict_with_template(
        self,
        data_dict: Dict[str, Any],
        template_ctx: Optional[Dict[str, Any]],
    ) -> ValidationResult | None:
        """Validate an arbitrary extracted dict with the same template_ctx validators."""
        return self._validate_data(data_dict or {}, template_ctx)

    def _build_response(
        self,
        common_result: Dict[str, Any],
        field_confidence: Dict[str, float],
        recognition_results: List[RecognitionResult],
        verify_result: VerifyResult,
        validation_result: ValidationResult | None,
        template_ctx: Optional[Dict[str, Any]],
        cost_time: int,
        debug_payload: Optional[Dict[str, Any]] = None,
    ) -> RecognitionResponse:
        """构建 API 响应（动态 schema）。"""
        del field_confidence  # 当前未直接出现在响应中
        # template_ctx is also used for per-engine validation_result (do not delete)
        del cost_time  # 暂未透传到响应；保留参数以便后续添加耗时字段

        engine_results: List[EngineResultItem] = []
        for result in recognition_results:
            meta = result.metadata or {}
            error = meta.get("error")
            engine_dict: Dict[str, Any] = {}

            if result.raw_data is not None and not error:
                try:
                    if (
                        result.node_type == "llm"
                        and isinstance(result.raw_data, dict)
                        and isinstance(result.raw_data.get("fields"), dict)
                    ):
                        engine_dict = dict(result.raw_data.get("fields") or {})
                    else:
                        tmp = self.template_manager.detect_template(
                            result.raw_data, None
                        )
                        if tmp:
                            fields = self.template_manager.get_template_fields(tmp.id)
                            if fields:
                                engine_dict, _ = self.extraction_engine.extract(
                                    result.raw_data, fields
                                )
                except Exception:
                    # 单个引擎失败不应影响响应；让该项的 result 留空。
                    engine_dict = {}

            engine_results.append(
                EngineResultItem(
                    id=f"{result.engine}:{result.node_type}",
                    engine=result.engine,
                    parser=result.node_type,
                    result=engine_dict,
                    validation_result=self._validate_dict_with_template(
                        engine_dict, template_ctx
                    ),
                    cost_time=result.cost_time,
                )
            )

        response_data = RecognitionResponseData(
            common_result=common_result or {},
            verify_result=verify_result,
            validation_result=validation_result,
            engine_results=engine_results,
            debug=debug_payload,
        )
        return RecognitionResponse(code=0, msg="SUCCESS", data=response_data)

    def _build_debug_payload(
        self,
        image_path: str,
        recognition_results: List[RecognitionResult],
        template_ctx: Optional[Dict[str, Any]],
        enabled: bool,
    ) -> Optional[Dict[str, Any]]:
        if not enabled:
            return None

        try:
            img_bytes = Path(image_path).read_bytes()
            input_b64 = base64.b64encode(img_bytes).decode("ascii")
        except Exception:
            input_b64 = ""

        nodes: List[Dict[str, Any]] = []
        for r in recognition_results:
            meta = r.metadata or {}
            node_name = meta.get("node_name") or ""
            error = meta.get("error")
            status = "success" if r.raw_data is not None and not error else "failed"

            business_result: Optional[Dict[str, Any]] = None
            business_template_ctx: Optional[Dict[str, Any]] = None
            if r.raw_data is not None and not error:
                try:
                    if (
                        r.node_type == "llm"
                        and isinstance(r.raw_data, dict)
                        and isinstance(r.raw_data.get("fields"), dict)
                    ):
                        business_result = dict(r.raw_data.get("fields") or {})
                    else:
                        tmp = self.template_manager.detect_template(r.raw_data, None)
                        if tmp:
                            fields = self.template_manager.get_template_fields(tmp.id)
                            if fields:
                                business_result, _ = self.extraction_engine.extract(
                                    r.raw_data, fields
                                )
                                business_template_ctx = {
                                    "template": {"id": tmp.id, "name": tmp.name},
                                    "fields": [
                                        {
                                            "field_name": f.field_name,
                                            "field_label": f.field_label,
                                            "field_type": getattr(
                                                f, "field_type", None
                                            ),
                                            "extractor_type": getattr(
                                                f, "extractor_type", None
                                            ),
                                            "extractor_config": getattr(
                                                f, "extractor_config", None
                                            ),
                                            "validation_rule": getattr(
                                                f, "validation_rule", None
                                            ),
                                            "order_index": getattr(
                                                f, "order_index", None
                                            ),
                                        }
                                        for f in fields
                                    ],
                                }
                except Exception:
                    business_result = None
                    business_template_ctx = None

            nodes.append(
                {
                    "node_name": node_name,
                    "engine": r.engine,
                    "node_type": r.node_type,
                    "status": status,
                    "cost_time": r.cost_time,
                    "input_base64": input_b64,
                    "output_json": r.raw_data,
                    "business_result": business_result,
                    "business_template_ctx": business_template_ctx,
                    "error": error,
                }
            )

        payload: Dict[str, Any] = {"nodes": nodes}
        if template_ctx:
            payload["template_ctx"] = template_ctx
        return payload

    # ------------------------------------------------------------------
    # Node mutation API
    # ------------------------------------------------------------------

    def add_node(self, node: Any) -> None:
        self.nodes.append(node)
        self.nodes.sort(key=lambda n: n.order)
        logger.info("Added node: %s (order=%d)", node.name, node.order)

    def remove_node(self, node_name: str) -> bool:
        for i, node in enumerate(self.nodes):
            if node.name == node_name:
                self.nodes.pop(i)
                logger.info("Removed node: %s", node_name)
                return True
        logger.warning("Node '%s' not found", node_name)
        return False

    def get_nodes(self) -> List[Any]:
        return self.nodes.copy()
