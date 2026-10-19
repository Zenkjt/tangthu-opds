#!/usr/bin/env python3
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

tool_anchor = '<button class="tool" id="shelfBtn"><span class="ico">📚</span><span class="lbl">Tủ sách</span></button>'
if 'id="newsBtn"' not in text:
    if tool_anchor not in text:
        raise SystemExit("News UI patch anchor missing: shelfBtn")
    text = text.replace(tool_anchor, tool_anchor + '\n    <button class="tool" id="newsBtn"><span class="ico">📰</span><span class="lbl">Tin tức</span></button>', 1)

anchor = "  function showShelf(){"
if anchor not in text:
    raise SystemExit("News UI patch anchor missing: showShelf")

if "function showNews(){" in text:
    start = text.index("  function showNews(){")
    end = text.index("\n  }\n\n", start) + len("\n  }")
    text = text[:start] + text[end:]

news_fn = r'''  function showNews(){
    var state={branch:null,canonicalUrl:'',name:'',exists:false};

    modal('THƯ VIỆN NGUỒN TIN',
      '<fieldset><legend>Thêm nguồn tin (không bắt buộc)</legend>'+
      '<div class="news-url-row"><div class="news-url-field">'+
      '<label for="newsSourceUrl">URL nguồn</label>'+
      '<input id="newsSourceUrl" type="url" placeholder="https://..." value="">'+
      '</div><button id="newsCheckBtn" class="news-inline-btn">Kiểm tra</button></div>'+
      '<div class="lookup-state" id="newsCheck">Chưa kiểm tra nguồn.</div></fieldset>'+

      '<fieldset><legend>Nguồn đang có</legend>'+
      '<div class="news-hint">Chọn nguồn tin và số bài báo lấy về mỗi ngày (5-25 bài)</div>'+
      '<div id="newsSources" class="news-sources"><div class="empty">Đang tải danh sách nguồn tin...</div></div>'+
      '<div class="lookup-state" id="newsSummary">Tổng cộng: 0 nguồn · 0 bài</div></fieldset>'+

      '<fieldset><legend>Chế độ bản tin</legend>'+
      '<label><input type="radio" name="newsMode" value="text" checked> Chỉ chữ (tối đa 200 bài)</label>'+
      '<label><input type="radio" name="newsMode" value="images"> Có hình (tối đa 100 bài)</label>'+
      '<div class="lookup-state news-warning" id="newsModeWarning"></div></fieldset>'+

      '<fieldset><legend>Địa chỉ nhận tin</legend>'+
      '<div class="news-hint">Dán địa chỉ tủ sách của bạn bên dưới và chọn đăng ký, chú ý Google folder phải để chế độ public/everyone can edit.</div>'+
      '<input id="newsShelfUrl" type="url" placeholder="https://drive.google.com/drive/folders/...">'+
      '<div class="lookup-state" id="newsShelfStatus">Chưa kiểm tra tủ sách.</div>'+
      '<div class="modal-actions news-register-actions"><button id="newsRegisterBtn" disabled>Đăng ký</button></div>'+
      '<div class="lookup-state" id="newsRegisterResult"></div></fieldset>');

    var configUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/config_news_sources.json';
    var subsUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/config_news_subscriptions.json';
    var branchesUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/branches.json';
    var registry=[],subscriptions=[],branchesList=[];

    function canonicalize(value){
      try{var u=new URL(value);if(u.protocol!=='http:'&&u.protocol!=='https:')return '';u.hash='';if(u.pathname.length>1)u.pathname=u.pathname.replace(/\/+$/,'');return u.toString();}catch(e){return '';}
    }
    function sourceName(value){
      try{var host=new URL(value).hostname.toLowerCase().replace(/^www\./,'');var first=host.split('.')[0];if(!first)return host;if(['bbc','cnn','npr','abc','nbc','cbs','cnbc','dw','ap','afp','ansa','upi'].indexOf(first)>=0)return first.toUpperCase();return first.replace(/[-_]+/g,' ').replace(/\b\w/g,function(c){return c.toUpperCase();});}catch(e){return '';}
    }
    function loadJSON(url){return fetch(url,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();});}
    function selectedSources(){var out=[];document.querySelectorAll('#newsSources .news-source-check').forEach(function(box){if(!box.checked)return;var input=document.querySelector('#newsSources .news-count[data-id="'+box.dataset.id+'"]');out.push({id:box.dataset.id,count:Math.max(5,Math.min(25,Number(input&&input.value)||5))});});return out;}
    function selectedTotal(){return selectedSources().reduce(function(n,x){return n+x.count;},0);}
    function updateRegisterState(){$('newsRegisterBtn').disabled=!(state.branch&&selectedSources().length);}
    function enforceMode(){var total=selectedTotal(),img=document.querySelector('input[name="newsMode"][value="images"]'),txt=document.querySelector('input[name="newsMode"][value="text"]');if(total>100&&img.checked){img.checked=false;txt.checked=true;$('newsModeWarning').textContent='Có hình tối đa 100 bài. Đã tự chuyển về “Chỉ chữ”; nếu muốn dùng hình, vui lòng xoá bớt tổng số bài xuống 100 hoặc ít hơn.';}else{$('newsModeWarning').textContent=total>100?'Tổng số đang trên 100 bài nên chỉ có thể dùng chế độ “Chỉ chữ”.':'';} }
    function updateSummary(){$('newsSummary').textContent='Tổng cộng: '+selectedSources().length+' nguồn · '+selectedTotal()+' bài';enforceMode();updateRegisterState();}
    function branchFromUrl(value){var raw=value.trim(),id='';try{var u=new URL(raw),m=u.pathname.match(/\/folders\/([a-zA-Z0-9_-]+)/);id=m?m[1]:(u.searchParams.get('id')||'');}catch(e){}if(!id){var m=raw.match(/^[a-zA-Z0-9_-]{10,}$/);if(m)id=m[0];}return id?(branchesList.find(function(b){return b.enabled!==false&&b.root_folder_id===id;})||null):null;}

    function renderSources(){
      var host=$('newsSources'),active=registry.filter(function(s){return s.enabled!==false;});
      if(!active.length){host.innerHTML='<div class="empty">Chưa có nguồn tin.</div>';updateSummary();return;}
      var branchId=state.branch?state.branch.id:'';
      host.innerHTML=active.map(function(s){var sub=subscriptions.find(function(x){return x.branch_id===branchId&&x.source_id===s.id&&x.enabled!==false;}),count=sub?Number(sub.article_count)||5:5;return '<div class="news-source-row"><label class="news-source-main"><input class="news-source-check" type="checkbox" data-id="'+esc(s.id)+'" '+(sub?'checked':'')+'><span><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.name)+'</a></span></label><input class="news-count" data-id="'+esc(s.id)+'" type="number" min="5" max="25" value="'+count+'" '+(sub?'':'disabled')+'></div>';}).join('');
      host.querySelectorAll('.news-source-check').forEach(function(box){box.onchange=function(){var input=host.querySelector('.news-count[data-id="'+box.dataset.id+'"]');if(input)input.disabled=!box.checked;$('newsRegisterResult').textContent='';$('newsRegisterBtn').disabled=false;updateSummary();};});
      host.querySelectorAll('.news-count').forEach(function(input){input.oninput=function(){$('newsRegisterResult').textContent='';$('newsRegisterBtn').disabled=false;updateSummary();};});
      updateSummary();
    }

    function checkShelf(){
      var raw=$('newsShelfUrl').value.trim();state.branch=branchFromUrl(raw);
      if(!raw){$('newsShelfStatus').textContent='Chưa kiểm tra tủ sách.';renderSources();return;}
      if(!state.branch){$('newsShelfStatus').textContent='Tủ sách không tồn tại, vui lòng tạo tủ mới hoặc chọn tủ khác';$('newsRegisterResult').textContent='';renderSources();updateRegisterState();return;}
      $('newsShelfStatus').textContent='Tủ sách: '+(state.branch.display_name||state.branch.id);$('newsRegisterResult').textContent='';renderSources();updateRegisterState();
    }

    $('newsSourceUrl').oninput=function(){state.canonicalUrl='';state.name='';state.exists=false;$('newsCheck').textContent='Chưa kiểm tra nguồn.';$('newsCheckBtn').textContent='Kiểm tra';$('newsCheckBtn').disabled=false;};
    $('newsCheckBtn').onclick=function(){
      var canonical=canonicalize($('newsSourceUrl').value.trim());
      if(!canonical){$('newsCheck').textContent='URL không hợp lệ.';return;}
      var name=sourceName(canonical),existing=registry.find(function(s){return canonicalize(s.url)===canonical;});state.canonicalUrl=canonical;state.name=name;state.exists=!!existing;
      if(existing){$('newsCheck').textContent='Tên nguồn tin: '+existing.name+' · Nguồn này đã có trong thư viện.';$('newsCheckBtn').textContent='Đã có';$('newsCheckBtn').disabled=true;return;}
      $('newsCheck').textContent='Tên nguồn tin: '+name+' · Nguồn này chưa có trong thư viện.';$('newsCheckBtn').textContent='Thêm nguồn';
      $('newsCheckBtn').onclick=function(){var body='- URL: '+state.canonicalUrl+'\n- Hành động: add';var issue='https://github.com/Zenkjt/tangthu-opds/issues/new?title='+encodeURIComponent('[TIN TỨC] '+state.name)+'&body='+encodeURIComponent(body);window.open(issue,'_blank','noopener');$('newsCheck').textContent='Đã mở yêu cầu thêm nguồn. Sau khi workflow xử lý xong, bấm Refresh để cập nhật danh sách.';$('newsCheckBtn').disabled=true;};
    };
    $('newsShelfUrl').oninput=function(){$('newsRegisterResult').textContent='';$('newsRegisterBtn').disabled=false;clearTimeout(window.__tangthuNewsShelfTimer);window.__tangthuNewsShelfTimer=setTimeout(checkShelf,250);};
    document.querySelectorAll('input[name="newsMode"]').forEach(function(radio){radio.onchange=function(){$('newsRegisterResult').textContent='';$('newsRegisterBtn').disabled=false;if(this.value==='images'&&selectedTotal()>100){$('newsModeWarning').textContent='Chế độ có hình tối đa 100 bài. Vui lòng xoá bớt tổng số bài xuống 100 hoặc ít hơn.';$('newsModeWarning').style.display='block';document.querySelector('input[name="newsMode"][value="text"]').checked=true;return;}enforceMode();};});

    $('newsRegisterBtn').onclick=function(){
      var branch=state.branch,selected=selectedSources(),mode=document.querySelector('input[name="newsMode"]:checked').value,total=selectedTotal();
      if(!branch||!selected.length)return;
      if(mode==='images'&&total>100){$('newsModeWarning').textContent='Chế độ có hình tối đa 100 bài. Vui lòng xoá bớt tổng số bài xuống 100 hoặc ít hơn.';return;}
      selected.forEach(function(item){var source=registry.find(function(s){return s.id===item.id;}),body='- Tủ sách ID: '+branch.id+'\n- Source ID: '+item.id+'\n- Số bài: '+item.count+'\n- Chế độ: '+mode+'\n- Hành động: add',issue='https://github.com/Zenkjt/tangthu-opds/issues/new?title='+encodeURIComponent('[TIN TỨC SUB] '+(source?source.name:item.id))+'&body='+encodeURIComponent(body);window.open(issue,'_blank','noopener');});
      $('newsRegisterResult').textContent=(branch.display_name||branch.id)+' đăng ký nhận tin thành công';$('newsRegisterBtn').disabled=true;
    };

    Promise.all([loadJSON(configUrl),loadJSON(subsUrl),loadJSON(branchesUrl)]).then(function(data){registry=Array.isArray(data[0].sources)?data[0].sources:[];subscriptions=Array.isArray(data[1].subscriptions)?data[1].subscriptions:[];branchesList=Array.isArray(data[2].branches)?data[2].branches:[];renderSources();updateRegisterState();}).catch(function(err){$('newsSources').innerHTML='<div class="empty">Không tải được Bulletin Registry: '+esc(String(err))+'</div>';updateRegisterState();});
  }

'''
text = text.replace(anchor, news_fn + anchor, 1)

marker = "$('shelfBtn').onclick=showShelf;"
if "  $('newsBtn').onclick=showNews;" not in text:
    if marker not in text:
        raise SystemExit("News UI patch anchor missing: shelfBtn handler")
    text = text.replace(marker, marker + "\n  $('newsBtn').onclick=showNews;", 1)

if ".news-source-row{" not in text:
    css = r''' .news-url-row{display:flex;align-items:flex-end;gap:10px}.news-url-field{flex:1;min-width:0}.news-inline-btn{height:38px;min-width:120px}.news-sources{display:flex;flex-direction:column;gap:4px}.news-source-row{display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px dotted #aaa}.news-source-main{display:flex;align-items:center;gap:7px;min-width:0;flex:1}.news-source-main span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.news-source-main a{color:#000}.news-count{width:70px;height:30px;padding:3px 5px;border:2px solid #777;border-right-color:#fff;border-bottom-color:#fff;background:#fff}.news-count:disabled{background:#ddd;color:#777}.news-hint{margin:0 0 8px;font-size:12px;color:#555}.news-warning{margin-top:7px}.news-register-actions{justify-content:flex-end}'''
    text = text.replace("</style>", css + "</style>", 1)

path.write_text(text, encoding="utf-8")
