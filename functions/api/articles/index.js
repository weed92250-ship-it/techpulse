import { checkAuth, unauthorized, rowToArticle } from '../../_utils.js';

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const limit = parseInt(url.searchParams.get('limit'));
  const offset = parseInt(url.searchParams.get('offset')) || 0;

  let query = 'SELECT * FROM articles ORDER BY date DESC, rowid DESC';
  const binds = [];
  if (limit) {
    query += ' LIMIT ? OFFSET ?';
    binds.push(limit, offset);
  }

  const { results } = await env.DB.prepare(query).bind(...binds).all();
  return Response.json(results.map(rowToArticle));
}

async function generateArticleImage(env, article) {
  const prompt = `Editorial illustration for a tech news article. Topic: ${article.title}. Category: ${article.category}. Modern minimalist digital art, dark navy blue background, teal accent lighting, abstract technology visual, no text, no logos, no recognizable real people or faces, professional news website header image, 16:9 composition.`;

  const result = await env.AI.run('@cf/black-forest-labs/flux-1-schnell', {
    prompt,
    steps: 4,
  });

  let base64;
  if (result && typeof result === 'object' && result.image) {
    base64 = result.image;
  } else {
    const bytes = new Uint8Array(result);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    base64 = btoa(binary);
  }
  return base64;
}

export async function onRequestPost({ request, env }) {
  if (!checkAuth(request, env)) return unauthorized();
  const body = await request.json();
  if (!body.title || !body.excerpt || !body.content || !body.author || !body.category) {
    return new Response(JSON.stringify({ error: 'Missing fields' }), { status: 400 });
  }
  const id = 'a' + Date.now();
  const date = new Date().toISOString().slice(0, 10);

  let image = body.image || '';

  if (body.breaking) {
    await env.DB.prepare('UPDATE articles SET breaking = 0').run();
  }

  await env.DB.prepare(
    `INSERT INTO articles (id, title, excerpt, content, category, author, date, breaking, image)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(id, body.title, body.excerpt, body.content, body.category, body.author, date, body.breaking ? 1 : 0, image)
    .run();

  if (!image) {
    try {
      const base64 = await generateArticleImage(env, { title: body.title, category: body.category });
      await env.DB.prepare(
        `INSERT INTO images (article_id, data, mime) VALUES (?, ?, ?)`
      ).bind(id, base64, 'image/jpeg').run();
      await env.DB.prepare('UPDATE articles SET image = ? WHERE id = ?')
        .bind(`/api/image/${id}`, id).run();
      image = `/api/image/${id}`;
    } catch (e) {
      const fallback = `https://picsum.photos/seed/${id}/900/500`;
      await env.DB.prepare('UPDATE articles SET image = ? WHERE id = ?').bind(fallback, id).run();
      image = fallback;
    }
  }

  return Response.json({ id, date, image });
}
