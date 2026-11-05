function checkAuth(request, env) {
  const key = request.headers.get('x-admin-key');
  return !!key && key === env.ADMIN_PASSWORD;
}

function unauthorized() {
  return new Response(JSON.stringify({ error: 'Unauthorized' }), {
    status: 401,
    headers: { 'content-type': 'application/json' },
  });
}

export async function onRequestPost({ request, env }) {
  if (!checkAuth(request, env)) return unauthorized();

  try {
    const body = await request.json();
    const topic = body.topic || "Последни иновации в изкуствения интелект и технологиите";

    const prompt = `Ти си главен редактор на технологичния портал TechPulse. Напиши задълбочена, професионална статия на български език на следната тема: "${topic}".
    
Върни САМО валиден JSON формат, без никакъв друг текст, обяснения или markdown codeblocks (никакви бранкети \`\`\`json). Форматът трябва да е точно следният:
{
  "title": "Заглавие на статията",
  "category": "AI",
  "excerpt": "Кратко резюме в едно изречение за началната страница.",
  "content": "<p>Първи параграф...</p><p>Втори параграф...</p>"
}`;

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
    
    if (data.error) {
      return new Response(JSON.stringify({ error: "Gemini API грешка: " + (data.error.message || JSON.stringify(data.error)) }), { status: 500, headers: { 'content-type': 'application/json' } });
    }

    let rawText = data.candidates?.[0]?.content?.parts?.[0]?.text || "";

    // Премахваме евентуални markdown блокове за сигурност
    rawText = rawText.replace(/```json/g, '').replace(/```/g, '').trim();

    // Намираме само JSON частта, ако има страничен текст
    const jsonStart = rawText.indexOf('{');
    const jsonEnd = rawText.lastIndexOf('}');
    if (jsonStart !== -1 && jsonEnd !== -1) {
      rawText = rawText.substring(jsonStart, jsonEnd + 1);
    }

    const articleData = JSON.parse(rawText);
    
    return Response.json({ success: true, article: articleData });

  } catch (err) {
    return new Response(JSON.stringify({ error: "Грешка при обработката: " + err.message }), { status: 500, headers: { 'content-type': 'application/json' } });
  }
}
