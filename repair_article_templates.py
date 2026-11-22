#!/usr/bin/env python3
"""Normalize legacy TechPulse article navigation, authorship and source references."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path("public")
ARTICLES_DIR = ROOT / "articles"
HISTORY_FILE = ROOT / "articles.json"

NAV_LINKS = [
    ("/", "Начало"),
    ("/articles.html", "Статии"),
    ("/articles.html?category=ai", "AI"),
    ("/articles.html?category=technologies", "Технологии"),
    ("/articles.html?category=hardware", "Хардуер"),
    ("/articles.html?category=cyber", "Киберсигурност"),
    ("/articles.html?category=quantum", "Квантови технологии"),
    ("/articles.html?category=future", "Бъдещи технологии"),
    ("/tools.html", "Инструменти"),
    ("/glossary.html", "Речник"),
    ("/about.html", "За нас"),
    ("/contacts.html", "Контакти"),
]

AUTHOR_BOX = (
    '<section class="author-box" aria-label="Информация за автора">'
    '<h2>Редакция и авторство</h2>'
    '<p><strong>Редакционен екип на TechPulse</strong></p>'
    '<p>Материалът е подготвен от редакцията на TechPulse. '
    'Фактите се разграничават от анализа, а посочените източници дават '
    'възможност за самостоятелна проверка.</p></section>'
)


def allowed_sources(record: dict) -> set[str]:
    allowed = set()
    for source in record.get("sources", []) or []:
        if isinstance(source, dict) and source.get("url"):
            allowed.add(str(source["url"]).rstrip("/"))
    for key in ("source_url", "source_urls"):
        value = record.get(key)
        if isinstance(value, str) and value:
            allowed.add(value.rstrip("/"))
        elif isinstance(value, list):
            allowed.update(str(url).rstrip("/") for url in value if url)
    return allowed


def normalize_nav(content: str) -> str:
    links = "".join(
        f'<a href="{html.escape(url, quote=True)}" class="nav-link">{label}</a>'
        for url, label in NAV_LINKS
    )

    pattern = re.compile(
        r'<nav\b[^>]*class=["\']([^"\']*\b(?:nav|nav-categories)\b[^"\']*)["\'][^>]*>'
        r'[\s\S]*?</nav>',
        re.I,
    )

    def replace(match: re.Match) -> str:
        classes = match.group(1)
        nav_class = "nav-categories" if "nav-categories" in classes else "nav"
        return (
            f'<nav class="{nav_class}" aria-label="Основна навигация">'
            f'{links}</nav>'
        )

    updated, count = pattern.subn(replace, content, count=1)
    if count:
        return updated

    nav = f'<nav class="nav" aria-label="Основна навигация">{links}</nav>'
    if re.search(r"<main\b", content, re.I):
        return re.sub(r"(<main\b)", nav + r"\1", content, count=1, flags=re.I)
    if re.search(r"<body\b[^>]*>", content, re.I):
        return re.sub(r"(<body\b[^>]*>)", r"\1" + nav, content, count=1, flags=re.I)
    return content


def normalize_author_box(content: str) -> str:
    pattern = re.compile(
        r'<section\b[^>]*class=["\'][^"\']*\bauthor-box\b[^"\']*["\'][^>]*>'
        r'[\s\S]*?</section>',
        re.I,
    )
    content, count = pattern.subn("", content)
    if count == 0:
        closing = re.search(r"</main\s*>", content, re.I)
        if not closing:
            closing = re.search(r"</article\s*>", content, re.I)
        if not closing:
            closing = re.search(r"</body\s*>", content, re.I)
        if closing:
            return content[:closing.start()] + AUTHOR_BOX + content[closing.start():]
        return content
    closing = re.search(r"</main\s*>", content, re.I)
    if not closing:
        closing = re.search(r"</article\s*>", content, re.I)
    if not closing:
        closing = re.search(r"</body\s*>", content, re.I)
    if closing:
        return content[:closing.start()] + AUTHOR_BOX + content[closing.start():]
    return content + AUTHOR_BOX


def remove_unrelated_rss_sources(content: str, allowed: set[str]) -> str:
    anchor_pattern = re.compile(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>[\s\S]*?</a>',
        re.I,
    )
    removed = 0
    for match in list(anchor_pattern.finditer(content))[::-1]:
        url = html.unescape(match.group(1)).rstrip("/")
        if "news.google.com/rss/" not in url or url in allowed:
            continue

        start, end = match.span()
        li_start = content.rfind("<li", 0, start)
        li_end = content.find("</li>", end)
        if li_start >= 0 and li_end >= 0:
            start, end = li_start, li_end + len("</li>")
        content = content[:start] + content[end:]
        removed += 1

    if removed:
        content = re.sub(
            r'<section\b[^>]*class=["\'][^"\']*article-sources[^"\']*["\']>'
            r'\s*(?:<h[1-6]\b[^>]*>[\s\S]*?</h[1-6]>)?\s*(?:<ul>\s*</ul>)?\s*</section>',
            "",
            content,
            flags=re.I,
        )
    return content


def related_urls(content: str) -> set[str]:
    match = re.search(
        r'<section\b[^>]*class=["\'][^"\']*\brelated-articles\b[^"\']*["\'][^>]*>'
        r'([\s\S]*?)</section>',
        content,
        re.I,
    )
    if not match:
        return set()
    return {
        html.unescape(url).rstrip("/")
        for url in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\']', match.group(1), re.I)
    }


def remove_sidebar_duplicates(content: str) -> str:
    duplicate_urls = related_urls(content)
    if not duplicate_urls:
        return content

    aside_pattern = re.compile(
        r'<aside\b[^>]*class=["\'][^"\']*\bsidebar\b[^"\']*["\'][^>]*>'
        r'([\s\S]*?)</aside>',
        re.I,
    )
    match = aside_pattern.search(content)
    if not match:
        return content

    sidebar = match.group(0)
    for url in duplicate_urls:
        escaped = re.escape(url)
        item_pattern = re.compile(
            r'<div\b[^>]*class=["\'][^"\']*\bsimilar-item\b[^"\']*["\'][^>]*>'
            r'(?:(?!<div\b)[\s\S])*?href=["\']' + escaped + r'["\']'
            r'(?:(?!<div\b)[\s\S])*?</div>\s*</div>',
            re.I,
        )
        sidebar = item_pattern.sub("", sidebar)

    return content[:match.start()] + sidebar + content[match.end():]


def main() -> None:
    if not ARTICLES_DIR.is_dir():
        print("Няма public/articles/. Няма какво да се обновява.")
        return

    history = json.loads(HISTORY_FILE.read_text(encoding="utf-8")) if HISTORY_FILE.exists() else []
    by_url = {item.get("url"): item for item in history if isinstance(item, dict)}
    changed = 0

    for path in sorted(ARTICLES_DIR.glob("*.html")):
        original = path.read_text(encoding="utf-8")
        record = by_url.get("/articles/" + path.name, {})
        updated = normalize_nav(original)
        updated = normalize_author_box(updated)
        updated = remove_unrelated_rss_sources(updated, allowed_sources(record))
        updated = remove_sidebar_duplicates(updated)

        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
            print(f"Обновена статия: {path.name}")

    print(f"Готово: {changed} от {len(list(ARTICLES_DIR.glob('*.html')))} HTML файла са обновени.")


if __name__ == "__main__":
    main()
