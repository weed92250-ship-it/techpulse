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
        "https://images.unsplash.com/photo-1535378273068-9bb67d5beacd?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop"
    ],
    "cyber": [
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1510511459019-5dda7724fd87?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&auto=format&fit=crop"
    ],
    "hardware": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1591799264318-7e6ef8ddb7ea?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1591405351990-4726e331f141?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop"
    ],
    "future": [
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1535223289827-42f1e9919769?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1523961131990-5ea7c61b2107?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1535378620166-273708d44e4c?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop"
    ],
    "ai": [
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1676299081847-824916de030a?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop"
    ],
    "technologies": [
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=800&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop"
    ]
}

def choose_article_images(category_slug, history):
    recent_images = {
        item.get("img") for item in history[:5]
        if isinstance(item, dict) and isinstance(item.get("img"), str)
    }

    category_images = IMAGE_POOLS.get(category_slug, [])
    available_category = [url for url in category_images if url not in recent_images]
    available_all = list(dict.fromkeys(
        url for urls in IMAGE_POOLS.values() for url in urls
        if url not in recent_images
    ))

    if not available_all:
        raise RuntimeError("Няма свободна снимка извън последните 5 публикации.")

    main_image = random.choice(available_category or available_all)
    fallback_candidates = [url for url in available_all if url != main_image]
    fallback_image = random.choice(fallback_candidates) if fallback_candidates else main_image
    return main_image, fallback_image


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

COOKIE_CONSENT_HTML = r"""<style id="tp-cookie-style">
#tp-cookie-banner{position:fixed;z-index:99999;left:16px;right:16px;bottom:16px;max-width:900px;margin:auto;padding:18px 20px;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,.38);font:14px/1.55 system-ui,sans-serif}
#tp-cookie-banner[hidden]{display:none}#tp-cookie-banner p{margin:0 0 12px}#tp-cookie-banner a{color:#7dd3fc;text-decoration:underline}
#tp-cookie-banner .tp-cookie-actions{display:flex;flex-wrap:wrap;gap:10px}
#tp-cookie-banner button{border:1px solid #475569;border-radius:7px;padding:9px 14px;font-weight:650;cursor:pointer}
#tp-cookie-accept{background:#0284c7;color:white;border-color:#0284c7}#tp-cookie-reject{background:#1e293b;color:#e2e8f0}
.site-footer{margin-top:36px;padding:22px 0;border-top:1px solid #1e293b;text-align:center;color:#64748b;font-size:13px}
.site-footer .footer-links{display:flex;flex-wrap:wrap;justify-content:center;gap:10px 18px}
.site-footer .footer-links a{color:#94a3b8;text-decoration:none;margin:0}
.site-footer .footer-links a:hover{color:#38bdf8}
@media(max-width:600px){#tp-cookie-banner{left:8px;right:8px;bottom:8px;padding:14px}.site-footer .footer-links{gap:10px 14px}}
</style>
<section id="tp-cookie-banner" role="dialog" aria-modal="false" aria-labelledby="tp-cookie-title" aria-describedby="tp-cookie-copy" hidden>
<strong id="tp-cookie-title">Настройки за бисквитки</strong>
<p id="tp-cookie-copy">TechPulse използва необходими бисквитки и, само след твое съгласие, рекламни бисквитки на Google AdSense. Рекламните технологии могат да обработват информация за устройството и посещенията ти, включително за персонализиране на реклами. Прочети <a href="/privacy.html">Политиката за поверителност и бисквитки</a> и <a href="https://business.safety.google/privacy/" target="_blank" rel="noopener noreferrer">как Google използва данните</a>.</p>
<div class="tp-cookie-actions"><button type="button" id="tp-cookie-reject">Отказвам рекламните бисквитки</button><button type="button" id="tp-cookie-accept">Приемам рекламните бисквитки</button></div>
</section>
<script>
(function(){
 const KEY="techpulse_cookie_choice_v1";
 const banner=document.getElementById("tp-cookie-banner");
 if(!banner)return;
 let choice=null;try{choice=localStorage.getItem(KEY)}catch(e){}
 function loadAds(){
  if(document.querySelector("script[data-tp-ads-loaded]"))return;
  const s=document.createElement("script");s.async=true;
  s.src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8109991761364968";
  s.crossOrigin="anonymous";s.setAttribute("data-tp-ads-loaded","true");document.head.appendChild(s);
 }
 function save(value){try{localStorage.setItem(KEY,value)}catch(e){}location.reload()}
 if(choice==="accepted")loadAds();else if(choice!=="rejected")banner.hidden=false;
 document.getElementById("tp-cookie-accept").addEventListener("click",()=>save("accepted"));
 document.getElementById("tp-cookie-reject").addEventListener("click",()=>save("rejected"));
 const settings=document.getElementById("tp-cookie-settings");
 if(settings)settings.addEventListener("click",e=>{e.preventDefault();banner.hidden=false});
})();
</script>"""

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
    <title>{title} — TechPulse</title>
    <style>{CSS_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header"><a href="/" class="logo">⚡ TechPulse</a></div>
        <div class="static-card">{content}</div>
        <footer>
            <div class="footer-links">
                <a href="/">Начало</a> | <a href="/articles.html">Статии</a> | <a href="/about.html">За нас</a> | <a href="/contacts.html">Контакти</a> | <a href="/privacy.html">Поверителност и бисквитки</a> | <a href="/terms.html">Общи условия</a> | <a href="#" id="tp-cookie-settings">Настройки за бисквитки</a>
            </div>
        </footer>
        {COOKIE_CONSENT_HTML}
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
<a href="/about.html">За нас</a>
<a href="/contacts.html">Контакти</a>
<a href="/privacy.html">Поверителност и бисквитки</a>
<a href="/terms.html">Общи условия</a>
<a href="#" id="tp-cookie-settings">Настройки за бисквитки</a>
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
            updated, count = re.subn(
                r"<footer\b[^>]*>[\s\S]*?</footer>",
                footer,
                content,
                count=1,
                flags=re.IGNORECASE,
            )
            if count and updated != content:
                with open(filepath, "w", encoding="utf-8") as article_file:
                    article_file.write(updated)
                print(f"Обновен футър: {filename}")
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
                <a href="/about.html">За нас</a>
                <a href="/contacts.html">Контакти</a>
                <a href="/privacy.html">Поверителност и бисквитки</a>
                <a href="/terms.html">Общи условия</a>
                <a href="#" id="tp-cookie-settings">Настройки за бисквитки</a>
            </nav>
            <p>© TechPulse. Всички права запазени.</p>
        </footer>
        {COOKIE_CONSENT_HTML}
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
Пиши на естествен български език, като редактор, който обяснява сложна тема на интелигентен читател, а не като генератор на SEO текст.
Целевата дължина е 1400–2000 думи. Задължително напиши поне 1400 думи; не приключвай след кратко резюме. Материалът трябва да е пълноценен, а не изкуствено удължен.
Развий темата последователно: започни с конкретния факт или новина, дай необходимия контекст, обясни как работи технологията или какво точно се е променило, разгледай практическите последици и ограниченията и завърши с трезв извод какво означава това в по-широк контекст.
Използвай конкретни примери, когато източниците ги позволяват.

Абзаците трябва да са свързани и достатъчно развити. Не превръщай всяка мисъл в отделен кратък абзац.
Не прекъсвай разказа с множество подзаглавия. Използвай най-много 4 <h3> подзаглавия и само ако действително помагат на читателя да се ориентира. За материал, който се чете по-добре като непрекъснат разказ, можеш да използваш само 1–2 или изобщо да няма <h3>.
Не използвай списъци, освен когато информацията реално е по-ясна като списък.
Не повтаряй една и съща идея с различни думи.

Избягвай шаблонни и рекламни AI формулировки като „в днешния динамичен свят“, „революционизира“, „нова ера“, „играта се променя“, „не е просто X, а Y“, „това може да промени всичко“ и подобни фрази, освен ако са част от пряко цитирано твърдение.
Не използвай първо лице. Не измисляй лично наблюдение, интервю или разговор с експерт.
Не заявявай, че текстът е написан от човек или от AI. Просто пиши естествено и професионално.

Важно: фактите, анализът и предположенията трябва да се различават. Не представяй бъдещи сценарии като сигурни резултати.
</writing>

<current_rss>
{RSS_CONTEXT}
</current_rss>

<format>
Върни само HTML, без Markdown и без code fences.
Първият ред трябва да е <h2>Заглавие</h2>.
След него постави един въвеждащ <p class="article-intro">...</p>.
След това използвай нормални <p> абзаци и най-много 4 <h3> подзаглавия при реална нужда.
Не добавяй секция „Източници“ — източниците ще бъдат добавени автоматично от системата.
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
    short_draft = None
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
                if short_draft:
                    request_prompt = f"""
Предишният отговор беше прекалено кратък. Разшири го до 1400–2000 думи, като запазиш проверимите факти и естествения български стил.
Не повтаряй вече казаното. Добави технически контекст, конкретни практически последици, ограничения и нюанси. Не измисляй факти.
Върни целия завършен материал отначало, само като HTML, със заглавие <h2>, един <p class="article-intro">, нормални <p> абзаци и максимум 4 <h3>.
Чернова за разширяване:
{short_draft}
"""
                response = client.models.generate_content(
                    model=model_name,
                    contents=request_prompt,
                )
                if not response or not response.text:
                    continue

                cleaned = response.text.replace(chr(96) * 3 + "html", "").replace(chr(96) * 3, "").strip()
                plain_text = re.sub(r"<[^>]+>", " ", cleaned)
                plain_text = re.sub(r"\s+", " ", plain_text).strip()
                word_count = len(re.findall(r"(?u)\b[\wА-Яа-яЁё]+\b", plain_text))
                h2_count = len(re.findall(r"<h2\b", cleaned, flags=re.I))
                h3_count = len(re.findall(r"<h3\b", cleaned, flags=re.I))
                short_paragraphs = len(re.findall(r"<p\b[^>]*>[^<]{1,120}</p>", cleaned, flags=re.I))

                valid_structure = (
                    h2_count == 1
                    and '<p class="article-intro">' in cleaned
                    and "<p>" in cleaned
                    and word_count >= 1300
                    and word_count <= 2600
                    and h3_count <= 4
                    and short_paragraphs <= 8
                )

                if valid_structure:
                    article_body = cleaned
                    print(f"Получена статия: {word_count} думи, {h3_count} подзаглавия чрез {model_name}.")
                    break

                reasons = []
                if h2_count != 1:
                    reasons.append(f"h2={h2_count} (трябва точно 1)")
                if '<p class="article-intro">' not in cleaned:
                    reasons.append("липсва article-intro")
                if "<p>" not in cleaned:
                    reasons.append("липсват стандартни абзаци")
                if word_count < 1300 or word_count > 2600:
                    reasons.append(f"думи={word_count} (допустими 1300–2600)")
                if h3_count > 4:
                    reasons.append(f"h3={h3_count} (максимум 4)")
                if short_paragraphs > 8:
                    reasons.append(f"кратки абзаци={short_paragraphs} (максимум 8)")
                print(f"Отхвърлена статия от {model_name}: {word_count} думи, {h3_count} подзаглавия. Причина: {', '.join(reasons) or 'непозната структурна грешка'}.")
                if 250 <= word_count < 1300 and h2_count == 1 and '<p class="article-intro">' in cleaned:
                    short_draft = cleaned
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

    title_match = re.search(r"<h2>(.*?)</h2>", article_body, re.S)
    title_text = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else "Технологична новина"

    history = load_history()
    category_label, category_slug = infer_category(title_text, article_body, history)
    main_image_url, fallback_img = choose_article_images(category_slug, history)

    sidebar_items = history[:3] if len(history) >= 3 else DEFAULT_ARTICLES
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
        "sources": source_links[:6]
    })
    save_history(history[:200])
    print(f"Публикационният пакет е готов: {article_url}")


if __name__ == "__main__":
    generate_news()
