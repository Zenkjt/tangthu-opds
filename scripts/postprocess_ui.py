#!/usr/bin/env python3
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

old_css = """.cover{width:64px;height:90px;object-fit:cover;display:block;background:#eee;border:1px solid #777}
.cover-fallback{width:64px;height:90px;display:grid;place-items:center;background:#ddd;border:1px solid #777;font-weight:bold;font-size:12px;text-align:center}
"""
new_css = """.book-icon{width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center}
.book-icon svg{width:20px;height:20px;display:block;shape-rendering:crispEdges}
"""
if old_css not in text:
    raise SystemExit("UI patch anchor missing: list cover CSS")
text = text.replace(old_css, new_css, 1)

old_header = '<th style="width:78px">Bìa</th>'
new_header = '<th style="width:34px"> </th>'
if old_header not in text:
    raise SystemExit("UI patch anchor missing: list cover header")
text = text.replace(old_header, new_header, 1)

old_mobile = '.books th:nth-child(1),.books td:nth-child(1){width:74px}'
new_mobile = '.books th:nth-child(1),.books td:nth-child(1){width:34px}'
if old_mobile not in text:
    raise SystemExit("UI patch anchor missing: mobile cover column")
text = text.replace(old_mobile, new_mobile, 1)

old_narrow = '.cover{width:58px;height:82px}.cover-fallback{width:58px;height:82px}.name-cell strong'
new_narrow = '.book-icon{width:18px;height:18px}.book-icon svg{width:18px;height:18px}.name-cell strong'
if old_narrow not in text:
    raise SystemExit("UI patch anchor missing: narrow cover CSS")
text = text.replace(old_narrow, new_narrow, 1)

old_js = r"""var img=f.cover?'<img class="cover" loading="lazy" src="'+esc(f.cover)+'" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\'/>':'<span class="cover-fallback">'+esc(ext(f.name))+'</span>';
        var fallback=f.cover?'<span class="cover-fallback" style="display:none">'+esc(ext(f.name))+'</span>':'';"""
new_js = r"""var icon='<span class="book-icon" aria-hidden="true"><svg viewBox="0 0 20 20" role="img" focusable="false"><path fill="#ffffff" d="M5 4h13v14H5z"/><path fill="#000000" d="M3 2h13v14H5c-1.1 0-2-.9-2-2V2z"/><path fill="#ffffff" d="M6 5h7v1H6zm0 3h7v1H6zm0 3h7v1H6z"/><path fill="#404040" d="M3 15h13v1H5c-1.1 0-2-.9-2-2z"/></svg></span>';"""
if old_js not in text:
    raise SystemExit("UI patch anchor missing: list cover renderer")
text = text.replace(old_js, new_js, 1)

old_td = """tr.innerHTML='<td>'+img+fallback+'</td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>'+esc((m.title&&m.title!==f.name)?m.title:'')+'</small><div class="meta-line">'+esc(sub)+'</div></td><td class="author-cell">'+esc(a||'—')+'</td><td>'+esc(ext(f.name))+'</td><td>'+esc(size(f.size))+'</td><td>'+esc(displayDate(f.modified))+'</td>';"""
new_td = """tr.innerHTML='<td class="icon-cell">'+icon+'</td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>'+esc((m.title&&m.title!==f.name)?m.title:'')+'</small><div class="meta-line">'+esc(sub)+'</div></td><td class="author-cell">'+esc(a||'—')+'</td><td>'+esc(ext(f.name))+'</td><td>'+esc(size(f.size))+'</td><td>'+esc(displayDate(f.modified))+'</td>';"""
if old_td not in text:
    raise SystemExit("UI patch anchor missing: list row renderer")
text = text.replace(old_td, new_td, 1)

old_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}.icon-cell{text-align:center;padding-left:4px!important;padding-right:4px!important}'
new_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}.icon-cell{text-align:center;padding-left:4px!important;padding-right:4px!important}'
if old_icon not in text:
    raise SystemExit("UI patch anchor missing: row CSS")
# Keep the existing row CSS unchanged; this guard ensures the current file is the expected version.

path.write_text(text, encoding="utf-8")
print("Patched docs/index.html: replaced the list icon with a simple black/white Windows 3.x-style book icon.")
