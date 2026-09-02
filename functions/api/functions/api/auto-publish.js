export async function onRequestGet(context) {
  const { env } = context;

  // Източници на новини през JSON API (избягва проблеми с RSS/XML parsing)
  const RSS_FEEDS = [
    'https://techcrunch.com/wp-json/wp/v2/posts?per_page=5',
    'https://venturebeat.com/wp-json/wp/v2/posts?per_page=5'
  ];

  try {
    const feedUrl = RSS_FEEDS[Math.floor(Math.random() * RSS_FEEDS.length)];
    const res = await fetch(feedUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
    });
    
    if (!res.ok) {
      throw new Error(`Грешка при теглене на източника: ${res.statusText}`);
    }

    const posts = await res.json();
    if (!posts || posts.length === 0) {
      return new Response(JSON.stringify({ error: "Няма намерени новини." }), { status: 400 });
    }

    // Избираме първата статия
    const post = posts[0];
    const sourceTitle = post.title.rendered.replace(/&#8217;/g, "'").replace(/&#8220;/g, '"').replace(/&#8221;/g, '"');
    const sourceLink = post.link;

    // Проверка дали вече съществува в базата
    const existing = await env.DB.prepare("SELECT id FROM articles WHERE source_url = ?").bind(sourceLink).first();
    if (existing) {
      return new Response(JSON.stringify({ message: "Статията вече съществува в базата." }), {
        headers: { "Content-Type": "application/json; charset=utf-8" }
      });
    }

    // Подготовка на prompt за Cloudflare Workers AI
    const prompt = `Ти си журналист за технологичната медия TechPulse BG. 
Напиши пълна новинарска статия на БЪЛГАРСКИ ЕЗИК (около 200-250 думи) по следното заглавие:
"${sourceTitle}"

ВЪРНИ САМО ВАЛИДЕН JSON БЕЗ НИКАКЪВ ДРУГ ТЕКСТ, СИМВОЛИ ИЛИ MARKDOWN CODEBLOCKS.
Формат:
{
  "title": "Интересно заглавие на български",
  "category": "AI",
  "summary": "Кратко резюме в две изречения.",
  "content": "<p>Първи параграф с подробности...</p><p>Втори параграф с заключение...</p>"
}`;

    const aiResponse = await env.AI.run('@cf/meta/llama-3-8b-instruct', {
      messages: [{ role: 'user', content: prompt }]
    });

    let rawText = aiResponse.response.trim();
    
    // Изчистване на евентуални markdown формати от AI отговора (```json ... ```)
    if (rawText.startsWith('```')) {
      rawText = rawText.replace(/^```(json)?/, '').replace(/```$/, '').trim();
    }

    const generatedData = JSON.parse(rawText);

    const slug = generatedData.title
      .toLowerCase()
      .replace(/[^a-z0-9а-я\s]/gi, '')
      .replace(/\s+/g, '-');

    // Запис в Cloudflare D1
    await env.DB.prepare(
      `INSERT INTO articles (title, slug, category, summary, content, author, status, source_url, created_at)
       VALUES (?, ?, ?, ?, ?, 'TechPulse AI', 'published', ?, DATETIME('now'))`
    ).bind(
      generatedData.title,
      slug,
      generatedData.category || 'Технологии',
      generatedData.summary,
      generatedData.content,
      sourceLink
    ).run();

    return new Response(JSON.stringify({ success: true, article: generatedData.title }), {
      headers: { "Content-Type": "application/json; charset=utf-8" }
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { 
      status: 500,
      headers: { "Content-Type": "application/json; charset=utf-8" }
    });
  }
}
