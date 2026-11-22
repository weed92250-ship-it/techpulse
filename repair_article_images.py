import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path("public")
HISTORY_FILE = ROOT / "articles.json"
ARTICLES_DIR = ROOT / "articles"
INDEX_FILE = ROOT / "index.html"
LIST_FILE = ROOT / "articles.html"
IMAGE_DIR = ROOT / "images" / "articles"

UNSPLASH_IDS = [
    "photo-1535378273068-9bb67d5beacd",
    "photo-1635070041078-e363dbe005cb",
    "photo-1451187580459-43490279c0fa",
    "photo-1523961131990-5ea7c61b2107",
    "photo-1535223289827-42f1e9919769",
    "photo-1535378620166-273708d44e4c",
    "photo-1618005182384-a83a8bd57fbe",
    "photo-1527443224154-c4a3942d3acf",
    "photo-1581091226825-a6a2a5aee158",
    "photo-1581092160562-40aa08e78837",
    "photo-1526374965328-7f61d4dc18c5",
    "photo-1550751827-4bd374c3f58b",
    "photo-1563013544-824ae1b704d3",
    "photo-1510511459019-5dda7724fd87",
    "photo-1558494949-ef010cbdcc31",
    "photo-1550439062-609e1531270e",
    "photo-1516321318423-f06f85e504b3",
    "photo-1581092795360-fd1ca04f0952",
    "photo-1515879218367-8466d910aaa4",
    "photo-1518770660439-4636190af475",
    "photo-1591799264318-7e6ef8ddb7ea",
    "photo-1587202372775-e229f172b9d7",
    "photo-1591405351990-4726e331f141",
    "photo-1550745165-9bc0b252726f",
    "photo-1581092580497-e0d23cbdf1dc",
    "photo-1581092335878-2d9ff86ca2bf",
    "photo-1581092921461-eab62e97a780",
    "photo-1597733336794-12d05021d510",
    "photo-1485827404703-89b55fcc595e",
    "photo-1521737711867-e3b97375f902",
    "photo-1531482615713-2afd69097998",
    "photo-1522071820081-009f0129c71c",
    "photo-1531297484001-80022131f5a1",
    "photo-1677442136019-21780ecad995",
    "photo-1620712943543-bcc4688e7485",
    "photo-1676299081847-824916de030a",
    "photo-1498050108023-c5249f4df085",
    "photo-1519389950473-47ba0277781c",
    "photo-1504384308090-c894fdcc538d",
    "photo-1504639725590-34d0984388bd",
    "photo-1516321497487-e288fb19713f",
    "photo-1517245386807-bb43f82c33c4",
    "photo-1522542550221-31fd19575a2d",
    "photo-1551288049-bebda4e38f71",
    "photo-1555949963-ff9fe0c870eb",
    "photo-1560472354-b33ff0c44a43",
    "photo-1563206767-5b18f218e8de",
    "photo-1563770660941-10a63607739e",
    "photo-1573164713714-d95e436ab8d6",
    "photo-1573496359142-b8d87734a5a2",
    "photo-1581092334651-ddf26d9a09d0",
    "photo-1581092918056-0c4c3acd3789",
    "photo-1581092160607-ee22621dd758",
    "photo-1593508512255-86ab42a8e620",
    "photo-1593642632823-8f785ba67e45",
]
UNSPLASH_PARAMS = "?auto=format&fit=crop&w=1200&h=675&q=82"
HEADERS = {
    "User-Agent": "TechPulseBot/1.0 (https://techpulseon.site)",
    "Accept": "image/avif,image/webp,image/jpeg,image/*;q=0.9,*/*;q=0.8",
}
API_HEADERS = {
    "User-Agent": "TechPulseBot/1.0 (https://techpulseon.site)",
    "Accept": "application/json",
}

def unsplash_url(photo_id):
    return "https://images.unsplash.com/" + photo_id + UNSPLASH_PARAMS

def is_live_image(url):
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=15) as response:
            mime = response.headers.get("Content-Type", "").lower().split(";")[0]
            return response.status == 200 and mime in ("image/jpeg", "image/webp")
    except Exception as exc:
        print(f"Непотвърдена снимка {url}: {exc}")
        return False

def api_json(url):
    request = urllib.request.Request(url, headers=API_HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            return {}
        return json.loads(response.read().decode("utf-8"))

def recent_image_urls(history):
    return {x.get("img") for x in history if isinstance(x, dict) and x.get("img")}

def pixabay_candidates(query):
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return []
    endpoint = "https://pixabay.com/api/?" + urllib.parse.urlencode({
        "key": key, "q": query, "image_type": "photo", "orientation": "horizontal",
        "safesearch": "true", "per_page": 50,
    })
    try:
        data = api_json(endpoint)
    except Exception as exc:
        print(f"Pixabay API грешка: {exc}")
        return []
    return [
        hit.get("largeImageURL") or hit.get("webformatURL")
        for hit in data.get("hits", [])
        if hit.get("imageWidth", 0) >= 800 and hit.get("imageWidth", 0) > hit.get("imageHeight", 0)
    ]

def download_pixabay(url, slug):
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / (slug + ".jpg")
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        mime = response.headers.get("Content-Type", "").lower()
        data = response.read()
        if response.status != 200 or not mime.startswith("image/") or not data:
            raise RuntimeError("Pixabay файлът не е валидно изображение.")
    path.write_bytes(data)
    return "/" + path.as_posix()

def commons_candidates(query, used, limit=50):
    params = {
        "action": "query", "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": 50, "prop": "imageinfo",
        "iiprop": "url|size|mime", "iiurlwidth": 1200, "format": "json",
    }
    endpoint = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        data = api_json(endpoint)
    except Exception as exc:
        print(f"Wikimedia Commons API грешка за '{query}': {exc}")
        return []
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 999999))
    found = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "").lower()
        width, height = info.get("width", 0), info.get("height", 0)
        url = info.get("thumburl") or info.get("url")
        if mime not in ("image/jpeg", "image/webp") or width < 800 or width <= height:
            continue
        if not isinstance(url, str) or not url.startswith("https://") or url in used:
            continue
        if url not in {item["url"] for item in found}:
            found.append({"url": url, "mime": mime, "width": width, "height": height})
        if len(found) >= limit:
            break
    return found

def replace_meta(content, name, url, prop=False):
    attr = "property" if prop else "name"
    pattern = rf'<meta\\s+{attr}=["\\']{re.escape(name)}["\\']\\s+content=["\\'][^"\\']*["\\']\\s*/?>'
    tag = f'<meta {attr}="{name}" content="{html.escape(url, quote=True)}">'
    if re.search(pattern, content, re.I):
        return re.sub(pattern, tag, content, count=1, flags=re.I)
    return re.sub(r"</head>", tag + "</head>", content, count=1, flags=re.I)

def main():
    history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    recent = history[:30]
    used = recent_image_urls(history)
    chosen = []

    # Pixabay is preferred only when its API key is configured. The selected
    # remote image is downloaded locally as public/images/articles/<slug>.jpg.
    for item in recent:
        slug = Path(item["url"]).stem
        if os.environ.get("PIXABAY_API_KEY", "").strip():
            for candidate in pixabay_candidates(item.get("image_query") or item.get("title", "technology")):
                try:
                    local_url = download_pixabay(candidate, slug)
                    if local_url not in used and local_url not in chosen:
                        chosen.append(local_url)
                        break
                except Exception as exc:
                    print(f"Pixabay изтеглянето пропуснато за {slug}: {exc}")
        if len(chosen) == len(recent):
            break

    # Fill remaining slots from the clean, unique Unsplash catalog.
    if len(chosen) < len(recent):
        catalog = list(dict.fromkeys(unsplash_url(photo_id) for photo_id in UNSPLASH_IDS))
        for url in catalog:
            if url in used or url in chosen:
                continue
            if is_live_image(url):
                chosen.append(url)
                if len(chosen) == len(recent):
                    break

    # Wikimedia Commons is the final provider fallback, with strict photo filters.
    if len(chosen) < len(recent):
        commons_queries = [
            "technology laboratory computer science",
            "semiconductor microchip electronics",
            "artificial intelligence robotics research",
            "cybersecurity data center server",
            "quantum computing laboratory",
        ]
        for query in commons_queries:
            for hit in commons_candidates(query, used | set(chosen), limit=50):
                if is_live_image(hit["url"]):
                    chosen.append(hit["url"])
                    if len(chosen) == len(recent):
                        break
            if len(chosen) == len(recent):
                break

    if len(chosen) < len(recent):
        raise RuntimeError(
            f"Намерени са само {len(chosen)} проверени уникални снимки за {len(recent)} статии. "
            "Не записвам частичен ремонт."
        )

    updates = {}
    for item, url in zip(recent, chosen):
        item["img"] = url
        item["image_source"] = (
            "pixabay_local" if url.startswith("/images/articles/")
            else "wikimedia_commons" if "wikimedia" in url or "wikipedia" in url
            else "unsplash_fallback"
        )
        updates[item["url"]] = url

    for article_url, url in updates.items():
        article_path = ARTICLES_DIR / Path(article_url).name
        if not article_path.exists():
            raise FileNotFoundError(f"Липсва HTML файлът за {article_url}")
        content = article_path.read_text(encoding="utf-8")
        content = replace_meta(content, "og:image", url, prop=True)
        content = replace_meta(content, "twitter:image", url)
        img_pattern = r'(<img\\b[^>]*?\\bsrc=["\\'])[^"\\']+((?:["\\']))'
        content, count = re.subn(
            img_pattern, lambda m: m.group(1) + url + m.group(2),
            content, count=1, flags=re.I
        )
        if not count:
            raise RuntimeError(f"Не е намерен основен img елемент в {article_path}")
        article_path.write_text(content, encoding="utf-8")

    page = INDEX_FILE.read_text(encoding="utf-8")
    def update_card(match):
        block = match.group(0)
        for article_url, url in updates.items():
            if article_url in block:
                return re.sub(
                    r'(<img\\b[^>]*?\\bsrc=["\\'])[^"\\']+((?:["\\']))',
                    lambda m: m.group(1) + url + m.group(2),
                    block, count=1, flags=re.I
                )
        return block
    page = re.sub(r"<article\\b[\\s\\S]*?</article>", update_card, page, flags=re.I)
    if recent:
        page = replace_meta(page, "og:image", recent[0]["img"], prop=True)
    INDEX_FILE.write_text(page, encoding="utf-8")

    page = LIST_FILE.read_text(encoding="utf-8")
    for item in recent:
        article_url, url = item["url"], item["img"]
        href = re.escape(article_url)
        pattern = re.compile(rf'(<a\\b[^>]*\\bhref=["\\']{href}["\\'][^>]*>)', re.I)
        thumb = (
            f'<img class="article-thumb" loading="lazy" width="320" height="180" '
            f'src="{html.escape(url, quote=True)}" '
            f'alt="{html.escape(item.get("title", "TechPulse"), quote=True)}">'
        )
        if pattern.search(page):
            page = pattern.sub(lambda m: m.group(1) + thumb, page, count=1)
    if ".article-thumb" not in page:
        page = page.replace(
            "</style>",
            ".article-thumb{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:6px;margin:0 0 12px}</style>",
            1
        )
    LIST_FILE.write_text(page, encoding="utf-8")
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(f"Обновени са снимките на {len(recent)} статии, HTML метаданните, началната страница и архивът.")

if __name__ == "__main__":
    main()
