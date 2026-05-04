# SPDX-License-Identifier: MIT

"""PaddleOCR recognition node.

This node runs PaddleOCR on the input image and returns **raw OCR lines** for
downstream template detection and field extraction.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from recognizer.common.config.settings import Settings
from recognizer.domain.recognition.nodes.base_node import BaseRecognitionNode
from recognizer.infrastructure.ocr.paddle_ocr_engine import PaddleOCREngine

logger = logging.getLogger(__name__)


class PaddleRecognitionNode(BaseRecognitionNode):
    """PaddleOCR recognition node (text + confidence + box)."""

    order = 10

    def __init__(
        self,
        use_angle_cls: bool | None = None,
        lang: str | None = None,
        *,
        configured_name: str | None = None,
    ) -> None:
        super().__init__(configured_name=configured_name)
        self.use_angle_cls = (
            Settings.get("ocr.use_angle_cls", True)
            if use_angle_cls is None
            else use_angle_cls
        )
        self.lang = Settings.get("ocr.lang", "ch") if lang is None else lang
        self._engine = PaddleOCREngine()

    @property
    def name(self) -> str:
        return self._resolved_name("paddle_ocr")

    @property
    def node_type(self) -> str:
        return "ocr"

    @property
    def engine_name(self) -> str:
        return "paddleocr"

    def _recognize(self, image_path: str, **kwargs) -> Any:
        """Run PaddleOCR and normalize results.

        Returns:
            list[dict]: [{"text": str, "confidence": float, "box": Any}, ...]
        """
        ocr = self._engine._get_instance()  # singleton PaddleOCR instance
        # PaddleOCR kwargs differ across versions:
        # - older: ocr(..., cls=True)
        # - newer (_pipelines): predict() does not accept `cls`, use `use_textline_orientation`
        try:
            result = ocr.ocr(image_path, cls=self.use_angle_cls)
        except TypeError:
            result = ocr.ocr(image_path, use_textline_orientation=self.use_angle_cls)

        text_lines: List[Dict[str, Any]] = []
        if not result or not result[0]:
            return text_lines

        for line in result[0]:
            # PaddleOCR format: [box, (text, confidence)]
            if not line or len(line) < 2:
                continue

            try:
                box = line[0]
                text_data = line[1]
                text = str(text_data[0]).strip()
                confidence = float(text_data[1])

                if not text:
                    continue

                text_lines.append({"text": text, "confidence": confidence, "box": box})
            except (IndexError, ValueError, TypeError) as e:
                logger.warning("Failed to parse PaddleOCR line: %s", e)
                continue

        return text_lines


class PaddleRecognitionTestNode(PaddleRecognitionNode):
    """Test PaddleOCR recognition node (same logic as PaddleRecognitionNode).

    Use this node to validate multi-node workflows and UI rendering without changing
    recognition behavior. Configure it in DB/workflow with module+class pointing to
    this implementation.
    """

    order = 11

    @property
    def name(self) -> str:
        return self._resolved_name("paddle_ocr_test")
