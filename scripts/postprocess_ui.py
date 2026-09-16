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
.folder-icon{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center}.folder-icon img{width:26px;height:30px;display:block;object-fit:contain}
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

new_renderer = r"""var icon='<span class="book-icon" aria-hidden="true"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABoAAAAeCAYAAAAy2w7YAAAD1klEQVR42r1Wz0tjZxQ9937fe8nkJaSdkVq0m9JFpKAD7iZOK5lpEdpuCkNBuu1fUWbtpqB76U6EUrrQaRcKRVLERYXgRgS7LdiFjSN2mLwf+e7t4r1oYmJGx2m/zdu87517zz3n3EdLS0tar9eR83NwIrjNIQDOtV25XDaff/bFD0++evJ1vV5nALC7u7vYrv+GICjCOQfS1wShFImJOIxjfDTz8BEAv1arhQBg876PIAgQFAqQtgPdoh0iAhHBWg/GsABon52djZRKpWmrohARqAhEb0GdpkAgwEHgUmZobW3tRyKq2Q63b/qIigDwTp8/nzg4ONAUSNE3GyICM7/yg85J2s4VfRKoVQgCsgCg2vsiMyMMQ7RaL0HEgGratl7MQzUVQBAUYYzpLVJ7ZsciAkvZpW6QOI4xOTmJavUBojgBM6UYlGEpYIkRRRE2NjbQbDbhed65xAm9TaoqbF+vqhBxyOVyuHdvBFESg5ggmYYFClLAJ0YURrCefbVIgH4g5xx838f29jae/fwMzAxVQDulZhdJFcyM0dF3kcvlICKp6gaYGIOAjDGIogjVahUzMzNIkpQ66ZhSU6oNE+IkwfraOk5OTmDt8M7sVcZzzkHEZU+CUC8fKgwV7S37JkAiAs+z2N39HZubm9067RYdSBXGGLwzOoo7+TycG0zdlUBMjCgKUas9wtzcHKIoAjFDL3nFskErbGFlZQXHx8fwrNc9/+tRByK0Wi00m3+j7RyYCO6y10CIogjuqnykC1AdqLq2g+/52Nvbw87OzjkdcqlO0tRzQTGANQaqejPqUgML8vk8CoXC+WV3GUhSeTvn+pJlIJD22LlLVyJwXVX2dKQAVKGqfbMbCqTDYnFQfl3j/T6R4X86fO4R+m+B7IUJCSbLtc4+ymIC3aukUxBld6izQtBZ5WmMMUj6VEfpanAvX7xQyf6E0rVMF2K4BHR5dnQBpFEck4jcSQNEM4MzIwxbGPtgzFQ/foi8n8tEpVlS9HY0ZBukRanA8zzcffvuAYDEGJP+boVh6Kbu3zffPn36y/T09E/GGGZjBM514ryzP641C2OMBkHAANYBtJmYVBWWmWl+fv6vTx8//pKI2m9SAKpqHNKIt+VymYvFYsv3/fbs7KytVCp0eHiotwGoVCq0vLzc7tiNiGAnJib+2draei+O409KpdKvjUbjWpEy7DQaDQRBgPHxcV1YWICqKjWbzW8WFxe/Ozo6emtkZOQPay2LiBLRawMSEUQEQRBgf3///bGxMUsZlx+urq5+f3p6+iBJkqEpfNOTJAmmpqb+/BfyecEL+bzvwAAAAABJRU5ErkJggg==" alt="" width="26" height="30"></span>';"""
text = text[:start] + new_renderer + text[fallback_end:]

old_td = """tr.innerHTML='<td>'+img+fallback+'</td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>'+esc((m.title&&m.title!==f.name)?m.title:'')+'</small><div class="meta-line">'+esc(sub)+'</div></td><td class="author-cell">'+esc(a||'—')+'</td><td>'+esc(ext(f.name))+'</td><td>'+esc(size(f.size))+'</td><td>'+esc(displayDate(f.modified))+'</td>';"""
new_td = """tr.innerHTML='<td class="icon-cell">'+icon+'</td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>'+esc((m.title&&m.title!==f.name)?m.title:'')+'</small><div class="meta-line">'+esc(sub)+'</div></td><td class="author-cell">'+esc(a||'—')+'</td><td>'+esc(ext(f.name))+'</td><td>'+esc(size(f.size))+'</td><td>'+esc(displayDate(f.modified))+'</td>';"""
if old_td not in text:
    raise SystemExit("UI patch anchor missing: list row renderer")
text = text.replace(old_td, new_td, 1)


old_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}'
new_icon = '.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}.icon-cell{text-align:center;padding-left:4px!important;padding-right:4px!important}'
if old_icon in text:
    text = text.replace(old_icon, new_icon, 1)

# Use the same supplied book icon for folders, recolored yellow.
folder_old = """<td>📁</td>"""
folder_new = """<td class="icon-cell"><span class="folder-icon" aria-hidden="true"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABoAAAAeCAYAAAAy2w7YAAACbklEQVR42t2WvW8TQRDFf7O7Pn+cLyYoHVBQIBAVMhUSjfmoKBA1Lf8NoqGi4A9AiAaBqCjcQIFEQ0EBJUipIhQnztl3tzsUZ+OIxLlLYhq2Wd3pdt7Ne7NvRjbfXdZOt4mqIqxgifjgg93Znry4cP/7w+FwaABcuxMRd5uEEEBWAKUYMbC3O70FRIPBYALgVJUQAiHoqXFUtUxKBYUAFKPRaCNJkr6bpQvoCliTRbjZq9Hw+sttdOD4R0vKjBrGypVmK1JXh4o6WSxVDFINKm55ALDWohWUhqBVrBsE3CzNAyCTNCcdZ0v/WFFEhO5aC+cMVcm7ZQyrgi8CYqS8Y7LY57SKSO0acsu06XQjkl6rMkCRe2pIeTiQCKTjjL3d6RHUld8lvTbWmcrMXEVJscyX5JjXbgl10I4jumv/nDphvDNlPJog5nDBFTBG6J3tnKbqFGOk5H5eWXIsZutT12pHdOJmhVErGvTk1M1LvCjCkVaz/17VAtKT+VhtkNKHYDWdtQ4Q/xNQZeP7055r6LHoXwJl4ztYDCLijRWVmWKLPnQcBQUUFSOC0N5/2AEYEbLC271xjoa/Yp8ETxVfhK9APpfHiYifpJn9mD552+/3X1lrjbE24H15yNpynz9XLGutxnFs1uE1UDAbFx0g27/Szbv3bj8QkWKVBaCqFik5cd4HE3xIoygqdj9cc9k0l6jZONXslU1zWd/oFvu9wE0n+U6ctM5nWXYnSZL3daefKsdQVXq9c/rpWQygsrW19ch/vvnYNewZX4RvqmpkJdMkBK80242LRe6dzDK4+vPNpefWmhsiqzekL/bpj99gwA36MdaMxwAAAABJRU5ErkJggg==" alt="" width="26" height="30"></span></td>"""
if folder_old not in text:
    raise SystemExit("UI patch anchor missing: folder icon")
text = text.replace(folder_old, folder_new, 1)

path.write_text(text, encoding="utf-8")
print("Patched docs/index.html with the 30px Windows-style folder SVG and existing book icon.")
