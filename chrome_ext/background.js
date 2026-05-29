const API_BASE = 'https://haven-api-is35.onrender.com';
const MAX_CHUNKS = 30;

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action !== 'classifyPage') return;

  classifyPage(request.texts, request.url)
    .then((flags) => {
      if (sender.tab?.id != null) {
        chrome.tabs.sendMessage(sender.tab.id, { action: 'applyFlags', flags });
      }
      sendResponse({ ok: true, flags });
    })
    .catch((err) => {
      console.error('Haven:', err);
      sendResponse({ ok: false, error: String(err) });
    });

  return true;
});

async function classifyPage(texts, url) {
  // Preserve order — block numbers must match content script chunk indices
  const ordered = (texts || []).map((t) => t.trim()).filter((t) => t.length >= 20).slice(0, MAX_CHUNKS);

  if (!ordered.length) return [];

  const res = await fetch(`${API_BASE}/classify/page`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts: ordered, url: url || '' }),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }

  const data = await res.json();
  return data.flags || [];
}
