(function () {
  const BLOCK_TAGS = new Set(['P', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'BLOCKQUOTE', 'TD']);

  const POST_ROOT_SELECTORS = [
    'shreddit-post',
    'article',
    '[data-testid="post-container"]',
    '.Post',
    '.block',
    'div.section',
  ].join(', ');

  injectStyles();

  const chunks = extractPageChunks();
  if (!chunks.length) return;

  chrome.runtime.sendMessage({
    action: 'classifyPage',
    texts: chunks.map((c) => c.text),
    url: location.href,
  });

  chrome.runtime.onMessage.addListener((request) => {
    if (request.action === 'applyFlags' && request.flags?.length) {
      applyFlags(request.flags, chunks);
    }
  });

  function injectStyles() {
    if (document.getElementById('haven-styles')) return;
    const style = document.createElement('style');
    style.id = 'haven-styles';
    style.textContent = `
      .haven-post-blurred {
        filter: blur(10px);
        background: rgba(124, 58, 237, 0.12);
        border-radius: 8px;
        cursor: pointer;
        transition: filter 0.2s ease;
        position: relative;
      }
      .haven-post-blurred::after {
        content: 'Haven — click to reveal';
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font: 500 13px system-ui, sans-serif;
        color: rgba(124, 58, 237, 0.9);
        pointer-events: none;
        letter-spacing: 0.02em;
      }
      .haven-post-blurred.haven-revealed {
        filter: none;
        background: transparent;
        cursor: default;
      }
      .haven-post-blurred.haven-revealed::after {
        content: none;
      }
    `;
    document.documentElement.appendChild(style);
  }

  function extractPageChunks() {
    const seen = new Set();
    const chunks = [];
    let blockIndex = 0;

    document.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, blockquote, td').forEach((el) => {
      if (!BLOCK_TAGS.has(el.tagName)) return;
      if (el.closest('.haven-post-blurred')) return;

      const text = el.textContent?.trim();
      if (!text || text.length < 20 || seen.has(text)) return;

      seen.add(text);
      blockIndex += 1;
      chunks.push({ block: blockIndex, text, element: el });
    });

    return chunks;
  }

  function findPostRoot(el) {
    const root = el.closest(POST_ROOT_SELECTORS);
    if (root) return root;
    return el;
  }

  function applyFlags(flags, chunks) {
    const chunkByBlock = new Map(chunks.map((c) => [c.block, c]));
    const blurred = new Set();

    for (const flag of flags) {
      if (!flag.harmful) continue;

      const chunk = chunkByBlock.get(flag.block);
      if (!chunk) continue;

      const root = findPostRoot(chunk.element);
      if (blurred.has(root)) continue;

      blurPost(root, flag.category || 'flagged');
      blurred.add(root);
    }
  }

  function blurPost(root, category) {
    if (root.classList.contains('haven-post-blurred')) return;

    root.classList.add('haven-post-blurred');
    root.dataset.havenCategory = category;
    root.title = `Haven: ${category} — click to reveal`;

    root.addEventListener(
      'click',
      (e) => {
        e.preventDefault();
        e.stopPropagation();
        root.classList.add('haven-revealed');
      },
      { once: true }
    );
  }
})();
