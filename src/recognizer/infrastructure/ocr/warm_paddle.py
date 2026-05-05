# SPDX-License-Identifier: MIT

"""`service.bat init` entry: download/cache Paddle OCR models before `service.bat start`.

与 API 进程中的单例无关；本脚本退出后仍会落盘到 `PADDLE_OCR_BASE_DIR`，启动时再次构造会复用缓存。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def main() -> int:
    from recognizer.common.config.settings import Settings
    from recognizer.common.logging.setup import setup_logging

    Settings.load()
    setup_logging()

    if not Settings.get("ocr.prefetch_on_init", True):
        print(
            "[init] ocr.prefetch_on_init=false — skip Paddle warm-up", file=sys.stderr
        )
        return 0

    # Ensure PaddleOCR cache root is stable even if upstream falls back to HOME/USERPROFILE.
    # This avoids models being downloaded into C:\\Users\\<name>\\.paddleocr on some setups.
    base = (
        Settings.get("ocr.paddle_ocr_home")
        if Settings.get("ocr.paddle_ocr_home") not in (None, "")
        else Settings.get("ocr.models_dir")
    )
    base_path = Settings.resolve_optional_project_path(base)
    if base_path is not None:
        try:
            base_path.mkdir(parents=True, exist_ok=True)
            base_abs = str(base_path.resolve())
            base_abs_with_sep = os.path.join(base_abs, "")
            # Force override for warm-up process: upstream may derive cache paths from HOME/USERPROFILE.
            os.environ["PADDLE_OCR_BASE_DIR"] = base_abs_with_sep
            os.environ["PADDLEOCR_HOME"] = base_abs_with_sep
            os.environ["PADDLEOCR_BASE_DIR"] = base_abs_with_sep
            # Some PaddleOCR builds decide cache dir by HOME/USERPROFILE; redirect for warm-up only.
            os.environ["HOME"] = base_abs
            if os.name == "nt":
                os.environ["USERPROFILE"] = base_abs
                # Some libraries derive "~" from HOMEDRIVE/HOMEPATH.
                d = str(Path(base_abs).drive) or "C:"
                os.environ["HOMEDRIVE"] = d
                os.environ["HOMEPATH"] = "\\"
        except Exception:
            pass

    # Import AFTER env vars are set; PaddleOCR may read cache roots at import time.
    from recognizer.infrastructure.ocr.paddle_ocr_engine import paddle_ocr

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
