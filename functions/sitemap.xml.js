const SITE_URL = 'https://techpulseon.site';

export async function onRequestGet({ env }) {
  const { results } = await env.DB.prepare('SELECT id, date FROM articles ORDER BY date DESC').all();
  const urls = results
    .map(r => `  <url>\n    <loc>${SITE_URL}/article/${r.id}</loc>\n    <lastmod>${r.date}</lastmod>\n  </url>`)
    .join('\n');
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${SITE_URL}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
${urls}
</urlset>`;
  return new Response(xml, { headers: { 'content-type': 'application/xml; charset=UTF-8' } });
}
