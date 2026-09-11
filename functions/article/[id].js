import { escapeHtml } from '../_utils.js';

const SITE_URL = 'https://techpulseon.site';

export async function onRequestGet({ env, params }) {
  const row = await env.DB.prepare('SELECT * FROM articles WHERE id = ?').bind(params.id).first();
  if (!row) {
    return new Response('Статията не е намерена', { status: 404 });
  }

  const title = escapeHtml(row.title);
  const desc = escapeHtml(row.excerpt);
  const image = row.image ? escapeHtml(row.image) : '';
  const url = `${SITE_URL}/article/${escapeHtml(row.id)}`;
  const paragraphs = (row.content || '')
    .split(/\n\n+/)
    .map(p => `<p>${escapeHtml(p)}</p>`)
    .join('\n');

  const html = `<!DOCTYPE html>
<html lang="bg">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title} — TechPulse</title>
<meta name="description" content="${desc}">
<link rel="canonical" href="${url}">
<meta property="og:type" content="article">
<meta property="og:title" content="${title}">
<meta property="og:description" content="${desc}">
<meta property="og:url" content="${url}">
${image ? `<meta property="og:image" content="${image}">` : ''}
<meta name="twitter:card" content="summary_large_image">
<style>
  body{font-family:'IBM Plex Sans',sans-serif;max-width:720px;margin:0 auto;padding:32px 20px 80px;background:#0A111F;color:#E8ECF4;line-height:1.6;}
  a{color:#49E0D2;}
  h1{font-family:'Space Grotesk',sans-serif;font-size:28px;line-height:1.25;}
  img{width:100%;border-radius:2px;margin:16px 0;display:block;}
  .meta{color:#8B96AC;font-size:13px;margin-bottom:20px;}
  .back{display:inline-block;margin-bottom:24px;font-size:14px;color:#8B96AC;}
  p{font-size:16.5px;color:#D6DCEA;}
  .cta{margin-top:30px;padding-top:20px;border-top:1px solid #20304C;font-size:14px;}
</style>
</head>
<body>
  <a href="/" class="back">← TechPulse</a>
  <h1>${title}</h1>
  <div class="meta">${escapeHtml(row.author)} · ${escapeHtml(row.date)}</div>
  ${image ? `<img src="${image}" alt="${title}" loading="lazy">` : ''}
  ${paragraphs}
  <div class="cta">
    <a href="/#/article/${escapeHtml(row.id)}">Отвори интерактивната версия с коментари →</a>
  </div>
</body>
</html>`;

  return new Response(html, {
    headers: { 'content-type': 'text/html; charset=UTF-8' },
  });
}
