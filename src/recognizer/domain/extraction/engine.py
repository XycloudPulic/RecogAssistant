# SPDX-License-Identifier: MIT

"""字段提取引擎

核心组件：根据模板字段配置，从识别结果中提取结构化字段。

通用化设计（与具体票据类型解耦）：
- 抽取结果以 dict[field_name -> value] 形式返回，模板字段决定 schema。
- 关键词提取器仅依赖 `extractor_config.keywords`，否则回退到 `field_label/field_name`，
  不再保留发票专用的关键词字典，从而支持发票/火车票/其他票据。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from recognizer.domain.extraction.script_runner import (
    ScriptContext,
    run_extractor_script,
)
from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    TemplateField,
)

logger = logging.getLogger(__name__)


class FieldExtractionEngine:
    """字段提取引擎

    根据模板字段配置，从识别结果中提取结构化字段。
    返回扁平的 dict（field_name -> value）和置信度 dict，schema 完全由模板决定。
    """

    def __init__(self) -> None:
        logger.info("FieldExtractionEngine initialized")

    def extract(
        self,
        raw_data: Any,
        fields: List[TemplateField],
        image_size: Optional[Tuple[int, int]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """根据模板字段从识别结果中抽取数据。

        Args:
            raw_data: OCR/LLM 节点的原始数据（list[dict|tuple] 或 dict）。
            fields: 模板字段配置。
            image_size: 图片尺寸 (width, height)（可选，用于区域提取）。

        Returns:
            (result_dict, confidence_dict)：键均为 `field.field_name`。
        """
        logger.info("Extracting %d fields", len(fields))

        result: Dict[str, Any] = {}
        confidence: Dict[str, float] = {}

        if not fields:
            logger.warning("No fields to extract")
            return result, confidence

        for field in sorted(fields, key=lambda f: f.order_index):
            try:
                value, score = self._extract_field(raw_data, field, image_size)
            except Exception:
                logger.exception("Failed to extract field '%s'", field.field_name)
                value, score = "", 0.0

            result[field.field_name] = value
            confidence[field.field_name] = score
            logger.debug(
                "Field '%s': %s (confidence: %.2f)", field.field_name, value, score
            )

        logger.info("Extraction completed: %d fields", len(fields))
        return result, confidence

    # ------------------------------------------------------------------
    # Per-field dispatch
    # ------------------------------------------------------------------

    def _extract_field(
        self,
        raw_data: Any,
        field: TemplateField,
        image_size: Optional[Tuple[int, int]] = None,
    ) -> Tuple[str, float]:
        extractor_type = field.extractor_type
        extractor_config = field.extractor_config

        if isinstance(extractor_config, str):
            import json

            try:
                extractor_config = json.loads(extractor_config)
            except json.JSONDecodeError as exc:
                logger.error("Invalid extractor_config JSON: %s", exc)
                extractor_config = {}

        if not isinstance(extractor_config, dict):
            extractor_config = {}

        if image_size:
            extractor_config["image_size"] = list(image_size)

        extractor = self._get_extractor(extractor_type)
        value = extractor(raw_data, field, extractor_config)
        score = self._calculate_confidence(value, extractor_config)
        return value, score

    def _get_extractor(self, extractor_type: str):
        extractors = {
            "keyword": self._extract_by_keyword,
            "regex": self._extract_by_regex,
            "region": self._extract_by_region,
            "script": self._extract_by_script,
        }
        return extractors.get(extractor_type, self._extract_by_keyword)

    # ------------------------------------------------------------------
    # Extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_text_lines(raw_data: Any) -> List[str]:
        """Return OCR/LLM text lines in reading order when ``box`` is present.

        Paddle returns detection-order lists; sorting by top-left of each box makes
        ``full_text`` joins stable for multi-column invoices (buyer left / seller right).
        """
        if not isinstance(raw_data, list):
            return []

        scored: List[Tuple[Tuple[float, float], str]] = []
        fallback: List[str] = []

        for item in raw_data:
            if isinstance(item, dict):
                txt = item.get("text", "")
                if not txt:
                    continue
                box = item.get("box")
                if isinstance(box, list) and box:
                    ys: List[float] = []
                    xs: List[float] = []
                    for pt in box:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            try:
                                xs.append(float(pt[0]))
                                ys.append(float(pt[1]))
                            except (TypeError, ValueError):
                                continue
                    key = (min(ys) if ys else 0.0, min(xs) if xs else 0.0)
                    scored.append((key, str(txt)))
                else:
                    fallback.append(str(txt))
            elif isinstance(item, (list, tuple)) and len(item) >= 1:
                fallback.append(str(item[0]))

        scored.sort(key=lambda t: (t[0][0], t[0][1]))
        # Merge boxes that share a visual row (close min_y), then order left→right.
        # Global y-sort alone mis-orders multi-column pairs when one side is 1–2px higher.
        row_y_thresh = 12.0
        rows: List[List[Tuple[float, float, str]]] = []
        for key, txt in scored:
            y, x = float(key[0]), float(key[1])
            if not rows:
                rows.append([(y, x, txt)])
                continue
            anchor = min(r[0] for r in rows[-1])
            if abs(y - anchor) <= row_y_thresh:
                rows[-1].append((y, x, txt))
            else:
                rows.append([(y, x, txt)])

        ordered: List[str] = []
        for row in rows:
            row.sort(key=lambda t: (t[1], t[0]))
            ordered.extend(t[2] for t in row)
        return ordered + fallback

    def _extract_by_keyword(
        self, raw_data: Any, field: TemplateField, config: Dict[str, Any]
    ) -> str:
        """关键词提取：模板驱动，无业务字段硬编码。

        优先级：
        1. `extractor_config.keywords`（list[str]）
        2. 回退 `[field.field_label, field.field_name]`（去重、过滤空值）
        """
        keywords: List[str] = []
        cfg_keywords = config.get("keywords")
        if isinstance(cfg_keywords, list):
            keywords = [str(k) for k in cfg_keywords if k]
        if not keywords:
            for candidate in (
                getattr(field, "field_label", None),
                getattr(field, "field_name", None),
            ):
                if candidate and candidate not in keywords:
                    keywords.append(str(candidate))
        if not keywords:
            return ""

        for line in self._iter_text_lines(raw_data):
            for keyword in keywords:
                if keyword in line:
                    idx = line.find(keyword)
                    value = line[idx + len(keyword) :].strip()
                    value = value.lstrip("：: \t")
                    if value:
                        return self._postprocess_value(value, config)
        return ""

    def _extract_by_regex(
        self, raw_data: Any, field: TemplateField, config: Dict[str, Any]
    ) -> str:
        import re

        pattern = config.get("pattern", "")
        if not pattern:
            return ""
        source = str(config.get("source") or "line")
        group = config.get("group", 0)

        if source == "full_text":
            full_text = "\n".join(self._iter_text_lines(raw_data))
            if not full_text:
                return ""
            flags = re.MULTILINE
            if config.get("dotall"):
                flags |= re.DOTALL
            matches = list(re.finditer(pattern, full_text, flags=flags))
            match_index = int(config.get("match_index", 0))
            if match_index < 0 or match_index >= len(matches):
                return ""
            match = matches[match_index]
            value = self._regex_group_value(match, group)
            return self._postprocess_value(value, config)

        for line in self._iter_text_lines(raw_data):
            match = re.search(pattern, line)
            if match:
                value = self._regex_group_value(match, group)
                return self._postprocess_value(value, config)
        return ""

    def _extract_by_region(
        self, raw_data: Any, field: TemplateField, config: Dict[str, Any]
    ) -> str:
        # TODO: 实际区域提取逻辑；当前回退为关键词提取。
        return self._extract_by_keyword(raw_data, field, config)

    def _extract_by_script(
        self, raw_data: Any, field: TemplateField, config: Dict[str, Any]
    ) -> str:
        script_ref = str(config.get("script_ref") or "").strip()
        if not script_ref:
            return ""
        entrypoint = str(config.get("entrypoint") or "extract").strip() or "extract"
        timeout_ms = int(config.get("timeout_ms") or 200)
        source = str(config.get("input") or "full_text")

        full_text = "\n".join(self._iter_text_lines(raw_data))
        ctx = ScriptContext(
            field_name=getattr(field, "field_name", ""),
            raw_data=raw_data if source != "full_text" else raw_data,
            full_text=full_text,
            image_size=tuple(config.get("image_size"))
            if isinstance(config.get("image_size"), list)
            and len(config.get("image_size")) == 2
            else None,
            config=dict(config),
        )
        return run_extractor_script(
            script_ref=script_ref,
            entrypoint=entrypoint,
            timeout_ms=timeout_ms,
            ctx=ctx,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _regex_group_value(match: Any, group: Any) -> str:
        """Return capture text for ``group`` (int or list of ints for alternation)."""
        if match is None:
            return ""
        if isinstance(group, list):
            for g in group:
                try:
                    gi = int(g)
                    val = match.group(gi) if gi != 0 else match.group(0)
                except (IndexError, TypeError, ValueError):
                    continue
                if val is not None and str(val).strip():
                    return str(val).strip()
            return ""
        try:
            gi = int(group)
        except (TypeError, ValueError):
            try:
                out = match.group(0)
            except IndexError:
                return ""
            return "" if out is None else str(out).strip()
        try:
            out = match.group(gi) if gi != 0 else match.group(0)
        except IndexError:
            try:
                out = match.group(0)
            except IndexError:
                return ""
        return "" if out is None else str(out).strip()

    @staticmethod
    def _calculate_confidence(value: str, config: Dict[str, Any]) -> float:
        if not value:
            return 0.0
        confidence = 0.8
        if config.get("validation"):
            confidence = 0.9
        if config.get("required"):
            confidence = 0.95
        return confidence

    @staticmethod
    def _postprocess_value(value: Any, config: Dict[str, Any]) -> str:
        out = "" if value is None else str(value)
        if not out:
            return ""
        if config.get("strip_spaces"):
            out = out.replace(" ", "")
        replace_map = config.get("replace_map")
        if isinstance(replace_map, dict):
            for k, v in replace_map.items():
                try:
                    out = out.replace(str(k), str(v))
                except Exception:
                    continue
        return out.strip()
