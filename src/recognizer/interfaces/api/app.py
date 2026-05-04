# SPDX-License-Identifier: MIT

"""Recognition Assistant - FastAPI application.

主入口路径：`/api/v1/recognition/parse`（通用识别，按命中模板字段产出动态结果）。
所有旧的 `/invoice/parse`、`/template/*`、`/nodes/*` 别名已移除。
"""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from recognizer.application.errors import (
    ApplicationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from recognizer.common.config.settings import Settings
from recognizer.common.logging.setup import setup_logging
from recognizer.common.middleware import RequestIDMiddleware

# Initialize logging (will be called when Settings is first accessed)
logger = logging.getLogger(__name__)


def _run_paddle_ocr_prefetch() -> None:
    from recognizer.infrastructure.ocr.paddle_ocr_engine import (
        prefetch_paddle_ocr_if_enabled,
    )

    prefetch_paddle_ocr_if_enabled()


app = FastAPI(
    title="Recognition Assistant",
    description="通用识别系统（OCR + LLM + 模板抽取），支持发票/火车票等多种票据。",
    version="3.0.0",
)


@app.exception_handler(ApplicationError)
async def handle_application_error(_: Request, exc: ApplicationError) -> JSONResponse:
    status_code = 500
    if isinstance(exc, ValidationError):
        status_code = 400
    elif isinstance(exc, NotFoundError):
        status_code = 404
    elif isinstance(exc, ConflictError):
        status_code = 409
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


# 注册请求追踪中间件（必须在最前面）
app.add_middleware(RequestIDMiddleware)

# Recognition routes (generic, document-agnostic)
from recognizer.interfaces.api.routes.recognition import router as recognition_router

app.include_router(recognition_router)

# Config/admin APIs
from recognizer.interfaces.api.routes.export_configs import (
    router as export_configs_router,
)
from recognizer.interfaces.api.routes.exports import router as exports_router
from recognizer.interfaces.api.routes.llm_configs import router as llm_configs_router
from recognizer.interfaces.api.routes.logs import router as logs_router
from recognizer.interfaces.api.routes.nodes import router as nodes_router
from recognizer.interfaces.api.routes.recognition_history import (
    router as recognition_history_router,
)
from recognizer.interfaces.api.routes.rules import router as rulesets_router
from recognizer.interfaces.api.routes.templates import router as templates_router
from recognizer.interfaces.api.routes.validators import router as validators_router
from recognizer.interfaces.api.routes.workflows import router as workflows_router

app.include_router(templates_router)
app.include_router(rulesets_router)
app.include_router(llm_configs_router)
app.include_router(nodes_router)
app.include_router(logs_router)
app.include_router(export_configs_router)
app.include_router(exports_router)
app.include_router(recognition_history_router)
app.include_router(workflows_router)
app.include_router(validators_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on application startup."""
    # Initialize logging (after Settings is loaded)
    setup_logging()

    # Initialize database
    from recognizer.infrastructure.persistence.recognition_runtime.session import (
        init_database,
    )

    init_database()
    logger.info("Database initialized")

    # 默认不在此预载 Paddle（建议 service.bat init + ocr.prefetch_on_init 先落盘模型）。
    # 若 ocr.prefetch_on_startup=true：阻塞预载或配合 prefetch_non_blocking 后台任务；冷机未 init 时可加长 SVC_BACKEND_WAIT_SEC。
    if Settings.get("ocr.prefetch_on_startup", False):
        if Settings.get("ocr.prefetch_non_blocking", False):

            async def _paddle_prefetch_background() -> None:
                try:
                    await asyncio.to_thread(_run_paddle_ocr_prefetch)
                except Exception:
                    logger.exception("PaddleOCR background prefetch task failed")

            asyncio.create_task(_paddle_prefetch_background())
            logger.info(
                "PaddleOCR prefetch in background (port may listen before OCR models are ready)"
            )
        else:
            await asyncio.to_thread(_run_paddle_ocr_prefetch)
            logger.info("PaddleOCR prefetch finished; API will now accept traffic")
    else:
        logger.info(
            "PaddleOCR startup prefetch skipped (ocr.prefetch_on_startup=false)"
        )

    # TODO: Import extractors to trigger auto-registration
    # from recognizer.domain.extraction.extractors import *

    logger.info("Recognition service started successfully")


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


def main() -> None:
    """Application entry point."""
    host = Settings.get("server.host", "0.0.0.0")
    port = Settings.get("server.port", 8000)
    debug = Settings.get("server.debug", False)
    workers = Settings.get("server.workers", 1)

    logger.info("Starting Recognition service: %s:%s", host, port)
    logger.info("Debug mode: %s, Workers: %s", debug, workers)

    uvicorn.run(
        "recognizer.interfaces.api.app:app",
        host=host,
        port=port,
        reload=debug,
        workers=workers,
    )


if __name__ == "__main__":
    main()
