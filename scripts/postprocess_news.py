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

if "function showNews(){" not in text:
    news_fn = r'''  function showNews(){
    var state={canonicalUrl:'',name:'',exists:false};

    modal('THƯ VIỆN NGUỒN TIN',
      '<fieldset><legend>Thêm nguồn mới</legend>'+
      '<label for="newsSourceUrl">URL nguồn</label>'+
      '<input id="newsSourceUrl" type="url" placeholder="https://..." value="">'+
      '<div class="news-note">Không bắt buộc</div>'+
      '<div class="lookup-state" id="newsCheck">Chưa kiểm tra nguồn.</div>'+ 
      '</fieldset>'+ 
      '<fieldset><legend>Nguồn đang có</legend>'+ 
      '<div id="newsSources" class="news-sources"><div class="empty">Đang tải danh sách nguồn tin...</div></div>'+ 
      '</fieldset>'+ 
      '<fieldset><legend>Tủ nhận tin</legend>'+ 
      '<label for="newsShelf">Tủ sách</label>'+ 
      '<select id="newsShelf" style="width:100%;height:34px"></select>'+ 
      '<div class="lookup-state" id="newsSummary">Tổng cộng: 0 nguồn · 0 bài</div>'+ 
      '</fieldset>'+ 
      '<fieldset><legend>Chế độ bản tin</legend>'+ 
      '<label><input type="radio" name="newsMode" value="text" checked> Chỉ chữ (tối đa 200 bài)</label>'+ 
      '<label><input type="radio" name="newsMode" value="images"> Có hình (tối đa 100 bài)</label>'+ 
      '</fieldset>'+ 
      '<div class="modal-actions"><button id="newsCheckBtn">Kiểm tra</button></div>');

    var configUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/config_news_sources.json';
    var subsUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/config_news_subscriptions.json';
    var branchesUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/branches.json';
    var registry=[],subscriptions=[],branchesList=[];

    function canonicalize(value){
      try{
        var u=new URL(value);
        if(u.protocol!=='http:' && u.protocol!=='https:')return '';
        u.hash='';
        if(u.pathname.length>1)u.pathname=u.pathname.replace(/\/+$/,'');
        return u.toString();
      }catch(e){return '';}
    }

    function sourceName(value){
      try{
        var host=new URL(value).hostname.toLowerCase().replace(/^www\./,'');
        var first=host.split('.')[0];
        if(!first)return host;
        if(['bbc','cnn','npr','abc','nbc','cbs','cnbc','dw','ap','afp','ansa','upi'].indexOf(first)>=0)return first.toUpperCase();
        return first.replace(/[-_]+/g,' ').replace(/\b\w/g,function(c){return c.toUpperCase();});
      }catch(e){return '';}
    }

    function setCheck(message){$('newsCheck').textContent=message;}

    function refreshAddButton(){
      var btn=$('newsCheckBtn');
      if(state.exists){btn.textContent='Nguồn đã có';btn.disabled=true;}
      else if(state.canonicalUrl && state.name){btn.textContent='Thêm nguồn';btn.disabled=false;}
      else{btn.textContent='Kiểm tra';btn.disabled=false;}
    }

    function loadJSON(url){
      return fetch(url,{cache:'no-store'}).then(function(r){
        if(!r.ok)throw new Error('HTTP '+r.status);
        return r.json();
      });
    }

    function renderSources(){
      var host=$('newsSources');
      var active=registry.filter(function(s){return s.enabled!==false;});
      if(!active.length){host.innerHTML='<div class="empty">Chưa có nguồn tin.</div>';updateSummary();return;}
      host.innerHTML=active.map(function(s){
        var sub=subscriptions.find(function(x){return x.source_id===s.id && x.enabled!==false;});
        var count=sub ? Number(sub.article_count)||10 : 10;
        return '<div class="news-source-row">'+
          '<label class="news-source-main"><input class="news-source-check" type="checkbox" data-id="'+esc(s.id)+'" '+(sub?'checked':'')+'>'+ 
          '<span><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.name)+'</a></span></label>'+ 
          '<input class="news-count" data-id="'+esc(s.id)+'" type="number" min="5" max="25" value="'+count+'" '+(sub?'':'disabled')+'></div>';
      }).join('');

      host.querySelectorAll('.news-source-check').forEach(function(box){
        box.onchange=function(){
          var input=host.querySelector('.news-count[data-id="'+box.dataset.id+'"]');
          if(input)input.disabled=!box.checked;
          updateSummary();
        };
      });
      host.querySelectorAll('.news-count').forEach(function(input){input.oninput=updateSummary;});
      updateSummary();
    }

    function updateSummary(){
      var count=0,total=0;
      document.querySelectorAll('#newsSources .news-source-check').forEach(function(box){
        if(!box.checked)return;
        count++;
        var input=document.querySelector('#newsSources .news-count[data-id="'+box.dataset.id+'"]');
        total+=Math.max(5,Math.min(25,Number(input&&input.value)||10));
      });
      $('newsSummary').textContent='Tổng cộng: '+count+' nguồn · '+total+' bài';
    }

    function renderShelves(){
      var select=$('newsShelf');
      var active=branchesList.filter(function(b){return b.enabled!==false;});
      select.innerHTML=active.length ? active.map(function(b){return '<option value="'+esc(b.id)+'">'+esc(b.display_name||b.id)+'</option>';}).join('') : '<option value="">Chưa có tủ sách khả dụng</option>';
    }

    $('newsSourceUrl').oninput=function(){
      state={canonicalUrl:'',name:'',exists:false};
      setCheck('Chưa kiểm tra nguồn.');
      refreshAddButton();
    };

    $('newsCheckBtn').onclick=function(){
      var raw=$('newsSourceUrl').value.trim();
      if(state.canonicalUrl && !state.exists){
        var body='- URL: '+state.canonicalUrl+'\n- Hành động: add';
        var issue='https://github.com/Zenkjt/tangthu-opds/issues/new?title='+encodeURIComponent('[TIN TỨC] '+state.name)+'&body='+encodeURIComponent(body);
        window.open(issue,'_blank','noopener');
        setCheck('Đã mở yêu cầu thêm nguồn. Sau khi workflow xử lý xong, bấm Refresh để cập nhật danh sách.');
        $('newsCheckBtn').disabled=true;
        return;
      }
      var canonical=canonicalize(raw);
      if(!canonical){state={canonicalUrl:'',name:'',exists:false};setCheck('URL không hợp lệ.');refreshAddButton();return;}
      var name=sourceName(canonical);
      var existing=registry.find(function(s){return canonicalize(s.url)===canonical;});
      state={canonicalUrl:canonical,name:name,exists:!!existing};
      setCheck(existing ? 'Tên nguồn: '+existing.name+' · Nguồn này đã có trong thư viện.' : 'Tên nguồn: '+name+' · Nguồn này chưa có trong thư viện.');
      refreshAddButton();
    };

    Promise.all([loadJSON(configUrl),loadJSON(subsUrl),loadJSON(branchesUrl)])
      .then(function(data){
        registry=Array.isArray(data[0].sources)?data[0].sources:[];
        subscriptions=Array.isArray(data[1].subscriptions)?data[1].subscriptions:[];
        branchesList=Array.isArray(data[2].branches)?data[2].branches:[];
        renderSources();renderShelves();
      })
      .catch(function(err){$('newsSources').innerHTML='<div class="empty">Không tải được Bulletin Registry: '+esc(String(err))+'</div>';});
  }

'''
    text = text.replace(anchor, news_fn + anchor, 1)

marker = "  $('shelfBtn').onclick=showShelf;"
if "  $('newsBtn').onclick=showNews;" not in text:
    if marker not in text: raise SystemExit("News UI patch anchor missing: shelfBtn handler")
    text = text.replace(marker, marker + "\n  $('newsBtn').onclick=showNews;", 1)

if ".news-source-row{" not in text:
    css = r''' .news-sources{display:flex;flex-direction:column;gap:4px}.news-source-row{display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px dotted #aaa}.news-source-main{display:flex;align-items:center;gap:7px;min-width:0;flex:1}.news-source-main span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.news-source-main a{color:#000}.news-count{width:70px;height:30px;padding:3px 5px;border:2px solid #777;border-right-color:#fff;border-bottom-color:#fff;background:#fff}.news-count:disabled{background:#ddd;color:#777}.news-note{margin-top:6px;font-size:12px;color:#555}'''
    text = text.replace("</style>", css + "</style>", 1)

path.write_text(text, encoding="utf-8")
