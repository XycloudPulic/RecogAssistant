# SPDX-License-Identifier: MIT

"""发票OCR助手 - 统一启动脚本

同时启动FastAPI后端和Streamlit前端
"""

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def print_banner():
    print("=" * 60)
    print("  发票OCR识别助手")
    print("  Invoice OCR Assistant")
    print("=" * 60)
    print()


def check_dependencies():
    print("[1/3] 检查依赖...")
    required = ["streamlit", "requests", "openai", "fastapi", "uvicorn"]
    missing = [p for p in required if not _importable(p)]

    if missing:
        print(f"  缺少: {', '.join(missing)}")
        print("  请运行: pip install -r requirements.txt")
        return False
    print("  依赖检查通过")
    return True


def _importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def start_fastapi():
    print("\n[2/3] 启动FastAPI后端...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR)

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "recognizer.interfaces.api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(f"  FastAPI启动中 (PID: {process.pid})...")
        return process
    except Exception as e:
        print(f"  启动失败: {e}")
        return None


def start_streamlit():
    print("\n[3/3] 启动Streamlit前端...")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR)

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "src/recognizer/interfaces/web/app.py",
                "--server.port",
                "8501",
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(f"  Streamlit启动中 (PID: {process.pid})...")
        return process
    except Exception as e:
        print(f"  启动失败: {e}")
        return None


def main():
    print_banner()

    if not check_dependencies():
        sys.exit(1)

    fastapi_proc = start_fastapi()
    if not fastapi_proc:
        sys.exit(1)

    time.sleep(3)

    streamlit_proc = start_streamlit()
    if not streamlit_proc:
        fastapi_proc.terminate()
        sys.exit(1)

    time.sleep(2)

    print()
    print("=" * 60)
    print("  服务已启动!")
    print("=" * 60)
    print()
    print("  前端界面: http://localhost:8501")
    print("  API文档:  http://localhost:8000/docs")
    print("  健康检查: http://localhost:8000/health")
    print()
    print("  按 Ctrl+C 停止服务")
    print("=" * 60)
    print()

    try:
        while True:
            if fastapi_proc.poll() is not None:
                print("FastAPI服务意外退出!")
                break
            if streamlit_proc.poll() is not None:
                print("Streamlit服务意外退出!")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n正在停止服务...")
    finally:
        if fastapi_proc:
            print("停止FastAPI服务...")
            fastapi_proc.terminate()
            fastapi_proc.wait()
        if streamlit_proc:
            print("停止Streamlit服务...")
            streamlit_proc.terminate()
            streamlit_proc.wait()
        print("服务已停止")


if __name__ == "__main__":
    main()
