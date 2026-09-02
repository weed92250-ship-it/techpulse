export async function onRequestGet({ env, params }) {
  const { results } = await env.DB.prepare(
    'SELECT name, text, date FROM comments WHERE article_id = ? ORDER BY id ASC'
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
