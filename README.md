# Haven MVP

Real-time harmful content redaction for children browsing the web.

**Live API:** https://haven-api-is35.onrender.com/health  
*(Render free tier may cold-start ~30s after idle.)*

## How it works

1. Chrome extension scans page text as the child browses
2. Text chunks are sent to the FastAPI backend as one page document
3. Backend makes **one** Claude Haiku call per page to classify harmful spans
4. Extension blurs entire posts/blocks flagged as harmful
5. Child can click a blurred block to reveal it

## Categories detected

- **Body image** — diet culture, weight/appearance shaming, unrealistic body standards
- **Self-harm** — references to self-harm, suicide, suicidal ideation
- **Violence** — graphic descriptions of violence or gore
- **Predatory** — grooming language, secrecy requests, inappropriate adult-child dynamics
- **Anxiety** — doom-inducing content inappropriate for children

---

## Setup

### 1. Chrome Extension (uses hosted API)

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the **`chrome_ext/`** folder (not the repo root)

### 2. Test it

1. Reload the extension after pulling latest `chrome_ext/` (API: `https://haven-api-is35.onrender.com`)
2. Open `test.html` in Chrome (`file://` — enable “Allow access to file URLs” on the extension if needed)
3. Harmful blocks should blur entirely; click a blurred block to reveal it

Debug: extension **Service worker** console (`chrome://extensions` → Inspect) and the page console.

### 3. Local backend (optional)

```bash
cd model
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key
uvicorn model:app --reload --port 8000
```

Point `chrome_ext/background.js` at `http://localhost:8000` for local dev.

### Deploy API (Render)

Repo includes `render.yaml`. Root directory: **`model`**. Set `ANTHROPIC_API_KEY` in Render environment variables.

---

## Project structure

```
Haven/
├── model/
│   ├── model.py           # FastAPI app + Claude classifier
│   ├── requirements.txt
│   └── .env.example
├── chrome_ext/
│   ├── manifest.json
│   ├── background.js      # Calls /classify/page (one LLM call per page)
│   └── content.js         # DOM scanner + whole-block blur
└── test.html
```

---

## Next steps

- Add per-child settings via extension popup
- Add parent notification when content is redacted
- Fine-tune confidence thresholds per category
