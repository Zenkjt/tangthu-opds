#!/usr/bin/env python3
"""Finalize Story GUI wording, restore current story, add mobile layout,
and add the CrossPoint plugin maker button.

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
          fetch(apiBase.replace(/\\/+$/,'')+'/story/current-by-user?user_id='+encodeURIComponent(b.id)+'&folder_id='+encodeURIComponent(b.root_folder_id),{cache:'no-store'})
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

wording = {
    'Chọn chương ...': 'Đi đến',
    "Đến vị trí TOC:": "Nhập vị trí TOC:",
    'Tác giả:': 'Tải lên bởi:',
    'Chương hiện tại:': 'Đang đọc:',
}
for old, new in wording.items():
    if old not in text:
        raise SystemExit(f"Story wording anchor missing: {old}")
    text = text.replace(old, new, 1)

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

/* CrossPoint plugin maker */
#storyCrosspointBtn{white-space:nowrap}
.tt-crosspoint-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:10000;padding:16px;box-sizing:border-box}
.tt-crosspoint-modal{width:min(520px,100%);background:#fff;border:1px solid #999;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.25);padding:22px;box-sizing:border-box;color:#222}
.tt-crosspoint-modal-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}
.tt-crosspoint-modal h3{margin:0;font-size:20px}
.tt-crosspoint-close{flex:0 0 auto;width:34px;height:34px;padding:0;border:1px solid #aaa;border-radius:6px;background:#fff;font-size:23px;line-height:1;cursor:pointer}
.tt-crosspoint-modal p{margin:0 0 18px;color:#666}
.tt-crosspoint-modal label{display:block;font-weight:600;margin-bottom:7px}
.tt-crosspoint-modal input{width:100%;box-sizing:border-box;padding:12px;font-size:18px;border:1px solid #aaa;border-radius:6px}
.tt-crosspoint-actions{display:flex;gap:8px;justify-content:flex-start;margin-top:14px}
.tt-crosspoint-actions button{padding:11px 20px;font-size:16px;border:1px solid #888;border-radius:6px;background:#fff;cursor:pointer}
.tt-crosspoint-actions button:hover,.tt-crosspoint-close:hover{background:#f3f3f3}
#ttCrosspointCancel{margin-left:auto}
.tt-crosspoint-status{margin-top:12px;white-space:pre-line}
.tt-crosspoint-status.err{color:#a00}
@media(max-width:600px){
  .tt-crosspoint-backdrop{padding:8px}
  .tt-crosspoint-modal{padding:18px}
}
</style>
"""

text = re.sub(r'\s*<style id="tangthu-story-current-css">.*?</style>\s*', "\n", text, count=1, flags=re.DOTALL)
if "</head>" not in text:
    raise SystemExit("Cannot find </head> for Story CSS.")
text = text.replace("</head>", css + "\n</head>", 1)

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
    '<p>Tàng thư có thể tạo cho bạn tool plugin dùng trên Crosspoint để điều khiển chuyển chương sách đang đọc cho bạn. bạn tải về, giải nén, chép vào .crosspoint/plugin để sử dụng.</p>'+
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

crosspoint_script = r"""
<script id="tangthu-story-crosspoint-script">
(function(){
  var WORKER='https://tangthu-story-worker.mienluonngon.workers.dev';
  var manifests=[
    ['TTnextChap/manifest.json',{
      name:'TTnextChap',version:'1.0.0',
      description:'Tàng Thư — yêu cầu chuyển sang chương tiếp theo.'
    }],
    ['TTprevChap/manifest.json',{
      name:'TTprevChap',version:'1.0.0',
      description:'Tàng Thư — yêu cầu chuyển về chương trước.'
    }]
  ];

  function enc(s){return new TextEncoder().encode(s)}
  function u16(n){return new Uint8Array([n&255,n>>>8&255])}
  function u32(n){return new Uint8Array([n&255,n>>>8&255,n>>>16&255,n>>>24&255])}
  function cat(){
    var parts=[].slice.call(arguments),out=new Uint8Array(parts.reduce(function(n,p){return n+p.length},0)),o=0;
    parts.forEach(function(p){out.set(p,o);o+=p.length});
    return out;
  }
  function crc32(a){
    var c=0xffffffff;
    for(var i=0;i<a.length;i++){
      c^=a[i];
      for(var j=0;j<8;j++)c=(c>>>1)^(0xedb88320&-(c&1));
    }
    return (c^0xffffffff)>>>0;
  }
  function zipEntry(name,text,offset){
    var n=enc(name),d=enc(text),c=crc32(d);
    var local=cat(new Uint8Array([80,75,3,4]),u16(20),u16(0),u16(0),u16(0),u16(0),u32(c),u32(d.length),u32(d.length),u16(n.length),u16(0),n,d);
    var central=cat(new Uint8Array([80,75,1,2]),u16(20),u16(20),u16(0),u16(0),u16(0),u16(0),u32(c),u32(d.length),u32(d.length),u16(n.length),u16(0),u16(0),u16(0),u16(0),u32(0),u32(offset),n);
    return {local:local,central:central};
  }
  function makeZip(files){
    var offset=0,locals=[],centrals=[];
    files.forEach(function(pair){
      var e=zipEntry(pair[0],pair[1],offset);
      locals.push(e.local);centrals.push(e.central);offset+=e.local.length;
    });
    var central=cat.apply(null,centrals);
    var end=cat(new Uint8Array([80,75,5,6]),u16(0),u16(0),u16(files.length),u16(files.length),u32(central.length),u32(offset),u16(0));
    return cat.apply(null,locals.concat([central,end]));
  }
  function device(title,description,endpoint,shelf){
    return {
      title:title,description:description,
      browse:{
        format:'json',url:WORKER+endpoint,method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({shelf_no:shelf}),items:'items',page_size:1,
        fields:{title:'title',author:'author',id:'id',url:'url',description:'description'}
      }
    };
  }
  function makePlugin(shelf){
    var files=[];
    manifests.forEach(function(pair){files.push([pair[0],JSON.stringify(pair[1],null,2)+'\n'])});
    files.push(['TTnextChap/device.json',JSON.stringify(device('Tàng Thư Story NEXT','Yêu cầu Tàng Thư xử lý chương tiếp theo.','/story/crosspoint-next',shelf),null,2)+'\n']);
    files.push(['TTprevChap/device.json',JSON.stringify(device('Tàng Thư Story PREV','Yêu cầu Tàng Thư xử lý chương trước.','/story/crosspoint-previous',shelf),null,2)+'\n']);
    var guide=[
      'Gói zip này có 2 thư mục: TTnextChap và TTprevChap được thiết kế theo chuẩn plugin của crosspoint.',
      '- Bạn chép cả 2 thư mục vào .crosspoint/plugins/ trên thẻ nhớ máy đọc sách.',
      '- Để điều khiển trên máy đọc sách, bạn chạy plugin tương ứng, Tàng thư sẽ tải chương tiếp theo / chương trước về thay thế vào 0neStory.epub trên tủ sách của bạn.',
      '- Chuỗi sử dụng hợp lí trên máy đọc sách: vào OPDS tải 0neStory.epub --> vào plugins chạy TTnextChap --> đọc sách. Khi hết chương sẽ luôn có chương tiếp theo để tải về đọc.',
      '*Lưu ý: có thể plugin lỗi, bạn vào https://tangthu.pages.dev để kiểm tra và điều khiển trực tiếp nhé.',
      'Happy reading...',
      'Zenkjt'
    ].join('\n');
    files.push(['Huong dan su dung.txt',guide+'\n']);
    var blob=new Blob([makeZip(files)],{type:'application/zip'});
    var a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='Tàng thư controller plugin4crosspoint - shelf '+shelf+'.zip';
    a.click();
    setTimeout(function(){URL.revokeObjectURL(a.href)},1000);
  }
  function showMaker(){
    var old=document.getElementById('ttCrosspointBackdrop');
    if(old)old.remove();
    var back=document.createElement('div');
    back.id='ttCrosspointBackdrop';
    back.className='tt-crosspoint-backdrop';
    back.innerHTML=
      '<div class="tt-crosspoint-modal" role="dialog" aria-modal="true" aria-labelledby="ttCrosspointTitle">'+
        '<div class="tt-crosspoint-modal-head">'+
          '<h3 id="ttCrosspointTitle">Tạo CrossPoint plugin</h3>'+
          '<button id="ttCrosspointClose" class="tt-crosspoint-close" type="button" aria-label="Đóng" title="Đóng">×</button>'+
        '</div>'+
        '<p>Nhập số tủ. Tool sẽ tạo một ZIP chứa đầy đủ hai plugin <code>TTnextChap</code> và <code>TTprevChap</code>, kèm hướng dẫn sử dụng.</p>'+
        '<label for="ttCrosspointShelf">Số tủ</label>'+
        '<input id="ttCrosspointShelf" type="number" min="1" step="1" placeholder="Ví dụ: 3" autofocus>'+
        '<div class="tt-crosspoint-actions">'+
          '<button id="ttCrosspointMake" type="button">OK — tạo plugin</button>'+
          '<button id="ttCrosspointCancel" type="button">Cancel</button>'+
        '</div>'+
        '<div id="ttCrosspointStatus" class="tt-crosspoint-status"></div>'+
      '</div>';
    document.body.appendChild(back);
    var input=document.getElementById('ttCrosspointShelf');
    var make=document.getElementById('ttCrosspointMake');
    var cancel=document.getElementById('ttCrosspointCancel');
    var closeBtn=document.getElementById('ttCrosspointClose');
    var status=document.getElementById('ttCrosspointStatus');
    function closeModal(){
      document.removeEventListener('keydown',onModalKeydown);
      back.remove();
    }
    function onModalKeydown(e){
      if(e.key==='Escape'){e.preventDefault();closeModal();}
    }
    document.addEventListener('keydown',onModalKeydown);
    closeBtn.onclick=closeModal;
    cancel.onclick=closeModal;
    function submit(){
      var shelf=Number(input.value);
      if(!Number.isInteger(shelf)||shelf<1){
        status.className='tt-crosspoint-status err';
        status.textContent='Số tủ phải là số nguyên >= 1.';
        input.focus();
        return;
      }
      make.disabled=true;
      status.className='tt-crosspoint-status';
      status.textContent='Đang tạo plugin...';
      try{
        makePlugin(shelf);
        status.textContent='Đã tạo plugin cho tủ '+shelf+'.';
        setTimeout(closeModal,350);
      }catch(e){
        make.disabled=false;
        status.className='tt-crosspoint-status err';
        status.textContent='Không thể tạo plugin: '+e.message;
      }
    }
    make.onclick=submit;
    input.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();submit()}});
    back.addEventListener('click',function(e){if(e.target===back)closeModal()});
    setTimeout(function(){input.focus()},0);
  }
  function injectButton(){
    var nav=document.querySelector('.story-nav');
    if(!nav||document.getElementById('storyCrosspointBtn'))return;
    var btn=document.createElement('button');
    btn.id='storyCrosspointBtn';
    btn.type='button';
    btn.textContent='Crosspoint plugin';
    btn.disabled=false;
    btn.addEventListener('click',showMaker);
    nav.appendChild(btn);
  }
  var observer=new MutationObserver(injectButton);
  function start(){
    injectButton();
    observer.observe(document.body,{childList:true,subtree:true});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
</script>
"""

text = re.sub(r'\s*<script id="tangthu-story-help-script">.*?</script>\s*', '\n', text, count=1, flags=re.DOTALL)
text = re.sub(r'\s*<script id="tangthu-story-crosspoint-script">.*?</script>\s*', '\n', text, count=1, flags=re.DOTALL)
if "</body>" not in text:
    raise SystemExit("Cannot find </body> for Story scripts.")
text = text.replace("</body>", help_script + crosspoint_script + "\n</body>", 1)

path.write_text(text, encoding="utf-8")
