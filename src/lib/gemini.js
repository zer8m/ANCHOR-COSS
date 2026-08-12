// Gemini로 신고 내용 요약. dev 프록시(/gemini) 경유, 키는 vite.config가 헤더 주입.
const MODEL = 'gemini-flash-lite-latest' // 빠른 응답(~1s). flash-latest는 ~8s로 느림.

export async function summarizeReport({ address, priority, items }) {
  const body = items.map((i) => `- ${i.label}: ${i.text}`).join('\n')
  const prompt =
    '너는 소방 상황실 요원이다. 아래 119 신고 접수 내용을 출동 대원이 3초 안에 파악할 수 있게 ' +
    '핵심만 2~3문장으로 요약하라. 위험 요소를 반드시 포함하고, 존댓말 없이 간결한 상황보고체로 써라.\n\n' +
    `[우선순위] ${priority}\n[위치] ${address}\n[접수내용]\n${body}`

  const res = await fetch(`/gemini/v1beta/models/${MODEL}:generateContent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
  })
  if (!res.ok) throw new Error(`Gemini HTTP ${res.status}`)
  const data = await res.json()
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text
  if (!text) throw new Error('빈 응답')
  return text.trim()
}
