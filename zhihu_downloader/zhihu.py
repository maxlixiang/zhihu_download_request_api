import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from .delay import random_sleep
from .files import clean_file_name
from .http import get_with_retries


ARTICLE_CONTAINER_CLASS = "RichContent-inner"
ARTICLE_CONTENT_SELECTORS = [
    f"div.{ARTICLE_CONTAINER_CLASS}",
    "div.Post-RichTextContainer",
    "div.RichText.ztext",
    "article",
]
CONTENT_TYPE_LABELS = {
    "articles": "文章",
    "answers": "回答",
    "pins": "想法",
}


@dataclass
class ZhihuItem:
    item_id: str
    title: str
    url: str
    created: int
    content_type: str
    markdown: str = ""


def format_timestamp(timestamp: int) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def item_metadata_markdown(item: dict, title: str, url: str, created: int, item_type: str) -> str:
    lines = [
        f"- 类型: {CONTENT_TYPE_LABELS.get(item_type, item_type)}",
        f"- 链接: {url}",
    ]
    created_text = format_timestamp(created)
    if created_text:
        lines.append(f"- 创建时间: {created_text}")
    if item_type == "answers":
        question = item.get("question") if isinstance(item.get("question"), dict) else {}
        voteup_count = item.get("voteup_count")
        comment_count = item.get("comment_count")
        question_title = str(question.get("title") or "").strip()
        question_url = str(question.get("url") or "").strip()
        if question_title:
            lines.append(f"- 问题: {question_title}")
        if question_url:
            lines.append(f"- 问题链接: {question_url}")
        if voteup_count is not None:
            lines.append(f"- 赞同数: {voteup_count}")
        if comment_count is not None:
            lines.append(f"- 评论数: {comment_count}")
    if item_type == "pins":
        reaction_count = item.get("reaction_count")
        comment_count = item.get("comment_count")
        if reaction_count is not None:
            lines.append(f"- 互动数: {reaction_count}")
        if comment_count is not None:
            lines.append(f"- 评论数: {comment_count}")
    return f"# {title}\n\n" + "\n".join(lines) + "\n"


def extract_text_from_pin_content(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part.strip() for part in parts if part and part.strip())
    if isinstance(value, dict):
        text = value.get("text") or value.get("content")
        if isinstance(text, str):
            return text.strip()
    return ""


def extract_pin_images(item: dict) -> List[str]:
    image_urls: List[str] = []
    for key in ("images", "image_list", "pics"):
        images = item.get(key)
        if not isinstance(images, list):
            continue
        for image in images:
            if isinstance(image, str):
                image_urls.append(image)
            elif isinstance(image, dict):
                url = image.get("url") or image.get("src") or image.get("original_url")
                if isinstance(url, str):
                    image_urls.append(url)
    return image_urls


def get_author_all_articles(
    session: requests.Session,
    user_id: str,
    timeout: int,
    retries: int,
    limit: int,
    delay_range: Tuple[float, float],
    count: Optional[int] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> List[ZhihuItem]:
    article_list: List[ZhihuItem] = []
    offset = 0
    base_api = f"https://www.zhihu.com/api/v4/members/{user_id}/articles"
    print("正在获取博主的所有文章列表...")

    while True:
        params = {
            "include": "data[*].id,title,url,created,updated",
            "offset": offset,
            "limit": limit,
            "sort_by": "created",
        }
        response = get_with_retries(session, base_api, timeout=timeout, retries=retries, params=params)
        data = response.json()
        items = data.get("data") or []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            article_id = str(item.get("id") or "")
            title = clean_file_name(str(item.get("title") or article_id))
            url = str(item.get("url") or "")
            created = int(item.get("created") or 0)
            if start_timestamp is not None and created and created < start_timestamp:
                return article_list
            if end_timestamp is not None and created and created > end_timestamp:
                continue
            if article_id and url:
                article_list.append(ZhihuItem(article_id, title, url, created, "articles"))
            if count is not None and len(article_list) >= count:
                return article_list

        print(f"已加载 {len(article_list)} 篇文章，继续加载下一页...")
        offset += limit
        random_sleep(delay_range)

    return article_list


def get_author_answers(
    session: requests.Session,
    user_id: str,
    timeout: int,
    retries: int,
    limit: int,
    delay_range: Tuple[float, float],
    count: Optional[int] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> List[ZhihuItem]:
    answer_list: List[ZhihuItem] = []
    offset = 0
    base_api = f"https://www.zhihu.com/api/v4/members/{user_id}/answers"
    print("正在获取用户的回答列表...")

    while True:
        params = {
            "include": (
                "data[*].id,url,content,excerpt,voteup_count,comment_count,"
                "created_time,updated_time,question"
            ),
            "offset": offset,
            "limit": limit,
            "sort_by": "created",
        }
        response = get_with_retries(session, base_api, timeout=timeout, retries=retries, params=params)
        data = response.json()
        items = data.get("data") or []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            answer_id = str(item.get("id") or "")
            question = item.get("question") if isinstance(item.get("question"), dict) else {}
            question_title = clean_file_name(str(question.get("title") or answer_id))
            title = clean_file_name(f"回答_{question_title}")
            question_id = str(question.get("id") or "")
            url = str(item.get("url") or "")
            if not url and question_id and answer_id:
                url = f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}"
            created = int(item.get("created_time") or item.get("created") or 0)
            if start_timestamp is not None and created and created < start_timestamp:
                return answer_list
            if end_timestamp is not None and created and created > end_timestamp:
                continue
            content = item.get("content")
            body = html_to_markdown(content) if isinstance(content, str) and content.strip() else str(item.get("excerpt") or "")
            markdown = item_metadata_markdown(item, title, url, created, "answers")
            if body:
                markdown += "\n## 回答正文\n\n" + body
            if answer_id and url:
                answer_list.append(ZhihuItem(answer_id, title, url, created, "answers", markdown))
            if count is not None and len(answer_list) >= count:
                return answer_list

        print(f"已加载 {len(answer_list)} 条回答，继续加载下一页...")
        offset += limit
        random_sleep(delay_range)

    return answer_list


def get_author_pins(
    session: requests.Session,
    user_id: str,
    timeout: int,
    retries: int,
    limit: int,
    delay_range: Tuple[float, float],
    count: Optional[int] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> List[ZhihuItem]:
    pin_list: List[ZhihuItem] = []
    offset = 0
    base_api = f"https://www.zhihu.com/api/v4/v2/pins/{user_id}/moments"
    print("正在获取用户的想法列表...")

    while True:
        params = {
            "includes": "data[*].upvoted_followees,admin_closed_comment,reaction",
            "offset": offset,
            "limit": limit,
        }
        response = get_with_retries(session, base_api, timeout=timeout, retries=retries, params=params)
        data = response.json()
        items = data.get("data") or []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            pin_id = str(item.get("id") or item.get("pin_id") or "")
            created = int(item.get("created") or item.get("created_time") or item.get("updated") or 0)
            if start_timestamp is not None and created and created < start_timestamp:
                return pin_list
            if end_timestamp is not None and created and created > end_timestamp:
                continue
            url = str(item.get("url") or item.get("detail_url") or "")
            if not url and pin_id:
                url = f"https://www.zhihu.com/pin/{pin_id}"

            text = extract_text_from_pin_content(item.get("content") or item.get("excerpt") or item.get("text"))
            title_source = text.splitlines()[0] if text else pin_id
            title = clean_file_name(f"想法_{title_source}", max_len=80)
            markdown = item_metadata_markdown(item, title, url, created, "pins")
            if text:
                markdown += "\n## 想法正文\n\n" + html_to_markdown(text)
            for image_url in extract_pin_images(item):
                markdown += f"\n\n![]({image_url})"

            if pin_id and url:
                pin_list.append(ZhihuItem(pin_id, title, url, created, "pins", markdown))
            if count is not None and len(pin_list) >= count:
                return pin_list

        print(f"已加载 {len(pin_list)} 条想法，继续加载下一页...")
        offset += limit
        random_sleep(delay_range)

    return pin_list


def get_author_items(
    session: requests.Session,
    user_id: str,
    content_type: str,
    timeout: int,
    retries: int,
    limit: int,
    delay_range: Tuple[float, float],
    count: Optional[int] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> List[ZhihuItem]:
    if content_type == "articles":
        return get_author_all_articles(
            session, user_id, timeout, retries, limit, delay_range, count, start_timestamp, end_timestamp
        )
    if content_type == "answers":
        return get_author_answers(
            session, user_id, timeout, retries, limit, delay_range, count, start_timestamp, end_timestamp
        )
    if content_type == "pins":
        return get_author_pins(
            session, user_id, timeout, retries, limit, delay_range, count, start_timestamp, end_timestamp
        )
    raise ValueError(f"不支持的下载类型: {content_type}")


def html_to_markdown(html: str) -> str:
    markdown_content = md(html, heading_style="ATX")
    lines = [line.rstrip() for line in markdown_content.splitlines()]
    return "\n".join(line for line in lines if line.strip())


def parse_article_from_api(
    session: requests.Session,
    article_id: str,
    timeout: int,
    retries: int,
) -> str:
    api_url = f"https://www.zhihu.com/api/v4/articles/{article_id}"
    params = {"include": "content,title,excerpt,author"}
    response = get_with_retries(session, api_url, timeout=timeout, retries=retries, params=params)
    data = response.json()
    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("文章 API 未返回正文 content 字段")
    return html_to_markdown(content)


def find_initial_state_content(value) -> str:
    if isinstance(value, dict):
        for key in ("content", "renderContent"):
            content = value.get(key)
            if isinstance(content, str) and "<" in content and len(content) > 100:
                return content
        for child in value.values():
            content = find_initial_state_content(child)
            if content:
                return content
    elif isinstance(value, list):
        for child in value:
            content = find_initial_state_content(child)
            if content:
                return content
    return ""


def parse_article_from_html(
    session: requests.Session,
    article_url: str,
    timeout: int,
    retries: int,
) -> str:
    response = get_with_retries(session, article_url, timeout=timeout, retries=retries)
    soup = BeautifulSoup(response.text, "html.parser")

    for selector in ARTICLE_CONTENT_SELECTORS:
        content_box = soup.select_one(selector)
        if content_box:
            return html_to_markdown(str(content_box))

    initial_data = soup.find("script", id="js-initialData")
    if initial_data and initial_data.string:
        try:
            content = find_initial_state_content(json.loads(initial_data.string))
            if content:
                return html_to_markdown(content)
        except json.JSONDecodeError:
            pass

    title = soup.title.get_text(strip=True) if soup.title else ""
    plain_text = soup.get_text(" ", strip=True)[:200]
    if "安全验证" in plain_text or "captcha" in plain_text.lower():
        raise RuntimeError("页面返回安全验证/验证码，请更新 Cookie 或降低抓取频率")
    if "登录" in plain_text and "知乎" in plain_text:
        raise RuntimeError("页面像是登录页，请检查 cookie.json 是否有效")
    raise RuntimeError(f"未能从页面提取正文。页面标题: {title or '无'}；页面片段: {plain_text or '空响应'}")


def parse_article_to_markdown(
    session: requests.Session,
    article_url: str,
    timeout: int,
    retries: int,
    article_id: Optional[str] = None,
) -> str:
    api_error = ""
    if article_id:
        try:
            return parse_article_from_api(session, article_id, timeout, retries)
        except Exception as exc:
            api_error = str(exc)

    try:
        return parse_article_from_html(session, article_url, timeout, retries)
    except Exception as exc:
        if api_error:
            raise RuntimeError(f"API 解析失败: {api_error}；页面解析失败: {exc}") from exc
        raise
