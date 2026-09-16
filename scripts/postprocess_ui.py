#!/usr/bin/env python3
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

# Replace the list's cover-thumbnail styling with compact book/folder icons.
old_css = """.cover{width:64px;height:90px;object-fit:cover;display:block;background:#eee;border:1px solid #777}
.cover-fallback{width:64px;height:90px;display:grid;place-items:center;background:#ddd;border:1px solid #777;font-weight:bold;font-size:12px;text-align:center}
"""
new_css = """.book-icon{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center}
.book-icon img{width:26px;height:30px;display:block;object-fit:contain}
.folder-icon{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center}
.folder-icon svg{width:30px;height:30px;display:block}
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
new_narrow = '.book-icon{width:30px;height:30px}.book-icon img{width:26px;height:30px}.folder-icon{width:30px;height:30px}.folder-icon svg{width:30px;height:30px}.name-cell strong'
if old_narrow not in text:
    raise SystemExit("UI patch anchor missing: narrow cover CSS")
text = text.replace(old_narrow, new_narrow, 1)

# Find the current list-book renderer without relying on Python's escaping
# syntax. The renderer is contained between these stable markers.
start_marker = "var img=f.cover?"
start = text.find(start_marker)
if start < 0:
    raise SystemExit("UI patch anchor missing: list book renderer start")

end_marker = "var fallback=f.cover?"
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("UI patch anchor missing: list book renderer end")

# Keep everything after the fallback declaration intact; replace the two
# cover variables with the supplied book icon.
fallback_end = text.find("\n", end)
if fallback_end < 0:
    raise SystemExit("UI patch anchor missing: list book renderer line end")

new_renderer = """var icon='<span class="book-icon" aria-hidden="true"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABoAAAAeCAYAAAAy2w7YAAAD1klEQVR42r1Wz0tjZxQ9937fe8nkJaSdkVq0m9JFpKAD7iZOK5lpEdpuCkNBuu1fUWbtpqB76U6EUrrQaRcKRVLERYXgRgS7LdiFjSN2mLwf+e7t4r1oYmJGx2m/zdu87517zzn3nEdLS0tar9eR83NwIrjNIQDOtV25XDaff/bFD0++evJ1vV5nALC7u7vYrv+GICjCOQfS1wShFImJOIxjfDTz8BEAv1arhQBg876PIAgQFAqQtgPdoh0iAhHBWg/GsABon52djZRKpWmrohARqAhEb0GdpkAgwEHgUmZobW3tRyKq2Q63b/qIigDwTp8/nzg4ONAUSNE3GyICM7/yg85J2s4VfRKoVQgCsgCg2vsiMyMMQ7RaL0HEgGratl7MQzUVQBAUYYzpLVJ7ZsciAkvZpW6QOI4xOTmJavUBojgBM6UYlGEpYIkRRRE2NjbQbDbhed65xAm9TaoqbF+vqhBxyOVyuHdvBFESg5ggmYYFClLAJ0YURrCefbVIgH4g5xx838f29jae/fwMzAxVQDulZhdJFcyM0dF3kcvlICKp6gaYGIOAjDGIogjVahUzMzNIkpQ66ZhSU6oNE+IkwfraOk5OTmDt8M7sVcZzzkHEZU+CUC8fKgwV7S37JkAiAs+z2N39HZubm9067RYdSBXGGLwzOoo7+TycG0zdlUBMjCgKUas9wtzcHKIoAjFDL3nFskErbGFlZQXHx8fwrNc9/+tRByK0Wi00m3+j7RyYCO6y10CIogjuqnykC1AdqLq2g+/52Nvbw87OzjkdcqlO0tRzQTGANQaqejPqUgML8vk8CoXC+WV3GUhSeTvn+pJlIJD22LlLVyJwXVX2dKQAVKGqfbMbCqTDYnFQfl3j/T6R4X86fO4R+m+B7IUJCSbLtc4+ymIC3aukUxBld6izQtBZ5WmMMUj6VEfpanAvX7xQyf6E0rVMF2K4BHR5dnQBpFEck4jcSQNEM4MzIwxbGPtgzFQ/foi8n8tEpVlS9HY0ZBukRanA8zzcffvuAYDEGJP+boVh6Kbu3zffPn36y/T09E/GGGZjBM514ryzP641C2OMBkHAANYBtJmYVBWWmWl+fv6vTx8//pKI2m9SAKpqHNKIt+VymYvFYsv3/fbs7KytVCp0eHiotwGoVCq0vLzc7tiNiGAnJib+2draei+O409KpdKvjUbjWpEy7DQaDQRBgPHxcV1YWICqKjWbzW8WFxe/Ozo6emtkZOQPay2LiBLRawMSEUQEQRBgf3///bGxMUsZlx+urq5+f3p6+iBJkqEpfNOTJAmmpqb+/BfyecEL+bzvwAAAAABJRU5ErkJggg==" alt="" width="26" height="30"></span>';"""
text = text[:start] + new_renderer + text[fallback_end:]

# Replace the folder emoji renderer. Locate the exact if(f.folder) block
# and change only its generated first cell.
folder_start = text.find("if(f.folder){")
if folder_start < 0:
    raise SystemExit("UI patch anchor missing: folder renderer start")

folder_end = text.find("else {", folder_start)
if folder_end < 0:
    raise SystemExit("UI patch anchor missing: folder renderer end")

folder_block = text[folder_start:folder_end]
if "📁" not in folder_block:
    raise SystemExit("UI patch anchor missing: folder emoji")

folder_icon = '<span class="folder-icon" aria-hidden="true"><svg viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg"><path d="M2 7h9l3 3h14v16H2z" fill="#c0c0c0" stroke="#000" stroke-width="2"/><path d="M2 10h26" stroke="#fff" stroke-width="2"/></svg></span>'
folder_block = folder_block.replace('<td>📁</td>', '<td class="icon-cell">'+folder_icon+'</td>', 1)
text = text[:folder_start] + folder_block + text[folder_end:]

old_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}'
new_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}.icon-cell{text-align:center;padding-left:4px!important;padding-right:4px!important}'
if old_icon in text:
    text = text.replace(old_icon, new_icon, 1)

path.write_text(text, encoding="utf-8")
print("Patched docs/index.html with the 30px Windows-style folder SVG and existing book icon.")
