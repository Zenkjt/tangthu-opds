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

# GUI wording and current-reading position.
wording = {
    'Chọn chương ...': 'Đi đến',
    "Đến chương số:": "Đi đến số tương ứng trong mục lục",
    'Tác giả:': 'Tải lên bởi:',
    'Chương hiện tại:': 'Đang đọc:',
}
for old, new in wording.items():
    if old not in text:
        raise SystemExit(f"Story wording anchor missing: {old}")
    text = text.replace(old, new, 1)

# "Đang đọc" must use the Story TOC position, not the source site's chapter number.
old_current = """var current=s.current_chapter!=null?s.current_chapter:
        (s.target_chapter_number!=null?s.target_chapter_number:'—');"""
new_current = """var current=s.current_toc_index!=null?s.current_toc_index:
        (s.current_chapter!=null?s.current_chapter:
        (s.target_chapter_number!=null?s.target_chapter_number:'—'));
      var currentEntry=(s.chapters||[]).find(function(c){
        return Number(c.toc_index)===Number(current);
      });
      var chapterTitle=currentEntry&&currentEntry.title
        ?currentEntry.title
        :(s.current_chapter_title||s.target_chapter_title||'');"""
if old_current not in text:
    raise SystemExit("Story current-position anchor missing.")
text = text.replace(old_current, new_current, 1)

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

.story-help-panel{margin:0 0 12px;padding:10px;border:1px solid #888;line-height:1.5;max-height:55vh;overflow:auto}
.story-help-panel p{margin:0 0 9px}
.story-help-panel p:last-child{margin-bottom:0}
.story-help-panel code{font-family:Consolas,monospace}
#storyHelpBtn{min-width:28px;height:24px;padding:0 7px;margin:0 4px 0 0;background:#c0c0c0;color:#000;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;font-weight:bold;cursor:pointer;flex:0 0 auto}
#storyHelpBtn:active{border-color:#555 #fff #fff #555;padding:1px 6px 0 8px}
</style>
"""

text = re.sub(r'\s*<style id="tangthu-story-current-css">.*?</style>\s*', "\n", text, count=1, flags=re.DOTALL)
if "</head>" not in text:
    raise SystemExit("Cannot find </head> for Story CSS.")
text = text.replace("</head>", css + "\n</head>", 1)

# Add a ? button to the Story modal title and show the exact user-supplied help text.
help_script = r"""
<script id="tangthu-story-help-script">
(function(){
  var HELP_ID='storyHelpBtn', PANEL_ID='storyHelpPanel';
  var HELP_HTML=
    '<p><strong>Đăng ký để đọc truyện online trong tủ sách của bạn.</strong></p>'+
    '<p>Theo thiết kế sau khi đăng ký thành công, Tàng thư sẽ tải chương truyện đầu tiên về file <code>0neStory.epub</code> và mục lục sách về file <code>0neStoryTOC.epub</code> trong thư mục chia sẻ (tủ sách) của bạn để sẵn sàng tải về máy đọc sách qua OPDS.</p>'+
    '<p><strong>Chuẩn bị:</strong> thư mục Google chia sẻ của bạn cần được để chế độ public - Anyone with the link can EDIT (để Tàng Thư có thể cập nhật file truyện).</p>'+
    '<p>Dán địa chỉ thư mục Google vào ô "Địa chỉ nhận sách", tên tủ sẽ tự động được hiển thị&nbsp; Dán địa chỉ sách vào ô "Địa chỉ truyện online" và bấm đăng ký, truyện đã sẵn sàng trong tủ của bạn.</p>'+
    '<p>Bấm "Chương tiếp", "Đi đến..." hay "Chương trước" Tàng thư sẽ tải chương tương ứng về thay thế vào <code>0neStory.epub</code> trong tủ.</p>'+
    '<p>Sau này muốn chọn truyện khác, bạn quay lại đây, dán địa chỉ tủ sách và thực hiện điều chỉnh.</p>'+
    '<p>Happy reading.<br>Zenkjt</p>';

  function isStoryModal(){
    var title=document.getElementById('modalTitle');
    if(!title)return false;
    return (title.textContent||'').trim()==='ĐĂNG KÝ ĐỌC ONLINE';
  }

  function sync(){
    var title=document.getElementById('modalTitle');
    var body=document.getElementById('modalBody');
    var close=document.getElementById('modalClose');
    if(!title||!body||!close)return;

    var btn=document.getElementById(HELP_ID);
    var panel=document.getElementById(PANEL_ID);

    if(!isStoryModal()){
      if(btn)btn.remove();
      if(panel)panel.remove();
      return;
    }

    if(!btn){
      btn=document.createElement('button');
      btn.id=HELP_ID;
      btn.type='button';
      btn.textContent='?';
      btn.title='Hướng dẫn';
      btn.onclick=function(){
        var p=document.getElementById(PANEL_ID);
        if(p)p.hidden=!p.hidden;
      };
      close.parentNode.insertBefore(btn,close);
    }

    if(!panel){
      panel=document.createElement('div');
      panel.id=PANEL_ID;
      panel.className='story-help-panel';
      panel.hidden=true;
      panel.innerHTML=HELP_HTML;
      body.insertBefore(panel,body.firstChild);
    }
  }

  var observer=new MutationObserver(sync);
  function start(){
    sync();
    var title=document.getElementById('modalTitle');
    if(title)observer.observe(title,{childList:true,subtree:true,characterData:true});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
</script>
"""

# Keep exactly one copy of this script when the postprocessor is rerun.
text = re.sub(r'\s*<script id="tangthu-story-help-script">.*?</script>\s*', '\n', text, count=1, flags=re.DOTALL)
if "</body>" not in text:
    raise SystemExit("Cannot find </body> for Story help script.")
text = text.replace("</body>", help_script + "\n</body>", 1)

path.write_text(text, encoding="utf-8")
