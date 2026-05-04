# SPDX-License-Identifier: MIT

"""PP-Structure版面分析引擎实现"""

import logging
import re
from typing import List, Tuple

import cv2
from paddleocr import PPStructure

from recognizer.infrastructure.ocr.base_ocr_engine import BaseOCREngine
from recognizer.infrastructure.ocr.ocr_engine_factory import OCREngineFactory

logger = logging.getLogger(__name__)


class PPStructureEngine(BaseOCREngine):
    """PP-Structure版面分析引擎实现"""

    _instance: PPStructure = None

    @property
    def name(self) -> str:
        return "ppstructure"

    def recognize(self, image_path: str) -> List[Tuple[str, float]]:
        """执行版面结构识别

        Args:
            image_path: 图片路径

        Returns:
            识别结果列表 [(text, confidence), ...]
        """
        engine = self._get_instance()
        img = cv2.imread(image_path)
        if img is None:
            raise RuntimeError(f"无法读取图片: {image_path}")

        result = engine(img)

        if not result:
            return []

        # 提取所有单元格的文本
        cell_texts = self._extract_all_cells(result)

        # 转换为标准格式 [(text, confidence), ...]
        # PP-Structure不提供per-cell置信度，使用默认值0.85
        default_confidence = 0.85
        return [(text, default_confidence) for text in cell_texts]

    def recognize_with_structure(self, image_path: str) -> dict:
        """执行版面识别并返回结构化数据（兼容旧接口）

        Args:
            image_path: 图片路径

        Returns:
            dict: {
                'html': str,           # 原始HTML表格
                'cell_texts': list,    # 每个单元格的文本列表
                'confidence': float,   # 整体置信度
            }
        """
        engine = self._get_instance()
        img = cv2.imread(image_path)
        if img is None:
            raise RuntimeError(f"无法读取图片: {image_path}")

        result = engine(img)

        if not result:
            return {"html": "", "cell_texts": [], "confidence": 0.85}

        # 取第一个表格结果
        first = result[0]
        res = first.get("res", {})

        html = ""
        if isinstance(res, dict):
            html = res.get("html", "")

        # 从HTML中提取每个单元格的文本
        cell_texts = self._extract_cell_texts(html)

        logger.info(f"PP-Structure识别完成，共 {len(cell_texts)} 个单元格")
        for i, text in enumerate(cell_texts):
            logger.info(f"  cell[{i}]: {text[:80]}")

        return {
            "html": html,
            "cell_texts": cell_texts,
            "confidence": 0.85,
        }

    def _get_instance(self) -> PPStructure:
        """获取PP-Structure单例实例"""
        if PPStructureEngine._instance is None:
            logger.info("初始化 PP-Structure: layout=False (纯表格识别模式)")
            PPStructureEngine._instance = PPStructure(
                layout=False,  # 不做版面分析，直接表格识别
            )
        return PPStructureEngine._instance

    def _extract_all_cells(self, result: list) -> List[str]:
        """从PP-Structure结果中提取所有单元格文本"""
        if not result:
            return []

        # 取第一个表格结果
        first = result[0]
        res = first.get("res", {})

        html = ""
        if isinstance(res, dict):
            html = res.get("html", "")

        return self._extract_cell_texts(html)

    def _extract_cell_texts(self, html: str) -> List[str]:
        """
        从HTML表格中提取每个<td>单元格的纯文本

        Args:
            html: PP-Structure输出的HTML字符串

        Returns:
            非空单元格文本列表
        """
        if not html:
            return []

        # 匹配所有 <td...>内容</td>
        td_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
        cells = td_pattern.findall(html)

        # 清理HTML标签，提取纯文本
        tag_pattern = re.compile(r"<[^>]+>")
        result = []
        for cell in cells:
            text = tag_pattern.sub("", cell).strip()
            if text:
                result.append(text)

        return result

    def __repr__(self) -> str:
        return f"<PPStructureEngine(name='{self.name}')>"


# 自动注册到OCR引擎工厂
OCREngineFactory.register("ppstructure", PPStructureEngine)

# 创建全局实例（保持向后兼容）
pp_structure = PPStructureEngine()


# ==================== 向后兼容层 ====================
# 以下函数保留以兼容现有代码调用，内部委托给PPStructureEngine实例


def structure_recognize(image_path: str) -> dict:
    """兼容旧接口：对图片进行PP-Structure表格结构识别（委托给PPStructureEngine）"""
    return pp_structure.recognize_with_structure(image_path)
