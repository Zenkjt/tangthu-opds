#!/usr/bin/env python3
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

tool_anchor = '<button class="tool" id="shelfBtn"><span class="ico">📚</span><span class="lbl">Tủ sách</span></button>'
if 'id="newsBtn"' not in text:
    if tool_anchor not in text:
        raise SystemExit("News UI patch anchor missing: shelfBtn")
    text = text.replace(
        tool_anchor,
        tool_anchor + '\n    <button class="tool" id="newsBtn"><span class="ico">📰</span><span class="lbl">Tin tức</span></button>',
        1,
    )

anchor = "  function showShelf(){"
if anchor not in text:
    raise SystemExit("News UI patch anchor missing: showShelf")

if "function showNews(){" in text:
    start = text.index("  function showNews(){")
    end = text.index("\n  }\n\n", start) + len("\n  }")
    text = text[:start] + text[end:]

news_fn = r'''  function showNews(){
    var draft={branch:null,mode:'text',sources:[],selected:{},touched:{},pending:{}};
    var guard=function(e){
      var t=e.target;
      if(!t||!t.closest)return;
      var input=t.closest('#newsSourceUrl, #newsShelfUrl, #newsSources input');
      if(input&&(e.key==='Backspace'||e.key==='Delete'))e.stopImmediatePropagation();
    };
    window.addEventListener('keydown',guard,true);

    modal('THƯ VIỆN NGUỒN TIN',
      '<fieldset><legend>Thêm nguồn tin (không bắt buộc)</legend>'+
      '<div class="news-url-row"><div class="news-url-field">'+
      '<label for="newsSourceUrl">URL nguồn</label>'+
      '<input id="newsSourceUrl" type="url" placeholder="https://..." value="" autocomplete="off">'+
      '</div><button id="newsCheckBtn" class="news-inline-btn" type="button">Kiểm tra</button></div>'+
      '<div class="lookup-state" id="newsCheck">Chưa kiểm tra nguồn.</div></fieldset>'+

      '<fieldset><legend>Nguồn đang có</legend>'+
      '<div class="news-hint">Chọn nguồn tin và số bài báo lấy về mỗi ngày (5-25 bài)</div>'+
      '<div id="newsSources" class="news-sources"><div class="empty">Đang tải danh sách nguồn tin...</div></div>'+
      '<div class="lookup-state" id="newsSummary">Tổng cộng: 0 nguồn · 0 bài</div></fieldset>'+

      '<fieldset><legend>Chế độ bản tin</legend>'+
      '<label><input type="radio" name="newsMode" value="text" checked> Chỉ chữ (tối đa 200 bài)</label>'+
      '<label><input type="radio" name="newsMode" value="images"> Có hình (tối đa 100 bài)</label>'+
      '<div class="news-warning" id="newsModeWarning"></div></fieldset>'+

      '<fieldset><legend>Địa chỉ nhận tin</legend>'+
      '<div class="news-hint">Dán địa chỉ tủ sách của bạn bên dưới và chọn đăng ký, chú ý Google folder phải để chế độ public/everyone can edit.</div>'+
      '<input id="newsShelfUrl" type="url" placeholder="https://drive.google.com/drive/folders/..." autocomplete="off">'+
      '<div class="lookup-state" id="newsShelfStatus">Tủ sách nhận tin</div>'+
      '<div class="modal-actions news-register-actions"><button id="newsRegisterBtn" disabled type="button">Đăng ký</button></div>'+
      '</fieldset>');

    var configUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/config_news_sources.json';
    var subsUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/config_news_subscriptions.json';
    var branchesUrl='https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main/config/branches.json';
    var newsWorkerUrl='https://tangthu-news-worker.mienluonngon.workers.dev';
    var registry=[],subscriptions=[],branchesList=[];

    function canonicalize(value){
      try{
        var u=new URL(String(value||'').trim());
        if(u.protocol!=='http:'&&u.protocol!=='https:')return '';
        u.hash='';
        if(u.pathname.length>1)u.pathname=u.pathname.replace(/\/+$/,'');
        return u.toString();
      }catch(e){return '';}
    }

    function repairMojibake(value){
      var text=String(value||'');
      if(!/[ÃÂ]/.test(text))return text;
      try{
        var bytes=Uint8Array.from(text,function(ch){return ch.charCodeAt(0)&255;});
        return new TextDecoder('utf-8',{fatal:true}).decode(bytes);
      }catch(e){return text;}
    }

    function displaySourceName(value){
      var text=repairMojibake(value).replace(/\s+/g,' ').trim();
      return text.length>52?text.slice(0,51).trimEnd()+'…':text;
    }

    function workerPost(path,body){
      return fetch(newsWorkerUrl+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
        .then(function(r){
          return r.json().catch(function(){return {};}).then(function(d){
            if(!r.ok||d.ok===false)throw new Error(d.error||('HTTP '+r.status));
            return d;
          });
        });
    }

    function loadJSON(url){
      return fetch(url,{cache:'no-store'}).then(function(r){
        if(!r.ok)throw new Error('HTTP '+r.status);
        return r.json();
      });
    }

    function selectedSources(){
      return draft.sources.filter(function(s){
        return draft.selected[s.id]&&draft.selected[s.id].checked;
      }).map(function(s){
        var n=Number(draft.selected[s.id].count);
        if(!Number.isFinite(n))n=5;
        n=Math.max(5,Math.min(25,Math.round(n)));
        return {id:s.id,count:n};
      });
    }

    function selectedTotal(){
      return selectedSources().reduce(function(total,item){return total+item.count;},0);
    }

    function updateRegisterState(){
      var btn=$('newsRegisterBtn');
      if(!btn)return;
      btn.disabled=!(draft.branch&&selectedSources().length);
    }

    function enforceMode(){
      var total=selectedTotal();
      var img=document.querySelector('input[name="newsMode"][value="images"]');
      var txt=document.querySelector('input[name="newsMode"][value="text"]');
      var warning=$('newsModeWarning');
      if(!img||!txt||!warning)return;
      if(total>200){
        draft.mode='text';
        txt.checked=true;
        img.checked=false;
        warning.textContent='Tổng số bài tối đa là 200. Vui lòng giảm số bài.';
      }else if(draft.mode==='images'&&total>100){
        draft.mode='text';
        txt.checked=true;
        img.checked=false;
        warning.textContent='Có hình tối đa 100 bài. Đã tự chuyển về “Chỉ chữ”; nếu muốn dùng hình, vui lòng giảm tổng số bài xuống 100 hoặc ít hơn.';
      }else{
        warning.textContent='';
      }
    }

    function updateSummary(){
      var summary=$('newsSummary');
      if(summary)summary.textContent='Tổng cộng: '+selectedSources().length+' nguồn · '+selectedTotal()+' bài';
      enforceMode();
      updateRegisterState();
    }

    function branchFromUrl(value){
      var raw=String(value||'').trim(),id='';
      try{
        var u=new URL(raw),m=u.pathname.match(/\/folders\/([a-zA-Z0-9_-]+)/);
        id=m?m[1]:(u.searchParams.get('id')||'');
      }catch(e){}
      if(!id){
        var m=raw.match(/^[a-zA-Z0-9_-]{10,}$/);
        if(m)id=m[0];
      }
      return id?(branchesList.find(function(b){return b.enabled!==false&&b.root_folder_id===id;})||null):null;
    }

    function syncSelectionForBranch(){
      draft.sources.forEach(function(s){
        if(draft.touched[s.id])return;
        var sub=draft.branch?subscriptions.find(function(x){
          return x.branch_id===draft.branch.id&&x.source_id===s.id&&x.enabled!==false;
        }):null;
        draft.selected[s.id]={checked:!!sub,count:sub?(Number(sub.article_count)||5):5};
      });
    }

    function renderSources(){
      var host=$('newsSources');
      if(!host)return;
      var active=draft.sources.filter(function(s){return s.enabled!==false;});
      if(!active.length){
        host.innerHTML='<div class="empty">Chưa có nguồn tin.</div>';
        updateSummary();
        return;
      }

      host.innerHTML=active.map(function(s){
        var sel=draft.selected[s.id]||{checked:false,count:5};
        var name=displaySourceName(s.name||s.url);
        var fullName=repairMojibake(s.name||s.url);
        var count=Math.max(5,Math.min(25,Number(sel.count)||5));
        return '<div class="news-source-row">'+
          '<label class="news-source-main">'+
          '<input class="news-source-check" type="checkbox" data-id="'+esc(s.id)+'" '+(sel.checked?'checked':'')+'>'+
          '<span title="'+esc(fullName)+'"><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(name)+'</a></span>'+
          '</label>'+
          '<input class="news-count" data-id="'+esc(s.id)+'" type="number" min="5" max="25" value="'+count+'" '+(sel.checked?'':'disabled')+'>'+
          '</div>';
      }).join('');

      host.querySelectorAll('.news-source-check').forEach(function(box){
        box.addEventListener('change',function(e){
          e.stopPropagation();
          var id=box.dataset.id;
          var input=host.querySelector('.news-count[data-id="'+id+'"]');
          if(!draft.selected[id])draft.selected[id]={checked:false,count:5};
          draft.selected[id].checked=box.checked;
          draft.touched[id]=true;
          if(input)input.disabled=!box.checked;
          if(draft.branch)$('newsShelfStatus').textContent='Tủ sách: '+(draft.branch.display_name||draft.branch.id);
          else $('newsShelfStatus').textContent='Tủ sách nhận tin';
          updateSummary();
        });
      });

      host.querySelectorAll('.news-count').forEach(function(input){
        input.addEventListener('input',function(e){
          e.stopPropagation();
          var id=input.dataset.id,n=Number(input.value);
          if(!draft.selected[id])draft.selected[id]={checked:false,count:5};
          if(Number.isFinite(n))draft.selected[id].count=Math.max(5,Math.min(25,Math.round(n)));
          draft.touched[id]=true;
          updateSummary();
        });
      });

      updateSummary();
    }

    function resetSourceForm(){
      $('newsSourceUrl').value='';
      $('newsCheck').textContent='Chưa kiểm tra nguồn.';
      $('newsCheckBtn').textContent='Kiểm tra';
      $('newsCheckBtn').disabled=false;
      $('newsCheckBtn').onclick=checkSource;
    }

    function addDraftSource(source){
      var canonical=canonicalize(source.url);
      var existing=draft.sources.find(function(s){return s.id===source.id||canonicalize(s.url)===canonical;});
      if(existing)return existing;
      var copy=JSON.parse(JSON.stringify(source));
      copy.url=canonical||copy.url;
      copy.name=repairMojibake(copy.name||copy.url);
      copy.enabled=true;
      draft.sources.push(copy);
      draft.pending[copy.id]=true;
      if(!draft.selected[copy.id])draft.selected[copy.id]={checked:false,count:5};
      return copy;
    }

    function checkSource(){
      var canonical=canonicalize($('newsSourceUrl').value);
      if(!canonical){
        $('newsCheck').textContent='URL không hợp lệ.';
        return;
      }

      $('newsCheckBtn').disabled=true;
      $('newsCheck').textContent='Đang kiểm tra nguồn...';

      workerPost('/source/check',{url:canonical}).then(function(result){
        var source=result.source||{};
        if(!source.id||!source.url)throw new Error('Worker trả về thông tin nguồn không hợp lệ');
        source.url=canonicalize(source.url)||canonical;
        source.name=repairMojibake(source.name||source.url);

        var existing=draft.sources.find(function(s){
          return s.id===source.id||canonicalize(s.url)===source.url;
        });

        if(existing){
          $('newsCheck').textContent='Tên nguồn tin: '+displaySourceName(existing.name)+' · Nguồn này đã có trong danh sách.';
          $('newsCheckBtn').textContent='Đã có';
          $('newsCheckBtn').disabled=true;
          return;
        }

        var added=addDraftSource(source);
        $('newsCheck').textContent='Đã thêm tạm: '+displaySourceName(added.name);
        $('newsCheckBtn').textContent='Đã thêm';
        $('newsCheckBtn').disabled=true;
        renderSources();
        resetSourceForm();
      }).catch(function(err){
        $('newsCheck').textContent='Không thể kiểm tra nguồn: '+err.message;
        $('newsCheckBtn').textContent='Kiểm tra';
        $('newsCheckBtn').disabled=false;
        $('newsCheckBtn').onclick=checkSource;
      });
    }

    $('newsSourceUrl').addEventListener('input',function(e){
      e.stopPropagation();
      $('newsCheck').textContent='Chưa kiểm tra nguồn.';
      $('newsCheckBtn').textContent='Kiểm tra';
      $('newsCheckBtn').disabled=false;
      $('newsCheckBtn').onclick=checkSource;
    });

    $('newsSourceUrl').addEventListener('keydown',function(e){e.stopPropagation();});
    $('newsCheckBtn').onclick=checkSource;

    $('newsShelfUrl').addEventListener('input',function(e){
      e.stopPropagation();
      draft.branch=null;
      $('newsShelfStatus').textContent='Tủ sách nhận tin';
      $('newsRegisterBtn').disabled=true;
      clearTimeout(window.__tangthuNewsShelfTimer);
      window.__tangthuNewsShelfTimer=setTimeout(checkShelf,300);
    });

    $('newsShelfUrl').addEventListener('keydown',function(e){e.stopPropagation();});

    document.querySelectorAll('input[name="newsMode"]').forEach(function(radio){
      radio.addEventListener('change',function(e){
        e.stopPropagation();
        draft.mode=this.value;
        $('newsShelfStatus').textContent=draft.branch?'Tủ sách: '+(draft.branch.display_name||draft.branch.id):'Tủ sách nhận tin';
        updateSummary();
      });
    });

    function checkShelf(){
      var raw=$('newsShelfUrl').value.trim();
      if(!raw){
        draft.branch=null;
        $('newsShelfStatus').textContent='Tủ sách nhận tin';
        updateRegisterState();
        return;
      }

      var branch=branchFromUrl(raw);
      if(!branch){
        draft.branch=null;
        $('newsShelfStatus').textContent='tủ sách không tồn tại, vui lòng tạo tủ';
        updateRegisterState();
        return;
      }

      draft.branch=branch;
      syncSelectionForBranch();
      $('newsShelfStatus').textContent='Tủ sách: '+(branch.display_name||branch.id);
      renderSources();
    }

    $('newsRegisterBtn').onclick=function(e){
      e.preventDefault();
      e.stopPropagation();

      var branch=draft.branch;
      var selected=selectedSources();
      var total=selectedTotal();
      var mode=draft.mode;

      if(!branch||!selected.length)return;
      if(total>200){enforceMode();return;}
      if(mode==='images'&&total>100){enforceMode();return;}

      var btn=$('newsRegisterBtn');
      btn.disabled=true;
      $('newsShelfStatus').textContent='Đang đăng ký nhận tin...';

      var newSources=draft.sources.filter(function(s){return draft.pending[s.id];}).map(function(s){
        return {id:s.id,name:s.name,url:s.url,enabled:true};
      });

      workerPost('/news/register',{
        branch_id:branch.id,
        edition_mode:mode,
        total_articles:total,
        new_sources:newSources,
        subscriptions:selected.map(function(x){
          return {source_id:x.id,article_count:x.count};
        })
      }).then(function(result){
        $('newsShelfStatus').textContent=(result.branch_name||branch.display_name||branch.id)+' đăng ký nhận tin thành công';
        btn.disabled=true;
        draft.pending={};
      }).catch(function(err){
        $('newsShelfStatus').textContent='Không thể đăng ký nhận tin: '+err.message;
        btn.disabled=false;
      });
    };

    Promise.all([
      loadJSON(configUrl),
      loadJSON(subsUrl),
      loadJSON(branchesUrl)
    ]).then(function(data){
      registry=Array.isArray(data[0].sources)?data[0].sources.map(function(s){
        s.name=repairMojibake(s.name);
        return s;
      }):[];
      subscriptions=Array.isArray(data[1].subscriptions)?data[1].subscriptions:[];
      branchesList=Array.isArray(data[2].branches)?data[2].branches:[];
      draft.sources=registry.slice();
      syncSelectionForBranch();
      renderSources();
      updateRegisterState();
    }).catch(function(err){
      $('newsSources').innerHTML='<div class="empty">Không tải được Bulletin Registry: '+esc(String(err))+'</div>';
      updateRegisterState();
    });
  }

'''

text = text.replace(anchor, news_fn + anchor, 1)

marker = "$('shelfBtn').onclick=showShelf;"
if "  $('newsBtn').onclick=showNews;" not in text:
    if marker not in text:
        raise SystemExit("News UI patch anchor missing: shelfBtn handler")
    text = text.replace(marker, marker + "\n  $('newsBtn').onclick=showNews;", 1)

if ".news-source-row{" not in text:
    css = r''' .news-url-row{display:flex;align-items:flex-end;gap:10px}.news-url-field{flex:1;min-width:0}.news-inline-btn{height:38px;min-width:120px}.news-sources{display:flex;flex-direction:column;gap:4px}.news-source-row{display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px dotted #aaa}.news-source-main{display:flex;align-items:center;gap:7px;min-width:0;flex:1}.news-source-main span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.news-source-main a{color:#000}.news-count{width:70px;height:30px;padding:3px 5px;border:2px solid #777;border-right-color:#fff;border-bottom-color:#fff;background:#fff}.news-count:disabled{background:#ddd;color:#777}.news-hint{margin:0 0 8px;font-size:12px;color:#555}.news-warning{margin-top:7px;color:#555}.news-warning:empty{display:none}.news-register-actions{justify-content:flex-end}'''
    text = text.replace("</style>", css + "</style>", 1)

path.write_text(text, encoding="utf-8")
