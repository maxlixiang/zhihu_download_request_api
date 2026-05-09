import argparse
from pathlib import Path

from .config import (
    DEFAULT_ARTICLE_DELAY_RANGE,
    DEFAULT_IMAGE_DELAY_RANGE,
    DEFAULT_LIMIT,
    DEFAULT_LIST_DELAY_RANGE,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    build_config,
)
from .delay import describe_delay_range, random_sleep
from .files import MANIFEST_FILE_NAME, load_manifest, mark_article, save_markdown_file
from .http import build_session
from .images import download_img_and_replace_md_link
from .zhihu import CONTENT_TYPE_LABELS, get_author_items, parse_article_to_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载知乎用户文章并保存为 Markdown。")
    parser.add_argument("--homepage", help="知乎主页 URL，例如 https://www.zhihu.com/people/xxx")
    parser.add_argument("--user-id", help="知乎用户 user_id；未传时可从 --homepage 或 .env 解析")
    parser.add_argument(
        "--type",
        choices=["articles", "answers", "pins", "upvoted_answers", "upvoted_articles"],
        help="下载类型：articles 文章、answers 回答、pins 想法、upvoted_answers 赞同过的回答、upvoted_articles 赞同过的文章",
    )
    parser.add_argument("--author-name", help="作者名称，用于输出目录命名")
    parser.add_argument("--env", type=Path, help="环境配置文件路径，默认读取当前目录 .env")
    parser.add_argument("--config", type=Path, help="JSON 配置文件路径，可包含 user_id、homepage、author_name、output_dir")
    parser.add_argument("--cookie-json", type=Path, help="Cookie JSON 文件路径，默认读取当前目录 cookie.json")
    parser.add_argument("--cookie", help="知乎 Cookie。也可使用 ZHIHU_COOKIE 环境变量")
    parser.add_argument("--cookie-file", type=Path, help="保存知乎 Cookie 的纯文本文件")
    parser.add_argument("--user-agent", help="自定义 User-Agent")
    parser.add_argument("--output-dir", type=Path, help="输出目录")
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help=f"固定文章列表/文章处理间隔秒数；不传则列表分页 {describe_delay_range(DEFAULT_LIST_DELAY_RANGE)}、单篇文章 {describe_delay_range(DEFAULT_ARTICLE_DELAY_RANGE)}",
    )
    parser.add_argument(
        "--image-delay",
        type=float,
        default=None,
        help=f"固定图片请求间隔秒数；不传则 {describe_delay_range(DEFAULT_IMAGE_DELAY_RANGE)}",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="请求超时时间")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="失败重试次数")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="知乎分页大小")
    parser.add_argument("--count", type=int, help="只抓取最新的 N 条内容，例如 --count 5")
    parser.add_argument("--date", help="兼容参数：等价于 --start-date，格式 YYYYMMDD，例如 --date 20260101")
    parser.add_argument("--start-date", help="只抓取该日期及之后的内容，格式 YYYYMMDD，例如 --start-date 20260101")
    parser.add_argument("--end-date", help="只抓取该日期及之前的内容，格式 YYYYMMDD，例如 --end-date 20260201")
    parser.add_argument("--force", action="store_true", help="即使 Markdown 已存在，也重新解析并覆盖")
    parser.add_argument("--no-images", action="store_true", help="只保存 Markdown，不下载图片")
    return parser.parse_args()


def confirm_full_download(config) -> bool:
    if config.count is not None or config.start_timestamp is not None or config.end_timestamp is not None:
        return True

    content_label = CONTENT_TYPE_LABELS.get(config.content_type, config.content_type)
    print(f"提示: 当前未指定 --count 或 --date，程序将尝试抓取该用户的全部{content_label}。")
    print(
        f"可以使用 --count 5 抓取最新 5 条{content_label}，"
        f"或使用 --start-date 20260101 --end-date 20260201 抓取日期区间内的{content_label}。"
    )
    answer = input(f"是否继续抓取全部{content_label}？输入 y 继续: ").strip().lower()
    return answer == "y"


def main() -> None:
    args = parse_args()
    try:
        config = build_config(args)
    except Exception as exc:
        print(f"配置错误: {exc}")
        return
    config.output_dir.mkdir(parents=True, exist_ok=True)

    if not confirm_full_download(config):
        print("已取消。")
        return

    if not config.cookie:
        print("提示: 当前未提供 Cookie。公开文章可能可下载，遇到权限/登录问题时请设置 cookie.json、ZHIHU_COOKIE 或 --cookie-file。")

    session = build_session(config.cookie, config.user_agent)
    manifest = load_manifest(config.output_dir)

    print("=" * 50)
    content_label = CONTENT_TYPE_LABELS.get(config.content_type, config.content_type)
    print(f"开始爬取【{config.author_name}】的知乎{content_label}")
    print(f"user_id: {config.user_id}")
    print(f"下载类型: {config.content_type} ({content_label})")
    print(f"输出目录: {config.output_dir}")
    print(f"文章列表分页间隔: {describe_delay_range(config.list_delay_range)}")
    print(f"单篇文章处理间隔: {describe_delay_range(config.article_delay_range)}")
    print(f"图片下载间隔: {describe_delay_range(config.image_delay_range)}")
    print("=" * 50)

    try:
        all_items = get_author_items(
            session=session,
            user_id=config.user_id,
            content_type=config.content_type,
            timeout=config.timeout,
            retries=config.retries,
            limit=config.limit,
            delay_range=config.list_delay_range,
            count=config.count,
            start_timestamp=config.start_timestamp,
            end_timestamp=config.end_timestamp,
        )
    except Exception as exc:
        print(f"获取文章列表失败: {exc}")
        return

    if not all_items:
        print(f"未获取到任何{content_label}，请检查主页/user_id、Cookie 或网络访问状态。")
        return

    total = len(all_items)
    scope = f"全部{content_label}"
    if config.count is not None:
        scope = f"最新 {config.count} 条{content_label}"
    if config.start_date:
        scope = f"{config.start_date} 至今的{content_label}"
    if config.end_date:
        scope = f"截至 {config.end_date} 的{content_label}"
    if config.start_date and config.end_date:
        scope = f"{config.start_date} 至 {config.end_date} 的{content_label}"
    print(f"\n本次范围: {scope}。共获取到 {total} 条{content_label}，开始解析、下载图片并保存...\n")

    for index, item in enumerate(all_items, start=1):
        md_file_path = config.output_dir / f"{item.title}.md"
        if md_file_path.exists() and not config.force:
            print(f"[{index}/{total}] 已存在，跳过: {md_file_path.name}")
            mark_article(config.output_dir, manifest, item.item_id, item.title, item.url, "skipped", "Markdown 已存在")
            continue

        print(f"[{index}/{total}] 正在处理: {item.title}")
        try:
            if item.markdown:
                raw_md = item.markdown
            else:
                raw_md = parse_article_to_markdown(session, item.url, config.timeout, config.retries, item.item_id)
            if item.content_type == "upvoted_articles" and "## 文章正文" not in raw_md:
                article_body = parse_article_to_markdown(session, item.url, config.timeout, config.retries, item.item_id)
                raw_md += "\n\n## 文章正文\n\n" + article_body
            final_md = raw_md
            if not config.no_images:
                final_md = download_img_and_replace_md_link(
                    session=session,
                    md_content=raw_md,
                    article_title=item.title,
                    save_dir=config.output_dir,
                    timeout=config.timeout,
                    retries=config.retries,
                    image_delay_range=config.image_delay_range,
                )
            saved_path = save_markdown_file(config.output_dir, item.title, final_md)
            mark_article(config.output_dir, manifest, item.item_id, item.title, item.url, "saved", str(saved_path))
            print(f"保存成功: {saved_path.name}")
        except Exception as exc:
            mark_article(config.output_dir, manifest, item.item_id, item.title, item.url, "failed", str(exc))
            print(f"处理失败: {item.title} | 原因: {str(exc)[:120]}")
        random_sleep(config.article_delay_range)

    print("\n" + "=" * 50)
    print("全部处理完成。下载清单:", config.output_dir / MANIFEST_FILE_NAME)
    print("=" * 50)
