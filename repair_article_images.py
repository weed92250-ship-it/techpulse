import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path("public")
HISTORY_FILE = ROOT / "articles.json"
ARTICLES_DIR = ROOT / "articles"
INDEX_FILE = ROOT / "index.html"
LIST_FILE = ROOT / "articles.html"

# Same curated, topic-grouped landscape pool as the publisher. Every candidate
# is fetched and must return HTTP 200 with an image content type before use.
POOLS = {
 "quantum": ["photo-1535378273068-9bb67d5beacd","photo-1635070041078-e363dbe005cb","photo-1451187580459-43490279c0fa","photo-1523961131990-5ea7c61b2107","photo-1535223289827-42f1e9919769","photo-1535378620166-273708d44e4c","photo-1618005182384-a83a8bd57fbe","photo-1527443224154-c4a3942d3acf","photo-1581091226825-a6a2a5aee158","photo-1581092160562-40aa08e78837""https://cdn.pixabay.com/photo/2018/05/08/08/44/artificial-intelligence-3382507_1280.jpg","https://cdn.pixabay.com/photo/2016/11/22/19/20/technology-1845385_1280.jpg","https://cdn.pixabay.com/photo/2017/06/13/09/36/technology-2396808_1280.jpg","https://cdn.pixabay.com/photo/2016/11/29/07/27/computer-1869236_1280.jpg",],
 "cyber": ["photo-1526374965328-7f61d4dc18c5","photo-1550751827-4bd374c3f58b","photo-1563013544-824ae1b704d3","photo-1510511459019-5dda7724fd87","photo-1558494949-ef010cbdcc31","photo-1550439062-609e1531270e","photo-1516321318423-f06f85e504b3","photo-1581092795360-fd1ca04f0952","photo-1515879218367-8466d910aaa4","photo-1531297484001-80022131f5a1""https://cdn.pixabay.com/photo/2016/11/19/14/00/code-1839406_1280.jpg","https://cdn.pixabay.com/photo/2016/11/30/20/58/programming-1873854_1280.jpg","https://cdn.pixabay.com/photo/2016/12/28/09/36/web-1935737_1280.jpg","https://cdn.pixabay.com/photo/2017/01/17/14/40/technology-1986105_1280.jpg",],
 "hardware": ["photo-1518770660439-4636190af475","photo-1591799264318-7e6ef8ddb7ea","photo-1587202372775-e229f172b9d7","photo-1591405351990-4726e331f141","photo-1550745165-9bc0b252726f","photo-1581092580497-e0d23cbdf1dc","photo-1581092335878-2d9ff86ca2bf","photo-1581092921461-eab62e97a780","photo-1597733336794-12d05021d510","photo-1527443224154-c4a3942d3acf""https://cdn.pixabay.com/photo/2017/08/10/03/47/technology-2615761_1280.jpg","https://cdn.pixabay.com/photo/2016/10/29/09/06/computer-1784430_1280.jpg","https://cdn.pixabay.com/photo/2017/03/20/17/07/technology-2159136_1280.jpg","https://cdn.pixabay.com/photo/2016/11/14/08/18/technology-1824969_1280.jpg",],
 "future": ["photo-1485827404703-89b55fcc595e","photo-1535378620166-273708d44e4c","photo-1521737711867-e3b97375f902","photo-1531482615713-2afd69097998","photo-1522071820081-009f0129c71c","photo-1531297484001-80022131f5a1","photo-1581091226825-a6a2a5aee158","photo-1581092160562-40aa08e78837","photo-1550439062-609e1531270e","photo-1535223289827-42f1e9919769""https://cdn.pixabay.com/photo/2017/03/19/20/19/robot-2159352_1280.jpg","https://cdn.pixabay.com/photo/2017/09/06/19/38/technology-2729801_1280.jpg","https://cdn.pixabay.com/photo/2017/08/07/14/14/technology-2608577_1280.jpg",],
 "ai": ["photo-1677442136019-21780ecad995","photo-1620712943543-bcc4688e7485","photo-1676299081847-824916de030a","photo-1498050108023-c5249f4df085","photo-1519389950473-47ba0277781c","photo-1504384308090-c894fdcc538d","photo-1515879218367-8466d910aaa4","photo-1531297484001-80022131f5a1","photo-1516321318423-f06f85e504b3","photo-1521737711867-e3b97375f902""https://cdn.pixabay.com/photo/2019/04/11/11/52/artificial-intelligence-4118111_1280.jpg","https://cdn.pixabay.com/photo/2018/04/23/14/38/technology-3348071_1280.jpg","https://cdn.pixabay.com/photo/2017/01/20/00/30/laptop-1997184_1280.jpg",],
 "technologies": ["photo-1504384308090-c894fdcc538d","photo-1498050108023-c5249f4df085","photo-1519389950473-47ba0277781c","photo-1522071820081-009f0129c71c","photo-1516321318423-f06f85e504b3","photo-1531297484001-80022131f5a1","photo-1515879218367-8466d910aaa4","photo-1550439062-609e1531270e","photo-1550745165-9bc0b252726f","photo-1531482615713-2afd69097998""https://cdn.pixabay.com/photo/2017/07/31/11/22/people-2557396_1280.jpg","https://cdn.pixabay.com/photo/2016/11/29/06/15/plans-1867745_1280.jpg","https://cdn.pixabay.com/photo/2016/03/09/09/30/desk-1245954_1280.jpg",],
}

def image_url(photo_id):
    if photo_id.startswith("https://"):
        return photo_id
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1200&h=675&q=82"

def is_live(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TechPulseImageRepair/1.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.status == 200 and response.headers.get("Content-Type", "").lower().startswith("image/")
    except Exception as exc:
        print(f"Непотвърдена снимка: {url}: {exc}")
        return False

def replace_meta(content, name, url, prop=False):
    attr = "property" if prop else "name"
    pattern = rf'<meta\s+{attr}=["\']{re.escape(name)}["\']\s+content=["\'][^"\']*["\']\s*/?>'
    tag = f'<meta {attr}="{name}" content="{html.escape(url, quote=True)}">'
    if re.search(pattern, content, re.I):
        return re.sub(pattern, tag, content, count=1, flags=re.I)
    return re.sub(r"</head>", tag + "</head>", content, count=1, flags=re.I)

def main():
    history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    recent = history[:30]
    blocked = {x.get("img") for x in history[:50] if isinstance(x, dict)}
    pool = []
    for group in POOLS.values():
        pool.extend(image_url(photo) for photo in group)
    candidates = list(dict.fromkeys(pool))
    chosen = []
    for candidate in candidates:
        if candidate in blocked or candidate in chosen:
            continue
        if is_live(candidate):
            chosen.append(candidate)
            if len(chosen) == len(recent):
                break
    if len(chosen) < len(recent):
        raise RuntimeError(f"Намерени са само {len(chosen)} проверени уникални снимки за {len(recent)} статии. Не записвам частичен ремонт.")

    updates = {}
    for item, url in zip(recent, chosen):
        item["img"] = url
        item["image_source"] = "unsplash_fallback"
        updates[item["url"]] = url

    for article_url, url in updates.items():
        article_path = ARTICLES_DIR / Path(article_url).name
        if not article_path.exists():
            raise FileNotFoundError(f"Липсва HTML файлът за {article_url}")
        content = article_path.read_text(encoding="utf-8")
        content = replace_meta(content, "og:image", url, prop=True)
        content = replace_meta(content, "twitter:image", url)
        img_pattern = r'(<img\b[^>]*?\bsrc=["\'])[^"\']+(["\'])'
        content, count = re.subn(img_pattern, lambda m: m.group(1) + url + m.group(2), content, count=1, flags=re.I)
        if not count:
            raise RuntimeError(f"Не е намерен основен img елемент в {article_path}")
        article_path.write_text(content, encoding="utf-8")

    # Update homepage article cards by matching each article href, not by global URL replacement.
    page = INDEX_FILE.read_text(encoding="utf-8")
    def update_card(match):
        block = match.group(0)
        for article_url, url in updates.items():
            if article_url in block:
                return re.sub(r'(<img\b[^>]*?\bsrc=["\'])[^"\']+(["\'])',
                              lambda m: m.group(1) + url + m.group(2), block, count=1, flags=re.I)
        return block
    page = re.sub(r'<article\b[\s\S]*?</article>', update_card, page, flags=re.I)
    if recent:
        page = replace_meta(page, "og:image", recent[0]["img"], prop=True)
    INDEX_FILE.write_text(page, encoding="utf-8")

    # The archive previously had text-only cards. Add a small landscape thumbnail
    # to each of the repaired recent entries so its image selection is visible there too.
    page = LIST_FILE.read_text(encoding="utf-8")
    for item in recent:
        article_url, url = item["url"], item["img"]
        href = re.escape(article_url)
        pattern = re.compile(rf'(<a\b[^>]*\bhref=["\']{href}["\'][^>]*>)', re.I)
        thumb = f'<img class="article-thumb" loading="lazy" width="320" height="180" src="{html.escape(url, quote=True)}" alt="{html.escape(item.get("title", "TechPulse"), quote=True)}">'
        if pattern.search(page):
            page = pattern.sub(lambda m: m.group(1) + thumb, page, count=1)
    if ".article-thumb" not in page:
        page = page.replace("</style>", ".article-thumb{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:6px;margin:0 0 12px}</style>", 1)
    LIST_FILE.write_text(page, encoding="utf-8")
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Обновени са снимките на {len(recent)} статии, HTML метаданните, началната страница и архивът.")

if __name__ == "__main__":
    main()
