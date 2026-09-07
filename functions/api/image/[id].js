function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export async function onRequestGet({ env, params }) {
  const row = await env.DB.prepare('SELECT data, mime FROM images WHERE article_id = ?').bind(params.id).first();
  if (!row) return new Response('Not found', { status: 404 });
  const bytes = base64ToBytes(row.data);
  return new Response(bytes, {
    headers: {
      'content-type': row.mime || 'image/png',
      'cache-control': 'public, max-age=31536000, immutable',
    },
  });
}
