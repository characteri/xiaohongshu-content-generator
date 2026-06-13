import os
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def load_streamlit_secrets() -> None:
    """Streamlit Cloud Secrets → 环境变量（本地无 secrets 时静默跳过）。"""
    try:
        import streamlit as st

        for key in ("DEEPSEEK_API_KEY", "XHS_COOKIES", "COOKIES"):
            if key in st.secrets and not os.environ.get(key):
                val = st.secrets[key]
                if val:
                    os.environ[key] = str(val)
    except Exception:
        pass


def ensure_npm_deps() -> None:
    """部署环境无 node_modules 时尝试 npm install（Streamlit Cloud 用）。"""
    if (_ROOT / "node_modules" / "crypto-js").exists():
        return
    if not (_ROOT / "package.json").exists():
        return
    try:
        subprocess.run(
            ["npm", "install", "--omit=dev"],
            cwd=_ROOT,
            check=False,
            timeout=180,
            capture_output=True,
        )
    except Exception:
        pass


def load_env_file() -> None:
    """从项目根目录的 .env 加载环境变量（不覆盖已存在的变量）。"""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
