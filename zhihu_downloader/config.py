import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse


DEFAULT_USER_ID = "mr-dang-77"
DEFAULT_AUTHOR_NAME = "MR Dang"
DEFAULT_LIST_DELAY_RANGE = (2.0, 4.0)
DEFAULT_ARTICLE_DELAY_RANGE = (1.5, 3.0)
DEFAULT_IMAGE_DELAY_RANGE = (1.0, 2.0)
DEFAULT_LIMIT = 10
DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 3

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class AppConfig:
    user_id: str
    author_name: str
    content_type: str
    output_dir: Path
    cookie: str
    user_agent: str
    list_delay_range: Tuple[float, float]
    article_delay_range: Tuple[float, float]
    image_delay_range: Tuple[float, float]
    timeout: int
    retries: int
    limit: int
    count: Optional[int]
    start_timestamp: Optional[int]
    end_timestamp: Optional[int]
    start_date: str
    end_date: str
    force: bool
    no_images: bool


def load_json_config(config_path: Optional[Path]) -> Dict[str, object]:
    if not config_path:
        return {}
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("配置文件必须是 JSON 对象")
    return data


def load_env_file(env_path: Optional[Path]) -> Dict[str, str]:
    if not env_path or not env_path.exists():
        return {}

    env: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env[key] = value
    return env


def load_cookie_json(cookie_json_path: Optional[Path]) -> Dict[str, object]:
    if not cookie_json_path:
        return {}
    if not cookie_json_path.exists():
        raise FileNotFoundError(f"Cookie JSON 文件不存在: {cookie_json_path}")
    with cookie_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Cookie JSON 文件必须是 JSON 对象")
    return data


def cookie_from_browser_export(data: object) -> str:
    if not isinstance(data, list):
        return ""
    pairs = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if name and value:
            pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def resolve_cookie(cookie_json: Dict[str, object], cli_cookie: Optional[str], cookie_file: Optional[Path]) -> str:
    if cli_cookie:
        return cli_cookie.strip()
    if cookie_file:
        if not cookie_file.exists():
            raise FileNotFoundError(f"Cookie 文件不存在: {cookie_file}")
        return cookie_file.read_text(encoding="utf-8").strip()
    if isinstance(cookie_json.get("cookie"), str):
        return str(cookie_json["cookie"]).strip()
    cookie_from_list = cookie_from_browser_export(cookie_json.get("cookies"))
    if cookie_from_list:
        return cookie_from_list
    return os.environ.get("ZHIHU_COOKIE", "").strip()


def parse_user_id_from_homepage(homepage: str) -> str:
    homepage = homepage.strip()
    if not homepage:
        return ""

    parsed = urlparse(homepage)
    path = parsed.path if parsed.scheme else homepage
    match = re.search(r"/people/([^/?#]+)", path)
    if match:
        return match.group(1).strip()

    cleaned = homepage.strip("/ ")
    if "/" not in cleaned and "zhihu.com" not in cleaned:
        return cleaned
    return ""


def first_value(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def parse_date_to_timestamp(date_text: str, end_of_day: bool = False) -> int:
    try:
        date_value = datetime.strptime(date_text, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("日期必须使用 YYYYMMDD 格式，例如 20260101") from exc
    if end_of_day:
        date_value = date_value + timedelta(days=1) - timedelta(seconds=1)
    return int(date_value.timestamp())


def normalize_delay_range(min_value: float, max_value: float, name: str) -> Tuple[float, float]:
    if min_value < 0 or max_value < 0:
        raise ValueError(f"{name} 不能是负数")
    if min_value > max_value:
        raise ValueError(f"{name} 的最小值不能大于最大值")
    return (min_value, max_value)


def read_delay_range(
    env: Dict[str, str],
    json_config: Dict[str, object],
    env_min_key: str,
    env_max_key: str,
    json_min_key: str,
    json_max_key: str,
    default_range: Tuple[float, float],
    name: str,
) -> Tuple[float, float]:
    min_text = first_value(env.get(env_min_key), json_config.get(json_min_key))
    max_text = first_value(env.get(env_max_key), json_config.get(json_max_key))
    min_value = float(min_text) if min_text else default_range[0]
    max_value = float(max_text) if max_text else default_range[1]
    return normalize_delay_range(min_value, max_value, name)


def build_config(args) -> AppConfig:
    env_path = args.env if args.env else Path(".env")
    env = load_env_file(env_path)
    json_config = load_json_config(args.config)
    cookie_json_path = args.cookie_json or Path(str(env.get("ZHIHU_COOKIE_JSON") or "cookie.json"))
    cookie_json = load_cookie_json(cookie_json_path) if cookie_json_path.exists() else {}

    homepage = first_value(args.homepage, env.get("ZHIHU_HOMEPAGE"), json_config.get("homepage"))
    user_id = first_value(args.user_id, env.get("ZHIHU_USER_ID"), json_config.get("user_id"))
    if not user_id and homepage:
        user_id = parse_user_id_from_homepage(homepage)
    user_id = user_id or DEFAULT_USER_ID

    author_name = first_value(args.author_name, env.get("ZHIHU_AUTHOR_NAME"), json_config.get("author_name")) or DEFAULT_AUTHOR_NAME
    content_type = first_value(args.type, env.get("ZHIHU_TYPE"), json_config.get("type")) or "articles"
    if content_type not in {"articles", "answers", "pins", "upvoted_answers", "upvoted_articles"}:
        raise ValueError("--type 只能是 articles、answers、pins、upvoted_answers 或 upvoted_articles")
    output_dir_text = first_value(args.output_dir, env.get("ZHIHU_OUTPUT_DIR"), json_config.get("output_dir"))
    output_dir = Path(output_dir_text or f"知乎_{author_name}_文章合集(含本地图片)")

    cookie = resolve_cookie(cookie_json, args.cookie, args.cookie_file)
    user_agent = first_value(args.user_agent, env.get("ZHIHU_USER_AGENT"), json_config.get("user_agent")) or DEFAULT_USER_AGENT
    start_date = first_value(args.start_date, args.date, env.get("ZHIHU_START_DATE"), json_config.get("start_date"), json_config.get("date"))
    end_date = first_value(args.end_date, env.get("ZHIHU_END_DATE"), json_config.get("end_date"))
    start_timestamp = parse_date_to_timestamp(start_date) if start_date else None
    end_timestamp = parse_date_to_timestamp(end_date, end_of_day=True) if end_date else None
    if start_timestamp is not None and end_timestamp is not None and start_timestamp > end_timestamp:
        raise ValueError("--start-date 不能晚于 --end-date")

    count_text = first_value(args.count, env.get("ZHIHU_COUNT"), json_config.get("count"))
    count = int(count_text) if count_text else None
    if count is not None and count <= 0:
        raise ValueError("--count 必须是大于 0 的整数")

    list_delay_range = read_delay_range(
        env,
        json_config,
        "ZHIHU_LIST_DELAY_MIN",
        "ZHIHU_LIST_DELAY_MAX",
        "list_delay_min",
        "list_delay_max",
        DEFAULT_LIST_DELAY_RANGE,
        "文章列表分页间隔",
    )
    article_delay_range = read_delay_range(
        env,
        json_config,
        "ZHIHU_ARTICLE_DELAY_MIN",
        "ZHIHU_ARTICLE_DELAY_MAX",
        "article_delay_min",
        "article_delay_max",
        DEFAULT_ARTICLE_DELAY_RANGE,
        "单篇文章处理间隔",
    )
    image_delay_range = read_delay_range(
        env,
        json_config,
        "ZHIHU_IMAGE_DELAY_MIN",
        "ZHIHU_IMAGE_DELAY_MAX",
        "image_delay_min",
        "image_delay_max",
        DEFAULT_IMAGE_DELAY_RANGE,
        "图片下载间隔",
    )
    if args.delay is not None:
        fixed_delay = float(args.delay)
        list_delay_range = normalize_delay_range(fixed_delay, fixed_delay, "--delay")
        article_delay_range = normalize_delay_range(fixed_delay, fixed_delay, "--delay")
    if args.image_delay is not None:
        fixed_image_delay = float(args.image_delay)
        image_delay_range = normalize_delay_range(fixed_image_delay, fixed_image_delay, "--image-delay")

    return AppConfig(
        user_id=user_id,
        author_name=author_name,
        content_type=content_type,
        output_dir=output_dir.expanduser().resolve(),
        cookie=cookie,
        user_agent=user_agent,
        list_delay_range=list_delay_range,
        article_delay_range=article_delay_range,
        image_delay_range=image_delay_range,
        timeout=int(args.timeout),
        retries=int(args.retries),
        limit=int(args.limit),
        count=count,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        start_date=start_date,
        end_date=end_date,
        force=bool(args.force),
        no_images=bool(args.no_images),
    )
