#!/usr/bin/env python3
"""Add current-story restoration to the generated Story GUI.

Run this after scripts/postprocess_story.py. It does not replace the main Story UI.
"""
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

marker = """        state.branch=b;
        renderInfo('Đã nhận tủ: '+(b.display_name||b.name||b.id)+'. Có thể nhập link truyện.'); update();
"""
replacement = """        state.branch=b;
        if(apiBase){
          renderInfo('Đã nhận tủ: '+(b.display_name||b.name||b.id)+'. Đang khôi phục truyện đang đọc...');
          fetch(apiBase.replace(/\\\\/+$/,'')+'/story/current-by-user?user_id='+encodeURIComponent(b.id),{cache:'no-store'})
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
    raise SystemExit("Cannot find Story shelf handler anchor. Run this after postprocess_story.py.")

text = text.replace(marker, replacement, 1)

# Ensure cover styling exists. Keep this small and scoped.
if ".story-cover{" not in text:
    css = """
<style id="tangthu-story-current-css">
.story-info-body{display:grid;grid-template-columns:180px 1fr;gap:20px}
.story-cover{width:180px;height:270px;border:1px solid #888;background:#ddd;display:flex;align-items:center;justify-content:center;overflow:hidden}
.story-cover img{width:100%;height:100%;object-fit:cover}
.story-cover-empty{font-size:18px;color:#777}
</style>
"""
    if "</head>" not in text:
        raise SystemExit("Cannot find </head> for Story cover CSS.")
    text = text.replace("</head>", css + "\n</head>", 1)

path.write_text(text, encoding="utf-8")
