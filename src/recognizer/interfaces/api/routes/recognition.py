# SPDX-License-Identifier: MIT

"""通用识别 API 路由（不绑定具体票据类型）。

接口：`POST /api/v1/recognition/parse`，与历史 `/invoice/parse` 等价但语义通用。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from recognizer.application.errors import (
    ApplicationError,
    NotFoundError,
    ValidationError,
)
from recognizer.application.services.recognition_history import (
    RecognitionHistoryService,
)
from recognizer.application.services.workflow_orchestrator_factory import (
    WorkflowOrchestratorFactory,
)
from recognizer.application.workflows.recognition_orchestrator import (
    RecognitionOrchestrator,
)
from recognizer.common.config.settings import Settings
from recognizer.common.utils.file import (
    cleanup_file,
    save_upload_file,
    validate_file_extension,
)
from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    RecognitionResponse,
)
from recognizer.infrastructure.persistence.recognition_runtime.session import (
    init_database,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["recognition"])

# 全局编排器实例（懒加载）
orchestrator: Optional[RecognitionOrchestrator] = None
history_service = RecognitionHistoryService()
workflow_orchestrator_factory = WorkflowOrchestratorFactory()


def get_orchestrator() -> RecognitionOrchestrator:
    """获取或创建编排器实例。"""
    global orchestrator
    if orchestrator is None:
        init_database()
        orchestrator = RecognitionOrchestrator()
        logger.info("RecognitionOrchestrator initialized")
    return orchestrator


@router.post("/recognition/parse", response_model=RecognitionResponse)
async def parse_document(
    file: UploadFile = File(...),
    workflow_id: Optional[int] = Query(None),
) -> RecognitionResponse:
    """通用识别接口。

    1. RecognitionOrchestrator 调度识别节点
    2. OCR/LLM 节点产出 raw_data
    3. FieldExtractionEngine 按命中模板字段抽取动态 schema
    4. 返回统一 RecognitionResponse
    """
    if not validate_file_extension(file.filename or ""):
        raise HTTPException(
            status_code=400, detail="Unsupported file type. Allowed extensions"
        )

    file_path: Optional[str] = None
    upload_path: Optional[str] = None
    extra_cleanup: list[str] = []
    try:
        # Server-side debug switch (backend-controlled):
        # - api.recognition.return_debug=false: NEVER include `data.debug`
        # - api.recognition.return_debug=true: include `data.debug`
        debug = bool(Settings.get("api.recognition.return_debug", False))

        logger.info("Received file: %s", file.filename)
        file_bytes = await file.read()
        original_name = file.filename or "upload.jpg"
        upload_path = save_upload_file(file_bytes, original_name)
        file_path = upload_path
        logger.info("File saved to: %s", file_path)

        ext = Path(original_name).suffix.lower()
        if ext == ".pdf":
            try:
                import fitz  # type: ignore
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail="PDF 识别需要额外依赖 PyMuPDF（pymupdf）。请先安装后重试。",
                )
            doc = fitz.open(file_path)
            try:
                if doc.page_count <= 0:
                    raise HTTPException(
                        status_code=400, detail="PDF 文件为空，无法识别"
                    )
                page0 = doc.load_page(0)
                pix = page0.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                png_path = str(Path(file_path).with_suffix(".page1.png"))
                pix.save(png_path)
                extra_cleanup.append(png_path)
                file_path = png_path
                logger.info("PDF rendered to image: %s", file_path)
            finally:
                doc.close()

        job_id = history_service.upsert_job(
            file_bytes=file_bytes,
            original_filename=file.filename,
            temp_path=upload_path,
        )

        default_workflow_id_used: Optional[int] = None
        if workflow_id is not None:
            orc = workflow_orchestrator_factory.create(int(workflow_id))
        else:
            default_workflow_id_used = (
                workflow_orchestrator_factory.get_default_workflow_id()
            )
            orc = (
                workflow_orchestrator_factory.create(int(default_workflow_id_used))
                if default_workflow_id_used is not None
                else get_orchestrator()
            )

        response = orc.execute(file_path, debug=debug)

        if (
            debug
            and getattr(response, "data", None) is not None
            and response.data
            and response.data.debug is not None
        ):
            try:
                response.data.debug["workflow_id_used"] = (
                    int(workflow_id)
                    if workflow_id is not None
                    else default_workflow_id_used
                )
            except Exception:
                pass

        try:
            if hasattr(response, "model_dump"):
                persist_payload = response.model_dump(mode="json")
            else:
                persist_payload = response.dict()
            run_id = history_service.save_run(
                job_id=int(job_id),
                response=persist_payload,
            )
            logger.info(
                "Persisted recognition run: run_id=%s job_id=%s",
                run_id,
                job_id,
            )
            if debug and getattr(response, "data", None) is not None:
                try:
                    response.data.debug = response.data.debug or {}
                    response.data.debug["persisted_job_id"] = int(job_id)
                    response.data.debug["persisted_run_id"] = int(run_id)
                except Exception:
                    pass
        except Exception:
            logger.exception("Failed to persist recognition run")

        logger.info("Recognition parsed: code=%d, msg=%s", response.code, response.msg)
        return response

    except Exception as exc:
        if isinstance(exc, ApplicationError):
            status_code = 500
            if isinstance(exc, NotFoundError):
                status_code = 404
            elif isinstance(exc, ValidationError):
                status_code = 400
            return RecognitionResponse(code=status_code, msg=str(exc), data=None)
        logger.error("Recognition failed: %s", str(exc), exc_info=True)
        return RecognitionResponse(code=500, msg=str(exc), data=None)
    finally:
        for p in extra_cleanup:
            cleanup_file(p)
        cleanup_file(upload_path or file_path)


@router.get("/health")
async def health_check() -> dict:
    """健康检查。"""
    return {
        "status": "ok",
        "version": "2.0.0",
        "architecture": "recognition-extraction-separated",
    }
