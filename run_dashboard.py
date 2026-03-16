"""Python 3.14 호환 대시보드 런처."""

import asyncio

_original_get_event_loop = asyncio.get_event_loop

def _patched_get_event_loop():
    try:
        return _original_get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

asyncio.get_event_loop = _patched_get_event_loop

import sys
from streamlit.web import cli as stcli

sys.argv = ["streamlit", "run", "dashboard.py"]
stcli.main()
