# SPDX-License-Identifier: MIT

"""文件处理工具"""

import os
import uuid
from pathlib import Path
from typing import Optional

from recognizer.common.config.settings import Settings


def get_temp_dir() -> Path:
    """获取临时文件目录"""
    temp_dir = Settings.get("file.temp_dir")
    if temp_dir:
        path = Path(temp_dir)
    else:
        path = Path(os.getcwd()) / "temp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload_file(
    file_bytes: bytes, filename: str, suffix: Optional[str] = None
) -> str:
    """
    保存上传文件到临时目录

    Args:
        file_bytes: 文件二进制内容
        filename: 原始文件名
        suffix: 自定义后缀（可选）

    Returns:
        保存后的文件路径
    """
    if suffix is None:
        suffix = Path(filename).suffix

    temp_dir = get_temp_dir()
    unique_name = f"upload_{uuid.uuid4().hex[:8]}{suffix}"
    file_path = temp_dir / unique_name

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    return str(file_path)


def cleanup_file(file_path: str) -> None:
    """
    清理临时文件

    Args:
        file_path: 文件路径
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
    except Exception:
        pass


def validate_file_extension(filename: str) -> bool:
    """
    验证文件扩展名是否允许

    Args:
        filename: 文件名

    Returns:
        是否允许
    """
    allowed = Settings.get("file.allowed_extensions", [".jpg", ".jpeg", ".png", ".pdf"])
    ext = Path(filename).suffix.lower()
    return ext in allowed


def guess_mime_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".png":
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".bmp":
        return "image/bmp"
    return "application/octet-stream"
