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


CATEGORY_ROTATION = [
    ("AI", "ai"),
    ("Хардуер", "hardware"),
    ("Киберсигурност", "cyber"),
    ("Технологии", "technologies"),
    ("Квантови технологии", "quantum"),
    ("Бъдещи технологии", "future"),
]

TOPIC_STOPWORDS = {
    "как", "защо", "кога", "кой", "коя", "кои", "това", "тези", "този", "тази",
    "при", "след", "преди", "между", "срещу", "от", "до", "на", "в", "и", "или",
    "с", "по", "за", "над", "под", "нов", "нова", "нови", "новото", "новият",
    "the", "and", "for", "with", "from", "into", "after", "before", "how", "why",
    "what", "this", "that", "new", "latest", "its", "their", "are", "is",
}


def classify_topic_category(title):
    text = (title or "").lower()
    rules = [
        ("quantum", ("квант", "quantum", "qubit", "кубит")),
        ("cyber", ("киберсигур", "cybersecurity", "zero trust", "passkey", "ransomware", "криптограф")),
        ("hardware", ("чип", "chip", "gpu", "cpu", "npu", "процесор", "хардуер", "semiconductor", "полупровод")),
        ("future", ("робот", "robot", "невроморф", "autonomous", "автоном", "humanoid")),
        ("ai", ("изкуствен интелект", "artificial intelligence", " ai", "ai ", "llm", "езиков модел", "генератив")),
    ]
    for slug, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return slug
    return "technologies"


def topic_tokens(title):
    words = re.findall(r"(?u)[a-zа-яё0-9]{3,}", (title or "").lower())
    return {word for word in words if word not in TOPIC_STOPWORDS}


def topic_titles_overlap(left, right):
    a, b = topic_tokens(left), topic_tokens(right)
    if len(a) < 2 or len(b) < 2:
        return False
    common = a & b
    if len(common) < 2:
        return False
    return (len(common) / min(len(a), len(b)) >= 0.55
            or len(common) / len(a | b) >= 0.38)


def source_urls_from_record(record):
    urls = set()
    for key in ("source_url", "source_urls"):
        value = record.get(key)
        if isinstance(value, str) and value:
            urls.add(value.rstrip("/"))
        elif isinstance(value, list):
            urls.update(item.rstrip("/") for item in value if isinstance(item, str) and item)
    for source in record.get("sources", []) or []:
        if isinstance(source, dict) and source.get("url"):
            urls.add(str(source["url"]).rstrip("/"))
    return urls


def filter_recent_topics(rss_items, history):
    """Exclude the last three published categories and topics covered in the last 20 articles."""
    blocked_categories = {
        item.get("category_slug") for item in (history or [])[:3]
        if item.get("category_slug")
    }
    recent = (history or [])[:20]
    seen_urls = set()
    for record in recent:
        seen_urls.update(source_urls_from_record(record))

    accepted = []
    rejected = {"recent_category": 0, "source_url": 0, "similar_title": 0}
    seen_rss_urls = set()

    for item in rss_items:
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        if not title or not link:
            continue
        normalized_link = link.rstrip("/")
        if normalized_link in seen_rss_urls:
            continue
        seen_rss_urls.add(normalized_link)

        category = item.get("category_hint") or classify_topic_category(title)
        if category in blocked_categories:
            rejected["recent_category"] += 1
            continue
        if normalized_link in seen_urls:
            rejected["source_url"] += 1
            continue

        duplicate = False
        for record in recent:
            old_title = record.get("title", "")
            old_source_title = record.get("source_title", "")
            if topic_titles_overlap(title, old_title) or (
                old_source_title and topic_titles_overlap(title, old_source_title)
            ):
                duplicate = True
                break
        if duplicate:
            rejected["similar_title"] += 1
            continue

        accepted.append(item)

    rotation_slugs = [slug for _, slug in CATEGORY_ROTATION]
    latest_slug = (history or [{}])[0].get("category_slug")
    rotation_start = (
        (rotation_slugs.index(latest_slug) + 1) % len(rotation_slugs)
        if latest_slug in rotation_slugs else 0
    )
    accepted.sort(
        key=lambda item: (
            rotation_slugs.index(classify_topic_category(item["title"])) - rotation_start
        ) % len(rotation_slugs)
    )

    print(
        "RSS филтър: "
        f"{len(accepted)} допустими теми; отхвърлени по категория: "
        f"{rejected['recent_category']}, по URL: {rejected['source_url']}, "
        f"по сходно заглавие: {rejected['similar_title']}. "
        f"Изключени категории: {', '.join(sorted(blocked_categories)) or 'няма'}. "
        f"Следваща категория по ротация: "
        f"{CATEGORY_ROTATION[rotation_start][0]}."
    )
    return accepted

RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

CATEGORY_FEEDS = {
    "ai": [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ],
    "hardware": [
        ("Tom's Hardware", "https://www.tomshardware.com/feeds/all"),
        ("Ars Technica Technology Lab", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ],
    "cyber": [
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("The Hacker News", "https://feeds.feedburner.com/TheHackerNews"),
    ],
    "technologies": [
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("WIRED", "https://www.wired.com/feed/rss"),
    ],
    "quantum": [
        ("Phys.org Technology", "https://phys.org/rss-feed/technology-news/"),
        ("ScienceDaily Computers & Math", "https://www.sciencedaily.com/rss/computers_math.xml"),
        ("The Quantum Insider", "https://thequantuminsider.com/feed/"),
    ],
    "future": [
        ("Phys.org Technology", "https://phys.org/rss-feed/technology-news/"),
        ("ScienceDaily Computers & Math", "https://www.sciencedaily.com/rss/computers_math.xml"),
        ("The Quantum Insider", "https://thequantuminsider.com/feed/"),
    ],
}

GOOGLE_NEWS_FALLBACKS = [
    ("Google News AI", "https://news.google.com/rss/search?q=AI+OR+artificial+intelligence&hl=en-US&gl=US&ceid=US:en", "ai"),
    ("Google News Hardware", "https://news.google.com/rss/search?q=semiconductors+OR+chips&hl=en-US&gl=US&ceid=US:en", "hardware"),
    ("Google News Cybersecurity", "https://news.google.com/rss/search?q=cybersecurity&hl=en-US&gl=US&ceid=US:en", "cyber"),
    ("Google News Technology", "https://news.google.com/rss/search?q=technology+OR+robotics+OR+quantum&hl=en-US&gl=US&ceid=US:en", "technologies"),
]


_RSS_REQUESTED = False


def fetch_rss_feed(feed_url, source_name, category_slug):
    global _RSS_REQUESTED
    if _RSS_REQUESTED:
        time.sleep(random.uniform(1.0, 2.0))
    _RSS_REQUESTED = True
    for attempt in range(2):
        try:
            request = urllib.request.Request(feed_url, headers=RSS_HEADERS)
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read()
            root = ET.fromstring(payload)
            entries = root.findall("./channel/item")
            if not entries:
                entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            parsed = []
            for entry in entries[:12]:
                title = entry.findtext("title") or entry.findtext("{http://www.w3.org/2005/Atom}title")
                link_element = entry.find("link")
                if link_element is None:
                    link_element = entry.find("{http://www.w3.org/2005/Atom}link")
                link = (
                    link_element.attrib.get("href", "")
                    if link_element is not None and link_element.attrib
                    else (link_element.text if link_element is not None else "")
                )
                pub_date = (
                    entry.findtext("pubDate")
                    or entry.findtext("published")
                    or entry.findtext("updated")
                    or entry.findtext("{http://www.w3.org/2005/Atom}published")
                    or entry.findtext("{http://www.w3.org/2005/Atom}updated")
                    or ""
                )
                if title and link:
                    parsed.append({
                        "title": title.strip(), "link": link.strip(),
                        "date": pub_date, "source": source_name,
                        "category_hint": category_slug,
                    })
            print(f"RSS OK: {feed_url} — {len(parsed)} записа.")
            return parsed
        except urllib.error.HTTPError as error:
            print(f"RSS грешка {error.code} за URL {feed_url}: {error}")
            if error.code in (429, 503) and attempt == 0:
                time.sleep(random.uniform(1.0, 2.0))
                continue
            return []
        except Exception as error:
            print(f"RSS грешка за URL {feed_url}: {type(error).__name__}: {error}")
            return []
    return []


def collect_category_news(history):
    blocked = {item.get("category_slug") for item in (history or [])[:3] if item.get("category_slug")}
    rotation = [slug for _, slug in CATEGORY_ROTATION]
    latest_slug = (history or [{}])[0].get("category_slug")
    start = (rotation.index(latest_slug) + 1) % len(rotation) if latest_slug in rotation else 0
    ordered = rotation[start:] + rotation[:start]
    eligible = [slug for slug in ordered if slug not in blocked]

    for category_slug in eligible:
        category_items = []
        feeds = CATEGORY_FEEDS.get(category_slug, [])
        print(f"RSS категория: {category_slug}; източници: {len(feeds)}.")
        for source_name, feed_url in feeds:
            category_items.extend(fetch_rss_feed(feed_url, source_name, category_slug))
        accepted = filter_recent_topics(category_items, history)
        if accepted:
            print(f"Избрана RSS категория: {category_slug}; допустими теми: {len(accepted)}.")
            return accepted
        print(f"Няма подходящи достъпни теми за {category_slug}; преминавам към следващата категория.")

    print("Всички директни RSS категории са изчерпани. Google News е последна резерва.")
    fallback_items = []
    for source_name, feed_url, category_slug in GOOGLE_NEWS_FALLBACKS:
        if category_slug in blocked:
            continue
        fallback_items.extend(fetch_rss_feed(feed_url, source_name, category_slug))
    return filter_recent_topics(fallback_items, history)


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
            <a href="/articles.html?category=quantum" class="nav-link">Квантови технологии</a>
            <a href="/articles.html?category=future" class="nav-link">Бъдещи технологии</a>
            <a href="/articles.html?category=cyber" class="nav-link">Киберсигурност</a>
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

def extract_image_query(response_text, article_html=""):
    lines = (response_text or "").lstrip("\ufeff").splitlines()
    image_query = ""
    if lines:
        match = re.match(r"^\s*IMAGE_QUERY\s*:\s*(.*?)\s*$", lines[0], re.I)
        if match:
            image_query = re.sub(r"[^A-Za-z ]", " ", match.group(1))
            image_query = re.sub(r"\s+", " ", image_query).strip()
            lines = lines[1:]
    html = "\n".join(lines).strip()
    fence = chr(96) * 3
    html = re.sub(r"^\s*" + re.escape(fence) + r"(?:html)?\s*", "", html, flags=re.I)
    html = re.sub(r"\s*" + re.escape(fence) + r"\s*$", "", html)
    if not 2 <= len(image_query.split()) <= 4:
        title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, re.I | re.S)
        title = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip() if title_match else ""
        _, slug = infer_category(title, html)
        image_query = {
            "quantum": "quantum computer laboratory",
            "cyber": "cybersecurity server room",
            "hardware": "semiconductor microchip wafer",
            "future": "humanoid robotics laboratory",
            "ai": "artificial intelligence data center",
            "technologies": "technology research laboratory",
        }.get(slug, "technology research laboratory")
    return image_query, html


def _html_text(value):
    import html as html_module
    return re.sub(r"\s+", " ", html_module.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def build_faq_json_ld(article_html):
    heading = re.search(
        r"<h[1-6]\b[^>]*>\s*Често\s+задаван[иия]+\s+въпроси\s*</h[1-6]>",
        article_html, re.I
    )
    if not heading:
        return None
    tail = article_html[heading.end():]
    next_h2 = re.search(r"<h2\b", tail, re.I)
    faq_html = tail[:next_h2.start()] if next_h2 else tail
    pairs = re.findall(
        r"<h3\b[^>]*>(.*?)</h3>\s*<p\b[^>]*>([\s\S]*?)</p>",
        faq_html, re.I
    )
    if len(pairs) != 3:
        return None
    entities = []
    for q_html, a_html in pairs:
        question, answer = _html_text(q_html), _html_text(a_html)
        if not question or not answer:
            return None
        entities.append({
            "@type": "Question",
            "name": question,
            "acceptedAnswer": {"@type": "Answer", "text": answer},
        })
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }


def validate_article(article_html):
    reasons = []
    if not article_html or not article_html.strip():
        return False, ["празен HTML отговор"], 0, 0, None

    plain = _html_text(article_html)
    words = len(re.findall(r"(?u)\b[\wА-Яа-яЁё]+\b", plain))
    h1 = len(re.findall(r"<h1\b", article_html, re.I))
    h2 = len(re.findall(r"<h2\b", article_html, re.I))
    lower = plain.lower()

    if h1 != 1:
        reasons.append(f"h1={h1}, изисква се точно 1")
    if not 3 <= h2 <= 8:
        reasons.append(f"H2={h2}, допустими са 3–8")
    if not 650 <= words <= 1800:
        reasons.append(f"думи={words}, допустими са 650–1800")
    if not re.search(r'<p\b[^>]*class=["\']article-intro["\']', article_html, re.I):
        reasons.append('липсва уводен абзац с class="article-intro"')
    if not re.search(r"<p\b", article_html, re.I):
        reasons.append("липсват абзаци <p>")
    for phrase, label in [
        ("ключови изводи", "липсва секция „Ключови изводи“"),
        ("какво означава това на практика", "липсва секция „Какво означава това на практика“"),
        ("често задавани въпроси", "липсва секция „Често задавани въпроси“"),
    ]:
        if phrase not in lower:
            reasons.append(label)
    cliches = [
        "на фона на засилената глобална конкуренция",
        "динамиката в технологичната индустрия",
        "в съвременния дигитален свят",
        "в днешния динамичен свят",
        "революционизира", "нова ера", "играта се променя",
        "това променя всичко",
    ]
    found = [phrase for phrase in cliches if phrase in lower]
    if found:
        reasons.append("клишета: " + "; ".join(found))

    faq = build_faq_json_ld(article_html)
    faq_count = len(faq.get("mainEntity", [])) if faq else 0
    if faq_count != 3:
        reasons.append(
            f"FAQ въпроси и отговори={faq_count}, изискват се точно 3 двойки H3/P"
        )
    return not reasons, reasons, words, h2, faq


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
Пиши на естествен и точен български език. Забранени са клишетата „На фона на засилената глобална конкуренция“, „Динамиката в технологичната индустрия“, „В съвременния дигитален свят“, „в днешния динамичен свят“, „революционизира“, „нова ера“, „играта се променя“ и „това променя всичко“. Започни с конкретен проверен факт, число, техническа промяна или практическа ситуация.
Целта е 950–1200 думи. Валидаторът допуска 650–1800 думи. Не повтаряй една теза и не добавяй празни абзаци.
Избери тема само от подадения RSS списък. Не сменяй темата с друга новина. Списъкът вече е филтриран срещу последните 20 статии и последните три категории.
Задължителна структура: конкретно въведение; 3–8 логични H2 секции; съдържателни абзаци с факти, обяснения и примери; „Ключови изводи“; „Какво означава това на практика“; FAQ „Често задавани въпроси“ с точно 3 въпроса като H3 и отговор за всеки в следващия P.
Обясни механизма, контекста, предимствата, недостатъците, разходите и ограниченията, когато са приложими. Разграничавай факт, анализ и прогноза. Не измисляй тестове, личен опит, цитати, експерти или числа.
</writing>
<current_rss>
{RSS_CONTEXT}
</current_rss>
<format>
Първият ред трябва да е IMAGE_QUERY: последван от 2–4 конкретни английски думи за подходяща хоризонтална снимка.
На следващия ред започни директно с чист HTML. Не връщай JSON, Markdown или code fences. HTML започва с един H1 и един P с class="article-intro", после 3–8 смислени H2 секции. Включи изискваните секции и точно три FAQ двойки H3/P. Не генерирай script или JSON-LD. Не включвай изображение в HTML.
</format>
Напиши материала като задълбочен редакционен анализ, а не като преразказ на новината.
"""

    history = load_history()
    rss_items = collect_category_news(history)

    if not rss_items:
        raise RuntimeError("Не бяха получени актуални RSS новини. Няма да се публикува.")

    rss_items = filter_recent_topics(rss_items, history)
    if not rss_items:
        raise RuntimeError(
            "Всички RSS теми са повторения или попадат в последните три категории. "
            "Няма да се публикува дублираща статия."
        )

    rss_context = "\n".join(
        f'- {item["title"]} | {item["source"]} | {item["date"]} | {item["link"]}'
        for item in rss_items[:1]
    )
    prompt = prompt.replace("{RSS_CONTEXT}", rss_context)

    article_body = None
    image_query = "technology research laboratory"
    retry_feedback = None
    models = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]

    for model_name in models:
        editorial_attempts = 0
        transient_retries = 0
        transient_delays = [15, 30, 45, 60]

        while editorial_attempts < 3:
            try:
                request_prompt = prompt
                if retry_feedback:
                    request_prompt += f"""

РЕДАКЦИОННА КОРЕКЦИЯ: Предишният материал не покрива тези критерии: {retry_feedback}.
Поправи всяка посочена причина. Запази проверимите факти, без повторения и без измисляне.
Върни целия материал отначало със същия формат IMAGE_QUERY на първия ред и чист HTML след него.
"""

                response = client.models.generate_content(
                    model=model_name,
                    contents=request_prompt,
                    config=types.GenerateContentConfig(max_output_tokens=8192),
                )
                if not response or not response.text:
                    editorial_attempts += 1
                    retry_feedback = "Gemini върна празен отговор"
                    print(f"Празен отговор от {model_name}, редакционен опит {editorial_attempts}/3.")
                    continue

                image_query, cleaned = extract_image_query(response.text)
                valid, reasons, word_count, h2_count, faq_schema = validate_article(cleaned)
                editorial_attempts += 1

                if valid:
                    article_body = cleaned
                    print(f"Получена статия: {word_count} думи, {h2_count} H2 секции чрез {model_name}.")
                    break

                retry_feedback = "; ".join(reasons)
                print(
                    f"Отхвърлена статия от {model_name}: {word_count} думи, "
                    f"{h2_count} H2. Причина: {retry_feedback}."
                )

            except Exception as error:
                error_text = f"{type(error).__name__}: {error}"
                upper_error = error_text.upper()
                transient = any(token in upper_error for token in (
                    "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                    "TIMEOUT", "DEADLINE", "CONNECTION", "NETWORK",
                    "500", "502", "504", "INTERNAL SERVER ERROR",
                ))
                if transient:
                    if transient_retries < len(transient_delays):
                        delay = transient_delays[transient_retries]
                        transient_retries += 1
                        print(
                            f"Временна API/мрежова грешка при {model_name}: {error_text}. "
                            f"Повторение {transient_retries}/4 след {delay} секунди."
                        )
                        time.sleep(delay)
                        continue
                    print(
                        f"Изчерпани са 4 временни повторения за {model_name}. "
                        "Преминавам към резервния модел."
                    )
                    break

                editorial_attempts += 1
                retry_feedback = f"грешка при заявката или парсването: {error_text}"
                print(
                    f"Грешка с {model_name} (редакционен опит "
                    f"{editorial_attempts}/3): {error_text}"
                )

        if article_body:
            break
        print(f"Моделът {model_name} изчерпа редакционните си опити. Преминавам към резервния модел.")

    if not article_body:
        raise RuntimeError(
            "Gemini не върна статия, която покрива редакционните критерии. "
            "Няма да се публикува непроверен fallback материал."
        )

    faq_schema = build_faq_json_ld(article_body)
    if faq_schema:
        article_body += (
            '<script type="application/ld+json">'
            + json.dumps(faq_schema, ensure_ascii=False)
            + "</script>"
        )

    source_links = []
    for candidate in rss_items:
        link_pattern = r"""href=["']""" + re.escape(candidate["link"]) + r"""["']"""
        if re.search(link_pattern, article_body, re.I):
            if candidate["link"] not in [item["url"] for item in source_links]:
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

    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", article_body, re.I | re.S)
    title_text = _html_text(title_match.group(1)) if title_match else "Технологична новина"
    article_words = len(re.findall(r"(?u)\b[\wА-Яа-яЁё]+\b", _html_text(article_body)))
    reading_minutes = max(1, round(article_words / 200))
    published_date = __import__("datetime").date.today().strftime("%d.%m.%Y")
    byline = f'<p class="meta">Редакция TechPulse · {published_date} · {reading_minutes} мин. четене</p>'
    article_body = re.sub(r"(</h1>)", r"\1" + byline, article_body, count=1, flags=re.I)

    category_label, category_slug = infer_category(title_text, article_body, history)
    if category_slug in {item.get("category_slug") for item in history[:3]}:
        raise RuntimeError(
            f"Статията попада в наскоро публикувана категория: {category_label}. "
            "Публикуването е спряно, за да не се наруши ротацията."
        )
    if any(topic_titles_overlap(title_text, item.get("title", "")) for item in history[:20]):
        raise RuntimeError(
            "Заглавието повтаря тема от последните 20 статии. Публикуването е спряно."
        )
    main_image_url, fallback_img, image_source = choose_article_images(
        category_slug, history, image_query
    )

    sidebar_items = history[:3] if len(history) >= 3 else DEFAULT_ARTICLES
    sidebar_urls = {item.get("url") for item in sidebar_items}
    related_items = [
        item for item in history
        if item.get("category_slug") == category_slug
        and item.get("url") not in sidebar_urls
    ][:3]
    related_links = "".join(
        '<li><a href="' + item.get("url", "#") + '">'
        + item.get("title", "Още по темата") + "</a></li>"
        for item in related_items
    )
    editorial = (
        '<section class="author-box"><h2>Редакция и авторство</h2>'
        '<p><strong>Редакция TechPulse</strong></p>'
        '<p>Материалът е подготвен от редакционния екип на TechPulse. '
        'Фактите се разграничават от анализа, а източниците дават възможност '
        'за самостоятелна проверка.</p></section>'
    )
    related = (
        '<section class="related-articles"><h2>Свързани статии</h2><ul>'
        + related_links + "</ul></section>"
    ) if related_links else ""
    article_body += editorial + related
    full_html = build_full_page(
        title_text, main_image_url, fallback_img, article_body, sidebar_items
    )

    article_slug = slugify(title_text)
    article_file_path = os.path.join(ARTICLES_DIR, f"{article_slug}.html")
    article_url = f"/articles/{article_slug}.html"

    if os.path.exists(article_file_path):
        raise RuntimeError(f"Статията вече съществува: {article_file_path}")

    with open(article_file_path, "w", encoding="utf-8") as article_file:
        article_file.write(full_html)

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
        "source_title": rss_items[0]["title"] if rss_items else "",
        "source_url": rss_items[0]["link"] if rss_items else "",
        "sources": source_links[:6],
    })
    save_history(history[:200])
    print(f"Публикационният пакет е готов: {article_url}")


if __name__ == "__main__":
    generate_news()
