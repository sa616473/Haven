# Haven MVP

Real-time harmful content redaction for children browsing the web.

## How it works

1. Chrome extension scans page text as the child browses
2. Text chunks are sent to a local FastAPI backend as one page document
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

### 1. Backend

```bash
cd model
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY, then:
export $(grep -v '^#' .env | xargs)   # or: set -a && source .env && set +a

uvicorn model:app --reload --port 8000
```

Verify it's running: http://localhost:8000/health

### 2. Chrome Extension

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the **`chrome_ext/`** folder (not the repo root)

### 3. Test it

1. Keep the backend running on port 8000
2. Open `test.html` in Chrome (`file://` or via a local static server)
3. Harmful blocks should blur entirely; click a blurred block to reveal it

Debug: extension **Service worker** console (`chrome://extensions` → Inspect) and the page console.

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

- Deploy backend to Railway / Render (remove localhost dependency)
- Add per-child settings via extension popup
- Add parent notification when content is redacted
- Fine-tune confidence thresholds per category
