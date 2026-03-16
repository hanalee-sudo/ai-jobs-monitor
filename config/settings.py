"""설정 로더: .env와 sources.yaml을 읽어 전역 설정 제공."""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


def _get_env(key: str, required: bool = True) -> str:
    """환경변수를 읽고, 필수값이 없으면 에러 메시지 출력."""
    value = os.getenv(key, "")
    if required and not value:
        print(f"[오류] .env 파일에 {key} 값이 없습니다.")
        print(f"       .env.example을 참고하여 .env 파일을 작성해주세요.")
        sys.exit(1)
    return value


# --- API 키 ---
ANTHROPIC_API_KEY = _get_env("ANTHROPIC_API_KEY", required=False)
NAVER_CLIENT_ID = _get_env("NAVER_CLIENT_ID", required=False)
NAVER_CLIENT_SECRET = _get_env("NAVER_CLIENT_SECRET", required=False)

# --- Claude 모델 ---
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 1024

# --- 경로 ---
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
DB_PATH = DATA_DIR / "articles.db"

# 디렉토리 자동 생성
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


def load_sources() -> dict:
    """sources.yaml 파일을 읽어 딕셔너리로 반환."""
    sources_path = ROOT_DIR / "config" / "sources.yaml"
    with open(sources_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
