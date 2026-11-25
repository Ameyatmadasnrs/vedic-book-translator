"""Minimal local book reader server for continuous Russian translation.

Serves a clean, responsive web interface for reading the accumulated book,
tracks reading progress and source page count, restores scroll position,
and provides personal bookmarks, text highlighting, and saved quotes.
Reads directly from data/direct_translation/translations/sri_ramcharitmanas_russian_edition.md.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

TOTAL_SOURCE_PAGES = 1200


def get_translation_stats(translations_dir: Path) -> dict[str, Any]:
    """Inspect translations directory to determine current sequential progress."""
    combined_file = translations_dir / "sri_ramcharitmanas_russian_edition.md"
    mtime = combined_file.stat().st_mtime if combined_file.exists() else 0
    size = combined_file.stat().st_size if combined_file.exists() else 0

    chunk_pattern = re.compile(r"^translation_pages_(\d+)_(\d+)\.md$")
    ranges: list[tuple[int, int]] = []
    for f in translations_dir.glob("translation_pages_*_*.md"):
        m = chunk_pattern.match(f.name)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if start == 215 and end == 229:
                continue
            ranges.append((start, end))

    ranges.sort()
    last_completed_page = 0
    expected_start = 1
    for s, e in ranges:
        if s == expected_start:
            last_completed_page = e
            expected_start = e + 1
        else:
            break

    percentage = round((last_completed_page / TOTAL_SOURCE_PAGES) * 100, 2)

    return {
        "total_source_pages": TOTAL_SOURCE_PAGES,
        "last_completed_page": last_completed_page,
        "translated_pages_count": last_completed_page,
        "percentage": percentage,
        "file_size": size,
        "modified_time": mtime,
        "chunks_count": len(ranges),
    }


READER_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
  <title>Шри Рамачаритаманаса</title>
  <style>
    :root {
      --bg: #fbf9f5;
      --card-bg: #ffffff;
      --text: #2c2523;
      --text-muted: #6b635c;
      --accent: #8e3a10;
      --accent-hover: #a84818;
      --border: #e6dfd5;
      --quote-bg: #f4ede3;
      --quote-border: #b87333;
      --sidebar-width: 330px;
      --font-body: 'Literata', 'Merriweather', 'PT Serif', 'Georgia', serif;
      --font-ui: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
      --hl-yellow: rgba(254, 240, 138, 0.7);
      --hl-orange: rgba(254, 215, 170, 0.7);
      --hl-green: rgba(187, 247, 208, 0.7);
      --hl-blue: rgba(186, 230, 253, 0.7);
    }

    [data-theme="sepia"] {
      --bg: #f4ebd9;
      --card-bg: #ede1cb;
      --text: #382c22;
      --text-muted: #736353;
      --accent: #823600;
      --accent-hover: #9c4100;
      --border: #d8c7ab;
      --quote-bg: #e2d3b9;
      --quote-border: #823600;
      --hl-yellow: rgba(250, 204, 21, 0.55);
      --hl-orange: rgba(251, 146, 60, 0.55);
      --hl-green: rgba(134, 239, 172, 0.55);
      --hl-blue: rgba(147, 197, 253, 0.55);
    }

    [data-theme="dark"] {
      --bg: #181514;
      --card-bg: #221f1d;
      --text: #e6dfdb;
      --text-muted: #a39891;
      --accent: #e57c46;
      --accent-hover: #f0905e;
      --border: #38312e;
      --quote-bg: #2b2522;
      --quote-border: #e57c46;
      --hl-yellow: rgba(161, 98, 7, 0.6);
      --hl-orange: rgba(194, 65, 12, 0.6);
      --hl-green: rgba(21, 128, 61, 0.6);
      --hl-blue: rgba(29, 78, 216, 0.6);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-body);
      line-height: 1.8;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      transition: background 0.2s, color 0.2s;
    }

    /* Top Bar */
    #topbar {
      position: sticky;
      top: 0;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      height: 56px;
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 100;
      font-family: var(--font-ui);
    }

    .bar-left, .bar-center, .bar-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .book-title {
      font-weight: 600;
      font-size: 1rem;
      letter-spacing: -0.01em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 220px;
    }

    .btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
      height: 36px;
      padding: 0 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.88rem;
      font-family: var(--font-ui);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: border-color 0.15s, color 0.15s, background 0.15s;
    }
    .btn:hover { border-color: var(--accent); color: var(--accent); }
    .btn.active { background: var(--quote-bg); border-color: var(--accent); color: var(--accent); }

    .btn-resume {
      background: var(--accent);
      color: #ffffff;
      border: 1px solid var(--accent);
      font-weight: 500;
    }
    .btn-resume:hover {
      background: var(--accent-hover);
      color: #ffffff;
    }

    /* Progress Widget */
    .progress-widget {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.82rem;
      color: var(--text-muted);
    }
    .progress-track {
      width: 110px;
      height: 6px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      background: var(--accent);
      width: 0%;
      transition: width 0.3s;
    }

    /* Sidebar Drawer */
    #drawer {
      position: fixed;
      top: 0; bottom: 0; left: 0;
      width: var(--sidebar-width);
      max-width: 88vw;
      background: var(--card-bg);
      border-right: 1px solid var(--border);
      z-index: 200;
      transform: translateX(-100%);
      transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      display: flex;
      flex-direction: column;
      box-shadow: 4px 0 20px rgba(0, 0, 0, 0.1);
      font-family: var(--font-ui);
    }
    #drawer.open {
      transform: translateX(0);
    }

    #drawer-overlay {
      position: fixed;
      top: 0; bottom: 0; left: 0; right: 0;
      background: rgba(0, 0, 0, 0.35);
      z-index: 199;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.25s ease;
    }
    #drawer-overlay.visible {
      opacity: 1;
      pointer-events: auto;
    }

    .drawer-header {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .drawer-tabs {
      display: flex;
      border-bottom: 1px solid var(--border);
      background: var(--bg);
    }
    .drawer-tab {
      flex: 1;
      padding: 10px;
      text-align: center;
      font-size: 0.88rem;
      cursor: pointer;
      color: var(--text-muted);
      border-bottom: 2px solid transparent;
      font-weight: 500;
    }
    .drawer-tab.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
      background: var(--card-bg);
    }
    .drawer-content {
      flex: 1;
      overflow-y: auto;
      padding: 14px;
    }

    /* TOC items */
    .toc-item {
      display: flex;
      align-items: baseline;
      padding: 5px 8px;
      color: var(--text);
      text-decoration: none;
      font-size: 0.82rem;
      border-radius: 5px;
      margin-bottom: 2px;
      line-height: 1.35;
      transition: background 0.15s, color 0.15s;
      word-break: break-word;
    }
    .toc-item:hover { background: var(--quote-bg); color: var(--accent); }
    .toc-item.level-1 {
      font-weight: 700;
      margin-top: 10px;
      margin-bottom: 4px;
      font-size: 0.88rem;
      color: var(--text);
      letter-spacing: 0.02em;
    }
    .toc-item.level-2 {
      font-weight: 600;
      padding-left: 10px;
      margin-top: 8px;
      margin-bottom: 3px;
      color: var(--accent);
      font-size: 0.84rem;
    }
    .toc-item.level-3 {
      padding-left: 20px;
      color: var(--text-muted);
      font-size: 0.79rem;
      line-height: 1.3;
    }
    .toc-item.level-3:hover { color: var(--text); }

    .toc-num {
      display: inline-block;
      min-width: 1.6em;
      font-weight: 600;
      color: var(--accent);
      font-feature-settings: "tnum";
      flex-shrink: 0;
      margin-right: 4px;
      font-size: 0.80rem;
    }
    .toc-text {
      flex: 1;
    }

    /* Bookmarks & Highlights list */
    .lib-card {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 10px;
      font-size: 0.88rem;
    }
    .lib-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 6px;
      font-size: 0.78rem;
      color: var(--text-muted);
    }
    .lib-badge {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .lib-text {
      font-family: var(--font-body);
      font-style: italic;
      line-height: 1.5;
      margin-bottom: 6px;
      cursor: pointer;
    }
    .lib-text:hover { color: var(--accent); }
    .lib-note {
      background: var(--card-bg);
      border-left: 2px solid var(--accent);
      padding: 4px 8px;
      font-size: 0.82rem;
      margin-top: 6px;
      border-radius: 0 4px 4px 0;
    }
    .lib-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 8px;
    }
    .btn-xs {
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.78rem;
      padding: 2px 4px;
    }
    .btn-xs:hover { color: var(--accent); }

    /* Reading Content Area */
    #reader-wrap {
      flex: 1;
      width: 100%;
      display: flex;
      justify-content: center;
    }

    #content {
      width: 100%;
      max-width: 1060px;
      padding: 40px 36px 120px;
      font-size: var(--book-font-size, 1.15rem);
      line-height: 1.8;
      box-sizing: border-box;
    }

    #content h1 {
      font-size: 1.85rem;
      color: var(--accent);
      margin: 44px 0 20px;
      text-align: center;
      line-height: 1.35;
      border-bottom: 1.5px solid var(--border);
      padding-bottom: 14px;
      scroll-margin-top: 80px;
    }

    #content h2 {
      font-size: 1.45rem;
      color: var(--accent);
      margin: 36px 0 16px;
      line-height: 1.35;
      scroll-margin-top: 80px;
    }

    #content h3 {
      font-size: 1.25rem;
      color: var(--text);
      margin: 28px 0 14px;
      line-height: 1.4;
      scroll-margin-top: 80px;
    }

    #content p {
      margin-bottom: 1.45em;
      text-align: justify;
      text-indent: 1.6em;
      word-break: break-word;
      line-height: 1.8;
    }

    #content blockquote {
      background: var(--quote-bg);
      border-left: 4px solid var(--quote-border);
      padding: 16px 22px;
      margin: 26px 0;
      border-radius: 0 6px 6px 0;
      font-size: 0.95em;
      line-height: 1.65;
      font-style: normal;
    }
    #content blockquote p {
      text-indent: 0;
      margin-bottom: 0.7em;
      line-height: 1.65;
    }
    #content blockquote p:last-child { margin-bottom: 0; }

    #content hr {
      border: 0;
      height: 1px;
      background: var(--border);
      margin: 40px 0;
    }

    mark.hl {
      border-radius: 2px;
      padding: 0 1px;
      cursor: pointer;
    }
    mark.hl-yellow { background-color: var(--hl-yellow); color: inherit; }
    mark.hl-orange { background-color: var(--hl-orange); color: inherit; }
    mark.hl-green  { background-color: var(--hl-green);  color: inherit; }
    mark.hl-blue   { background-color: var(--hl-blue);   color: inherit; }

    /* Selection Floating Toolbar */
    #selection-bar {
      position: absolute;
      background: var(--card-bg);
      border: 1px solid var(--border);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
      border-radius: 8px;
      padding: 6px 8px;
      display: none;
      align-items: center;
      gap: 6px;
      z-index: 300;
      font-family: var(--font-ui);
    }
    .color-dot {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      cursor: pointer;
      border: 2px solid #fff;
      box-shadow: 0 0 2px rgba(0,0,0,0.3);
      transition: transform 0.15s;
    }
    .color-dot:hover { transform: scale(1.15); }
    .dot-yellow { background: #fde047; }
    .dot-orange { background: #fb923c; }
    .dot-green  { background: #4ade80; }
    .dot-blue   { background: #38bdf8; }

    /* Modal for Bookmark/Note */
    #modal-overlay {
      position: fixed;
      top: 0; bottom: 0; left: 0; right: 0;
      background: rgba(0, 0, 0, 0.45);
      z-index: 400;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .modal-box {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      width: 100%;
      max-width: 420px;
      padding: 20px;
      font-family: var(--font-ui);
    }
    .modal-box h4 {
      margin-bottom: 12px;
      color: var(--accent);
      font-size: 1.05rem;
    }
    .modal-box input, .modal-box textarea {
      width: 100%;
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      border-radius: 5px;
      font-family: inherit;
      font-size: 0.9rem;
      margin-bottom: 14px;
    }
    .modal-box textarea { height: 75px; resize: vertical; }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }

    /* Mobile Adaptations */
    @media (max-width: 768px) {
      .book-title { max-width: 130px; font-size: 0.9rem; }
      .progress-widget .progress-track { width: 70px; }
      #content { padding: 24px 16px 100px; max-width: 100%; font-size: calc(var(--book-font-size, 1.15rem) * 0.94); line-height: 1.65; text-align: left; }
      #content p { text-align: left; text-indent: 1.2em; line-height: 1.65; }
      #content blockquote { padding: 12px 14px; margin: 18px 0; font-size: 0.92em; }
      .bar-center { display: none; }
    }
  </style>
</head>
<body>

  <!-- Top Bar -->
  <header id="topbar">
    <div class="bar-left">
      <button class="btn" onclick="toggleDrawer()" title="Меню книги">☰ Меню</button>
      <span class="book-title">Шри Рамачаритаманаса</span>
    </div>

    <div class="bar-center">
      <div class="progress-widget" title="Прогресс перевода оригинала">
        <div class="progress-track"><div class="progress-fill" id="pfill"></div></div>
        <span id="ptext">0%</span>
        <span style="font-weight:600;" id="ppage">Стр. 0 / 1200</span>
      </div>
    </div>

    <div class="bar-right">
      <button class="btn btn-resume" id="btn-resume" onclick="resumeReading()" title="Продолжить чтение с последнего места" style="display:none;">
        ▶ Продолжить
      </button>
      <button class="btn" onclick="openAddBookmarkModal()" title="Добавить закладку на текущем месте">
        🔖 <span class="hide-mobile">Закладка</span>
      </button>
      <select class="btn" id="theme-select" onchange="changeTheme(this.value)">
        <option value="light">Светлая</option>
        <option value="sepia">Сепия</option>
        <option value="dark">Тёмная</option>
      </select>
      <button class="btn" onclick="changeFontSize(-1)" title="Уменьшить шрифт">A-</button>
      <button class="btn" onclick="changeFontSize(1)" title="Увеличить шрифт">A+</button>
    </div>
  </header>

  <!-- Navigation Drawer (TOC + Bookmarks/Highlights) -->
  <div id="drawer-overlay" onclick="closeDrawer()"></div>
  <aside id="drawer">
    <div class="drawer-header">
      <strong style="color:var(--accent);">Навигация и библиотека</strong>
      <button class="btn-xs" style="font-size:1.1rem;" onclick="closeDrawer()">✕</button>
    </div>
    <div class="drawer-tabs">
      <div class="drawer-tab active" id="tab-toc-btn" onclick="switchDrawerTab('toc')">Оглавление</div>
      <div class="drawer-tab" id="tab-lib-btn" onclick="switchDrawerTab('lib')">Закладки и заметки (<span id="lib-count">0</span>)</div>
    </div>
    <div class="drawer-content" id="tab-toc">
      <div id="toc-list">Загрузка оглавления...</div>
    </div>
    <div class="drawer-content" id="tab-lib" style="display:none;">
      <div style="margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:0.8rem; color:var(--text-muted);">Ваша личная библиотека:</span>
        <button class="btn btn-xs" onclick="openAddBookmarkModal()">+ Закладка</button>
      </div>
      <div id="lib-list">Пока нет закладок или сохранённых цитат.</div>
    </div>
  </aside>

  <!-- Main Reading Area -->
  <main id="reader-wrap">
    <article id="content">Загрузка книги...</article>
  </main>

  <!-- Selection Popup Toolbar -->
  <div id="selection-bar">
    <span style="font-size:0.75rem; color:var(--text-muted); margin-right:2px;">Выделить:</span>
    <div class="color-dot dot-yellow" title="Жёлтый" onclick="applyHighlight('yellow')"></div>
    <div class="color-dot dot-orange" title="Шафрановый" onclick="applyHighlight('orange')"></div>
    <div class="color-dot dot-green"  title="Зелёный" onclick="applyHighlight('green')"></div>
    <div class="color-dot dot-blue"   title="Голубой" onclick="applyHighlight('blue')"></div>
    <button class="btn btn-xs" onclick="openHighlightNoteModal()" style="margin-left:4px;">💬 Заметка</button>
    <button class="btn-xs" onclick="hideSelectionBar()" style="margin-left:2px;">✕</button>
  </div>

  <!-- Bookmark Modal -->
  <div id="modal-overlay">
    <div class="modal-box" id="bm-modal" style="display:none;">
      <h4>Добавить закладку</h4>
      <p style="font-size:0.82rem; color:var(--text-muted); margin-bottom:8px;" id="bm-chapter-label">Глава: ...</p>
      <input type="text" id="bm-title-input" placeholder="Название закладки (необязательно)">
      <div class="modal-actions">
        <button class="btn" onclick="closeModal()">Отмена</button>
        <button class="btn btn-resume" onclick="saveBookmarkFromModal()">Сохранить</button>
      </div>
    </div>

    <!-- Highlight Note Modal -->
    <div class="modal-box" id="note-modal" style="display:none;">
      <h4>Заметка к цитате</h4>
      <p style="font-size:0.82rem; font-style:italic; color:var(--text-muted); margin-bottom:8px;" id="note-quote-preview">...</p>
      <textarea id="note-input" placeholder="Ваш личный комментарий или мысль..."></textarea>
      <div class="modal-actions">
        <button class="btn" onclick="closeModal()">Отмена</button>
        <button class="btn btn-resume" onclick="saveHighlightNoteFromModal()">Сохранить</button>
      </div>
    </div>
  </div>

  <script>
    let currentFontSize = 1.15;
    let lastMtime = 0;
    let cachedMarkdown = '';
    let isInitialLoad = true;
    let activeSelection = null;
    let editingHighlightId = null;

    // Storage Keys
    const KEY_SCROLL = 'manas_scroll_y';
    const KEY_HEADING = 'manas_last_heading';
    const KEY_THEME = 'manas_theme';
    const KEY_FONTSIZE = 'manas_fontsize';
    const KEY_BOOKMARKS = 'manas_bookmarks';
    const KEY_HIGHLIGHTS = 'manas_highlights';

    function getBookmarks() {
      try { return JSON.parse(localStorage.getItem(KEY_BOOKMARKS) || '[]'); } catch { return []; }
    }
    function saveBookmarks(bms) {
      localStorage.setItem(KEY_BOOKMARKS, JSON.stringify(bms));
      renderLibrary();
    }

    function getHighlights() {
      try { return JSON.parse(localStorage.getItem(KEY_HIGHLIGHTS) || '[]'); } catch { return []; }
    }
    function saveHighlights(hls) {
      localStorage.setItem(KEY_HIGHLIGHTS, JSON.stringify(hls));
      renderLibrary();
    }

    // Drawer Controls
    function toggleDrawer() {
      const d = document.getElementById('drawer');
      const o = document.getElementById('drawer-overlay');
      if (d.classList.contains('open')) {
        closeDrawer();
      } else {
        d.classList.add('open');
        o.classList.add('visible');
      }
    }
    function closeDrawer() {
      document.getElementById('drawer').classList.remove('open');
      document.getElementById('drawer-overlay').classList.remove('visible');
    }

    function switchDrawerTab(tab) {
      document.getElementById('tab-toc-btn').classList.toggle('active', tab === 'toc');
      document.getElementById('tab-lib-btn').classList.toggle('active', tab === 'lib');
      document.getElementById('tab-toc').style.display = tab === 'toc' ? 'block' : 'none';
      document.getElementById('tab-lib').style.display = tab === 'lib' ? 'block' : 'none';
    }

    // Theme & Font
    function changeTheme(theme) {
      if (theme === 'light') {
        document.body.removeAttribute('data-theme');
      } else {
        document.body.setAttribute('data-theme', theme);
      }
      localStorage.setItem(KEY_THEME, theme);
    }

    function changeFontSize(delta) {
      currentFontSize = Math.max(0.9, Math.min(1.55, currentFontSize + delta * 0.06));
      document.getElementById('content').style.setProperty('--book-font-size', currentFontSize + 'rem');
      localStorage.setItem(KEY_FONTSIZE, currentFontSize);
    }

    // Markdown Parser (Pure JS, offline)
    function parseMarkdown(md) {
      const lines = md.split('\\n');
      let html = '';
      let inBlockquote = false;
      let blockquoteContent = [];

      for (let i = 0; i < lines.length; i++) {
        let line = lines[i];

        if (line.startsWith('>')) {
          inBlockquote = true;
          blockquoteContent.push(line.replace(/^>\\s?/, ''));
          continue;
        } else if (inBlockquote) {
          html += '<blockquote>' + parseMarkdown(blockquoteContent.join('\\n')) + '</blockquote>';
          blockquoteContent = [];
          inBlockquote = false;
        }

        if (/^---+\\s*$/.test(line)) {
          html += '<hr>';
          continue;
        }

        const hMatch = line.match(/^(#{1,3})\\s+(.+)$/);
        if (hMatch) {
          const level = hMatch[1].length;
          const text = hMatch[2];
          const slug = 'heading-' + i;
          html += `<h${level} id="${slug}">${formatInline(text)}</h${level}>`;
          continue;
        }

        if (line.trim() === '') continue;

        html += `<p>${formatInline(line.trim())}</p>`;
      }

      if (inBlockquote) {
        html += '<blockquote>' + parseMarkdown(blockquoteContent.join('\\n')) + '</blockquote>';
      }

      return html;
    }

    function formatInline(str) {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*(.+?)\\*/g, '<em>$1</em>')
        .replace(/\\[неразборчивый фрагмент\\]/g, '<span style="color:var(--text-muted);font-style:italic;">[неразборчивый фрагмент]</span>');
    }

    // Build Table of Contents
    function buildTOC() {
      const headings = document.querySelectorAll('#content h1, #content h2, #content h3');
      const tocList = document.getElementById('toc-list');
      if (headings.length === 0) {
        tocList.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; padding:12px 8px;">Разделы формируются...</div>';
        return;
      }

      let chapterCount = 0;
      let tocHtml = '';
      headings.forEach((h) => {
        const text = h.textContent.trim();
        if (!text) return;
        if (text.startsWith('[') && text.endsWith(']')) return;
        const tag = h.tagName.toLowerCase();
        const level = tag === 'h1' ? '1' : (tag === 'h2' ? '2' : '3');

        if (level === '3') {
          chapterCount++;
          tocHtml += `<a class="toc-item level-${level}" href="#${h.id}" onclick="onTocItemClick(event, '${h.id}')"><span class="toc-num">${chapterCount}.</span><span class="toc-text">${text}</span></a>`;
        } else {
          tocHtml += `<a class="toc-item level-${level}" href="#${h.id}" onclick="onTocItemClick(event, '${h.id}')"><span class="toc-text">${text}</span></a>`;
        }
      });
      tocList.innerHTML = tocHtml;
    }

    function onTocItemClick(e, id) {
      e.preventDefault();
      closeDrawer();
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setTimeout(saveReadingPosition, 500);
      }
    }

    // Continuous Reading Position Saving
    function getCurrentChapter() {
      const headings = Array.from(document.querySelectorAll('#content h1, #content h2, #content h3'));
      let current = 'Начало книги';
      const scrollY = window.scrollY;
      for (let h of headings) {
        if (h.offsetTop <= scrollY + 120) {
          current = h.textContent;
        } else {
          break;
        }
      }
      return current;
    }

    function saveReadingPosition() {
      const scrollY = window.scrollY;
      if (scrollY > 50) {
        localStorage.setItem(KEY_SCROLL, scrollY);
        localStorage.setItem(KEY_HEADING, getCurrentChapter());
        updateResumeButton();
      }
    }

    window.addEventListener('scroll', () => {
      clearTimeout(window._scrollDebounce);
      window._scrollDebounce = setTimeout(saveReadingPosition, 350);
    });

    function updateResumeButton() {
      const savedY = localStorage.getItem(KEY_SCROLL);
      const btn = document.getElementById('btn-resume');
      if (savedY && parseFloat(savedY) > 80 && Math.abs(window.scrollY - parseFloat(savedY)) > 400) {
        btn.style.display = 'inline-flex';
      } else {
        btn.style.display = 'none';
      }
    }

    function resumeReading() {
      const savedY = localStorage.getItem(KEY_SCROLL);
      if (savedY) {
        window.scrollTo({ top: parseFloat(savedY), behavior: 'smooth' });
      }
    }

    // Bookmarks & Highlights UI
    function openAddBookmarkModal() {
      const currentChapter = getCurrentChapter();
      document.getElementById('bm-chapter-label').textContent = 'Глава: ' + currentChapter;
      document.getElementById('bm-title-input').value = 'Закладка: ' + currentChapter;
      document.getElementById('modal-overlay').style.display = 'flex';
      document.getElementById('bm-modal').style.display = 'block';
      document.getElementById('note-modal').style.display = 'none';
    }

    function saveBookmarkFromModal() {
      const title = document.getElementById('bm-title-input').value.trim() || getCurrentChapter();
      const bms = getBookmarks();
      bms.push({
        id: 'bm_' + Date.now(),
        title: title,
        chapter: getCurrentChapter(),
        scrollY: window.scrollY,
        timestamp: Date.now()
      });
      saveBookmarks(bms);
      closeModal();
    }

    function closeModal() {
      document.getElementById('modal-overlay').style.display = 'none';
      document.getElementById('bm-modal').style.display = 'none';
      document.getElementById('note-modal').style.display = 'none';
      editingHighlightId = null;
    }

    // Selection & Highlighting
    document.addEventListener('selectionchange', () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.toString().trim()) {
        return;
      }
      activeSelection = {
        text: sel.toString().trim(),
        range: sel.getRangeAt(0).cloneRange()
      };
      showSelectionBar(activeSelection.range);
    });

    function showSelectionBar(range) {
      const rect = range.getBoundingClientRect();
      const bar = document.getElementById('selection-bar');
      bar.style.display = 'flex';
      const top = window.scrollY + rect.top - 46;
      const left = Math.max(10, Math.min(window.innerWidth - 220, window.scrollX + rect.left));
      bar.style.top = top + 'px';
      bar.style.left = left + 'px';
    }

    function hideSelectionBar() {
      document.getElementById('selection-bar').style.display = 'none';
    }

    function applyHighlight(color) {
      if (!activeSelection) return;
      const text = activeSelection.text;
      const hls = getHighlights();
      hls.push({
        id: 'hl_' + Date.now(),
        text: text,
        color: color,
        chapter: getCurrentChapter(),
        note: '',
        scrollY: window.scrollY,
        timestamp: Date.now()
      });
      saveHighlights(hls);
      hideSelectionBar();
      window.getSelection()?.removeAllRanges();
      renderContentHighlights();
    }

    function openHighlightNoteModal() {
      if (!activeSelection) return;
      hideSelectionBar();
      document.getElementById('note-quote-preview').textContent = '«' + activeSelection.text.substring(0, 100) + '...»';
      document.getElementById('note-input').value = '';
      document.getElementById('modal-overlay').style.display = 'flex';
      document.getElementById('bm-modal').style.display = 'none';
      document.getElementById('note-modal').style.display = 'block';
    }

    function saveHighlightNoteFromModal() {
      const note = document.getElementById('note-input').value.trim();
      if (editingHighlightId) {
        const hls = getHighlights();
        const item = hls.find(h => h.id === editingHighlightId);
        if (item) item.note = note;
        saveHighlights(hls);
      } else if (activeSelection) {
        const hls = getHighlights();
        hls.push({
          id: 'hl_' + Date.now(),
          text: activeSelection.text,
          color: 'yellow',
          chapter: getCurrentChapter(),
          note: note,
          scrollY: window.scrollY,
          timestamp: Date.now()
        });
        saveHighlights(hls);
        renderContentHighlights();
      }
      closeModal();
    }

    function renderContentHighlights() {
      // Re-apply highlight tags visually inside content
      const hls = getHighlights();
      const contentEl = document.getElementById('content');
      // For each highlight, wrap the text if found
      hls.forEach(h => {
        if (!h.text || h.text.length < 4) return;
        // Escape special chars for regex
        const safe = h.text.replace(/[-\\/\\\\^$*+?.()|[\\]{}]/g, '\\\\$&');
        const re = new RegExp(`(${safe})`, 'gi');
        // Simple text replacement inside paragraphs
        contentEl.querySelectorAll('p, blockquote p').forEach(p => {
          if (p.textContent.includes(h.text) && !p.innerHTML.includes(`id="${h.id}"`)) {
            p.innerHTML = p.innerHTML.replace(re, `<mark class="hl hl-${h.color}" id="${h.id}" title="${h.note || 'Сохранено в избранное'}">$1</mark>`);
          }
        });
      });
    }

    function renderLibrary() {
      const bms = getBookmarks();
      const hls = getHighlights();
      const total = bms.length + hls.length;
      document.getElementById('lib-count').textContent = total;

      const container = document.getElementById('lib-list');
      if (total === 0) {
        container.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; padding:10px 0;">Пока нет закладок или заметок. Выделите любой текст в книге или нажмите «Закладка».</div>';
        return;
      }

      // Combine and sort by scrollY (book order)
      const allItems = [
        ...bms.map(b => ({ ...b, type: 'bookmark' })),
        ...hls.map(h => ({ ...h, type: 'highlight' }))
      ].sort((a, b) => (a.scrollY || 0) - (b.scrollY || 0));

      let html = '';
      allItems.forEach(item => {
        if (item.type === 'bookmark') {
          html += `
            <div class="lib-card">
              <div class="lib-card-header">
                <span class="lib-badge" style="background:var(--accent); color:#fff;">Закладка</span>
                <span>${item.chapter}</span>
              </div>
              <div class="lib-text" onclick="jumpToPosition(${item.scrollY})">🔖 ${item.title}</div>
              <div class="lib-actions">
                <button class="btn-xs" onclick="jumpToPosition(${item.scrollY})">Перейти</button>
                <button class="btn-xs" onclick="deleteBookmark('${item.id}')">Удалить</button>
              </div>
            </div>
          `;
        } else {
          html += `
            <div class="lib-card">
              <div class="lib-card-header">
                <span class="lib-badge" style="background:var(--hl-${item.color || 'yellow'}); color:#000;">Цитата</span>
                <span>${item.chapter}</span>
              </div>
              <div class="lib-text" onclick="jumpToPosition(${item.scrollY})">«${item.text}»</div>
              ${item.note ? `<div class="lib-note">💬 ${item.note}</div>` : ''}
              <div class="lib-actions">
                <button class="btn-xs" onclick="editHighlightNote('${item.id}')">${item.note ? 'Заметка' : '+ Заметка'}</button>
                <button class="btn-xs" onclick="jumpToPosition(${item.scrollY})">Перейти</button>
                <button class="btn-xs" onclick="deleteHighlight('${item.id}')">Удалить</button>
              </div>
            </div>
          `;
        }
      });
      container.innerHTML = html;
    }

    function jumpToPosition(scrollY) {
      closeDrawer();
      window.scrollTo({ top: scrollY || 0, behavior: 'smooth' });
    }

    function deleteBookmark(id) {
      const bms = getBookmarks().filter(b => b.id !== id);
      saveBookmarks(bms);
    }

    function deleteHighlight(id) {
      const hls = getHighlights().filter(h => h.id !== id);
      saveHighlights(hls);
      loadBook(true);
    }

    function editHighlightNote(id) {
      const hls = getHighlights();
      const item = hls.find(h => h.id === id);
      if (!item) return;
      editingHighlightId = id;
      document.getElementById('note-quote-preview').textContent = '«' + item.text.substring(0, 100) + '...»';
      document.getElementById('note-input').value = item.note || '';
      document.getElementById('modal-overlay').style.display = 'flex';
      document.getElementById('bm-modal').style.display = 'none';
      document.getElementById('note-modal').style.display = 'block';
    }

    // Load & Live Sync with Server
    async function loadBook(forceRender = false) {
      try {
        // 1. Check status first via relative URL (with cache-busting timestamp)
        const statusRes = await fetch('./status.json?_t=' + Date.now());
        if (!statusRes.ok) {
          throw new Error('HTTP ' + statusRes.status + ' (' + statusRes.statusText + ')');
        }
        const status = await statusRes.json();

        // 2. Update progress bar
        const pct = status.percentage || 0;
        document.getElementById('pfill').style.width = pct + '%';
        document.getElementById('ptext').textContent = pct + '%';
        document.getElementById('ppage').textContent = `Стр. ${status.last_completed_page || 0} / ${status.total_source_pages || 1200}`;

        // 3. Fetch book markdown ONLY if modified_time changed or not yet loaded
        const isModified = status.modified_time !== lastMtime;
        if (isModified || !cachedMarkdown) {
          const bookRes = await fetch('./sri_ramcharitmanas_russian_edition.md?_t=' + (status.modified_time || Date.now()));
          if (!bookRes.ok) {
            throw new Error('HTTP ' + bookRes.status + ' (' + bookRes.statusText + ')');
          }
          cachedMarkdown = await bookRes.text();
          lastMtime = status.modified_time;
          renderBookContent(cachedMarkdown);
        } else if (forceRender && cachedMarkdown) {
          // Re-render from cache (e.g. after highlight deletion)
          renderBookContent(cachedMarkdown);
        }
      } catch (err) {
        console.error('Ошибка загрузки книги:', err);
        if (isInitialLoad || !cachedMarkdown) {
          const contentEl = document.getElementById('content');
          contentEl.innerHTML = `
            <div style="text-align: center; padding: 48px 20px; color: var(--text-muted);">
              <div style="font-size: 2.2rem; margin-bottom: 12px; color: var(--accent);">⚠️</div>
              <h3 style="color: var(--accent); margin-bottom: 12px; font-size: 1.25rem;">Не удалось загрузить книгу</h3>
              <p style="margin-bottom: 20px; max-width: 500px; margin-left: auto; margin-right: auto; line-height: 1.6;">
                Произошла ошибка при загрузке данных: ${err.message || 'Ошибка сети'}.<br>
                Пожалуйста, проверьте интернет-соединение или попробуйте снова.
              </p>
              <button onclick="loadBook(true)" style="padding: 10px 24px; border-radius: 6px; border: 1px solid var(--accent); background: var(--accent); color: white; cursor: pointer; font-size: 1rem; font-weight: 500;">
                Повторить попытку
              </button>
            </div>
          `;
        }
      }
    }

    function renderBookContent(markdownText) {
      const contentEl = document.getElementById('content');
      contentEl.innerHTML = parseMarkdown(markdownText);
      buildTOC();
      renderContentHighlights();

      if (isInitialLoad) {
        isInitialLoad = false;
        const savedY = localStorage.getItem(KEY_SCROLL);
        if (savedY) {
          window.scrollTo({ top: parseFloat(savedY), behavior: 'instant' });
        }
      }
    }

    // Initialize Preferences
    const savedTheme = localStorage.getItem(KEY_THEME) || 'light';
    changeTheme(savedTheme);
    document.getElementById('theme-select').value = savedTheme;

    const savedSize = localStorage.getItem(KEY_FONTSIZE);
    if (savedSize) {
      currentFontSize = parseFloat(savedSize);
      document.getElementById('content').style.setProperty('--book-font-size', currentFontSize + 'rem');
    }

    renderLibrary();
    loadBook();

    // Auto-sync polling every 5s for growing book
    setInterval(() => loadBook(false), 5000);
  </script>
</body>
</html>
"""


class BookReaderHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler for the continuous book reader."""

    def __init__(self, translations_dir: Path, *args: Any, **kwargs: Any) -> None:
        self.translations_dir = translations_dir
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        clean_path = self.path.split("?")[0]

        if clean_path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(READER_HTML.encode("utf-8"))

        elif clean_path in ("/status.json", "/api/status"):
            stats = get_translation_stats(self.translations_dir)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode("utf-8"))

        elif clean_path in ("/sri_ramcharitmanas_russian_edition.md", "/api/book"):
            combined_file = self.translations_dir / "sri_ramcharitmanas_russian_edition.md"
            markdown = combined_file.read_text(encoding="utf-8") if combined_file.exists() else ""
            if "api/book" in clean_path:
                stats = get_translation_stats(self.translations_dir)
                data = {
                    "markdown": markdown,
                    **stats,
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.end_headers()
                self.wfile.write(markdown.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Silence default stderr logging
        pass


def run_reader_server(
    port: int = 8080,
    translations_dir: Path | None = None,
) -> None:
    """Start local book reader server."""
    t_dir = translations_dir or Path("data/direct_translation/translations")

    def handler_factory(*args: Any, **kwargs: Any) -> BookReaderHandler:
        return BookReaderHandler(t_dir, *args, **kwargs)

    server = HTTPServer(("127.0.0.1", port), handler_factory)
    print(f"Book Reader server running on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    import sys

    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8080
    run_reader_server(port=port_arg)
