#!/usr/bin/env python3
import os
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

api_url = os.environ.get("TANGTHU_APPS_SCRIPT_URL", "").strip()
if not api_url:
    raise SystemExit("TANGTHU_APPS_SCRIPT_URL is required for shelf Reload UI")

start = text.find("  function renderBranches(){")
if start < 0:
    raise SystemExit("Shelf Reload patch anchor missing: renderBranches")

end = text.find("\n  function renderContent(){", start)
if end < 0:
    raise SystemExit("Shelf Reload patch anchor missing: renderBranches end")

new_fn = r'''  function renderBranches(){
    var list=$('branchList');list.innerHTML='';
    branches().forEach(function(b){
      var li=document.createElement('li');
      li.className='branch'+(state.branch===b.id?' active':'');
      li.style.display='flex';
      li.style.alignItems='center';
      li.style.gap='5px';

      var main=document.createElement('span');
      main.style.display='flex';
      main.style.alignItems='center';
      main.style.gap='7px';
      main.style.minWidth='0';
      main.style.flex='1 1 auto';
      main.innerHTML='<span class="folder-icon">📚</span><span class="branch-name">'+esc(b.name)+'</span>';
      main.onclick=function(){
        state.branch=b.id;
        state.parent=b.root_folder_id;
        state.selected=null;
        renderBranches();
        renderContent();
      };

      var reload=document.createElement('button');
      reload.type='button';
      reload.title='Reload tủ này';
      reload.textContent='↻';
      reload.style.flex='0 0 auto';
      reload.style.width='28px';
      reload.style.height='24px';
      reload.style.padding='0';
      reload.style.background='#c0c0c0';
      reload.style.color='#000';
      reload.style.border='2px solid #fff';
      reload.style.borderRightColor='#555';
      reload.style.borderBottomColor='#555';
      reload.onclick=function(e){
        e.preventDefault();
        e.stopPropagation();
        reloadShelfFromGUI(b,reload);
      };

      li.appendChild(main);
      li.appendChild(reload);
      list.appendChild(li);
    });
    $('branchCount').textContent=branches().length+' tủ';
    $('sidebarFoot').textContent=branches().length+' tủ sách';
  }

  function reloadShelfFromGUI(b,button){
    var apiUrl=__API_URL__;
    if(!apiUrl){
      $('statusLeft').textContent='Apps Script chưa được cấu hình.';
      return;
    }
    if(button.disabled)return;

    button.disabled=true;
    button.textContent='…';
    $('statusLeft').textContent='Đang reload tủ "'+b.name+'"...';

    fetch(apiUrl,{
      method:'POST',
      headers:{'Content-Type':'text/plain;charset=utf-8'},
      body:JSON.stringify({action:'reload',branch_id:b.id})
    })
      .then(function(r){
        return r.text().then(function(t){
          var data={};
          try{data=JSON.parse(t||'{}')}catch(e){
            throw new Error('Apps Script trả về dữ liệu không hợp lệ.');
          }
          if(!r.ok)throw new Error('HTTP '+r.status);
          return data;
        });
      })
      .then(function(data){
        if(!data.ok)throw new Error(data.error||'Không thể reload tủ.');
        if(data.changed){
          $('statusLeft').textContent='Tủ "'+b.name+'" đã thay đổi. Đã yêu cầu build lại OPDS.';
        }else if(data.queued){
          $('statusLeft').textContent='Tủ "'+b.name+'" đang được scan và sẽ tiếp tục tự động.';
        }else{
          $('statusLeft').textContent='Tủ "'+b.name+'" đã được scan: không có thay đổi.';
        }
      })
      .catch(function(err){
        $('statusLeft').textContent='Reload lỗi: '+String(err);
      })
      .finally(function(){
        button.disabled=false;
        button.textContent='↻';
      });
  }
'''.replace("__API_URL__", repr(api_url))

text = text[:start] + new_fn + text[end:]
path.write_text(text, encoding="utf-8")
