# SPDX-License-Identifier: MIT

"""``service.bat clear`` / 手工「恢复出厂」：删本机识别库与项目内 OCR 模型缓存。

- 删除 ``Settings.db_recognition_path()`` 对应文件及 SQLite ``-wal`` / ``-shm``（路径须在项目根下才删，防误删）。
- 删除 YAML 中 ``ocr.paddle_ocr_home``、``ocr.models_dir`` 解析到、且位于项目根下的目录树。

不是删 pip 包；删库后需再跑 ``init`` / ``initial_bootstrap`` 才能重建表与种子数据。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _is_under_project(target: Path, root: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _clear_database_bundle() -> None:
    from recognizer.common.config.settings import Settings

    root = Settings.project_root().resolve()
    db = Settings.db_recognition_path().resolve()
    try:
        db.relative_to(root)
    except ValueError:
        print(
            f"[clear] Skip database (path not under project root): {db}",
            file=sys.stderr,
        )
        return

    candidates = (
        db,
        db.parent / f"{db.name}-wal",
        db.parent / f"{db.name}-shm",
    )
    removed = 0
    for f in candidates:
        if f.is_file():
            f.unlink()
            print(f"[clear] removed {f.relative_to(root)}")
            removed += 1
    if removed == 0 and not candidates[0].exists():
        print("[clear] database file already absent")


def _clear_paddle_ocr_model_dirs() -> None:
    from recognizer.common.config.settings import Settings

    root = Settings.project_root().resolve()
    dirs: dict[Path, None] = {}
    for yaml_key in ("paddle_ocr_home", "models_dir"):
        raw = Settings.get(f"ocr.{yaml_key}")
        resolved = Settings.resolve_optional_project_path(raw)
        if resolved is None:
            continue
        if not _is_under_project(resolved, root):
            print(
                f"[clear] Skip OCR path (outside project root): {resolved}",
                file=sys.stderr,
            )
            continue
        dirs[resolved.resolve()] = None

    if not dirs:
        print(
            "[clear] no PaddleOCR model dirs to clear "
            "(ocr.paddle_ocr_home / ocr.models_dir unset or empty)"
        )
        return

    for d in sorted(dirs.keys()):
        if not d.exists():
            print(f"[clear] PaddleOCR path already absent {d.relative_to(root)}")
            continue
        if d.is_file():
            d.unlink()
            print(f"[clear] removed file {d.relative_to(root)}")
            continue
        try:
            shutil.rmtree(d)
            print(f"[clear] removed tree {d.relative_to(root)}")
        except OSError as exc:
            print(
                f"[clear] WARN could not fully remove {d}: {exc}",
                file=sys.stderr,
            )


def main() -> int:
    from recognizer.common.config.settings import Settings

    Settings.load()
    _clear_database_bundle()
    _clear_paddle_ocr_model_dirs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
