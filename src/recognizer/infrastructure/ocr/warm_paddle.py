# SPDX-License-Identifier: MIT

"""`service.bat init` entry: download/cache Paddle OCR models before `service.bat start`.

与 API 进程中的单例无关；本脚本退出后仍会落盘到 `PADDLE_OCR_BASE_DIR`，启动时再次构造会复用缓存。
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def main() -> int:
    from recognizer.common.config.settings import Settings
    from recognizer.common.logging.setup import setup_logging
    from recognizer.infrastructure.ocr.paddle_ocr_engine import paddle_ocr

    Settings.load()
    setup_logging()

    if not Settings.get("ocr.prefetch_on_init", True):
        print(
            "[init] ocr.prefetch_on_init=false — skip Paddle warm-up", file=sys.stderr
        )
        return 0

    logger.info(
        "service init: warming up PaddleOCR (may download; see ocr.models_dir / PADDLE_OCR_BASE_DIR)"
    )
    try:
        paddle_ocr.ensure_loaded()
    except Exception:
        logger.exception("service init: PaddleOCR warm-up failed")
        print(
            "[init][ERROR] PaddleOCR warm-up failed (network or disk). "
            "You can retry: py -m recognizer.infrastructure.ocr.warm_paddle",
            file=sys.stderr,
        )
        return 1

    logger.info("service init: PaddleOCR warm-up finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
