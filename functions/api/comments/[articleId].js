import { checkAuth, unauthorized } from '../../_utils.js';

export async function onRequestGet({ env, params }) {
  const { results } = await env.DB.prepare(
    'SELECT id, name, text, date FROM comments WHERE article_id = ? ORDER BY id ASC'
  )
    .bind(params.articleId)
    .all();
  return Response.json(results);
}

export async function onRequestPost({ request, env, params }) {
  const body = await request.json();
  const name = (body.name || '').trim();
  const text = (body.text || '').trim();
  if (!name || !text) {
    return new Response(JSON.stringify({ error: 'Missing fields' }), { status: 400 });
  }
  const date = new Date().toISOString().slice(0, 10);
  await env.DB.prepare(
    'INSERT INTO comments (article_id, name, text, date) VALUES (?, ?, ?, ?)'
  )
    .bind(params.articleId, name.slice(0, 80), text.slice(0, 2000), date)
    .run();
  return Response.json({ ok: true, date });
}

export async function onRequestDelete({ request, env, params }) {
  if (!checkAuth(request, env)) return unauthorized();
  const url = new URL(request.url);
  const commentId = url.searchParams.get('id');
  if (!commentId) return new Response(JSON.stringify({ error: 'Missing id' }), { status: 400 });
  await env.DB.prepare('DELETE FROM comments WHERE id = ? AND article_id = ?')
    .bind(commentId, params.articleId)
    .run();
  return Response.json({ ok: true });
}
