#!/usr/bin/env python3
from pathlib import Path
import os

path = Path('docs/index.html')
text = path.read_text(encoding='utf-8')
api_url = os.environ.get('TANGTHU_STORY_API_URL', '').strip()

news_anchor = '<button class="tool" id="newsBtn"><span class="ico">📰</span><span class="lbl">Tin tức</span></button>'
shelf_anchor = '<button class="tool" id="shelfBtn"><span class="ico">📚</span><span class="lbl">Tủ sách</span></button>'
if 'id="storyBtn"' not in text:
    if news_anchor in text:
        text = text.replace(news_anchor, news_anchor + '\n    <button class="tool" id="storyBtn"><span class="ico">📖</span><span class="lbl">Truyện online</span></button>', 1)
    elif shelf_anchor in text:
        text = text.replace(shelf_anchor, shelf_anchor + '\n    <button class="tool" id="storyBtn"><span class="ico">📖</span><span class="lbl">Truyện online</span></button>', 1)
    else:
        raise SystemExit('Story UI patch anchor missing: shelfBtn/newsBtn')

anchor = '  function runSearch(){'
if anchor not in text:
    raise SystemExit('Story UI patch anchor missing: runSearch')

marker = '  function showStory(){'
if marker in text:
    start = text.index(marker)
    end = text.index('\n  }\n\n', start) + len('\n  }')
    text = text[:start] + text[end:]

story_fn = r'''  function showStory(){
    var state={branch:null,story:null,storyUrl:'',registered:false};
    var apiBase=__API_URL__;
    modal('ĐĂNG KÝ ĐỌC ONLINE',
      '<fieldset><legend>Thông tin truyện</legend>'+
      '<div id="storyInfo" class="story-info">Chưa đăng ký nội dung đọc</div>'+
      '<div class="story-nav">'+
      '<button id="storyPrevBtn" disabled>&lt; chương trước</button>'+
      '<button id="storyJumpBtn" disabled>đến chương ...</button>'+
      '<button id="storyNextBtn" disabled>chương sau &gt;</button>'+
      '</div></fieldset>'+
      '<fieldset><legend>Địa chỉ truyện</legend>'+
      '<div class="story-hint">Dán link truyện online rồi bấm <strong>Đăng ký</strong>.</div>'+
      '<input id="storyUrl" type="url" placeholder="https://..." disabled>'+
      '<div class="lookup-state" id="storyUrlStatus">Trước tiên hãy nhập địa chỉ tủ sách.</div>'+
      '<div class="modal-actions"><button id="storyRegisterBtn" disabled>Đăng ký</button></div>'+
      '</fieldset>'+
      '<fieldset><legend>Địa chỉ nhận sách</legend>'+
      '<div class="story-hint">Dán link thư mục Google Drive của tủ sách Tàng Thư.</div>'+
      '<input id="storyShelfUrl" type="url" placeholder="https://drive.google.com/drive/folders/...">'+
      '<div class="lookup-state" id="storyShelfStatus">Chưa kiểm tra tủ sách.</div>'+
      '</fieldset>'+
      '<fieldset><legend>Thông báo</legend>'+
      '<div id="storyBulletin" class="story-bulletin">Chưa có thông báo.</div></fieldset>');

    var branchesUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/branches.json';
    var branchesList=[];
    function loadJSON(url){return fetch(url,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();});}
    function branchFromUrl(value){
      var raw=String(value||'').trim(),id='';
      try{var u=new URL(raw),m=u.pathname.match(/\/folders\/([a-zA-Z0-9_-]+)/);id=m?m[1]:(u.searchParams.get('id')||'');}catch(e){}
      if(!id){var m2=raw.match(/^[a-zA-Z0-9_-]{10,}$/);if(m2)id=m2[0];}
      return id?(branchesList.find(function(b){return b.enabled!==false&&String(b.root_folder_id)===String(id);})||null):null;
    }
    function bulletin(s){$('storyBulletin').textContent=String(s||'');}
    function renderInfo(){
      var h=$('storyInfo');
      if(!state.registered||!state.story){h.textContent='Chưa đăng ký nội dung đọc';return;}
      var s=state.story,current=s.current_chapter!=null?s.current_chapter:(s.target_chapter_number!=null?s.target_chapter_number:'—'),total=s.total_chapters!=null?s.total_chapters:(s.chapters?s.chapters.length:'—');
      h.innerHTML='<div class="story-info-grid"><div><strong>'+esc(s.title||'Không có tên')+'</strong></div><div>Tác giả: '+esc(s.author||'—')+'</div><div>Nguồn: '+esc(s.site||s.source||state.storyUrl)+'</div><div>Chương hiện tại: '+esc(current)+' / '+esc(total)+'</div><div>Tủ nhận sách: '+esc(state.branch?(state.branch.display_name||state.branch.name||state.branch.id):'—')+'</div><div>File: <strong>0neStory.epub</strong></div><div>TOC: <strong>0neStoryTOC.epub</strong></div><div>Trạng thái: '+esc(s.status||'Đang đọc')+'</div></div>';
    }
    function update(){
      var ok=!!state.branch;
      $('storyUrl').disabled=!ok;
      $('storyRegisterBtn').disabled=!(ok&&$('storyUrl').value.trim());
      var nav=!!(state.registered&&state.story);
      $('storyPrevBtn').disabled=!nav;$('storyNextBtn').disabled=!nav;$('storyJumpBtn').disabled=!nav;
    }
    function call(action,payload){
      if(!apiBase)return Promise.reject(new Error('Story backend chưa được cấu hình.'));
      return fetch(apiBase.replace(/\/+$/,'')+'/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})}).then(function(r){return r.text().then(function(t){var d={};try{d=JSON.parse(t||'{}')}catch(e){throw new Error('Backend trả về dữ liệu không hợp lệ.');}if(!r.ok||d.ok===false)throw new Error(d.error||('HTTP '+r.status));return d;});});
    }
    function register(){
      var url=$('storyUrl').value.trim();if(!state.branch||!url)return;
      $('storyRegisterBtn').disabled=true;$('storyUrlStatus').textContent='Đang đăng ký và tạo chapter index...';bulletin('Đang xử lý đăng ký truyện...');
      call('register',{branch_id:state.branch.id,folder_id:state.branch.root_folder_id,story_url:url}).then(function(r){state.storyUrl=url;state.story=r.story||r;state.registered=true;renderInfo();bulletin(r.message||'Đăng ký truyện thành công.');$('storyUrlStatus').textContent='Đăng ký truyện thành công.';}).catch(function(e){state.registered=false;renderInfo();bulletin('Scrape/đăng ký thất bại: '+e.message);$('storyUrlStatus').textContent='Không thể đăng ký truyện.';}).finally(update);
    }
    function trigger(action,extra){
      if(!state.registered||!state.story)return;
      bulletin('Đang xử lý...');
      var p={story_id:state.story.story_id||state.story.id,branch_id:state.branch.id};Object.assign(p,extra||{});
      call(action,p).then(function(r){state.story=r.story||r;renderInfo();bulletin(r.message||'Đã cập nhật.');}).catch(function(e){bulletin('Lỗi: '+e.message);});
    }
    $('storyShelfUrl').oninput=function(){
      clearTimeout(window.__tangthuStoryShelfTimer);state.branch=null;state.registered=false;state.story=null;renderInfo();update();$('storyShelfStatus').textContent='Đang kiểm tra tủ sách...';
      window.__tangthuStoryShelfTimer=setTimeout(function(){var raw=$('storyShelfUrl').value.trim();if(!raw){$('storyShelfStatus').textContent='Chưa kiểm tra tủ sách.';update();return;}var b=branchFromUrl(raw);if(!b){$('storyShelfStatus').textContent='Tủ sách không tồn tại, vui lòng tạo tủ trước.';bulletin('Chưa có tủ sách nhận nội dung. Hãy tạo/đăng ký tủ sách trước.');update();return;}state.branch=b;$('storyShelfStatus').textContent='Tủ sách: '+(b.display_name||b.name||b.id);$('storyUrlStatus').textContent='Đã nhận ra tủ sách. Có thể nhập link truyện.';bulletin('Đã nhận ra tủ sách. Bạn có thể nhập link truyện.');update();},250);
    };
    $('storyShelfUrl').onkeydown=function(e){e.stopPropagation();};
    $('storyUrl').oninput=function(){$('storyUrlStatus').textContent=state.branch?'Đã nhận ra tủ sách. Bấm Đăng ký để xử lý truyện.':'Trước tiên hãy nhập địa chỉ tủ sách.';update();};
    $('storyUrl').onkeydown=function(e){e.stopPropagation();};
    $('storyRegisterBtn').onclick=register;
    $('storyPrevBtn').onclick=function(){trigger('previous');};
    $('storyNextBtn').onclick=function(){trigger('next');};
    $('storyJumpBtn').onclick=function(){var c=state.story&&(state.story.current_chapter||state.story.target_chapter_number),v=window.prompt('Đến chương số:',c||1);if(v===null)return;var n=parseInt(v,10);if(!Number.isFinite(n)||n<1){bulletin('Số chương không hợp lệ.');return;}trigger('jump',{chapter_number:n});};
    loadJSON(branchesUrl).then(function(c){branchesList=Array.isArray(c.branches)?c.branches:[];update();}).catch(function(e){$('storyShelfStatus').textContent='Không tải được danh sách tủ sách.';bulletin('Không tải được branches.json: '+e.message);});
  }
'''.replace('__API_URL__', repr(api_url))
text = text.replace(anchor, story_fn + '\n' + anchor, 1)

handler = "$('newsBtn').onclick=showNews;"
if handler not in text:
    handler = "$('shelfBtn').onclick=showShelf;"
    if handler not in text: raise SystemExit('Story UI patch anchor missing: toolbar handler')
if "$('storyBtn').onclick=showStory;" not in text:
    text=text.replace(handler, handler+"\n  $('storyBtn').onclick=showStory;",1)

if '.story-info-grid{' not in text:
    css=''' .story-hint{margin:0 0 8px;font-size:12px;color:#555}.story-info{min-height:70px}.story-info-grid{display:flex;flex-direction:column;gap:5px}.story-nav{display:flex;gap:7px;justify-content:center;flex-wrap:wrap;margin-top:10px}.story-nav button{min-width:112px}.story-bulletin{min-height:44px;padding:8px;background:#f5f5f5;border:1px solid #999;white-space:pre-wrap}'''
    text=text.replace('</style>',css+'\n</style>',1)

path.write_text(text,encoding='utf-8')
