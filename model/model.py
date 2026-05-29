import logging
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import anthropic

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("haven")

app = FastAPI(title="Haven API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_client: anthropic.Anthropic | None = None

SYSTEM_PROMPT = """You are a child safety content classifier for parents protecting young children (ages 5-12).

Categories (only when clearly present in the text):
- body_image: diet culture, weight/appearance shaming, unrealistic body standards
- self_harm: self-harm, suicide, suicidal ideation, or methods
- violence: graphic violence, gore, assault, abuse, or sexual violence
- predatory: grooming, secrecy requests, inappropriate adult-child dynamics
- anxiety: graphic disaster/war/suffering content likely to terrify a young child

Rules:
- Judge each text block as a whole: should a parent hide this ENTIRE block from a child?
- When in doubt, do NOT flag (prefer false negatives over false positives).
- Clinical, educational, or news summaries without graphic detail are usually safe.
- Return ONLY valid JSON, no preamble.

Minimum confidence to set harmful=true: 0.85

Response format:
{
  "blocks": [
    {
      "block": 1,
      "harmful": false
    },
    {
      "block": 2,
      "harmful": true,
      "category": "violence",
      "confidence": 0.92
    }
  ]
}"""

PAGE_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + """

The user message contains multiple excerpts separated by ---BLOCK N--- lines.
- Return one entry in "blocks" for EVERY block number present in the input.
- Set harmful=true only if the ENTIRE excerpt is clearly unsuitable for a child.
- Do not return substring spans; only per-block harmful true/false.
"""
)

MAX_PAGE_BLOCKS = 30
MAX_PAGE_CHARS = 12_000
MAX_BLOCK_CHARS = 1_500
MIN_CONFIDENCE = 0.85


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY is not set. Export it or add it to model/.env",
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


class ClassifyRequest(BaseModel):
    text: str
    url: str = ""


class PageClassifyRequest(BaseModel):
    texts: list[str] = Field(default_factory=list, max_length=MAX_PAGE_BLOCKS)
    url: str = ""


class BlockFlag(BaseModel):
    block: int
    harmful: bool
    category: str = ""
    confidence: float = 0.0


class PageClassifyResponse(BaseModel):
    flags: list[BlockFlag]


def _parse_block_flags(raw: str) -> list[BlockFlag]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    flags: list[BlockFlag] = []

    for item in data.get("blocks", []):
        harmful = bool(item.get("harmful", False))
        confidence = float(item.get("confidence", 0.0))
        if harmful and confidence < MIN_CONFIDENCE:
            harmful = False
        flags.append(
            BlockFlag(
                block=int(item["block"]),
                harmful=harmful,
                category=str(item.get("category", "") or ""),
                confidence=confidence,
            )
        )

    return flags


def _build_page_document(texts: list[str]) -> tuple[str, list[int]]:
    """Combine chunks into one document; return (document, block_numbers in order)."""
    seen: set[str] = set()
    parts: list[str] = []
    block_numbers: list[int] = []
    total_len = 0
    block_num = 0

    for text in texts:
        text = text.strip()
        if len(text) < 20 or text in seen:
            continue
        seen.add(text)
        if len(parts) >= MAX_PAGE_BLOCKS:
            break

        block_num += 1
        block_numbers.append(block_num)
        block = text[:MAX_BLOCK_CHARS]
        segment = f"---BLOCK {block_num}---\n{block}"
        if total_len + len(segment) > MAX_PAGE_CHARS:
            remaining = MAX_PAGE_CHARS - total_len
            if remaining < 50:
                block_numbers.pop()
                break
            segment = segment[:remaining]
        parts.append(segment)
        total_len += len(segment) + 2

    return "\n\n".join(parts), block_numbers


def _classify_page(texts: list[str]) -> list[BlockFlag]:
    page_text, _ = _build_page_document(texts)
    if not page_text or len(page_text.strip()) < 20:
        return []

    client = get_client()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=PAGE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Classify each block for child safety (whole block, not phrases):\n\n"
                    + page_text
                ),
            }
        ],
    )

    return _parse_block_flags(message.content[0].text.strip())


def _classify_single_block(text: str) -> list[BlockFlag]:
    if not text or len(text.strip()) < 20:
        return []

    text = text[:2000]
    client = get_client()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"---BLOCK 1---\n{text}",
            }
        ],
    )

    return _parse_block_flags(message.content[0].text.strip())


@app.post("/classify", response_model=PageClassifyResponse)
async def classify(req: ClassifyRequest):
    logger.info("POST /classify | url=%s | text_len=%d", req.url or "(none)", len(req.text))
    try:
        flags = _classify_single_block(req.text)
        harmful = sum(1 for f in flags if f.harmful)
        logger.info("POST /classify | url=%s | harmful_blocks=%d", req.url or "(none)", harmful)
        return PageClassifyResponse(flags=flags)
    except json.JSONDecodeError:
        logger.info("POST /classify | url=%s | flags=0 (json decode error)", req.url or "(none)")
        return PageClassifyResponse(flags=[])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("POST /classify | url=%s | error=%s", req.url or "(none)", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/classify/page", response_model=PageClassifyResponse)
async def classify_page(req: PageClassifyRequest):
    logger.info(
        "POST /classify/page | url=%s | chunks=%d",
        req.url or "(none)",
        len(req.texts),
    )
    try:
        flags = _classify_page(req.texts)
        harmful = sum(1 for f in flags if f.harmful)
        logger.info(
            "POST /classify/page | url=%s | harmful_blocks=%d",
            req.url or "(none)",
            harmful,
        )
        return PageClassifyResponse(flags=flags)
    except json.JSONDecodeError:
        logger.info(
            "POST /classify/page | url=%s | flags=0 (json decode error)",
            req.url or "(none)",
        )
        return PageClassifyResponse(flags=[])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "POST /classify/page | url=%s | error=%s",
            req.url or "(none)",
            e,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/classify/batch", response_model=PageClassifyResponse)
async def classify_batch(req: PageClassifyRequest):
    """One LLM call for the whole page (alias kept for the extension)."""
    return await classify_page(req)


@app.get("/health")
def health():
    return {"status": "ok", "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))}
