export async function onRequestPost({ request, env }) {
  try {
    const { password } = await request.json();
    if (password && password === env.ADMIN_PASSWORD) {
      return Response.json({ ok: true, key: password });
    }
    return new Response(JSON.stringify({ error: 'Грешна парола' }), {
      status: 401,
      headers: { 'content-type': 'application/json' },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Bad request' }), { status: 400 });
  }
}
