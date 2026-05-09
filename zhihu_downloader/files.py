import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict


MANIFEST_FILE_NAME = "download_manifest.json"


def clean_file_name(value: str, max_len: int = 80) -> str:
    value = re.sub(r'[\\/:*?"<>|\r\n\t]', "", value)
    value = value.replace("，", "").replace("。", "").strip()
    value = re.sub(r"\s+", " ", value)
    return (value[:max_len].strip() or "untitled")


def load_manifest(save_dir: Path) -> Dict[str, object]:
    manifest_path = save_dir / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        return {"articles": {}}
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("articles"), dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"articles": {}}


def save_manifest(save_dir: Path, manifest: Dict[str, object]) -> None:
    manifest_path = save_dir / MANIFEST_FILE_NAME
    tmp_path = manifest_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    tmp_path.replace(manifest_path)


def mark_article(
    save_dir: Path,
    manifest: Dict[str, object],
    article_id: str,
    title: str,
    url: str,
    status: str,
    message: str = "",
) -> None:
    articles = manifest.setdefault("articles", {})
    if not isinstance(articles, dict):
        manifest["articles"] = articles = {}
    articles[article_id] = {
        "title": title,
        "url": url,
        "status": status,
        "message": message,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_manifest(save_dir, manifest)


def save_markdown_file(save_dir: Path, article_title: str, markdown_content: str) -> Path:
    md_file_path = save_dir / f"{article_title}.md"
    tmp_path = md_file_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        if not markdown_content.lstrip().startswith("# "):
            f.write(f"# {article_title}\n\n")
        f.write(markdown_content)
        f.write("\n")
    tmp_path.replace(md_file_path)
    return md_file_path
