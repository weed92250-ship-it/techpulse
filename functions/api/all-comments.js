import { checkAuth, unauthorized } from '../_utils.js';

export async function onRequestGet({ request, env }) {
  if (!checkAuth(request, env)) return unauthorized();
  const { results } = await env.DB.prepare(
    `SELECT comments.id as id, comments.article_id as articleId, comments.name as name,
            comments.text as text, comments.date as date, articles.title as articleTitle
     FROM comments
     LEFT JOIN articles ON articles.id = comments.article_id
     ORDER BY comments.id DESC`
  ).all();
  return Response.json(results);
}
