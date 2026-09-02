import { checkAuth, unauthorized, rowToArticle } from '../../_utils.js';

export async function onRequestGet({ env, params }) {
  const row = await env.DB.prepare('SELECT * FROM articles WHERE id = ?').bind(params.id).first();
  if (!row) return new Response(JSON.stringify({ error: 'Not found' }), { status: 404 });
  return Response.json(rowToArticle(row));
}

export async function onRequestPut({ request, env, params }) {
  if (!checkAuth(request, env)) return unauthorized();
  const body = await request.json();
  if (body.breaking) {
    await env.DB.prepare('UPDATE articles SET breaking = 0').run();
  }
  await env.DB.prepare(
    `UPDATE articles SET title=?, excerpt=?, content=?, category=?, author=?, breaking=? WHERE id=?`
  )
    .bind(body.title, body.excerpt, body.content, body.category, body.author, body.breaking ? 1 : 0, params.id)
    .run();
  return Response.json({ ok: true });
}

export async function onRequestDelete({ request, env, params }) {
  if (!checkAuth(request, env)) return unauthorized();
  await env.DB.prepare('DELETE FROM articles WHERE id = ?').bind(params.id).run();
  await env.DB.prepare('DELETE FROM comments WHERE article_id = ?').bind(params.id).run();
  return Response.json({ ok: true });
}
