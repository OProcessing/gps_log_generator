"""실행 환경(파이썬/배포 EXE)에 따른 경로 유틸."""

from pathlib import Path
import sys


def get_runtime_root() -> Path:
    """프로젝트 루트 또는 EXE 폴더를 반환."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
