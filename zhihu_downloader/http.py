import time
from typing import Dict, Optional

import requests


ZHIHU_REFERER = "https://www.zhihu.com/"


def build_session(cookie: str, user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Referer": ZHIHU_REFERER,
        }
    )
    if cookie:
        session.headers["Cookie"] = cookie
    return session


def get_with_retries(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    params: Optional[Dict[str, object]] = None,
) -> requests.Response:
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 * attempt, 6))
    raise RuntimeError(f"请求失败: {last_error}")

