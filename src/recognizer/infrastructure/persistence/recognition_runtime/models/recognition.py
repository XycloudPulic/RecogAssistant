# SPDX-License-Identifier: MIT

"""识别相关数据模型（通用，不再绑定发票）。

集中包含：
- 枚举：NodeTypeEnum / EngineEnum / ExtractorTypeEnum / FieldTypeEnum
- 模板 ORM：Template / TemplateField / TemplateRule（运行期 DB）
- 识别历史 ORM：RecognitionJob / RecognitionRun / NodeRunResult
- 通用 Pydantic：RecognitionResult / VerifyResult / EngineResultItem / RecognitionResponse 等

历史命名 InvoiceResponse / InvoiceResponseData 已重命名为
RecognitionResponse / RecognitionResponseData，不保留兼容别名。
common_result / engine_results[].result 均为模板驱动的动态 dict。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from recognizer.infrastructure.persistence.recognition_runtime.session import Base

# ==================== 枚举类型 ====================


class NodeTypeEnum(str, Enum):
    """识别节点类型"""

    OCR = "ocr"
    LLM = "llm"
    HUMAN = "human"
    RULE = "rule"


class EngineEnum(str, Enum):
    """识别引擎枚举"""

    PADDLEOCR = "paddleocr"
    PPSTRUCTURE = "ppstructure"
    GPT4V = "gpt4v"
    QWEN_VL = "qwen_vl"


class ExtractorTypeEnum(str, Enum):
    """提取器类型枚举"""

    REGEX = "regex"
    REGION = "region"
    HYBRID = "hybrid"
    TABLE = "table"
    KEY_VALUE = "key_value"


class FieldTypeEnum(str, Enum):
    """字段类型枚举"""

    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    AMOUNT = "amount"


# ==================== 模板 ORM 模型（通用，去 invoice 命名） ====================


class Template(Base):
    """识别模板表（通用，可承载发票/火车票/其他票据）。"""

    __tablename__ = "runtime_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="模板名称")
    code = Column(
        String(50), unique=True, nullable=False, comment="模板代码（唯一标识）"
    )
    engine = Column(String(50), nullable=False, comment="推荐识别引擎")
    category = Column(
        String(50), comment="模板分类（业务上自定义，如 invoice/train_ticket）"
    )
    priority = Column(Integer, default=100, comment="匹配优先级（数字越小越优先）")
    enabled = Column(Boolean, default=True, comment="是否启用")
    description = Column(Text, comment="模板描述")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    fields = relationship(
        "TemplateField", back_populates="template", cascade="all, delete-orphan"
    )
    rules = relationship(
        "TemplateRule", back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<Template(id={self.id}, name='{self.name}', code='{self.code}')>"


class TemplateField(Base):
    """模板字段表（每个字段的提取配置）。"""

    __tablename__ = "runtime_template_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(
        Integer, ForeignKey("runtime_templates.id"), nullable=False, comment="模板ID"
    )
    field_name = Column(
        String(50), nullable=False, comment="字段名（如 invoice_number / train_no）"
    )
    field_label = Column(String(100), comment="字段显示名（如 发票号码 / 车次）")
    field_type = Column(
        String(20), default="string", comment="字段类型：string/number/date/amount"
    )
    extractor_type = Column(
        String(20), nullable=False, comment="提取器类型：regex/region/hybrid"
    )
    extractor_config = Column(JSON, nullable=False, comment="提取器配置（JSON）")
    required = Column(Boolean, default=False, comment="是否必填")
    validation_rule = Column(String(200), comment="验证规则（正则表达式）")
    order_index = Column(Integer, default=0, comment="解析顺序")

    template = relationship("Template", back_populates="fields")

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<TemplateField(id={self.id}, field_name='{self.field_name}')>"


class TemplateRule(Base):
    """模板识别规则表（用于模板匹配打分）。"""

    __tablename__ = "runtime_template_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(
        Integer, ForeignKey("runtime_templates.id"), nullable=False, comment="模板ID"
    )
    rule_type = Column(
        String(20), nullable=False, comment="规则类型：keyword/regex/layout"
    )
    rule_value = Column(Text, nullable=False, comment="规则值")
    weight = Column(Integer, default=1, comment="规则权重（用于打分）")

    template = relationship("Template", back_populates="rules")

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<TemplateRule(id={self.id}, type='{self.rule_type}')>"


# ==================== 识别历史 ORM ====================


class RecognitionJob(Base):
    """识别任务（按上传图像聚合多次运行）。"""

    __tablename__ = "runtime_recognition_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_filename = Column(String(255), nullable=True)
    image_sha256 = Column(String(64), nullable=False, index=True)
    image_path = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    runs = relationship(
        "RecognitionRun", back_populates="job", cascade="all, delete-orphan"
    )


class RecognitionRun(Base):
    """单次识别运行结果。"""

    __tablename__ = "runtime_recognition_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        Integer, ForeignKey("runtime_recognition_jobs.id"), nullable=False, index=True
    )

    status = Column(String(20), default="success", nullable=False)
    cost_time_ms = Column(Integer, default=0, nullable=False)

    orchestrator_config = Column(JSON, nullable=True)
    node_config_snapshot = Column(JSON, nullable=True)

    common_result = Column(JSON, nullable=True)
    verify_result = Column(JSON, nullable=True)
    engine_results = Column(JSON, nullable=True)
    raw_response = Column(JSON, nullable=True)
    template_ctx = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("RecognitionJob", back_populates="runs")
    node_results = relationship(
        "NodeRunResult", back_populates="run", cascade="all, delete-orphan"
    )


class NodeRunResult(Base):
    """节点级运行结果。"""

    __tablename__ = "runtime_node_run_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        Integer, ForeignKey("runtime_recognition_runs.id"), nullable=False, index=True
    )

    node_name = Column(String(100), nullable=False)
    node_type = Column(String(20), nullable=True)
    engine = Column(String(50), nullable=True)
    status = Column(String(20), default="success", nullable=False)
    cost_time_ms = Column(Integer, default=0, nullable=False)

    output_json = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    run = relationship("RecognitionRun", back_populates="node_results")


# ==================== 通用 Pydantic 模型 ====================


class TemplateFieldRegion(BaseModel):
    """模板字段的相对坐标区域（0~1）。"""

    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0


class RecognitionResult(BaseModel):
    """单个识别节点统一返回的结果。"""

    engine: str
    node_type: str
    raw_data: Any
    cost_time: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "node_type": self.node_type,
            "cost_time": self.cost_time,
            "metadata": self.metadata,
        }


class FieldValueGroup(BaseModel):
    """字段值分组（用于一致性对比）。"""

    value: str
    count: int
    sources: List[str] = Field(default_factory=list)


class DiffDetail(BaseModel):
    """字段差异详情。"""

    field: str
    values: List[FieldValueGroup] = Field(default_factory=list)
    status: str = "conflict"  # consistent / format_diff / conflict / missing


class VerifyResult(BaseModel):
    """一致性校验结果。"""

    is_consistent: bool = True
    total_fields: int = 0
    consistent_fields: int = 0
    inconsistent_fields: int = 0
    diff_details: List[DiffDetail] = Field(default_factory=list)


class EngineResultItem(BaseModel):
    """单引擎/解析器结果（动态 schema）。"""

    id: str
    engine: str
    parser: str
    result: Dict[str, Any] = Field(default_factory=dict)
    validation_result: Optional["ValidationResult"] = None
    cost_time: Optional[int] = None


class FieldValidationError(BaseModel):
    validator_id: Optional[int] = None
    validator_type: str
    message: str


class FieldValidationItem(BaseModel):
    field: str
    value: Any = None
    is_valid: bool = True
    errors: List[FieldValidationError] = Field(default_factory=list)


class ValidationResult(BaseModel):
    is_valid: bool = True
    total_fields: int = 0
    valid_fields: int = 0
    invalid_fields: int = 0
    items: List[FieldValidationItem] = Field(default_factory=list)


class RecognitionResponseData(BaseModel):
    """API 响应数据（通用）。

    common_result 由命中模板字段决定，各类票据共享同一份响应结构。
    """

    common_result: Optional[Dict[str, Any]] = None
    verify_result: Optional[VerifyResult] = None
    validation_result: Optional[ValidationResult] = None
    engine_results: List[EngineResultItem] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None


class RecognitionResponse(BaseModel):
    """API 统一响应。"""

    code: int = 0
    msg: str = "SUCCESS"
    data: Optional[RecognitionResponseData] = None
