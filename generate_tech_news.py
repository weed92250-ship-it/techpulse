import os
import time
import random
import urllib.parse
import re
import json
import urllib.request
import xml.etree.ElementTree as ET
from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise ValueError("ГРЕШКА: Липсва GEMINI_API_KEY в Secrets!")

client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=90000))

PUBLIC_DIR = "public"
ARTICLES_DIR = os.path.join(PUBLIC_DIR, "articles")
HISTORY_FILE = os.path.join(PUBLIC_DIR, "articles.json")

os.makedirs(ARTICLES_DIR, exist_ok=True)

DEFAULT_ARTICLES = []

CATEGORY_RULES = [
    ("Квантови технологии", "quantum", ("квант", "qubit", "кубит")),
    ("Киберсигурност", "cyber", ("киберсигур", "zero trust", "passkey", "парол")),
    ("Хардуер", "hardware", ("чип", "gpu", "cpu", "npu", "процесор", "хардуер", "ускорител")),
    ("Бъдещи технологии", "future", ("робот", "невроморф", "автоном", "мултимодал", "edge")),
    ("AI", "ai", ("изкуствен интелект", " ai", "ai ", "модел", "агент", "llm")),
]

def infer_category(title, article_html, history=None):
    text = f" {title} {re.sub(r'<[^>]+>', ' ', article_html)} ".lower()
    history = history or []

    scored = []
    for label, slug, keywords in CATEGORY_RULES:
        score = sum(text.count(keyword) for keyword in keywords)
        if score:
            scored.append((score, label, slug))

    if not scored:
        return "Технологии", "technologies"

    scored.sort(key=lambda item: item[0], reverse=True)
    preferred = scored[0]
    today = __import__("datetime").date.today().isoformat()
    latest_today = next(
        (item for item in history if item.get("time") == today and item.get("category_slug")),
        None
    )

    # Avoid assigning consecutive same-day stories to one category
    # when the current article contains evidence for another category.
    if latest_today and preferred[2] == latest_today.get("category_slug"):
        alternatives = [item for item in scored if item[2] != latest_today.get("category_slug")]
        if alternatives:
            preferred = alternatives[0]

    return preferred[1], preferred[2]

CSS_STYLES = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-color: #070c18;
        color: #94a3b8;
        margin: 0;
        padding: 20px;
        line-height: 1.7;
    }
    .container { max-width: 1180px; margin: 0 auto; }
    .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 15px; margin-bottom: 15px; }
    .logo { font-size: 24px; font-weight: 800; color: #38bdf8; text-decoration: none; display: flex; align-items: center; gap: 8px; }
    .search-box input { padding: 8px 16px; border-radius: 6px; border: 1px solid #1e293b; background-color: #0f172a; color: #f8fafc; width: 220px; font-size: 13px; outline: none; }
    .nav-categories { display: flex; flex-wrap: wrap; gap: 18px; padding-bottom: 15px; border-bottom: 1px solid #1e293b; margin-bottom: 25px; }
    .nav-link { color: #cbd5e1; text-decoration: none; font-size: 13px; font-weight: 500; }
    .nav-link:hover, .nav-link.active { color: #38bdf8; }
    .main-layout { display: grid; grid-template-columns: 1fr 340px; gap: 30px; }
    .article-card, .static-card { background: #0f172a; border-radius: 10px; padding: 30px; border: 1px solid #1e293b; }
    .article-image { width: 100%; height: 420px; object-fit: cover; border-radius: 6px; margin-bottom: 20px; }
    .article-card h2, .static-card h1 { color: #f8fafc; margin-top: 10px; font-size: 28px; line-height: 1.3; }
    .article-intro { font-size: 18px; color: #cbd5e1; margin-bottom: 25px; line-height: 1.8; font-weight: 400; }
    .article-card p { margin-bottom: 18px; font-size: 15px; color: #94a3b8; }
    ul, ol { padding-left: 20px; margin-bottom: 20px; color: #94a3b8; font-size: 15px; }
    li { margin-bottom: 10px; }
    .sidebar { background: #0f172a; border-radius: 10px; padding: 20px; border: 1px solid #1e293b; height: fit-content; }
    .sidebar h3 { margin-top: 0; color: #f8fafc; font-size: 16px; border-bottom: 1px solid #1e293b; padding-bottom: 10px; margin-bottom: 18px; }
    .similar-item { display: flex; gap: 12px; margin-bottom: 18px; align-items: flex-start; }
    .similar-item img { width: 75px; height: 60px; border-radius: 4px; object-fit: cover; }
    .similar-item-info h4 { margin: 0 0 4px 0; font-size: 13px; line-height: 1.3; }
    .similar-item-info h4 a { color: #f8fafc; text-decoration: none; }
    .similar-item-info h4 a:hover { color: #38bdf8; }
    .similar-tag { color: #38bdf8; font-size: 11px; font-weight: bold; display: block; margin-bottom: 2px; }
    .similar-item-info span { font-size: 11px; color: #64748b; }
    footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #1e293b; color: #64748b; font-size: 13px; }
    .footer-links a { color: #94a3b8; text-decoration: none; margin: 0 10px; }
    .footer-links a:hover { color: #38bdf8; }
    @media (max-width: 850px) { .main-layout { grid-template-columns: 1fr; } }
"""

def slugify(text):
    bg_to_en = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'zh','з':'z','и':'i','й':'y',
        'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
        'ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sht','ъ':'a','ь':'y','ю':'yu','я':'ya'
    }
    slug = text.lower()
    res = []
    for char in slug:
        if char in bg_to_en:
            res.append(bg_to_en[char])
        elif char.isalnum():
            res.append(char)
        elif char in [' ', '-']:
            res.append('-')
    slug_str = re.sub(r'-+', '-', ''.join(res)).strip('-')
    return slug_str if slug_str else f"news-{int(time.time())}"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []

    if not isinstance(raw, list):
        return []

    cleaned = []
    seen_urls = set()

    for item in raw:
        if not isinstance(item, dict):
            continue

        url = item.get("url")
        title = item.get("title")
        if not isinstance(url, str) or not url.startswith("/articles/"):
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        if url in seen_urls:
            continue

        article_path = os.path.join(PUBLIC_DIR, url.lstrip("/"))
        if not os.path.isfile(article_path):
            continue

        seen_urls.add(url)
        cleaned.append(item)

    return cleaned

IMAGE_POOLS = {
    "quantum": [
        "photo-1535378273068-9bb67d5beacd", "photo-1635070041078-e363dbe005cb",
        "photo-1451187580459-43490279c0fa", "photo-1523961131990-5ea7c61b2107",
        "photo-1535223289827-42f1e9919769", "photo-1535378620166-273708d44e4c",
        "photo-1618005182384-a83a8bd57fbe", "photo-1527443224154-c4a3942d3acf",
        "photo-1581091226825-a6a2a5aee158", "photo-1581092160562-40aa08e78837"
        "https://cdn.pixabay.com/photo/2018/05/08/08/44/artificial-intelligence-3382507_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/11/22/19/20/technology-1845385_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/06/13/09/36/technology-2396808_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/11/29/07/27/computer-1869236_1280.jpg",
    ],
    "cyber": [
        "photo-1526374965328-7f61d4dc18c5", "photo-1550751827-4bd374c3f58b",
        "photo-1563013544-824ae1b704d3", "photo-1510511459019-5dda7724fd87",
        "photo-1558494949-ef010cbdcc31", "photo-1550439062-609e1531270e",
        "photo-1516321318423-f06f85e504b3", "photo-1527443224154-c4a3942d3acf",
        "photo-1581092795360-fd1ca04f0952", "photo-1515879218367-8466d910aaa4"
        "https://cdn.pixabay.com/photo/2016/11/19/14/00/code-1839406_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/11/30/20/58/programming-1873854_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/12/28/09/36/web-1935737_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/01/17/14/40/technology-1986105_1280.jpg",
    ],
    "hardware": [
        "photo-1518770660439-4636190af475", "photo-1591799264318-7e6ef8ddb7ea",
        "photo-1587202372775-e229f172b9d7", "photo-1591405351990-4726e331f141",
        "photo-1550745165-9bc0b252726f", "photo-1527443224154-c4a3942d3acf",
        "photo-1581092580497-e0d23cbdf1dc", "photo-1581092335878-2d9ff86ca2bf",
        "photo-1581092921461-eab62e97a780", "photo-1597733336794-12d05021d510"
        "https://cdn.pixabay.com/photo/2017/08/10/03/47/technology-2615761_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/10/29/09/06/computer-1784430_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/03/20/17/07/technology-2159136_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/11/14/08/18/technology-1824969_1280.jpg",
    ],
    "future": [
        "photo-1485827404703-89b55fcc595e", "photo-1535378620166-273708d44e4c",
        "photo-1521737711867-e3b97375f902", "photo-1531482615713-2afd69097998",
        "photo-1522071820081-009f0129c71c", "photo-1531297484001-80022131f5a1",
        "photo-1581091226825-a6a2a5aee158", "photo-1581092160562-40aa08e78837",
        "photo-1521737711867-e3b97375f902", "photo-1550439062-609e1531270e"
        "https://cdn.pixabay.com/photo/2017/03/19/20/19/robot-2159352_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/09/06/19/38/technology-2729801_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/08/07/14/14/technology-2608577_1280.jpg",
    ],
    "ai": [
        "photo-1677442136019-21780ecad995", "photo-1620712943543-bcc4688e7485",
        "photo-1676299081847-824916de030a", "photo-1498050108023-c5249f4df085",
        "photo-1519389950473-47ba0277781c", "photo-1504384308090-c894fdcc538d",
        "photo-1515879218367-8466d910aaa4", "photo-1531297484001-80022131f5a1",
        "photo-1516321318423-f06f85e504b3", "photo-1521737711867-e3b97375f902"
        "https://cdn.pixabay.com/photo/2019/04/11/11/52/artificial-intelligence-4118111_1280.jpg",
        "https://cdn.pixabay.com/photo/2018/04/23/14/38/technology-3348071_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/01/20/00/30/laptop-1997184_1280.jpg",
    ],
    "technologies": [
        "photo-1504384308090-c894fdcc538d", "photo-1498050108023-c5249f4df085",
        "photo-1519389950473-47ba0277781c", "photo-1522071820081-009f0129c71c",
        "photo-1516321318423-f06f85e504b3", "photo-1531297484001-80022131f5a1",
        "photo-1515879218367-8466d910aaa4", "photo-1550439062-609e1531270e",
        "photo-1550745165-9bc0b252726f", "photo-1531482615713-2afd69097998"
        "https://cdn.pixabay.com/photo/2017/07/31/11/22/people-2557396_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/11/29/06/15/plans-1867745_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/03/09/09/30/desk-1245954_1280.jpg",
    ]
}

def _image_url(photo_id):
    if photo_id.startswith("https://"):
        return photo_id
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1200&h=675&q=82"

def _http_image_ok(url):
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "TechPulseImagePicker/1.0", "Accept": "image/avif,image/webp,image/*,*/*"}
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.getcode() == 200 and response.headers.get("Content-Type", "").lower().startswith("image/")
    except Exception as error:
        print(f"Снимката не премина HTTP проверката: {url} ({error})")
        return False

def _json_get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "TechPulse/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.getcode() != 200:
            return {}
        return json.loads(response.read().decode("utf-8"))

def _recent_image_urls(history, count=50):
    return {
        item.get("img") for item in history[:count]
        if isinstance(item, dict) and isinstance(item.get("img"), str)
    }

def _provider_image(image_query, history, provider):
    used_all = {
        item.get("img") for item in history
        if isinstance(item, dict) and isinstance(item.get("img"), str)
    }
    query = urllib.parse.quote(image_query.strip())
    candidates = []
    try:
        if provider == "pixabay":
            key = os.environ.get("PIXABAY_API_KEY", "").strip()
            if not key:
                return None
            endpoint = (
                "https://pixabay.com/api/?key=" + urllib.parse.quote(key)
                + "&q=" + query
                + "&image_type=photo&orientation=horizontal&safesearch=true&per_page=20"
            )
            data = _json_get(endpoint)
            for hit in data.get("hits", []):
                if hit.get("imageWidth", 0) > hit.get("imageHeight", 0):
                    candidates.append(hit.get("largeImageURL") or hit.get("webformatURL"))
        else:
            endpoint = (
                "https://api.openverse.org/v1/images/?q=" + query
                + "&aspect_ratio=wide&license_type=commercial,modification&page_size=20"
            )
            data = _json_get(endpoint)
            for hit in data.get("results", []):
                width, height = hit.get("width", 0), hit.get("height", 0)
                if not width or not height or width > height:
                    candidates.append(hit.get("url"))
    except Exception as error:
        print(f"{provider} търсенето не е достъпно: {error}")
        return None

    for url in candidates:
        if isinstance(url, str) and url.startswith("https://") and url not in used_all and _http_image_ok(url):
            print(f"Избрана снимка от {provider}: {url}")
            return url
    return None

def choose_article_images(category_slug, history, image_query):
    recent = _recent_image_urls(history, 50)
    # Providers have priority. Their URLs are never reused from the full history.
    main_image = _provider_image(image_query, history, "pixabay")
    source = "pixabay" if main_image else None
    if not main_image:
        main_image = _provider_image(image_query, history, "openverse")
        source = "openverse" if main_image else None

    if not main_image:
        pool = IMAGE_POOLS.get(category_slug, []) + [
            photo for key, photos in IMAGE_POOLS.items() if key != category_slug for photo in photos
        ]
        candidates = list(dict.fromkeys(_image_url(photo) for photo in pool))
        random.shuffle(candidates)
        for candidate in candidates:
            if candidate not in recent and _http_image_ok(candidate):
                main_image = candidate
                source = "unsplash_fallback"
                break

    if not main_image:
        raise RuntimeError("Няма свободна хоризонтална снимка с HTTP 200 извън последните 50 статии.")

    fallback_image = next(
        (url for url in (_image_url(photo) for photos in IMAGE_POOLS.values() for photo in photos)
         if url != main_image and url not in recent and _http_image_ok(url)),
        main_image
    )
    return main_image, fallback_image, source

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

ADSENSE_HEAD_SCRIPT = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8109991761364968" crossorigin="anonymous"></script>'

def create_static_pages():
    pages = {
        "about.html": ("За нас", "<h1>За TechPulse</h1><p>TechPulse е медия за изкуствен интелект, технологии и иновации.</p>"),
        "contacts.html": ("Контакти", "<h1>Контакти</h1><p>Пишете ни на: contact@techpulseon.site</p>"),
    }
    for filename, (title, content) in pages.items():
        filepath = os.path.join(PUBLIC_DIR, filename)
        html = f"""<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {ADSENSE_HEAD_SCRIPT}
    <title>{title} — TechPulse</title>
    <style>{CSS_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header"><a href="/" class="logo">⚡ TechPulse</a></div>
        <div class="static-card">{content}</div>
        <footer>
            <div class="footer-links">
                <a href="/">Начало</a> | <a href="/articles.html">Статии</a> | <a href="/tools.html">Инструменти</a>
                <a href="/glossary.html">Речник</a>
                <a href="/about.html">За нас</a> | <a href="/contacts.html">Контакти</a> | <a href="/privacy.html">Поверителност и бисквитки</a> | <a href="/terms.html">Общи условия</a>
            </div>
        </footer>
        
    </div>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

def sync_article_footers():
    """Bring existing article footers in line with the site-wide legal/navigation links."""
    footer = """<footer class="site-footer">
<nav class="footer-links" aria-label="Полезни връзки">
<a href="/">Начало</a>
<a href="/articles.html">Статии</a>
<a href="/tools.html">Инструменти</a>
<a href="/glossary.html">Речник</a>
<a href="/about.html">За нас</a>
<a href="/contacts.html">Контакти</a>
<a href="/privacy.html">Поверителност и бисквитки</a>
<a href="/terms.html">Общи условия</a>
</nav>
<p>© TechPulse. Всички права запазени.</p>
</footer>"""
    if not os.path.isdir(ARTICLES_DIR):
        return
    for filename in os.listdir(ARTICLES_DIR):
        if not filename.lower().endswith(".html"):
            continue
        filepath = os.path.join(ARTICLES_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as article_file:
                content = article_file.read()
            original_content = content
            updated, count = re.subn(
                r"<footer\b[^>]*>[\s\S]*?</footer>",
                footer,
                content,
                count=1,
                flags=re.IGNORECASE,
            )
            if count:
                content = updated
            # Remove legacy local consent UI and ensure AdSense is loaded directly in head.
            content = re.sub(r'<style[^>]*id="tp-cookie-style"[^>]*>[\s\S]*?</style>', "", content, flags=re.IGNORECASE)
            content = re.sub(r'<section[^>]*id="tp-cookie-banner"[\s\S]*?</section>', "", content, flags=re.IGNORECASE)
            content = re.sub(r'<script>\s*\(function\(\)\{[\s\S]*?techpulse_cookie_choice_v1[\s\S]*?</script>', "", content, flags=re.IGNORECASE)
            content = re.sub(r'<a[^>]*id="tp-cookie-settings"[^>]*>[\s\S]*?</a>', "", content, flags=re.IGNORECASE)
            if "adsbygoogle.js?client=ca-pub-8109991761364968" not in content:
                content = re.sub(r'<head[^>]*>', lambda match: match.group(0) + ADSENSE_HEAD_SCRIPT, content, count=1, flags=re.IGNORECASE)
            if "author-box" not in content:
                content = content.replace("</main>", '<section class="author-box"><h2>Редакция и авторство</h2><p><strong>Редакция TechPulse</strong></p><p>Материалът е подготвен от редакционния екип на TechPulse. Проверимите факти се разграничават от анализа.</p></section></main>', 1)
            if "related-articles" not in content:
                history = load_history()
                current = next((x for x in history if x.get("url", "").endswith(filename)), None)
                related = [x for x in history if current and x.get("category_slug") == current.get("category_slug") and x.get("url") != current.get("url")][:3]
                if related:
                    links = "".join('<li><a href="' + x.get("url", "#") + '">' + x.get("title", "Още по темата") + "</a></li>" for x in related)
                    block = '<section class="related-articles"><h2>Свързани статии</h2><ul>' + links + "</ul></section>"
                    content = content.replace("</main>", block + "</main>", 1)
            if content != original_content:
                with open(filepath, "w", encoding="utf-8") as article_file:
                    article_file.write(content)
                print(f"Обновена редакционна информация: {filename}")
        except (OSError, UnicodeError) as error:
            print(f"Неуспешно обновяване на футъра в {filename}: {error}")


def build_full_page(title, main_image_url, fallback_backup_img, article_body, sidebar_items):
    sidebar_html = ""
    for item in sidebar_items:
        sidebar_html += f"""
        <div class="similar-item">
            <img src="{item.get('img', 'https://images.unsplash.com/photo-1535378273068-9bb67d5beacd?w=200&auto=format&fit=crop')}" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1518770660439-4636190af475?w=200&auto=format&fit=crop';" alt="{item.get('title', 'Новина')}">
            <div class="similar-item-info">
                <span class="similar-tag">{item.get('category', 'AI')}</span>
                <h4><a href="{item.get('url', '#')}">{item.get('title', 'Новина')}</a></h4>
                <span>{item.get('time', '2026-09-26')}</span>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {ADSENSE_HEAD_SCRIPT}
    <title>{title} — TechPulse</title>
    <style>{CSS_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="/" class="logo">⚡ TechPulse</a>
            <form class="search-box" action="/articles.html" method="get" role="search"><input type="search" name="q" placeholder="🔍 Търсене..." aria-label="Търсене в TechPulse"></form>
        </div>
        <nav class="nav-categories" aria-label="Основна навигация">
            <a href="/" class="nav-link active">Начало</a>
            <a href="/articles.html" class="nav-link">Статии</a>
            <a href="/articles.html?category=ai" class="nav-link">AI</a>
            <a href="/articles.html?category=technologies" class="nav-link">Технологии</a>
            <a href="/articles.html?category=hardware" class="nav-link">Хардуер</a>
            <a href="/tools.html" class="nav-link">Инструменти</a>
            <a href="/glossary.html" class="nav-link">Речник</a>
            <a href="/about.html" class="nav-link">За нас</a>
            <a href="/contacts.html" class="nav-link">Контакти</a>
        </nav>
        <div class="main-layout">
            <div class="main-content">
                <article class="article-card">
                    <img src="{main_image_url}" onerror="this.onerror=null;this.src='{fallback_backup_img}';" alt="{title}" class="article-image">
                    {article_body}
                </article>
            </div>
            <aside class="sidebar">
                <h3>Още новини</h3>
                {sidebar_html}
            </aside>
        </div>
        <footer class="site-footer">
            <nav class="footer-links" aria-label="Полезни връзки">
                <a href="/">Начало</a>
                <a href="/articles.html">Статии</a>
                <a href="/tools.html">Инструменти</a>
                <a href="/glossary.html">Речник</a>
                <a href="/about.html">За нас</a>
                <a href="/contacts.html">Контакти</a>
                <a href="/privacy.html">Поверителност и бисквитки</a>
                <a href="/terms.html">Общи условия</a>
            </nav>
            <p>© TechPulse. Всички права запазени.</p>
        </footer>
        
    </div>
</body>
</html>"""

def generate_news():
    print("TechPulse: търсене на актуална технологична тема чрез публични RSS източници (безплатен режим)...")

    prompt = """
<role>
Ти си опитен редактор на българско технологично издание. Напиши един завършен, задълбочен материал за реална и актуална технологична тема.
</role>

<research>
Използвай подадения RSS пакет като отправна точка. Избери конкретна тема с новинарска стойност от последните няколко дни в AI, чипове, квантови технологии, роботика, киберсигурност или потребителски технологии.
Провери ключовите твърдения. Предпочитай първични източници: официални съобщения и документация на компании, научни публикации, регулаторни документи и изявления на организациите, за които се говори.
Не измисляй факти, числа, дати, цитати, експерти, продукти, събития или резултати. Ако информацията не може да бъде надеждно потвърдена, не я представяй като факт.
</research>

<writing>
Пиши на естествен и точен български език. Забранени са шаблонните AI клишета и общите фрази, включително „На фона на засилената глобална конкуренция“, „Динамиката в технологичната индустрия“, „В съвременния дигитален свят“, „в днешния динамичен свят“, „революционизира“, „нова ера“, „играта се променя“ и „това променя всичко“. Не започвай с общи приказки. Започни с конкретен проверен факт, число, техническа промяна или практическа ситуация.
Целта е 950–1200 думи. Валидаторът допуска 700–1600 думи, но се стреми към целевия диапазон. Не повтаряй една теза с различни думи и не добавяй празни абзаци за обем.
Задължителна структура: конкретно въведение; 4–8 логични подзаглавия H2; всяка основна H2 секция трябва да съдържа по 2–3 плътни, съдържателни абзаца с факти, обяснения и примери. Тази дълбочина трябва естествено да доведе до около 950–1200 думи. Включи сравнителен блок или списък „Ключови изводи“; отделна секция „Какво означава това на практика“; FAQ с точно 3 въпроса и ясни отговори.
Обясни механизма, контекста, предимствата, недостатъците, разходите и ограниченията, когато са приложими. Включи конкретни сценарии и критерии за решение. Разграничавай факт, анализ и прогноза. Не измисляй тестове, личен опит, цитати, експерти или числа. Ако липсват надеждни данни, кажи го изрично.
</writing>

<current_rss>
{RSS_CONTEXT}
</current_rss>

<format>
Върни валиден JSON обект без Markdown и code fences. Форматът е точно: {"article_html":"Пълният HTML материал...","image_query":"2–3 конкретни английски думи"}. В article_html запази следната структура: първият елемент е <h1>, следван от точно един <p class="article-intro">, после 4–8 смислени <h2> секции с по 2–3 плътни абзаца, секция „Ключови изводи“, отделна секция „Какво означава това на практика“ и FAQ с точно 3 въпроса като <h3> и <p>, плюс валиден FAQPage JSON-LD. image_query трябва да е кратка фраза на английски с 2–3 думи, описваща конкретния обект/сцена в статията (например "quantum computer lab", "microchip silicon wafer", "cybersecurity server room"). Не връщай URL в image_query и не включвай изображение в HTML.
</format>

Напиши материала така, че читателят да получи реално обяснение на темата, а не просто преразказ на новината.
"""

    rss_items = []
    feeds = ["https://news.google.com/rss/search?q=AI+OR+artificial+intelligence&hl=en-US&gl=US&ceid=US:en", "https://news.google.com/rss/search?q=semiconductors+OR+chips&hl=en-US&gl=US&ceid=US:en", "https://news.google.com/rss/search?q=robotics+OR+quantum+computing&hl=en-US&gl=US&ceid=US:en", "https://news.google.com/rss/search?q=cybersecurity+OR+technology&hl=en-US&gl=US&ceid=US:en"]
    for feed_url in feeds:
        try:
            with urllib.request.urlopen(feed_url, timeout=15) as response:
                root = ET.fromstring(response.read())
            for item in root.findall("./channel/item")[:8]:
                title = item.findtext("title"); link = item.findtext("link"); pub_date = item.findtext("pubDate")
                source = item.find("source"); source_name = source.text if source is not None else ""
                if title and link: rss_items.append({"title": title, "link": link, "date": pub_date or "", "source": source_name})
        except Exception as e:
            print(f"RSS източникът не е достъпен: {e}")
    if not rss_items: raise RuntimeError("Не бяха получени актуални RSS новини. Няма да се публикува.")
    rss_context = "\n".join(f'- {x["title"]} | {x["source"]} | {x["date"]} | {x["link"]}' for x in rss_items[:25])
    prompt = prompt.replace("{RSS_CONTEXT}", rss_context)
    article_body = None
    retry_feedback = None
    models = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
    for model_name in models:
        for attempt in range(3):
            try:
                if attempt:
                    import time
                    delay = 15 * (2 ** (attempt - 1))
                    print(f"Временен проблем с {model_name}; нов опит след {delay} секунди...")
                    time.sleep(delay)

                request_prompt = prompt
                if retry_feedback:
                    request_prompt += f"""

БЕЛЕЖКА ОТ ПРЕДИШНИЯ ОПИТ: Предишният вариант беше отхвърлен поради: {retry_feedback}.
Коригирай точно този проблем в новия пълен HTML материал. При недостатъчен брой думи развий основните H2 секции с по 2–3 плътни абзаца и се стреми към 950–1200 думи. При грешен брой H2 добави или премахни смислени секции така, че да има 4–8. Запази проверимите факти, без повторения и без измисляне.
Върни целия завършен материал отначало.
"""
                response = client.models.generate_content(
                    model=model_name,
                    contents=request_prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=8192,
                        response_mime_type="application/json",
                    ),
                )
                if not response or not response.text:
                    continue

                payload = json.loads(response.text)
                cleaned = str(payload.get("article_html", "")).strip()
                image_query = str(payload.get("image_query", "")).strip()
                image_query = re.sub(r"[^A-Za-z ]", " ", image_query)
                image_query = re.sub(r"\\s+", " ", image_query).strip()
                if not 2 <= len(image_query.split()) <= 3:
                    image_query = " ".join(re.findall(r"[A-Za-z]+", title_text if "title_text" in locals() else "technology innovation")[:3]) or "technology innovation"
                if not cleaned:
                    raise ValueError("JSON отговорът няма article_html")
                plain_text = re.sub(r"<[^>]+>", " ", cleaned)
                plain_text = re.sub(r"\s+", " ", plain_text).strip()
                word_count = len(re.findall(r"(?u)\b[\wА-Яа-яЁё]+\b", plain_text))
                h2_count = len(re.findall(r"<h2\b", cleaned, flags=re.I))
                h3_count = len(re.findall(r"<h3\b", cleaned, flags=re.I))
                short_paragraphs = len(re.findall(r"<p\b[^>]*>[^<]{1,120}</p>", cleaned, flags=re.I))

                h1_count = len(re.findall(r"<h1\b", cleaned, flags=re.I))
                faq_schema_valid = False
                faq_payloads = re.findall(
                    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
                    cleaned,
                    flags=re.I,
                )
                for faq_payload in faq_payloads:
                    try:
                        faq_data = json.loads(faq_payload)
                        faq_type = faq_data.get("@type", "")
                        faq_items = faq_data.get("mainEntity", [])
                        if (
                            (faq_type == "FAQPage" or str(faq_type).endswith("/FAQPage"))
                            and len(faq_items) == 3
                            and all(
                                (
                                    item.get("@type") == "Question"
                                    or str(item.get("@type", "")).endswith("/Question")
                                )
                                and (
                                    item.get("acceptedAnswer", {}).get("@type") == "Answer"
                                    or str(item.get("acceptedAnswer", {}).get("@type", "")).endswith("/Answer")
                                )
                                for item in faq_items
                            )
                        ):
                            faq_schema_valid = True
                            break
                    except (json.JSONDecodeError, AttributeError, TypeError):
                        continue

                valid_structure = (
                    h1_count == 1
                    and 4 <= h2_count <= 8
                    and "Ключови изводи" in cleaned
                    and "Какво означава това на практика" in cleaned
                    and "Често задавани въпроси" in cleaned
                    and faq_schema_valid
                    and '<p class="article-intro">' in cleaned
                    and "<p>" in cleaned
                    and word_count >= 700
                    and word_count <= 1600
                    and h3_count == 3
                    and short_paragraphs <= 8
                )

                if valid_structure:
                    article_body = cleaned
                    print(f"Получена статия: {word_count} думи, {h3_count} подзаглавия чрез {model_name}.")
                    break

                reasons = []
                if h1_count != 1:
                    reasons.append(f"h1={h1_count} (трябва точно 1)")
                if h2_count < 4 or h2_count > 8:
                    reasons.append(f"h2={h2_count} (допустими 4–8)")
                if not faq_schema_valid:
                    reasons.append("FAQPage JSON-LD е невалиден или няма точно 3 въпроса")
                if '<p class="article-intro">' not in cleaned:
                    reasons.append("липсва article-intro")
                if "<p>" not in cleaned:
                    reasons.append("липсват стандартни абзаци")
                if word_count < 700 or word_count > 1600:
                    reasons.append(f"думи={word_count} (допустими 700–1600)")
                if h3_count != 3:
                    reasons.append(f"h3={h3_count} (трябва точно 3 FAQ въпроса)")
                if short_paragraphs > 8:
                    reasons.append(f"кратки абзаци={short_paragraphs} (максимум 8)")
                print(f"Отхвърлена статия от {model_name}: {word_count} думи, {h3_count} подзаглавия. Причина: {', '.join(reasons) or 'непозната структурна грешка'}.")
                retry_feedback = ", ".join(reasons) or "структурата не покрива критериите"
            except Exception as e:
                print(f"Грешка с {model_name} (опит {attempt + 1}/3): {e}")
                error_text = str(e).upper()
                transient = any(token in error_text for token in (
                    "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                    "TIMEOUT", "DEADLINE", "CONNECTION", "500", "502", "504"
                ))
                if not transient:
                    break

        if article_body:
            break

    if not article_body:
        raise RuntimeError(
            "Gemini не върна статия, която покрива редакционните критерии за дължина и структура. "
            "Няма да се публикува непроверен fallback материал."
        )

    # Записвай само RSS източници, към които статията има изричен линк.
    # RSS контекстът сам по себе си не доказва, че даден материал е използван.
    source_links = []
    for candidate in rss_items:
        link_pattern = r"""href=["']""" + re.escape(candidate["link"]) + r"""["']"""
        if re.search(link_pattern, article_body, re.I):
            if candidate["link"] not in [x["url"] for x in source_links]:
                source_links.append({"title": candidate["title"], "url": candidate["link"]})

    if source_links:
        source_html = '<section class="article-sources"><h3>Източници</h3><ul>'
        for source in source_links:
            source_html += (
                f'<li><a href="{source["url"]}" rel="noopener noreferrer">'
                f'{source["title"]}</a></li>'
            )
        source_html += "</ul></section>"
        article_body += source_html

    title_match = re.search(r"<h1>(.*?)</h1>", article_body, re.S)
    title_text = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else "Технологична новина"
    article_plain_for_reading = re.sub(r"<[^>]+>", " ", article_body)
    article_words_for_reading = len(re.findall(r"(?u)\b[\wА-Яа-яЁё]+\b", article_plain_for_reading))
    reading_minutes = max(1, round(article_words_for_reading / 200))
    published_date = __import__("datetime").date.today().strftime("%d.%m.%Y")
    byline = f'<p class="meta">Редакция TechPulse · {published_date} · {reading_minutes} мин. четене</p>'
    article_body = re.sub(r"(</h1>)", r"\1" + byline, article_body, count=1, flags=re.I)

    history = load_history()
    category_label, category_slug = infer_category(title_text, article_body, history)
    main_image_url, fallback_img, image_source = choose_article_images(category_slug, history, image_query)

    sidebar_items = history[:3] if len(history) >= 3 else DEFAULT_ARTICLES
    related_items = [x for x in history if x.get("category_slug") == category_slug][:3]
    related_links = "".join('<li><a href="' + x.get("url", "#") + '">' + x.get("title", "Още по темата") + "</a></li>" for x in related_items)
    editorial = '<section class="author-box"><h2>Редакция и авторство</h2><p><strong>Редакция TechPulse</strong></p><p>Материалът е подготвен от редакционния екип на TechPulse. Фактите се разграничават от анализа, а източниците дават възможност за самостоятелна проверка.</p></section>'
    related = '<section class="related-articles"><h2>Свързани статии</h2><ul>' + related_links + "</ul></section>" if related_links else ""
    article_body += editorial + related
    full_html = build_full_page(title_text, main_image_url, fallback_img, article_body, sidebar_items)

    article_slug = slugify(title_text)
    article_file_path = os.path.join(ARTICLES_DIR, f"{article_slug}.html")
    article_url = f"/articles/{article_slug}.html"

    if os.path.exists(article_file_path):
        raise RuntimeError(f"Статията вече съществува: {article_file_path}")

    with open(article_file_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    # Update legal/navigation links in all existing article pages without touching article text.
    sync_article_footers()

    history.insert(0, {
        "title": title_text,
        "time": __import__("datetime").date.today().isoformat(),
        "category": category_label,
        "category_slug": category_slug,
        "url": article_url,
        "img": main_image_url,
        "image_source": image_source,
        "image_query": image_query,
        "sources": source_links[:6]
    })
    save_history(history[:200])
    print(f"Публикационният пакет е готов: {article_url}")


if __name__ == "__main__":
    generate_news()
