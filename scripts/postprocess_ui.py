#!/usr/bin/env python3
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

old_css = """.cover{width:64px;height:90px;object-fit:cover;display:block;background:#eee;border:1px solid #777}
.cover-fallback{width:64px;height:90px;display:grid;place-items:center;background:#ddd;border:1px solid #777;font-weight:bold;font-size:12px;text-align:center}
"""
new_css = """.book-icon{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center}
.book-icon img{width:26px;height:30px;display:block;object-fit:contain}
.folder-icon{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;font-size:30px;line-height:30px}
"""
if old_css not in text:
    raise SystemExit("UI patch anchor missing: list cover CSS")
text = text.replace(old_css, new_css, 1)

old_header = '<th style="width:78px">Bìa</th>'
new_header = '<th style="width:44px"> </th>'
if old_header not in text:
    raise SystemExit("UI patch anchor missing: list cover header")
text = text.replace(old_header, new_header, 1)

old_mobile = '.books th:nth-child(1),.books td:nth-child(1){width:74px}'
new_mobile = '.books th:nth-child(1),.books td:nth-child(1){width:44px}'
if old_mobile not in text:
    raise SystemExit("UI patch anchor missing: mobile cover column")
text = text.replace(old_mobile, new_mobile, 1)

old_narrow = '.cover{width:58px;height:82px}.cover-fallback{width:58px;height:82px}.name-cell strong'
new_narrow = '.book-icon{width:30px;height:30px}.book-icon img{width:26px;height:30px}.name-cell strong'
if old_narrow not in text:
    raise SystemExit("UI patch anchor missing: narrow cover CSS")
text = text.replace(old_narrow, new_narrow, 1)

old_js = r"""var img=f.cover?'<img class="cover" loading="lazy" src="'+esc(f.cover)+'" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\'/>':'<span class="cover-fallback">'+esc(ext(f.name))+'</span>';
        var fallback=f.cover?'<span class="cover-fallback" style="display:none">'+esc(ext(f.name))+'</span>':'';"""
new_js = r"""var icon='<span class="book-icon" aria-hidden="true"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABoAAAAeCAYAAAAy2w7YAAAD1klEQVR42r1Wz0tjZxQ9937fe8nkJaSdkVq0m9JFpKAD7iZOK5lpEdpuCkNBuu1fUWbtpqB76U6EUrrQaRcKRVLERYXgRgS7LdiFjSN2mLwf+e7t4r1oYmJGx2m/zdu87517zz3n3EdLS0tar9eR83NwIrjNIQDOtV25XDaff/bFD0++evJ1vV5nALC7u7vYrv+GICjCOQfS1wShFImJOIxjfDTz8BEAv1arhQBg876PIAgQFAqQtgPdoh0iAhHBWg/GsABon52djZRKpWmrohARqAhEb0GdpkAgwEHgUmZobW3tRyKq2Q63b/qIigDwTp8/nzg4ONAUSNE3GyICM7/yg85J2s4VfRKoVQgCsgCg2vsiMyMMQ7RaL0HEgGratl7MQzUVQBAUYYzpLVJ7ZsciAkvZpW6QOI4xOTmJavUBojgBM6UYlGEpYIkRRRE2NjbQbDbhed65xAm9TaoqbF+vqhBxyOVyuHdvBFESg5ggmYYFClLAJ0YURrCefbVIgH4g5xx838f29jae/fwMzAxVQDulZhdJFcyM0dF3kcvlICKp6gaYGIOAjDGIogjVahUzMzNIkpQ66ZhSU6oNE+IkwfraOk5OTmDt8M7sVcZzzkHEZU+CUC8fKgwV7S37JkAiAs+z2N39HZubm9067RYdSBXGGLwzOoo7+TycG0zdlUBMjCgKUas9wtzcHKIoAjFDL3nFskErbGFlZQXHx8fwrNc9/+tRByK0Wi00m3+j7RyYCO6y10CIogjuqnykC1AdqLq2g+/52Nvbw87OzjkdcqlO0tRzQTGANQaqejPqUgML8vk8CoXC+WV3GUhSeTvn+pJlIJD22LlLVyJwXVX2dKQAVKGqfbMbCqTDYnFQfl3j/T6R4X86fO4R+m+B7IUJCSbLtc4+ymIC3aukUxBld6izQtBZ5WmMMUj6VEfpanAvX7xQyf6E0rVMF2K4BHR5dnQBpFEck4jcSQNEM4MzIwxbGPtgzFQ/foi8n8tEpVlS9HY0ZBukRanA8zzcffvuAYDEGJP+boVh6Kbu3zffPn36y/T09E/GGGZjBM514ryzP641C2OMBkHAANYBtJmYVBWWmWl+fv6vTx8//pKI2m9SAKpqHNKIt+VymYvFYsv3/fbs7KytVCp0eHiotwGoVCq0vLzc7tiNiGAnJib+2draei+O409KpdKvjUbjWpEy7DQaDQRBgPHxcV1YWICqKjWbzW8WFxe/Ozo6emtkZOQPay2LiBLRawMSEUQEQRBgf3///bGxMUsZlx+urq5+f3p6+iBJkqEpfNOTJAmmpqb+/BfyecEL+bzvwAAAAABJRU5ErkJggg==" alt="" width="26" height="30"></span>';"""
if old_js not in text:
    raise SystemExit("UI patch anchor missing: list cover renderer")
text = text.replace(old_js, new_js, 1)

old_td = """tr.innerHTML='<td>'+img+fallback+'</td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>'+esc((m.title&&m.title!==f.name)?m.title:'')+'</small><div class="meta-line">'+esc(sub)+'</div></td><td class="author-cell">'+esc(a||'—')+'</td><td>'+esc(ext(f.name))+'</td><td>'+esc(size(f.size))+'</td><td>'+esc(displayDate(f.modified))+'</td>';"""
new_td = """tr.innerHTML='<td class="icon-cell">'+icon+'</td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>'+esc((m.title&&m.title!==f.name)?m.title:'')+'</small><div class="meta-line">'+esc(sub)+'</div></td><td class="author-cell">'+esc(a||'—')+'</td><td>'+esc(ext(f.name))+'</td><td>'+esc(size(f.size))+'</td><td>'+esc(displayDate(f.modified))+'</td>';"""
if old_td not in text:
    raise SystemExit("UI patch anchor missing: list row renderer")
text = text.replace(old_td, new_td, 1)

old_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}'
new_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}.icon-cell{text-align:center;padding-left:4px!important;padding-right:4px!important}'
if old_icon in text:
    text = text.replace(old_icon, new_icon, 1)

path.write_text(text, encoding="utf-8")
print("Patched docs/index.html: replaced list cover thumbnails with a small black/white Windows 3.x-style book icon.")
