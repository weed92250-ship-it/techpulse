export function checkAuth(request, env) {
  const key = request.headers.get('x-admin-key');
  return !!key && key === env.ADMIN_PASSWORD;
}
export function unauthorized() {
  return new Response(JSON.stringify({ error: 'Unauthorized' }), {
    status: 401,
    headers: { 'content-type': 'application/json' },
  });
}
export function rowToArticle(r) {
  return {
    id: r.id,
    title: r.title,
    excerpt: r.excerpt,
    content: r.content,
    category: r.category,
    author: r.author,
    date: r.date,
    breaking: !!r.breaking,
    image: r.image || null,
  };
}
