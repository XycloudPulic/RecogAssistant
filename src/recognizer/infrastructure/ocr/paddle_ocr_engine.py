# SPDX-License-Identifier: MIT

"""PaddleOCR引擎实现"""

import functools
import importlib
import logging
import os
import tarfile
import threading
from pathlib import Path
from typing import List, Tuple

from recognizer.common.config.settings import Settings
from recognizer.infrastructure.ocr.base_ocr_engine import BaseOCREngine

logger = logging.getLogger(__name__)

_ENV_PADDLE_OCR_HOME = "PADDLE_OCR_BASE_DIR"
"""paddleocr.paddleocr 在 import 时读取此环境变量作为下载与本机缓存根目录。"""


def _ensure_paddle_ocr_base_dir_before_import() -> None:
    """在 import paddleocr 之前设置缓存根目录。

    PaddleOCR（2.x）：``BASE_DIR = os.environ.get("PADDLE_OCR_BASE_DIR", "~/.paddleocr/")``
    """
    paddle_home_raw = Settings.get("ocr.paddle_ocr_home")
    fallback_raw = Settings.get("ocr.models_dir")
    raw = paddle_home_raw if paddle_home_raw not in (None, "") else fallback_raw
    home = Settings.resolve_optional_project_path(raw)
    if home is None:
        logger.info(
            "PaddleOCR 未配置 %s（且未配置 ocr.models_dir），使用默认 ~/.paddleocr/",
            _ENV_PADDLE_OCR_HOME,
        )
        return
    home.mkdir(parents=True, exist_ok=True)
    path_with_sep = os.path.join(str(home.resolve()), "")
    os.environ[_ENV_PADDLE_OCR_HOME] = path_with_sep
    # Some PaddleOCR/Paddle versions use different env keys for cache roots.
    # Setting these is harmless and improves cross-version portability.
    os.environ.setdefault("PADDLEOCR_HOME", path_with_sep)
    os.environ.setdefault("PADDLEOCR_BASE_DIR", path_with_sep)
    logger.info(
        "%s=%s （首次将由 Paddle 自动下载模型到此目录树下）",
        _ENV_PADDLE_OCR_HOME,
        path_with_sep,
    )


def _paddle_infer_subdirs_for_lang(lang: str) -> tuple[str, str, str]:
    """与 PaddleOCR 2.x 常见离线 inference 解压目录名一致（PP-OCRv4 为主）。

    未单独列出的 lang 退回中文三套名，可自行用 ocr.det_model_dir 等覆盖。
    """
    k = str(lang or "ch").strip().lower()
    if k == "en":
        return (
            "en_PP-OCRv4_det_infer",
            "en_PP-OCRv4_rec_infer",
            "ch_ppocr_mobile_v2.0_cls_infer",
        )
    if k == "chinese_cht":
        return (
            "chinese_cht_PP-OCRv3_det_infer",
            "chinese_cht_PP-OCRv3_rec_infer",
            "ch_ppocr_mobile_v2.0_cls_infer",
        )
    if k.startswith("ch"):
        return (
            "ch_PP-OCRv4_det_infer",
            "ch_PP-OCRv4_rec_infer",
            "ch_ppocr_mobile_v2.0_cls_infer",
        )
    logger.warning(
        "PaddleOCR 未为 lang=%s 配置默认模型子目录，使用中文 ch_PP-OCRv4_* 命名；请到 settings 中为 det/rec/cls 指定路径",
        k,
    )
    return (
        "ch_PP-OCRv4_det_infer",
        "ch_PP-OCRv4_rec_infer",
        "ch_ppocr_mobile_v2.0_cls_infer",
    )


def _patch_paddleocr_download_robustness() -> None:
    """Make PaddleOCR model download resilient to partial/corrupt .tar files.

    Upstream ``download_with_progressbar`` skips re-download if the path exists, and
    ``maybe_download`` opens the tar without validating integrity — a truncated
    download causes ``tarfile.ReadError: unexpected end of data`` on every run.

    PaddleOCR loads ``ppocr`` as a top-level package (``import ppocr``), which is a
    *different module object* than ``paddleocr.ppocr`` in some installs. Patch both.
    """
    modules: list = []
    for mod_name in ("ppocr.utils.network", "paddleocr.ppocr.utils.network"):
        try:
            modules.append(importlib.import_module(mod_name))
        except Exception:
            continue

    if not modules:
        return

    def _apply_to(paddle_network) -> None:
        if getattr(paddle_network, "_recog_assistant_download_patch", False):
            return

        orig_download = paddle_network.download_with_progressbar
        orig_maybe = paddle_network.maybe_download

        @functools.wraps(orig_download)
        def download_with_progressbar(url, save_path):
            if save_path and os.path.exists(save_path):
                try:
                    sz = os.path.getsize(save_path)
                except OSError:
                    sz = 0
                if sz < 1024:
                    try:
                        os.remove(save_path)
                    except OSError:
                        pass
                else:
                    try:
                        with tarfile.open(save_path, "r") as tf:
                            tf.getmembers()
                        return
                    except (tarfile.ReadError, OSError):
                        try:
                            os.remove(save_path)
                        except OSError:
                            pass
            orig_download(url, save_path)
            if save_path and os.path.exists(save_path):
                try:
                    with tarfile.open(save_path, "r") as tf:
                        tf.getmembers()
                except (tarfile.ReadError, OSError) as e:
                    try:
                        os.remove(save_path)
                    except OSError:
                        pass
                    raise RuntimeError(
                        f"PaddleOCR model archive is corrupt or incomplete: {save_path}. "
                        f"Removed for retry. ({e})"
                    ) from e

        @functools.wraps(orig_maybe)
        def maybe_download(model_storage_directory, url):
            last_err: Exception | None = None
            for attempt in range(2):
                try:
                    return orig_maybe(model_storage_directory, url)
                except (tarfile.ReadError, OSError, RuntimeError) as e:
                    last_err = e
                    tar_name = url.split("/")[-1]
                    tmp_path = os.path.join(model_storage_directory, tar_name)
                    for p in (tmp_path,):
                        try:
                            if os.path.isfile(p):
                                os.remove(p)
                        except OSError:
                            pass
                    logger.warning(
                        "PaddleOCR model download/extract failed (attempt %s/2): %s",
                        attempt + 1,
                        e,
                    )
            if last_err:
                raise last_err

        paddle_network.download_with_progressbar = download_with_progressbar
        paddle_network.maybe_download = maybe_download
        paddle_network._recog_assistant_download_patch = True

    seen_ids: set[int] = set()
    for m in modules:
        mid = id(m)
        if mid in seen_ids:
            continue
        seen_ids.add(mid)
        _apply_to(m)

    # paddleocr.paddleocr binds maybe_download at import time; re-bind to patched callables.
    try:
        import paddleocr.paddleocr as paddleocr_entry

        src = None
        for m in modules:
            if getattr(m, "_recog_assistant_download_patch", False):
                src = m
                break
        if src is not None:
            paddleocr_entry.maybe_download = src.maybe_download
            paddleocr_entry.download_with_progressbar = src.download_with_progressbar
    except Exception:
        pass

    logger.info(
        "Applied PaddleOCR download robustness patch (corrupt tar retry) to: %s",
        ", ".join(sorted({m.__name__ for m in modules})),
    )


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR引擎实现"""

    _instance = None
    _init_lock = threading.Lock()

    @property
    def name(self) -> str:
        return "paddle"

    def recognize(self, image_path: str) -> List[Tuple[str, float]]:
        """执行OCR识别

        Args:
            image_path: 图片路径

        Returns:
            识别结果列表 [(text, confidence), ...]
        """
        ocr = self._get_instance()
        # Delegate to PaddleOCR instance; kwargs vary by version.
        try:
            result = ocr.ocr(image_path, cls=True)
        except TypeError:
            result = ocr.ocr(image_path, use_textline_orientation=True)

        text_lines: List[Tuple[str, float]] = []
        if result and result[0]:
            for line in result[0]:
                # PaddleOCR 2.x 格式: [box, (text, confidence)]
                if line and len(line) >= 2:
                    text = line[1][0]
                    conf = float(line[1][1])  # 置信度 0~1
                    if text and text.strip():
                        text_lines.append((text.strip(), conf))

        return text_lines

    def _get_instance(self):
        """获取PaddleOCR单例实例"""
        if PaddleOCREngine._instance is not None:
            return PaddleOCREngine._instance
        with PaddleOCREngine._init_lock:
            if PaddleOCREngine._instance is not None:
                return PaddleOCREngine._instance
            # PaddleOCR 3.x may trigger PIR/oneDNN issues on some Windows setups.
            # These flags are safe no-ops for older versions.
            os.environ["FLAGS_enable_pir_api"] = "0"
            os.environ["FLAGS_enable_pir_in_executor"] = "0"
            os.environ["FLAGS_enable_new_executor"] = "0"
            os.environ["FLAGS_use_mkldnn"] = "0"

            # 须在 import paddleocr 之前写入；否则仍会落到 ~/.paddleocr/
            Settings.load()
            _ensure_paddle_ocr_base_dir_before_import()
            _patch_paddleocr_download_robustness()

            from paddleocr import PaddleOCR  # lazy import after env flags

            # 从配置读取参数
            use_angle_cls = Settings.get("ocr.use_angle_cls", True)
            lang = Settings.get("ocr.lang", "ch")
            # 仅传入已存在的本地目录：未解压时留白，由 Paddle 依 PADDLE_OCR_BASE_DIR 自动下载缓存
            model_kw: dict = {}
            for key in ("det_model_dir", "rec_model_dir", "cls_model_dir"):
                p = Settings.resolve_optional_project_path(Settings.get(f"ocr.{key}"))
                if p is None:
                    continue
                if p.is_dir():
                    model_kw[key] = str(p)
                else:
                    logger.warning(
                        "已配置 PaddleOCR %s 但该路径不存在或非目录（将忽略该项，沿用自动下载）：%s",
                        key,
                        p,
                    )

            root = Settings.resolve_optional_project_path(
                Settings.get("ocr.models_dir")
            )
            det_sub, rec_sub, cls_sub = _paddle_infer_subdirs_for_lang(lang)
            for key, sub in (
                ("det_model_dir", det_sub),
                ("rec_model_dir", rec_sub),
                ("cls_model_dir", cls_sub),
            ):
                if key in model_kw or root is None:
                    continue
                p = root / Path(sub)
                if p.is_dir():
                    model_kw[key] = str(p)
                else:
                    logger.debug(
                        "models_dir + %s 尚未存在，不交予 PaddleOCR 以免阻塞自动下载路径",
                        sub,
                    )
            logger.info(
                "初始化 PaddleOCR: use_angle_cls=%s, lang=%s, model_dirs=%s",
                use_angle_cls,
                lang,
                {
                    k: model_kw.get(k)
                    for k in ("det_model_dir", "rec_model_dir", "cls_model_dir")
                },
            )
            try:
                # PaddleOCR 3.x: use_textline_orientation replaces use_angle_cls
                PaddleOCREngine._instance = PaddleOCR(
                    use_textline_orientation=use_angle_cls,
                    lang=lang,
                    **model_kw,
                )
            except TypeError:
                PaddleOCREngine._instance = PaddleOCR(
                    use_angle_cls=use_angle_cls,
                    lang=lang,
                    **model_kw,
                )
        return PaddleOCREngine._instance

    def ensure_loaded(self) -> None:
        """构造内部 PaddleOCR 单例（会触发模型下载/加载）。"""
        self._get_instance()


def prefetch_paddle_ocr_if_enabled() -> None:
    """在 API 启动时调用：按配置预加载，避免首次识别时才下载模型。"""
    Settings.load()
    if not Settings.get("ocr.prefetch_on_startup", False):
        logger.info("PaddleOCR 启动预加载已关闭（ocr.prefetch_on_startup=false）")
        return
    try:
        logger.info(
            "PaddleOCR 启动预加载：开始构造引擎（可能下载模型，耗时取决于网络与缓存）…"
        )
        paddle_ocr.ensure_loaded()
        logger.info("PaddleOCR 启动预加载完成")
    except Exception:
        logger.exception("PaddleOCR 启动预加载失败；首次识别时会再次尝试初始化")


# 创建全局实例
paddle_ocr = PaddleOCREngine()
