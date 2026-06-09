---
name: visual-explainer
description: |
  Generate beautiful, self-contained HTML pages that visually explain systems,
  code changes, plans, and data. Uses the shadcn/ui zinc design system with
  Mermaid v11 ESM diagrams, zoom/pan controls, and responsive layouts.
  Use when: the user asks for a diagram, architecture overview, data flow,
  system diagram, module breakdown, or any visual explanation of technical
  concepts. Use when: generating a diff review, plan review, project recap,
  comparison table, feature matrix, audit report, or status report with 4+
  rows or 3+ columns. Use when: the user says "show me", "visualize",
  "diagram", "flowchart", "architecture", "explain how it works", or
  "what does the system look like". Use proactively when about to render
  complex ASCII tables in the terminal — generate HTML instead.
license: MIT
metadata:
  author: nicobailon + shadcn-zinc-adaptation
  version: "1.0.0"
---

# Visual Explainer v2 — shadcn/ui Zinc Edition

Generate self-contained HTML files for technical diagrams, visualizations, and
structured data. Always open the result in the browser. Never fall back to ASCII
art when this skill is loaded.

**Proactive table rendering.** When you're about to present tabular data as an
ASCII box-drawing table in the terminal (comparisons, audits, feature matrices,
status reports, any structured rows/columns), generate an HTML page instead.
The threshold: if the table has 4+ rows or 3+ columns, it belongs in the browser.
Don't wait for the user to ask — render it as HTML automatically and tell them
the file path. You can still include a brief text summary in the chat, but the
table itself should be the HTML page.

---

## 1. Design System — shadcn/ui Zinc (Mandatory)

Every page MUST use the shadcn/ui zinc palette. Do not invent custom palettes.
The zinc system is battle-tested, accessible, and consistent.

### 1.1 CSS Custom Properties

Define these HSL variables in `:root`. All components reference them via
`hsl(var(--name))`.

```css
:root {
  --background:          0 0% 100%;
  --foreground:          240 10% 3.9%;
  --card:                0 0% 100%;
  --card-foreground:     240 10% 3.9%;
  --primary:             240 5.9% 10%;
  --primary-foreground:  0 0% 98%;
  --secondary:           240 4.8% 95.9%;
  --secondary-foreground:240 5.9% 10%;
  --muted:               240 4.8% 95.9%;
  --muted-foreground:    240 3.8% 46.1%;
  --accent:              240 4.8% 95.9%;
  --accent-foreground:   240 5.9% 10%;
  --destructive:         0 84.2% 60.2%;
  --border:              240 5.9% 90%;
  --ring:                240 10% 3.9%;
  --radius:              0.5rem;
  /* Semantic accent colours (HSL) */
  --c-blue:    221.2 83.2% 53.3%;
  --c-green:   142.1 76.2% 36.3%;
  --c-orange:  24.6  95%   53.1%;
  --c-rose:    346.8 77.2% 49.8%;
  --c-violet:  263.4 70%   50.4%;
  --c-amber:   45.4  93.4% 47.5%;
  --c-teal:    173.4 80.4% 40%;
  --c-sage:    142.8 62.3% 44.1%;
}

@media (prefers-color-scheme: dark) {
  :root {
    --background:          240 10% 3.9%;
    --foreground:          0 0% 98%;
    --card:                240 10% 3.9%;
    --card-foreground:     0 0% 98%;
    --primary:             0 0% 98%;
    --primary-foreground:  240 5.9% 10%;
    --secondary:           240 3.7% 15.9%;
    --secondary-foreground:0 0% 98%;
    --muted:               240 3.7% 15.9%;
    --muted-foreground:    240 5% 64.9%;
    --accent:              240 3.7% 15.9%;
    --accent-foreground:   0 0% 98%;
    --destructive:         0 62.8% 30.6%;
    --border:              240 3.7% 15.9%;
    --ring:                240 4.9% 83.9%;
  }
}

[data-theme="dark"] {
  /* Same values as @media (prefers-color-scheme: dark) */
  --background: 240 10% 3.9%; --foreground: 0 0% 98%;
  --card: 240 10% 3.9%; --card-foreground: 0 0% 98%;
  --primary: 0 0% 98%; --primary-foreground: 240 5.9% 10%;
  --secondary: 240 3.7% 15.9%; --secondary-foreground: 0 0% 98%;
  --muted: 240 3.7% 15.9%; --muted-foreground: 240 5% 64.9%;
  --accent: 240 3.7% 15.9%; --accent-foreground: 0 0% 98%;
  --destructive: 0 62.8% 30.6%; --border: 240 3.7% 15.9%;
  --ring: 240 4.9% 83.9%;
}
[data-theme="light"] {
  /* Same values as :root */
  --background: 0 0% 100%; --foreground: 240 10% 3.9%;
  --card: 0 0% 100%; --card-foreground: 240 10% 3.9%;
  --primary: 240 5.9% 10%; --primary-foreground: 0 0% 98%;
  --secondary: 240 4.8% 95.9%; --secondary-foreground: 240 5.9% 10%;
  --muted: 240 4.8% 95.9%; --muted-foreground: 240 3.8% 46.1%;
  --accent: 240 4.8% 95.9%; --accent-foreground: 240 5.9% 10%;
  --destructive: 0 84.2% 60.2%; --border: 240 5.9% 90%;
  --ring: 240 10% 3.9%;
}
```

### 1.2 Typography

**Mandatory font pairing:**
- Body: `Inter` (weights 400, 500, 600, 700)
- Mono: `JetBrains Mono` (weights 400, 500, 600)

Load from Google Fonts:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

Font stacks:
```css
body { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
code, pre { font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; }
```

### 1.3 Component Patterns

**Badge** — pill, monospace, semantic colour:
```css
.badge {
  display: inline-flex; align-items: center;
  border-radius: 9999px; border: 1px solid hsl(var(--border));
  padding: 2px 10px; font-size: 11px; font-weight: 500;
  font-family: 'JetBrains Mono', monospace;
  color: hsl(var(--muted-foreground));
  background-color: transparent; white-space: nowrap;
}
.badge--secondary { background: hsl(var(--secondary)); color: hsl(var(--secondary-foreground)); border-color: transparent; }
.badge--blue   { background: hsl(var(--c-blue)/.1);   border-color: hsl(var(--c-blue)/.3);   color: hsl(var(--c-blue)); }
.badge--green  { background: hsl(var(--c-green)/.1);  border-color: hsl(var(--c-green)/.3);  color: hsl(var(--c-green)); }
.badge--teal   { background: hsl(var(--c-teal)/.1);   border-color: hsl(var(--c-teal)/.3);   color: hsl(var(--c-teal)); }
```

**Card** — left accent stripe, hover shadow:
```css
.ve-card {
  background: hsl(var(--card)); color: hsl(var(--card-foreground));
  border: 1px solid hsl(var(--border)); border-radius: var(--radius);
  padding: 20px 24px; position: relative; overflow: hidden;
  transition: box-shadow .15s;
}
.ve-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); }
.ve-card::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 3px; }
.ve-card--accent::before { background: hsl(var(--foreground)); }
.ve-card--blue::before   { background: hsl(var(--c-blue)); }
.ve-card--green::before  { background: hsl(var(--c-green)); }
.ve-card--teal::before   { background: hsl(var(--c-teal)); }
.ve-card--violet::before { background: hsl(var(--c-violet)); }
.ve-card--orange::before { background: hsl(var(--c-orange)); }
.ve-card--amber::before  { background: hsl(var(--c-amber)); }
.ve-card--rose::before   { background: hsl(var(--c-rose)); }
.ve-card--sage::before   { background: hsl(var(--c-sage)); }
```

**Callout** — left stripe, card border:
```css
.callout {
  position: relative; width: 100%;
  background: hsl(var(--card)); border: 1px solid hsl(var(--border));
  border-radius: var(--radius); padding: 16px 16px 16px 18px;
  font-size: 13.5px; line-height: 1.65; color: hsl(var(--muted-foreground));
  margin: 16px 0; overflow: hidden;
}
.callout::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 3px; background: hsl(var(--foreground)); opacity: .3; }
.callout--green::before { background: hsl(var(--c-green)); opacity: 1; }
.callout--amber::before { background: hsl(var(--c-amber)); opacity: 1; }
.callout--rose::before  { background: hsl(var(--c-rose));  opacity: 1; }
.callout--blue::before  { background: hsl(var(--c-blue));  opacity: 1; }
.callout--teal::before  { background: hsl(var(--c-teal));  opacity: 1; }
.callout--violet::before{ background: hsl(var(--c-violet));opacity: 1; }
```

**Data Table** — sticky header, hover highlight:
```css
.data-table {
  width: 100%; border-collapse: collapse; font-size: 13.5px;
  margin: 16px 0; border: 1px solid hsl(var(--border));
  border-radius: var(--radius); overflow: hidden;
}
.data-table thead tr { background: hsl(var(--muted)); border-bottom: 1px solid hsl(var(--border)); }
.data-table th { text-align: left; padding: 10px 14px; font-weight: 500; font-size: 13px; color: hsl(var(--muted-foreground)); }
.data-table tbody tr { border-bottom: 1px solid hsl(var(--border)); transition: background-color .1s; }
.data-table tbody tr:last-child { border-bottom: none; }
.data-table tbody tr:hover { background: hsl(var(--muted)/.5); }
.data-table td { padding: 10px 14px; color: hsl(var(--foreground)); vertical-align: top; }
```

**Concept List** — numbered cards with monospace counter circle:
```css
.concept-list { counter-reset: concept; list-style: none; margin: 20px 0; display: flex; flex-direction: column; gap: 12px; }
.concept-list li { position: relative; padding: 14px 16px 14px 52px; background: hsl(var(--card)); border: 1px solid hsl(var(--border)); border-radius: var(--radius); min-height: 44px; }
.concept-list li::before { counter-increment: concept; content: counter(concept); position: absolute; left: 14px; top: 14px; width: 26px; height: 26px; background: hsl(var(--foreground)); color: hsl(var(--background)); font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.concept-list li strong { display: block; color: hsl(var(--foreground)); font-weight: 600; font-size: 13.5px; margin-bottom: 4px; }
.concept-list li span { font-size: 13px; color: hsl(var(--muted-foreground)); line-height: 1.65; }
```

---

## 2. Diagrams — Mermaid v11 ESM

### 2.1 Mandatory Rules

These rules are non-negotiable. Violating any of them produces broken diagrams
or `SyntaxError` in Chrome.

| Rule | Correct | Incorrect |
|------|---------|-----------|
| Diagram source storage | `DIAGRAM_SOURCES` JS object with template literal strings | `<script type="text/plain">` inside `.diagram-shell` |
| Unicode in labels | Raw UTF-8 emoji characters (`🤖`) written directly | `\u{1F916}` curly-brace escapes inside template literals |
| HTML-in-JS strings | `<\/style><\/head><body>` with backslash escape | `</style></head><body>` literal in `openInNewTab` |
| Serial rendering | `[...document.querySelectorAll(...)].reduce(...)` | `NodeList.reduce()` (NodeList has no `.reduce`) |
| Script tag balance | Exactly 2 `<script>` blocks: nav inline + module ESM | Multiple `<script>` elements risking parser confusion |

**Why these rules exist:**
- `<script type="text/plain">` elements are terminated by the HTML parser when
  it sees `</script>`, corrupting the diagram source.
- `\u{XXXX}` curly-brace escapes are rejected by Chrome's parser in
  `<script type="module">` blocks, producing `SyntaxError: Invalid or
  unexpected token` with no stack trace.
- `</style></head><body>` inside a `<script>` block can terminate the script
  prematurely in Chrome.
- `NodeList` is not an Array — `.reduce()` throws `TypeError`.

### 2.2 Mandatory HTML Structure

Every diagram shell MUST have this exact DOM:

```html
<div class="diagram-shell" data-diagram-id="arch">
  <p class="diagram-shell__hint">
    Ctrl/Cmd+scroll to zoom &middot; drag to pan &middot; double-click to fit &middot; &#x26F6; to expand
  </p>
  <div class="mermaid-wrap">
    <div class="zoom-controls">
      <button type="button" data-action="zoom-in"  title="Zoom in">+</button>
      <button type="button" data-action="zoom-out" title="Zoom out">&minus;</button>
      <button type="button" data-action="zoom-fit" title="Fit">&#8634;</button>
      <button type="button" data-action="zoom-one" title="1:1">1:1</button>
      <button type="button" data-action="zoom-expand" title="Open full size">&#x26F6;</button>
      <span class="zoom-label">Loading&hellip;</span>
    </div>
    <div class="mermaid-viewport">
      <div class="mermaid mermaid-canvas"></div>
    </div>
  </div>
</div>
```

**Never use `<pre class="mermaid">` or `<script type="text/plain">`.** Both have
parser and runtime issues. The `.mermaid-canvas` div is populated by JS after
`mermaid.render()` returns.

### 2.3 Mandatory CSS for Diagram Engine

```css
.diagram-shell     { position: relative; margin: 20px 0; }
.diagram-shell__hint { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: hsl(var(--muted-foreground)); margin-bottom: 6px; opacity: .8; }
.mermaid-wrap      { position: relative; background: hsl(var(--card)); border: 1px solid hsl(var(--border)); border-radius: var(--radius); overflow: hidden; cursor: grab; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.mermaid-wrap.is-panning { cursor: grabbing; user-select: none; }
.mermaid-viewport  { position: relative; overflow: hidden; width: 100%; height: 100%; min-height: 320px; }
.mermaid-canvas    { position: absolute; top: 0; left: 0; }
.zoom-controls     { position: absolute; top: 8px; right: 8px; display: flex; gap: 1px; z-index: 10; background: hsl(var(--background)); border: 1px solid hsl(var(--border)); border-radius: var(--radius); padding: 2px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.zoom-controls button { width: 28px; height: 28px; border: none; background: transparent; color: hsl(var(--muted-foreground)); font-family: 'JetBrains Mono', monospace; font-size: 13px; cursor: pointer; border-radius: calc(var(--radius) - 2px); display: flex; align-items: center; justify-content: center; transition: background-color .12s, color .12s; }
.zoom-controls button:hover { background: hsl(var(--accent)); color: hsl(var(--accent-foreground)); }
.zoom-label        { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: hsl(var(--muted-foreground)); padding: 0 6px; white-space: nowrap; display: flex; align-items: center; }
```

### 2.4 Mandatory JS Module (Verified Working)

This is the exact engine that renders diagrams. Copy it wholesale. Do not
modify the rendering pipeline unless you have verified the change with
`node --check` AND a live browser test.

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

  const isDark = matchMedia('(prefers-color-scheme: dark)').matches
    || document.body.getAttribute('data-theme') === 'dark';

  mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    look: 'classic',
    themeVariables: {
      fontFamily: "'Inter', system-ui, sans-serif",
      fontSize: '14px',
      primaryColor:         isDark ? '#1c1c21' : '#f4f4f5',
      primaryBorderColor:   isDark ? '#3f3f46' : '#a1a1aa',
      primaryTextColor:     isDark ? '#fafafa' : '#09090b',
      secondaryColor:       isDark ? '#18181b' : '#f4f4f5',
      secondaryBorderColor: isDark ? '#27272a' : '#d4d4d8',
      secondaryTextColor:   isDark ? '#fafafa' : '#09090b',
      tertiaryColor:        isDark ? '#1c1917' : '#fef9c3',
      tertiaryBorderColor:  isDark ? '#44403c' : '#fde047',
      tertiaryTextColor:    isDark ? '#fafafa' : '#09090b',
      lineColor:            isDark ? '#52525b' : '#a1a1aa',
      noteBkgColor:         isDark ? '#18181b' : '#ffffff',
      noteTextColor:        isDark ? '#fafafa' : '#09090b',
      noteBorderColor:      isDark ? '#3f3f46' : '#e4e4e7',
    }
  });

  // CRITICAL: Store diagram sources as a JS object, NOT in <script type="text/plain">.
  // The HTML parser can corrupt or prematurely terminate script blocks.
  const DIAGRAM_SOURCES = {
    arch: `flowchart TD\n    ... your mermaid source ...`,
    flow: `sequenceDiagram\n    ... your mermaid source ...`,
    video:`flowchart TD\n    ... your mermaid source ...`,
  };

  const cfg = {
    fitPadding: 24, minHeight: 320, maxHeightPx: 900, maxHeightVh: 0.82,
    maxInitialZoom: 1.6, minZoom: 0.06, maxZoom: 6, zoomStep: 0.14,
    readabilityFloor: 0.55,
  };
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  let activeDrag = null;
  addEventListener('mousemove', (e) => activeDrag?.onMove(e));
  addEventListener('mouseup',   () => { activeDrag?.onEnd(); activeDrag = null; });

  function initDiagram(shell, diagramCode) {
    const wrap     = shell.querySelector('.mermaid-wrap');
    const viewport = shell.querySelector('.mermaid-viewport');
    const canvas   = shell.querySelector('.mermaid-canvas');
    const label    = shell.querySelector('.zoom-label');
    if (!wrap || !viewport || !canvas || !label) return;

    let zoom = 1, fitMode = 'contain', panX = 0, panY = 0;
    let svgW = 0, svgH = 0, sx = 0, sy = 0, spx = 0, spy = 0;
    let touchDist = 0, touchCx = 0, touchCy = 0;

    function constrainPan() {
      const vpW = viewport.clientWidth, vpH = viewport.clientHeight;
      const rW = svgW * zoom, rH = svgH * zoom, pad = cfg.fitPadding;
      panX = (rW + pad * 2 <= vpW) ? (vpW - rW) / 2 : clamp(panX, vpW - rW - pad, pad);
      panY = (rH + pad * 2 <= vpH) ? (vpH - rH) / 2 : clamp(panY, vpH - rH - pad, pad);
    }
    function applyTransform() {
      const svg = canvas.querySelector('svg'); if (!svg || !svgW) return;
      constrainPan();
      svg.style.width  = (svgW * zoom) + 'px';
      svg.style.height = (svgH * zoom) + 'px';
      canvas.style.transform = `translate(${panX}px, ${panY}px)`;
      label.textContent = Math.round(zoom * 100) + '% \u2014 ' + fitMode;
    }
    function canPan() {
      return svgW * zoom + cfg.fitPadding * 2 > viewport.clientWidth
          || svgH * zoom + cfg.fitPadding * 2 > viewport.clientHeight;
    }
    function computeSmartFit() {
      const vpW = viewport.clientWidth, vpH = viewport.clientHeight;
      const aW = Math.max(80, vpW - cfg.fitPadding * 2);
      const aH = Math.max(80, vpH - cfg.fitPadding * 2);
      const contain = Math.min(aW / svgW, aH / svgH);
      let z = contain, mode = 'contain';
      if (contain < cfg.readabilityFloor) {
        z = (svgH / svgW >= vpH / Math.max(vpW, 1)) ? aW / svgW : aH / svgH;
        mode = 'priority';
      }
      return { zoom: clamp(z, cfg.minZoom, cfg.maxInitialZoom), mode };
    }
    function fitDiagram() {
      if (!svgW) return;
      const fit = computeSmartFit(); zoom = fit.zoom; fitMode = fit.mode;
      panX = (viewport.clientWidth  - svgW * zoom) / 2;
      panY = (viewport.clientHeight - svgH * zoom) / 2;
      applyTransform();
    }
    function setOneToOne() {
      zoom = clamp(1, cfg.minZoom, cfg.maxZoom); fitMode = '1:1';
      panX = (viewport.clientWidth  - svgW * zoom) / 2;
      panY = (viewport.clientHeight - svgH * zoom) / 2;
      applyTransform();
    }
    function zoomAround(factor, cx, cy) {
      const next = clamp(zoom * factor, cfg.minZoom, cfg.maxZoom);
      const ratio = next / zoom;
      panX = cx - ratio * (cx - panX);
      panY = cy - ratio * (cy - panY);
      zoom = next; fitMode = 'custom'; applyTransform();
    }
    function readSvgSize(svg) {
      let w = 0, h = 0;
      if (svg.viewBox?.baseVal?.width > 0) { w = svg.viewBox.baseVal.width; h = svg.viewBox.baseVal.height; }
      if (!w) { w = parseFloat(svg.getAttribute('width')) || 0; h = parseFloat(svg.getAttribute('height')) || 0; }
      if (!w) { const b = svg.getBBox(); w = b.width; h = b.height; }
      if (!w) { const r = svg.getBoundingClientRect(); w = r.width || 1000; h = r.height || 700; }
      if (!svg.getAttribute('viewBox')) svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
      return { w, h };
    }
    function setAdaptiveHeight() {
      if (!svgW) return;
      const usableW = Math.max(280, wrap.getBoundingClientRect().width - 2);
      const idealH = (svgH / svgW) * usableW + cfg.fitPadding * 2;
      const maxVp = Math.floor(innerHeight * cfg.maxHeightVh);
      const hardMax = Math.min(cfg.maxHeightPx, Math.max(cfg.minHeight + 40, maxVp));
      wrap.style.height = Math.round(clamp(idealH, cfg.minHeight, hardMax)) + 'px';
    }
    function openInNewTab() {
      const svg = canvas.querySelector('svg'); if (!svg) return;
      const clone = svg.cloneNode(true); clone.style.width = ''; clone.style.height = '';
      const bg = isDark ? '#09090b' : '#ffffff';
      // CRITICAL: Escape </style>, </head>, </body>, </html> with backslash.
      // Unescaped closing tags inside a <script> block can terminate the script
      // prematurely in Chrome, causing "SyntaxError: Invalid or unexpected token".
      const html = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        + '<title>Diagram<\/title><style>'
        + 'body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;'
        + 'background:' + bg + ';padding:40px;box-sizing:border-box}'
        + 'svg{max-width:100%;max-height:90vh;height:auto}'
        + '<\/style><\/head><body>' + clone.outerHTML + '<\/body><\/html>';
      open(URL.createObjectURL(new Blob([html], { type: 'text/html' })), '_blank');
    }
    async function render() {
      try {
        const code = diagramCode.trim();
        if (!code) { label.textContent = 'Error: empty source'; return; }
        const id = 'diag-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
        const { svg } = await mermaid.render(id, code);
        canvas.innerHTML = svg;
        const svgNode = canvas.querySelector('svg');
        if (!svgNode) { label.textContent = 'Error: no SVG'; return; }
        const size = readSvgSize(svgNode);
        svgW = size.w; svgH = size.h;
        svgNode.removeAttribute('width'); svgNode.removeAttribute('height');
        svgNode.style.maxWidth = 'none'; svgNode.style.display = 'block';
        setAdaptiveHeight(); fitDiagram();
      } catch (err) {
        console.error('Mermaid render failed:', err);
        label.textContent = 'Error: ' + (err.message || 'render failed');
      }
    }
    const actions = {
      'zoom-in':    () => zoomAround(1 + cfg.zoomStep, viewport.clientWidth / 2, viewport.clientHeight / 2),
      'zoom-out':   () => zoomAround(1 / (1 + cfg.zoomStep), viewport.clientWidth / 2, viewport.clientHeight / 2),
      'zoom-fit':   fitDiagram,
      'zoom-one':   setOneToOne,
      'zoom-expand':openInNewTab,
    };
    wrap.querySelectorAll('[data-action]').forEach(btn => {
      const a = btn.dataset.action;
      if (actions[a]) btn.addEventListener('click', (e) => { e.stopPropagation(); actions[a](); });
    });
    viewport.addEventListener('dblclick', fitDiagram);
    viewport.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const rect = viewport.getBoundingClientRect();
        const factor = e.deltaY < 0 ? 1 + cfg.zoomStep : 1 / (1 + cfg.zoomStep);
        zoomAround(factor, e.clientX - rect.left, e.clientY - rect.top); return;
      }
      if (canPan()) { e.preventDefault(); panX -= e.deltaX; panY -= e.deltaY; applyTransform(); }
    }, { passive: false });
    viewport.addEventListener('mousedown', (e) => {
      if (e.target.closest('.zoom-controls') || !canPan()) return;
      wrap.classList.add('is-panning');
      sx = e.clientX; sy = e.clientY; spx = panX; spy = panY; e.preventDefault();
      activeDrag = {
        onMove: (ev) => { panX = spx + (ev.clientX - sx); panY = spy + (ev.clientY - sy); applyTransform(); },
        onEnd:  () => { wrap.classList.remove('is-panning'); },
      };
    });
    viewport.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; spx = panX; spy = panY; }
      else if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        touchDist = Math.sqrt(dx * dx + dy * dy);
        const r = viewport.getBoundingClientRect();
        touchCx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - r.left;
        touchCy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - r.top;
      }
    }, { passive: true });
    viewport.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1 && canPan()) {
        if (touchDist > 0) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; spx = panX; spy = panY; touchDist = 0; }
        e.preventDefault();
        panX = spx + (e.touches[0].clientX - sx); panY = spy + (e.touches[0].clientY - sy); applyTransform();
      } else if (e.touches.length === 2 && touchDist > 0) {
        e.preventDefault();
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const d = Math.sqrt(dx * dx + dy * dy);
        zoomAround(d / touchDist, touchCx, touchCy); touchDist = d;
      }
    }, { passive: false });
    new ResizeObserver(() => { if (svgW) { setAdaptiveHeight(); fitDiagram(); } }).observe(wrap);
    return render();
  }

  // CRITICAL: NodeList has no .reduce(). Spread to Array first.
  // Render serially (not concurrently) to avoid Mermaid ID collisions.
  [...document.querySelectorAll('.diagram-shell')].reduce(
    (chain, shell) => chain.then(() => initDiagram(shell, DIAGRAM_SOURCES[shell.dataset.diagramId] ?? '')),
    Promise.resolve()
  );
</script>
```

### 2.5 Mermaid Content Rules

**Unicode in diagram source:** Use raw UTF-8 characters directly. Do NOT use
`\u{XXXX}` curly-brace escapes inside template literals — Chrome's parser
rejects them in `<script type="module">` blocks, producing
`SyntaxError: Invalid or unexpected token` with no stack trace.

**Line breaks in labels:** Use `<br/>` inside quoted labels. Never use `\n` —
Mermaid renders literal backslash-n as text in HTML output.

**Layout direction:** Prefer `flowchart TD` (top-down). Use `flowchart LR` only
for simple 3-4 node linear flows. LR spreads horizontally and makes labels
unreadable with many nodes.

**Scaling:** Diagrams with 10+ nodes render too small by default. Increase
`fontSize` in `themeVariables` to 18-20px and set `maxInitialZoom` to 1.5-1.6.
For 15+ elements, use the hybrid pattern (simple Mermaid overview + CSS Grid
cards for details).

**CSS class collision:** Never define `.node` as a page-level CSS class. Mermaid
uses `.node` internally on SVG `<g>` elements with `transform: translate(x, y)`.
Page-level `.node` styles leak into diagrams and break layout. Use `.ve-card`
for card components instead.

---

## 3. Layout & Page Structure

### 3.1 Sidebar Navigation (4+ Sections)

For pages with 4+ sections, use a sticky sidebar TOC on desktop and a
horizontal scrollable bar on mobile.

```html
<div class="layout">
  <nav class="sidebar">
    <div class="sidebar-title">On this page</div>
    <ul>
      <li><a href="#identity" class="active">Project Identity</a></li>
      <li><a href="#architecture">Architecture</a></li>
      <li><a href="#dataflow">Data Flow</a></li>
      <li><a href="#modules">Modules</a></li>
    </ul>
  </nav>
  <main class="main">...</main>
</div>
```

```css
.layout { display: flex; max-width: 1400px; margin: 0 auto; min-height: 100vh; }
.sidebar { width: 248px; flex-shrink: 0; padding: 32px 16px; position: sticky; top: 0; height: 100vh; overflow-y: auto; border-right: 1px solid hsl(var(--border)); }
.sidebar a { display: block; padding: 6px 10px; border-radius: calc(var(--radius) - 2px); color: hsl(var(--muted-foreground)); text-decoration: none; font-size: 13px; transition: background-color .12s, color .12s; }
.sidebar a:hover { background: hsl(var(--accent)); color: hsl(var(--accent-foreground)); }
.sidebar a.active { background: hsl(var(--accent)); color: hsl(var(--foreground)); font-weight: 500; }
.main { flex: 1; padding: 40px 48px; min-width: 0; }
@media (max-width: 900px) { .layout { flex-direction: column; } .sidebar { width: 100%; height: auto; position: relative; border-right: none; border-bottom: 1px solid hsl(var(--border)); padding: 12px 16px; overflow-x: auto; white-space: nowrap; } .sidebar ul { display: flex; gap: 4px; } .main { padding: 24px 16px; } }
```

### 3.2 Hero Section

```css
.hero { background: hsl(var(--card)); border: 1px solid hsl(var(--border)); border-radius: calc(var(--radius) * 1.5); padding: 32px 36px; margin-bottom: 40px; box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04); position: relative; overflow: hidden; }
.hero::before { content: ''; position: absolute; inset: 0 0 auto 0; height: 3px; background: linear-gradient(90deg, hsl(var(--foreground)), hsl(var(--muted-foreground))); opacity: .4; }
```

### 3.3 Module Grid

```css
.module-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin: 20px 0; }
```

### 3.4 Animation

```css
@keyframes fadeUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.animate { animation: fadeUp .4s ease-out both; animation-delay: calc(var(--i, 0) * .06s); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .01ms !important; animation-delay: 0ms !important; transition-duration: .01ms !important; } }
```

---

## 4. Content Types

### 4.1 Architecture / System Diagrams

Three approaches depending on complexity:

**Simple topology (under 10 elements):** Use Mermaid `flowchart TD` with custom
`themeVariables`.

**Text-heavy overviews (under 15 elements):** CSS Grid with explicit row/column
placement. Sections as rounded cards with colored borders and monospace labels.
Vertical flow arrows between sections.

**Complex architectures (15+ elements):** Hybrid pattern — simple Mermaid overview
(5-8 nodes) followed by detailed CSS Grid cards for each module's internals.

### 4.2 Flowcharts / Pipelines

Use Mermaid. Prefer `flowchart TD`; use `flowchart LR` only for simple 3-4 node
linear flows. Color-code node types with `classDef` or `themeVariables`.

### 4.3 Sequence Diagrams

Use Mermaid `sequenceDiagram`. Style actors and messages via CSS overrides on
`.actor`, `.messageText`, `.activation` classes.

### 4.4 Data Tables / Comparisons / Audits

Use a real `<table>` element — not CSS Grid pretending to be a table. Tables get
accessibility, copy-paste behavior, and column alignment for free.

Layout patterns:
- Sticky `<thead>` for long tables
- Alternating row backgrounds via `tr:nth-child(even)` (subtle, 2-3% shift)
- Responsive wrapper with `overflow-x: auto`
- Row hover highlight for scanability
- Status indicators as styled `<span>` elements, never emoji

### 4.5 State Machines / Decision Trees

Use Mermaid `stateDiagram-v2` for states with labeled transitions. Supports
nested states, forks, joins, and notes.

**`stateDiagram-v2` label caveat:** Transition labels have a strict parser —
colons, parentheses, `<br/>`, HTML entities, and most special characters cause
silent parse failures. If your labels need any of these, use `flowchart TD`
instead with rounded nodes and quoted edge labels (`|"label text"|`).

### 4.6 C4 Architecture Diagrams

Use Mermaid flowchart syntax — NOT native `C4Context`. Native C4 hardcodes sharp
corners, its own font, blue icons, and inline SVG colors that ignore
`themeVariables`.

Flowchart-as-C4 pattern: Persons → rounded nodes `(("Name"))`, systems →
rectangles `["Name"]`, databases → cylinders `[("Name")]`, boundaries →
`subgraph` blocks, relationships → labeled arrows `-->|"protocol"|`. Use
`classDef` + `:::className` to visually differentiate external systems (e.g.
dashed borders). This inherits `themeVariables`, `fontFamily`, and CSS overrides.

### 4.7 Documentation (READMEs, Library Docs, API References)

When visualizing documentation, extract structure into visual elements:

| Content | Visual Treatment |
|---------|------------------|
| Features | Card grid (2-3 columns) |
| Install/setup steps | Numbered cards or vertical flow |
| API endpoints/commands | Table with sticky header |
| Config options | Table |
| Architecture | Mermaid diagram or CSS card layout |
| Comparisons | Side-by-side panels or table |
| Warnings/notes | Callout boxes |

Don't just format the prose — transform it. A feature list becomes a card grid.
Install steps become a numbered flow. An API reference becomes a table.

### 4.8 Implementation Plans

For visualizing implementation plans, extension designs, or feature
specifications. The goal is **understanding the approach**, not reading the full
source code.

**Don't dump full files.** Displaying entire source files inline overwhelms the
page. Instead:
- Show **file structure with descriptions** — list functions/exports with one-line explanations
- Show **key snippets only** — the 5-10 lines that illustrate the core logic
- Use **collapsible sections** for full code if truly needed

**Code blocks require explicit formatting.** Without `white-space: pre-wrap`,
code runs together into an unreadable wall.

```css
pre code {
  white-space: pre-wrap;
  word-break: break-word;
}
```

---

## 5. Quality Checks

Before delivering, verify:

- **The squint test**: Blur your eyes. Can you still perceive hierarchy? Are
  sections visually distinct?
- **The swap test**: Would replacing your fonts and colors with a generic dark
  theme make this indistinguishable from a template? If yes, push the aesthetic
  further.
- **Both themes**: Toggle your OS between light and dark mode. Both should look
  intentional, not broken.
- **Information completeness**: Does the diagram actually convey what the user
  asked for? Pretty but incomplete is a failure.
- **No overflow**: Resize the browser to different widths. No content should
  clip or escape its container. Every grid and flex child needs `min-width: 0`.
  Side-by-side panels need `overflow-wrap: break-word`.
- **Mermaid zoom controls**: Every `.mermaid-wrap` container must have zoom
  controls (+/−/reset/1:1/expand buttons), Ctrl/Cmd+scroll zoom, click-and-drag
  panning, and click-to-expand. The expand button (⛶) provides the same
  functionality.
- **Mermaid source safety**: Diagram sources are in a JS `DIAGRAM_SOURCES`
  object, NOT in `<script type="text/plain">` elements. Unicode is raw UTF-8,
  not `\u{XXXX}` escapes. `openInNewTab` uses `<\/style>` etc. to avoid
  premature script termination.
- **File opens cleanly**: No console errors, no broken font loads, no layout
  shifts. Run `node --check` on the module script if you changed it.

---

## 6. Anti-Patterns (AI Slop)

These patterns are explicitly forbidden. They signal "AI-generated template"
and undermine the skill's purpose of producing distinctive, high-quality
diagrams.

### Typography

**Forbidden fonts as primary body font:**
- Inter — when used with violet/indigo accents, this is the single most
  overused AI default. Inter is acceptable ONLY when paired with the shadcn
  zinc palette (which this skill mandates).
- Roboto, Arial, Helvetica — generic system fallbacks promoted to primary
- system-ui, sans-serif alone — no character, no intent

**Required:** Use Inter + JetBrains Mono as specified in section 1.2. This is
non-negotiable for shadcn/ui zinc consistency.

### Color Palette

**Forbidden accent colors:**
- Indigo-500/violet-500 (`#8b5cf6`, `#7c3aed`, `#a78bfa`) — Tailwind's default
  purple range
- The cyan + magenta + pink neon gradient combination
- Any palette that could be described as "Tailwind defaults with purple/pink/cyan
  accents"

**Required:** Use the shadcn zinc HSL variables. Semantic colours (`--c-blue`,
`--c-green`, `--c-orange`, etc.) are pre-defined and match the zinc system.

### Section Headers

**Forbidden:**
- Emoji icons in section headers (🏗️, ⚙️, 📁, 💻, 📅, 🔗, ⚡, 🔧, 📦, 🚀, etc.)
- Section headers that all use the same icon-in-rounded-box pattern

**Required:** Use styled monospace labels with colored dot indicators
(`.ve-card__label` pattern), numbered badges, or asymmetric section dividers.
If an icon is genuinely needed, use an inline SVG that matches the palette —
not emoji.

### Layout & Hierarchy

**Forbidden:**
- Perfectly centered everything with uniform padding
- All cards styled identically with the same border-radius, shadow, and spacing
- Every section getting equal visual treatment — no hero/primary vs. secondary
  distinction
- Symmetric layouts where left and right halves mirror each other

**Required:** Vary visual weight. Hero sections should dominate (larger type,
more padding, accent-tinted background). Reference sections should feel compact.
Use the depth tiers (hero → elevated → default → recessed). Asymmetric layouts
create interest.

### Template Patterns

**Forbidden:**
- Three-dot window chrome (red/yellow/green dots) on code blocks
- KPI cards where every metric has identical gradient text treatment
- "Neon Dashboard" as an aesthetic choice
- Gradient meshes with pink/purple/cyan blobs in the background

**Required:** Code blocks use a simple header with filename or language label.
KPI cards vary by importance. The shadcn zinc system provides natural
constraints that prevent generic output.

### The Slop Test

Before delivering, apply this test: **Would a developer looking at this page
immediately think "AI generated this"?** The telltale signs:

1. Inter or Roboto font with purple/violet gradient accents
2. Every heading has `background-clip: text` gradient
3. Emoji icons leading every section
4. Glowing cards with animated shadows
5. Cyan-magenta-pink color scheme on dark background
6. Perfectly uniform card grid with no visual hierarchy
7. Three-dot code block chrome

If two or more of these are present, the page is slop. Regenerate with the
shadcn zinc system. The constrained HSL palette and Inter + JetBrains Mono
pairing are harder to mess up because they have specific visual requirements
that prevent defaulting to generic patterns.

---

## 7. File Structure

Every diagram is a single self-contained `.html` file. No external assets except
CDN links (fonts, Mermaid ESM). Structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Descriptive Title</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    /* shadcn zinc HSL variables, components, layout — all inline */
  </style>
</head>
<body>
  <!-- Semantic HTML: sections, headings, lists, tables, inline SVG -->
  <!-- Mermaid diagrams rendered by the ESM module script -->
  <!-- Nav script (inline, non-module) for theme toggle and scroll-spy -->
  <!-- Module script for Mermaid init, DIAGRAM_SOURCES, zoom/pan engine -->
</body>
</html>
```

**Output location:** Write to `~/.agent/diagrams/`. Use a descriptive filename
based on content: `modem-architecture.html`, `pipeline-flow.html`,
`schema-overview.html`. The directory persists across sessions.

**Open in browser:**
- macOS: `open ~/.agent/diagrams/filename.html`
- Linux: `xdg-open ~/.agent/diagrams/filename.html`

**Tell the user** the file path so they can re-open or share it.

Flowchart-as-C4 pattern: Persons → rounded nodes `((