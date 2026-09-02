export async function onRequestGet(context) {
  const { env } = context;

  // Източници на новини
  const RSS_FEEDS = [
    'https://techcrunch.com/feed/',
    'https://www.theverge.com/rss/index.xml'
  ];

  try {
    const feedUrl = RSS_FEEDS[Math.floor(Math.random() * RSS_FEEDS.length)];
    const response = await fetch(feedUrl);
    const xmlText = await response.text();

    const titleMatch = xmlText.match(/<title><!\[CDATA\[(.*?)\]\]><\/title>/) || xmlText.match(/<title>(.*?)<\/title>/);
    const linkMatch = xmlText.match(/<link>(.*?)<\/link>/);

    if (!titleMatch || !linkMatch) {
      return new Response(JSON.stringify({ error: "Няма намерени новини" }), { status: 400 });
    }

    const sourceTitle = titleMatch[1];
    const sourceLink = linkMatch[1];

    // Проверка за дублиране
    const existing = await env.DB.prepare("SELECT id FROM articles WHERE source_url = ?").bind(sourceLink).first();
    if (existing) {
      return new Response(JSON.stringify({ message: "Статията вече съществува в базата." }));
    }

    // Подготовка на prompt за Cloudflare AI
    const prompt = `Ти си технологичен журналист за българската медия TechPulse.
Преведи и разшири следното заглавие на български език в пълноценна новинарска статия (около 250-300 думи):
Заглавие: "${sourceTitle}"

Върни отговора САМО в валиден JSON формат без никакви допълнителни обяснения, в следния вид:
{
  "title": "Заглавие на български",
  "category": "AI",
  "summary": "Кратко резюме в 2 изречения",
  "content": "<p>Първи параграф...</p><p>Втори параграф...</p>"
}`;

    const aiResponse = await env.AI.run('@cf/meta/llama-3-8b-instruct', {
      messages: [{ role: 'user', content: prompt }]
    });

    const generatedData = JSON.parse(aiResponse.response);

    const slug = generatedData.title
      .toLowerCase()
      .replace(/[^a-z0-9а-я\s]/gi, '')
      .replace(/\s+/g, '-');

    // Запис в D1
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
      headers: { "Content-Type": "application/json" }
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
}
