import { checkAuth, unauthorized } from './_utils.js';

export async function onRequestPost({ request, env }) {
  if (!checkAuth(request, env)) return unauthorized();

  try {
    const body = await request.json();
    const topic = body.topic || "Последни иновации в изкуствения интелект и технологиите";

    const prompt = `Ти си главен редактор на технологичния портал TechPulse. Напиши задълбочена, професионална статия на български език (около 1000-1400 думи) на следната тема: "${topic}".
    
Върни САМО валиден JSON без никакъв друг текст или markdown codeblocks, по следния формат:
{
  "title": "Заглавие на статията",
  "category": "AI",
  "excerpt": "Кратко резюме в едно изречение за началната страница.",
  "content": "<p>Първи параграф...</p><p>Втори параграф...</p>"
}`;

    // Използваме твоя Gemini API ключ директно от Cloudflare Environment Variables
    const geminiRes = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${env.GEMINI_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }]
        })
      }
    );

    const data = await geminiRes.json();
    let rawText = data.candidates?.[0]?.content?.parts?.[0]?.text || "";

    if (rawText.startsWith('```')) {
      rawText = rawText.replace(/^```(json)?/, '').replace(/```$/, '').trim();
    }

    const articleData = JSON.parse(rawText);
    
    return Response.json({ success: true, article: articleData });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
}
