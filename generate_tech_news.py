import os
import time
import random
import urllib.parse
import re
import json
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise ValueError("ГРЕШКА: Липсва GEMINI_API_KEY в Secrets!")

client = genai.Client(api_key=api_key)

PUBLIC_DIR = "public"
ARTICLES_DIR = os.path.join(PUBLIC_DIR, "articles")
HISTORY_FILE = os.path.join(PUBLIC_DIR, "articles.json")

os.makedirs(ARTICLES_DIR, exist_ok=True)

DEFAULT_ARTICLES = [
    {
        "title": "Meta представи малко носимо устройство за асистента си с изкуствен интелект",
        "time": "2026-09-24",
        "category": "AI",
        "url": "#",
        "img": "https://images.unsplash.com/photo-1535378273068-9bb67d5beacd?w=400&auto=format&fit=crop"
    },
    {
        "title": "Qualcomm представи нови чипове за смартфони с фокус върху изкуствения интелект",
        "time": "2026-09-23",
        "category": "Мобилни",
        "url": "#",
        "img": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&auto=format&fit=crop"
    },
    {
        "title": "Snorkel AI набра 350 милиона долара за разширяване на платформата си",
        "time": "2026-09-23",
        "category": "AI",
        "url": "#",
        "img": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&auto=format&fit=crop"
    }
]

CSS_STYLES = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-color: #070c18;
        color: #94a3b8;
        margin: 0;
        padding: 20px;
        line-height: 1.6;
    }
    .container { max-width: 1180px; margin: 0 auto; }
    .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 15px; margin-bottom: 15px; }
    .logo { font-size: 24px; font-weight: 800; color: #38bdf8; text-decoration: none; display: flex; align-items: center; gap: 8px; }
    .search-box input { padding: 8px 16px; border-radius: 6px; border: 1px solid #1e293b; background-color: #0f172a; color: #f8fafc; width: 220px; font-size: 13px; outline: none; }
    .nav-categories { display: flex; flex-wrap: wrap; gap: 18px; padding-bottom: 15px; border-bottom: 1px solid #1e293b; margin-bottom: 25px; }
    .nav-link { color: #cbd5e1; text-decoration: none; font-size: 13px; font-weight: 500; }
    .nav-link:hover, .nav-link.active { color: #38bdf8; }
    .main-layout { display: grid; grid-template-columns: 1fr 340px; gap: 30px; }
    .article-card, .static-card { background: #0f172a; border-radius: 10px; padding: 25px; border: 1px solid #1e293b; }
    .article-image { width: 100%; height: 420px; object-fit: cover; border-radius: 6px; margin-bottom: 20px; }
    .article-card h2, .static-card h1 { color: #f8fafc; margin-top: 10px; font-size: 26px; line-height: 1.3; }
    .article-card h3 { color: #38bdf8; margin-top: 25px; border-bottom: 1px solid #1e293b; padding-bottom: 8px; }
    .article-meta { background-color: #070c18; border-left: 3px solid #38bdf8; padding: 10px 14px; border-radius: 0 4px 4px 0; font-size: 13px; color: #cbd5e1; margin-bottom: 20px; }
    .article-intro { font-size: 16px; color: #cbd5e1; }
    ul, ol { padding-left: 20px; }
    li { margin-bottom: 8px; }
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
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def create_static_pages():
    pages = {
        "about.html": ("За нас", "<h1>За TechPulse</h1><p>TechPulse е медия за изкуствен интелект, технологии и иновации.</p>"),
        "contacts.html": ("Контакти", "<h1>Контакти</h1><p>Пишете ни на: contact@techpulseon.site</p>"),
        "privacy.html": ("Поверителност", "<h1>Политика за поверителност</h1><p>Зачитаме вашата поверителност.</p>")
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
                <a href="/about.html">За нас</a> | <a href="/contacts.html">Контакти</a> | <a href="/privacy.html">Поверителност</a>
            </div>
        </footer>
    </div>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

def build_full_page(title, main_image_url, fallback_backup_img, article_body, sidebar_items):
    sidebar_html = ""
    for item in sidebar_items:
        sidebar_html += f"""
        <div class="similar-item">
            <img src="{item.get('img', 'https://images.unsplash.com/photo-1535378273068-9bb67d5beacd?w=200&auto=format&fit=crop')}" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1518770660439-4636190af475?w=200&auto=format&fit=crop';" alt="{item.get('title', 'Новина')}">
            <div class="similar-item-info">
                <span class="similar-tag">{item.get('category', 'AI')}</span>
                <h4><a href="{item.get('url', '#')}">{item.get('title', 'Новина')}</a></h4>
                <span>{item.get('time', '2026-09-25')}</span>
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
            <div class="search-box"><input type="text" placeholder="🔍 Търсене..."></div>
        </div>
        <nav class="nav-categories">
            <a href="/" class="nav-link active">Начало</a>
            <a href="#" class="nav-link">AI</a>
            <a href="#" class="nav-link">Технологии</a>
            <a href="#" class="nav-link">Мобилни</a>
            <a href="#" class="nav-link">Компютри</a>
            <a href="#" class="nav-link">Приложения</a>
            <a href="#" class="nav-link">AI инструменти</a>
            <a href="#" class="nav-link">Ревюта</a>
            <a href="#" class="nav-link">Новини</a>
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
        <footer>
            <div class="footer-links">
                <a href="/about.html">За нас</a> | <a href="/contacts.html">Контакти</a> | <a href="/privacy.html">Поверителност</a>
            </div>
            <p>© TechPulse. Всички права запазени.</p>
        </footer>
    </div>
</body>
</html>"""

def generate_news():
    print("⚡ Gemini генерира нова статия с нов модел...")
    prompt = """
    Напиши подробна и актуална технологична новина на български език (свързана с AI, смарт устройства, хардуер или автопилоти).
    Структурирай я в HTML:
    1. <h2>Заглавие</h2>
    2. <p class="article-meta">📅 <strong>Дата:</strong> 25 септември 2026 | 🏷️ <strong>Категория:</strong> AI | ⏱️ <strong>Време за четене:</strong> 3 мин</p>
    3. <p class="article-intro">Въведение (2-3 изречения).</p>
    4. <h3>Първо подзаглавие</h3>
    5. Текст и списък (ul / li)
    6. <h3>Второ подзаглавие</h3>
    7. Заключение и перспективи.
    Върни САМО чисто HTML съдържание без markdown.
    """
    
    models = ['gemini-3.8-flash', 'gemini-3.1-pro-preview']
    article_body = None
    
    for model_name in models:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response and response.text:
                article_body = response.text.replace("```html", "").replace("```", "").strip()
                break
        except Exception as e:
            print(f"Грешка с {model_name}: {e}")

    fallback_img = "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=800&auto=format&fit=crop"

    if not article_body:
        title_text = "Нов пробив в квантовите компютри и изкуствения интелект"
        article_body = f"<h2>{title_text}</h2><p class='article-intro'>Технологиите напредват бързо.</p>"
    else:
        title_match = re.search(r'<h2>(.*?)</h2>', article_body)
        title_text = title_match.group(1) if title_match else "Технологична новина"

    image_prompt = f"high tech modern {title_text} cyber style 4k photography"
    encoded_prompt = urllib.parse.quote(image_prompt)
    main_image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=450&nologo=true"

    history = load_history()
    sidebar_items = history[:3] if len(history) >= 3 else DEFAULT_ARTICLES

    full_html = build_full_page(title_text, main_image_url, fallback_img, article_body, sidebar_items)

    index_path = os.path.join(PUBLIC_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    article_slug = slugify(title_text)
    article_file_path = os.path.join(ARTICLES_DIR, f"{article_slug}.html")
    article_url = f"/articles/{article_slug}.html"

    with open(article_file_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    history.insert(0, {
        "title": title_text,
        "time": "2026-09-25",
        "category": "AI",
        "url": article_url,
        "img": main_image_url
    })
    save_history(history)
    create_static_pages()
    print("🎉 Успешно създадена и записана статия в public!")

if __name__ == "__main__":
    generate_news()
