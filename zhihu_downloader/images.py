import hashlib
import re
from pathlib import Path
from typing import Dict, Iterable, Tuple
from urllib.parse import unquote, urlparse

import requests

from .delay import random_sleep
from .files import clean_file_name
from .http import get_with_retries


def guess_image_suffix(img_url: str, content_type: str = "") -> str:
    content_type = content_type.split(";")[0].strip().lower()
    content_type_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }
    if content_type in content_type_map:
        return content_type_map[content_type]

    path = unquote(urlparse(img_url).path)
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in {"jpg", "jpeg", "png", "gif", "webp", "svg"}:
        return suffix
    return "jpg"


def image_file_stem(img_desc: str, img_url: str) -> str:
    readable = clean_file_name(img_desc, max_len=30)
    url_hash = hashlib.sha1(img_url.encode("utf-8")).hexdigest()[:12]
    return f"{readable}_{url_hash}" if readable != "untitled" else url_hash


def download_image(
    session: requests.Session,
    img_url: str,
    img_desc: str,
    img_save_path: Path,
    timeout: int,
    retries: int,
) -> Path:
    stem = image_file_stem(img_desc, img_url)
    existing = list(img_save_path.glob(f"{stem}.*"))
    if existing:
        return existing[0]

    response = get_with_retries(session, img_url, timeout=timeout, retries=retries)
    suffix = guess_image_suffix(img_url, response.headers.get("Content-Type", ""))
    img_file_path = img_save_path / f"{stem}.{suffix}"
    with img_file_path.open("wb") as f:
        f.write(response.content)
    return img_file_path


def iter_markdown_images(markdown_content: str) -> Iterable[Tuple[str, str]]:
    img_pattern = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")
    return img_pattern.findall(markdown_content)


def download_img_and_replace_md_link(
    session: requests.Session,
    md_content: str,
    article_title: str,
    save_dir: Path,
    timeout: int,
    retries: int,
    image_delay_range: Tuple[float, float],
) -> str:
    images = list(iter_markdown_images(md_content))
    if not images:
        return md_content

    img_sub_dir = f"{clean_file_name(article_title)}_文章图片"
    img_save_path = save_dir / img_sub_dir
    img_save_path.mkdir(parents=True, exist_ok=True)

    replaced_urls: Dict[str, str] = {}
    for img_desc, img_url in images:
        if img_url in replaced_urls:
            continue
        try:
            img_file_path = download_image(session, img_url, img_desc, img_save_path, timeout, retries)
            replaced_urls[img_url] = f"{img_sub_dir}/{img_file_path.name}"
            random_sleep(image_delay_range)
        except Exception as exc:
            print(f"图片下载失败: {img_url} | 原因: {str(exc)[:80]}")

    for img_url, local_path in replaced_urls.items():
        md_content = md_content.replace(img_url, local_path)
    return md_content
