#!/usr/bin/env python3
"""Finalize Story GUI wording, restore current story, and add mobile layout.

Run this after scripts/postprocess_story.py.
This file is called by the Cloudflare Pages workflow.
"""
from pathlib import Path
import re

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

marker = """        state.branch=b;
        renderInfo('Đã nhận tủ: '+(b.display_name||b.name||b.id)+'. Có thể nhập link truyện.'); update();
"""
replacement = """        state.branch=b;
        if(apiBase){
          renderInfo('Đã nhận tủ: '+(b.display_name||b.name||b.id)+'. Đang khôi phục truyện đang đọc...');
          fetch(apiBase.replace(/\\/+$/,'')+'/story/current-by-user?user_id='+encodeURIComponent(b.id),{cache:'no-store'})
            .then(function(r){return r.text().then(function(t){
              var d={}; try{d=JSON.parse(t||'{}');}catch(e){throw new Error('Backend trả về dữ liệu không hợp lệ.');}
              if(!r.ok||d.ok===false) return null;
              return d;
            });})
            .then(function(d){
              if(d&&d.story){
                state.story=d.story;
                state.registered=true;
                state.storyUrl=d.story.source_url||'';
                $('storyUrl').value=state.storyUrl;
                renderInfo('Đã khôi phục truyện đang đọc.');
              }else{
                renderInfo('Đã nhận tủ: '+(b.display_name||b.name||b.id)+'. Có thể nhập link truyện.');
              }
              update();
            })
            .catch(function(e){
              renderInfo('Đã nhận tủ: '+(b.display_name||b.name||b.id)+'. Có thể nhập link truyện.');
              update();
            });
        }else{
          renderInfo('Đã nhận tủ: '+(b.display_name||b.name||b.id)+'. Có thể nhập link truyện.');
          update();
        }
"""
if marker not in text:
    raise SystemExit("Story shelf handler anchor missing. Run after postprocess_story.py.")
text = text.replace(marker, replacement, 1)

# postprocess_story.py creates these strings. Change only their GUI wording.
wording = {
    'Chọn chương ...': 'Đi đến',
    "Đến chương số:": "Đi đến số tương ứng trong mục lục",
}
for old, new in wording.items():
    if old not in text:
        raise SystemExit(f"Story wording anchor missing: {old}")
    text = text.replace(old, new, 1)

css = """
<style id="tangthu-story-current-css">
.story-info-body{min-width:0}
.story-details{min-width:0}
.story-row{min-width:0}
.story-row b{min-width:0;overflow-wrap:anywhere;word-break:break-word}
.story-message{min-width:0;overflow-wrap:anywhere;word-break:break-word}

@media(max-width:600px){
  .modal-backdrop{padding:6px}
  .modal{width:100%;max-width:100%;max-height:94vh}
  .modal-body{padding:8px}
  .story-info-panel{padding:8px;min-width:0}
  .story-info{min-height:0}
  .story-info-body{grid-template-columns:120px minmax(0,1fr);column-gap:10px;row-gap:8px;min-width:0}
  .story-cover{width:120px;height:180px;max-width:100%}
  .story-details{min-width:0;overflow:hidden}
  .story-details h2{font-size:20px;line-height:1.15;overflow-wrap:anywhere;word-break:break-word}
  .story-row{grid-template-columns:78px minmax(0,1fr);gap:5px;margin:6px 0;font-size:13px;align-items:start}
  .story-row span{min-width:0}
  .story-row b{min-width:0;overflow-wrap:anywhere;word-break:break-word}
  .story-message{grid-column:1/-1;margin-top:4px}
  .story-nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
  .story-nav button{min-width:0;width:100%;padding:5px 4px}
  .story-inputs fieldset{min-width:0;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:8px}
  .story-inputs input{min-width:0;width:100%}
  .story-inputs button{min-width:92px}
}

@media(max-width:360px){
  .story-info-body{grid-template-columns:1fr}
  .story-cover{width:120px;height:180px}
  .story-details h2{margin-top:2px}
}
</style>
"""

text = re.sub(r'\s*<style id="tangthu-story-current-css">.*?</style>\s*', "\n", text, count=1, flags=re.DOTALL)
if "</head>" not in text:
    raise SystemExit("Cannot find </head> for Story CSS.")
text = text.replace("</head>", css + "\n</head>", 1)
path.write_text(text, encoding="utf-8")
