#!/usr/bin/env python3
"""
构建知识库静态 HTML 页面
将 knowledge_base 中所有文章和元数据打包进一个独立的 HTML 文件，
可以直接用浏览器打开，支持搜索和浏览。
"""
import json
import re
from pathlib import Path
from datetime import datetime

# 适配本地和 CI 环境
import os
_cwd = Path(os.getcwd())
KB_ROOT = _cwd / "knowledge_base"
if not KB_ROOT.exists():
    KB_ROOT = Path.home() / "Documents/内容知识库搭建/knowledge_base"
OUTPUT = KB_ROOT / "index.html"

def parse_frontmatter(text):
    result = {}
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            fm = text[3:end]
            for line in fm.strip().split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    result[key.strip()] = val.strip()
            content = text[end + 3:].strip()
            return result, content
    return result, text

def extract_summary_and_body(body):
    summary = ""
    full_body = body
    match = re.search(r'## 📝 摘要\n\n(.*?)(?=\n---\n)', body, re.DOTALL)
    if match:
        summary = match.group(1).strip()
        full_body = body[match.end():].strip()
        full_body = re.sub(r'^---\n*', '', full_body).strip()
        full_body = re.sub(r'^## 📄 原文\n*', '', full_body).strip()
    return summary, full_body

def scan_and_build():
    articles = []
    for file in sorted(KB_ROOT.rglob("*.md")):
        rel_path = str(file.relative_to(KB_ROOT))
        text = file.read_text(encoding="utf-8", errors="ignore")
        fm, body = parse_frontmatter(text)
        summary, full_body = extract_summary_and_body(body)
        
        articles.append({
            "path": rel_path,
            "title": fm.get("title", file.stem),
            "date": fm.get("date", ""),
            "source": fm.get("source", ""),
            "category": fm.get("category", ""),
            "summary_method": fm.get("summary_method", ""),
            "summary": summary,
            "content": full_body[:50000],  # 限制最大长度
            "word_count": len(full_body),
        })
    
    return articles

def escape_js(text):
    """转义文本用于 JS 模板字面量"""
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

data_json = json.dumps(scan_and_build(), ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📚 知识库</title>
<style>
:root {{
  --bg: #f8f9fa; --card-bg: #ffffff; --text: #2c3e50; --text-secondary: #6b7280;
  --border: #e5e7eb; --accent: #3b82f6; --accent-hover: #2563eb;
  --accent-light: #eff6ff; --tag-bg: #f3f4f6; --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 8px; --transition: 0.15s ease;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh; }}
.app {{ display: flex; height: 100vh; }}
.sidebar {{ width: 260px; background: var(--card-bg); border-right: 1px solid var(--border); overflow-y: auto; padding: 16px; flex-shrink: 0; }}
.main {{ flex: 1; overflow-y: auto; }}
.header {{ padding: 20px 28px 12px; position: sticky; top: 0; background: var(--bg); backdrop-filter: blur(10px); z-index: 10; }}
.header h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }}
.search-box {{ display: flex; gap: 8px; max-width: 500px; }}
.search-box input {{ flex: 1; padding: 8px 14px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 14px; outline: none; transition: border-color var(--transition); }}
.search-box input:focus {{ border-color: var(--accent); }}
.search-box button {{ padding: 8px 16px; background: var(--accent); color: #fff; border: none; border-radius: var(--radius); font-size: 13px; cursor: pointer; }}
.search-box button:hover {{ background: var(--accent-hover); }}
.sidebar h3 {{ font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin: 12px 0 6px; }}
.sidebar h3:first-child {{ margin-top: 0; }}
.sidebar .link {{ display: block; padding: 5px 8px; border-radius: 5px; font-size: 13px; color: var(--text); text-decoration: none; cursor: pointer; transition: background var(--transition); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.sidebar .link:hover, .sidebar .link.active {{ background: var(--accent-light); color: var(--accent); }}
.content {{ padding: 0 28px 40px; max-width: 900px; }}
.list-header {{ font-size: 13px; color: var(--text-secondary); margin-bottom: 10px; }}
.card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 20px; margin-bottom: 10px; cursor: pointer; transition: box-shadow var(--transition); }}
.card:hover {{ box-shadow: var(--shadow); }}
.card .card-title {{ font-size: 15px; font-weight: 600; margin-bottom: 3px; }}
.card .card-meta {{ font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; display: flex; gap: 12px; flex-wrap: wrap; }}
.card .card-summary {{ font-size: 13px; color: #4b5563; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
.article-detail {{ padding: 0 28px 40px; max-width: 900px; }}
.article-detail .back-btn {{ display: inline-flex; align-items: center; gap: 4px; padding: 6px 12px; margin-bottom: 16px; background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; color: var(--text); cursor: pointer; }}
.article-detail .back-btn:hover {{ border-color: var(--accent); }}
.article-meta {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 10px 0 16px; font-size: 13px; color: var(--text-secondary); }}
.summary-block {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: var(--radius); padding: 14px 18px; margin: 16px 0 20px; }}
.summary-block h3 {{ color: #92400e; font-size: 13px; margin-bottom: 4px; }}
.summary-block p {{ font-size: 14px; color: #78350f; margin: 0; line-height: 1.7; }}
.article-body {{ font-size: 15px; line-height: 1.8; }}
.article-body h1 {{ font-size: 20px; margin-top: 20px; margin-bottom: 10px; }}
.article-body h2 {{ font-size: 16px; margin-top: 20px; margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }}
.article-body h3 {{ font-size: 14px; margin-top: 16px; margin-bottom: 6px; }}
.article-body p {{ margin-bottom: 10px; }}
.article-body ul, .article-body ol {{ padding-left: 22px; margin-bottom: 10px; }}
.article-body li {{ margin-bottom: 3px; }}
.article-body code {{ padding: 2px 5px; border-radius: 3px; font-size: 13px; background: #f1f5f9; color: #e11d48; }}
.article-body pre {{ padding: 14px; border-radius: var(--radius); overflow-x: auto; background: #1e293b; color: #e2e8f0; font-size: 13px; line-height: 1.5; margin-bottom: 14px; }}
.article-body pre code {{ background: none; color: inherit; padding: 0; }}
.article-body blockquote {{ border-left: 3px solid var(--accent); padding: 6px 14px; margin: 10px 0; color: var(--text-secondary); background: var(--accent-light); border-radius: 0 var(--radius) var(--radius) 0; }}
.article-body table {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 13px; }}
.article-body th {{ background: #f8fafc; padding: 8px 10px; text-align: left; font-weight: 600; border: 1px solid var(--border); }}
.article-body td {{ padding: 6px 10px; border: 1px solid var(--border); }}
.article-body hr {{ border: none; border-top: 1px solid var(--border); margin: 20px 0; }}
.empty {{ text-align: center; padding: 60px 20px; color: var(--text-secondary); }}
.empty .icon {{ font-size: 40px; margin-bottom: 8px; }}
.tag {{ display: inline-block; padding: 2px 7px; border-radius: 3px; font-size: 11px; background: #e0e7ff; color: #4338ca; }}
    .tag-green {{ background: #d1fae5; color: #065f46; }}
@media (max-width: 768px) {{ .app {{ flex-direction: column; }} .sidebar {{ width: 100%; height: auto; border-right: none; border-bottom: 1px solid var(--border); }} .content, .article-detail {{ padding: 0 14px 28px; }} }}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar" id="sidebar"><h3>📂 分类</h3><div id="categoryList"></div></aside>
<div class="main" id="main">
<div class="header"><h1>📚 知识库</h1>
<div class="search-box"><input type="text" id="searchInput" placeholder="搜索文章标题、摘要、正文..." onkeyup="if(event.key==='Enter')performSearch()"><button onclick="performSearch()">🔍 搜索</button></div>
</div>
<div id="viewArea"></div>
</div>
</div>
<script>
const DATA = {data_json};
let currentView = 'list';
let selectedCategory = null;

function init() {{
  renderSidebar();
  renderList();
}}
function getCategories() {{
  const cats = {{}};
  DATA.forEach(a => {{
    if (!cats[a.category]) cats[a.category] = [];
    cats[a.category].push(a);
  }});
  return Object.entries(cats).sort((a,b) => a[0].localeCompare(b[0]));
}}
function renderSidebar() {{
  const el = document.getElementById('categoryList');
  const cats = getCategories();
  const total = DATA.length;
  let h = `<a class="link ${{!selectedCategory ? 'active' : ''}}" onclick="showAll()">📋 全部文章 (${{total}})</a>`;
  cats.forEach(([cat, arts]) => {{
    h += `<h3>📁 ${{escHtml(cat)}} (${{arts.length}})</h3>`;
    arts.forEach(a => {{
      h += `<a class="link" onclick="openArticle('${{escJs(a.path)}}')">${{escHtml(a.title)}}</a>`;
    }});
  }});
  el.innerHTML = h;
}}
function showAll() {{ selectedCategory = null; currentView = 'list'; renderSidebar(); renderList(); }}
function performSearch() {{
  const q = document.getElementById('searchInput').value.trim().toLowerCase();
  if (!q) {{ showAll(); return; }}
  const results = [];
  DATA.forEach(a => {{
    let score = 0;
    if (a.title.toLowerCase().includes(q)) score += 10;
    if (a.summary.toLowerCase().includes(q)) score += 5;
    if (a.content.toLowerCase().includes(q)) score += 2;
    if (score > 0) {{
      let snippet = '';
      const idx = a.content.toLowerCase().indexOf(q);
      if (idx >= 0) {{
        const start = Math.max(0, idx - 50);
        const end = Math.min(a.content.length, idx + q.length + 50);
        snippet = (start > 0 ? '...' : '') + a.content.slice(start, end).replace(/\\n/g, ' ') + (end < a.content.length ? '...' : '');
      }}
      results.push({{...a, score, snippet}});
    }}
  }});
  results.sort((a,b) => b.score - a.score);
  const area = document.getElementById('viewArea');
  let h = '<div class="content">';
  h += `<div class="list-header">搜索 "${{escHtml(q)}}"，共 ${{results.length}} 条结果</div>`;
  results.forEach(r => {{
    h += `<div class="card" onclick="openArticle('${{escJs(r.path)}}')">
      <div class="card-title">${{escHtml(r.title)}}</div>
      <div class="card-meta"><span>📅 ${{r.date}}</span><span>📂 ${{r.category}}</span><span>⭐ ${{r.score}}</span></div>
      <div class="card-summary">${{escHtml(r.snippet || r.summary)}}</div>
    </div>`;
  }});
  h += '</div>';
  area.innerHTML = h;
}}
function renderList() {{
  const area = document.getElementById('viewArea');
  let arts = DATA;
  if (selectedCategory) arts = arts.filter(a => a.category === selectedCategory);
  if (arts.length === 0) {{ area.innerHTML = '<div class="content"><div class="empty"><div class="icon">📭</div><p>暂无文章</p></div></div>'; return; }}
  let h = '<div class="content">';
  h += `<div class="list-header">共 <b>${{arts.length}}</b> 篇文章</div>`;
  arts.forEach(a => {{
    h += `<div class="card" onclick="openArticle('${{escJs(a.path)}}')">
      <div class="card-title">${{escHtml(a.title)}}</div>
      <div class="card-meta"><span>📅 ${{a.date}}</span><span>📂 ${{a.category}}</span><span class="tag">${{a.summary_method || 'auto'}}</span><span>${{a.word_count.toLocaleString()}} 字</span></div>
      <div class="card-summary">${{escHtml(a.summary || '暂无摘要')}}</div>
    </div>`;
  }});
  h += '</div>';
  area.innerHTML = h;
}}
function openArticle(path) {{
  const a = DATA.find(x => x.path === path);
  if (!a) return;
  currentView = 'detail';
  const area = document.getElementById('viewArea');
  let h = '<div class="article-detail">';
  h += `<button class="back-btn" onclick="goBack()">← 返回列表</button>`;
  h += `<h1>${{escHtml(a.title)}}</h1>`;
  h += `<div class="article-meta"><span>📅 ${{a.date}}</span><span>📂 ${{a.category}}</span>${{a.source && a.source.startsWith('http') ? `<span>🔗 <a href="${{escHtml(a.source)}}" target="_blank" style="color:var(--accent);text-decoration:none">${{escHtml(a.source)}}</a></span>` : `<span>🔗 ${{escHtml(a.source)}}</span>`}}<span class="tag tag-green">${{a.summary_method || 'auto'}}</span></div>`;
  if (a.summary) h += `<div class="summary-block"><h3>📝 AI 摘要</h3><p>${{escHtml(a.summary)}}</p></div>`;
  h += `<div class="article-body">${{renderMD(a.content)}}</div>`;
  h += '</div>';
  area.innerHTML = h;
  window.scrollTo(0, 0);
}}
function goBack() {{ currentView = 'list'; renderList(); window.scrollTo(0, 0); }}
function escHtml(t) {{ if (!t) return ''; const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }}
function escJs(t) {{ return t.replace(/\\\\/g, '\\\\\\\\').replace(/`/g, '\\\\`').replace(/\\$/g, '\\\\$'); }}
function renderMD(text) {{
  if (!text) return '';
  let h = text;
  h = h.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  h = h.replace(/\\*\\*\\*(.+?)\\*\\*\\*/g, '<strong><em>$1</em></strong>');
  h = h.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  h = h.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  h = h.replace(/!\\[([^\\]]*)\\]\\(([^)]+)\\)/g, '<img src="$2" alt="$1">');
  h = h.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
  h = h.replace(/^---$/gm, '<hr>');
  h = h.replace(/^- (.+)$/gm, '<li>$1</li>');
  h = h.replace(/(<li>.*<\\/li>\\n?)+/g, '<ul>$&</ul>');
  h = h.replace(/^\\|(.+)\\|$/gm, m => {{ const cells = m.split('|').filter(c => c.trim()); if (cells.every(c => c.trim().match(/^-+$/))) return ''; return '<tr>' + cells.map(c => `<td>${{c.trim()}}</td>`).join('') + '</tr>'; }});
  h = h.replace(/\\n\\n/g, '</p><p>');
  h = '<p>' + h + '</p>';
  return h;
}}
init();
</script>
</body>
</html>'''

OUTPUT.write_text(html, encoding="utf-8")
print(f"✅ 知识库 HTML 已生成: {OUTPUT}")
print(f"   共 {len(json.loads(data_json))} 篇文章")
