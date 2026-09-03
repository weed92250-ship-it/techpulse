import { checkAuth, unauthorized, rowToArticle } from '../../_utils.js';

export async function onRequestGet({ env }) {
  const { results } = await env.DB.prepare(
    'SELECT * FROM articles ORDER BY date DESC, rowid DESC'
  ).all();
  return Response.json(results.map(rowToArticle));
}

export async function onRequestPost({ request, env }) {
  if (!checkAuth(request, env)) return unauthorized();
  const body = await request.json();
  if (!body.title || !body.excerpt || !body.content || !body.author || !body.category) {
    return new Response(JSON.stringify({ error: 'Missing fields' }), { status: 400 });
  }
  const id = 'a' + Date.now();
  const date = new Date().toISOString().slice(0, 10);
  if (body.breaking) {
    await env.DB.prepare('UPDATE articles SET breaking = 0').run();
  }
  await env.DB.prepare(
    `INSERT INTO articles (id, title, excerpt, content, category, author, date, breaking, image)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(id, body.title, body.excerpt, body.content, body.category, body.author, date, body.breaking ? 1 : 0, body.image || null)
    .run();
  return Response.json({ id, date });
}
