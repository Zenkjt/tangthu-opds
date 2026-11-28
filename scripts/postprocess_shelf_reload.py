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

# Replace ONLY renderBranches(). Do not replace everything up to renderContent(),
# because postprocess_ui.py may already have inserted renderShelfStats() there.
next_fn = text.find("\n  function ", start + len("  function renderBranches(){"))
if next_fn < 0:
    raise SystemExit("Shelf Reload patch anchor missing: next function after renderBranches")

new_fn = r'''  function renderBranches(){
    var list=$('branchList');list.innerHTML='';
    branches().forEach(function(b){
      var li=document.createElement('li');
      li.className='branch'+(state.branch===b.id?' active':'');
      li.style.position='relative';
      li.style.display='flex';
      li.style.alignItems='center';
      li.style.gap='5px';
      li.style.paddingRight='42px';
      li.style.boxSizing='border-box';

      var main=document.createElement('span');
      main.style.display='flex';
      main.style.alignItems='center';
      main.style.gap='7px';
      main.style.minWidth='0';
      main.style.flex='1 1 auto';
      main.style.overflow='hidden';
      main.innerHTML='<span class="folder-icon">📚</span><span class="branch-name">'+esc(b.name)+'</span>';
      main.onclick=function(){
        state.branch=b.id;state.parent=b.root_folder_id;state.selected=null;
        renderBranches();renderContent();
      };

      var reload=document.createElement('button');
      reload.type='button';reload.title='Reload tủ này';
      reload.setAttribute('aria-label','Reload tủ '+b.name);
      reload.textContent='↻';
      reload.style.position='absolute';reload.style.right='8px';
      reload.style.top='50%';reload.style.transform='translateY(-50%)';
      reload.style.zIndex='5';reload.style.display='inline-flex';
      reload.style.alignItems='center';reload.style.justifyContent='center';
      reload.style.flex='0 0 28px';reload.style.width='28px';
      reload.style.minWidth='28px';reload.style.height='24px';
      reload.style.padding='0';reload.style.margin='0';
      reload.style.boxSizing='border-box';reload.style.background='#c0c0c0';
      reload.style.color='#000';reload.style.border='2px solid #fff';
      reload.style.borderRightColor='#555';reload.style.borderBottomColor='#555';
      reload.onclick=function(e){e.preventDefault();e.stopPropagation();reloadShelfFromGUI(b,reload);};
      li.appendChild(main);li.appendChild(reload);list.appendChild(li);
    });
    $('branchCount').textContent=branches().length+' tủ';
    $('sidebarFoot').textContent=branches().length+' tủ sách';
  }

  function shelfSnapshot(shelf){
    if(!shelf)return '';
    return JSON.stringify({id:shelf.id,name:shelf.name,root_folder_id:shelf.root_folder_id,revision:shelf.revision||'',file_count:shelf.file_count||0});
  }

  function fetchFreshCatalog(){
    return fetch('catalog.json?__refresh='+Date.now(),{cache:'no-store'}).then(function(r){
      if(!r.ok)throw new Error('catalog '+r.status);
      return r.json();
    });
  }

  function postRefreshStatus(jobId,branchId){
    return fetch(__API_URL__,{
      method:'POST',headers:{'Content-Type':'text/plain;charset=utf-8'},
      body:JSON.stringify({action:'refresh_status',job_id:jobId,branch_id:branchId})
    }).then(function(r){return r.text();}).then(function(t){
      try{return JSON.parse(t||'{}');}catch(e){throw new Error('Trạng thái Refresh không hợp lệ.');}
    });
  }

  function waitForShelfUpdate(b,button,baseline,attempt){
    attempt=attempt||0;
    if(attempt>=120){
      $('statusLeft').textContent='Refresh đã hoàn tất nhưng chưa thấy bản deploy mới của tủ "'+b.name+'".';
      button.disabled=false;button.textContent='↻';return;
    }
    window.setTimeout(function(){
      fetchFreshCatalog().then(function(catalog){
        var updated=(catalog.branches||[]).find(function(x){return x.id===b.id});
        if(updated && shelfSnapshot(updated)!==baseline){
          state.catalog=catalog;if(state.fileCache)delete state.fileCache[b.id];
          renderBranches();renderContent();
          $('statusLeft').textContent='Tủ "'+b.name+'" đã được cập nhật.';
          button.disabled=false;button.textContent='↻';return;
        }
        $('statusLeft').textContent='Đang chờ GitHub build và deploy tủ "'+b.name+'"…';
        waitForShelfUpdate(b,button,baseline,attempt+1);
      }).catch(function(){waitForShelfUpdate(b,button,baseline,attempt+1);});
    },10000);
  }

  function pollRefreshJob(b,button,baseline,jobId,attempt){
    attempt=attempt||0;
    if(attempt>=360){
      $('statusLeft').textContent='Refresh vẫn chưa có kết quả. Job được giữ trên máy chủ; có thể bấm Reload lại để xem trạng thái.';
      button.disabled=false;button.textContent='↻';return;
    }
    postRefreshStatus(jobId,b.id).then(function(data){
      if(!data.ok)throw new Error(data.error||'Không đọc được trạng thái Refresh.');
      if(!data.found){$('statusLeft').textContent='Không tìm thấy job Refresh trên máy chủ.';button.disabled=false;button.textContent='↻';return;}
      var job=data.job||{};
      if(job.status==='completed'){
        if(job.changed && job.build_dispatched){
          $('statusLeft').textContent='Scan hoàn tất. Đang chờ deploy tủ "'+b.name+'"…';
          waitForShelfUpdate(b,button,baseline,0);
        }else{
          $('statusLeft').textContent='Đã kiểm tra tủ "'+b.name+'": không có thay đổi.';
          button.disabled=false;button.textContent='↻';
        }
        return;
      }
      if(job.status==='failed'){
        $('statusLeft').textContent='Không thể Refresh tủ này: '+(job.last_error||'tủ không còn hoạt động');
        button.disabled=false;button.textContent='↻';return;
      }
      if(job.status==='dispatch_pending'){
        $('statusLeft').textContent='Scan đã xong; đang gửi yêu cầu build và deploy…';
        window.setTimeout(function(){pollRefreshJob(b,button,baseline,jobId,attempt+1);},10000);
        return;
      }
      if(job.status==='dispatch_error'){
        $('statusLeft').textContent='Scan xong nhưng gửi yêu cầu build thất bại: '+(job.last_error||'lỗi không xác định');
        button.disabled=false;button.textContent='↻';return;
      }
      if(job.status==='paused_error'){
        $('statusLeft').textContent='Refresh tạm dừng sau 5 lần lỗi: '+(job.last_error||'lỗi không xác định');
        button.disabled=false;button.textContent='↻';return;
      }
      var labels={queued:'Đang chờ ưu tiên Refresh…',running:'Đang quét Google Drive…',retry_wait:'Lỗi tạm thời; sẽ tự thử lại…'};
      $('statusLeft').textContent=(labels[job.status]||'Đang xử lý Refresh…')+' ('+(job.error_count||0)+'/5)';
      window.setTimeout(function(){pollRefreshJob(b,button,baseline,jobId,attempt+1);},10000);
    }).catch(function(err){
      $('statusLeft').textContent='Đang chờ trạng thái Refresh: '+String(err);
      window.setTimeout(function(){pollRefreshJob(b,button,baseline,jobId,attempt+1);},15000);
    });
  }

  function reloadShelfFromGUI(b,button){
    if(!__API_URL__){$('statusLeft').textContent='Apps Script chưa được cấu hình.';return;}
    if(button.disabled)return;
    var oldShelf=(state.catalog.branches||[]).find(function(x){return x.id===b.id});
    var baseline=shelfSnapshot(oldShelf);
    button.disabled=true;button.textContent='…';
    $('statusLeft').textContent='Đang gửi yêu cầu Refresh cho tủ "'+b.name+'”…';
    fetch(__API_URL__,{
      method:'POST',headers:{'Content-Type':'text/plain;charset=utf-8'},
      body:JSON.stringify({action:'reload',branch_id:b.id})
    }).then(function(r){
      return r.text().then(function(t){
        var data={};try{data=JSON.parse(t||'{}');}catch(e){throw new Error('Apps Script trả về dữ liệu không hợp lệ.');}
        if(!r.ok)throw new Error('HTTP '+r.status);return data;
      });
    }).then(function(data){
      if(data.no_op || (data.queued && data.error)){window.location.reload();return;}
      if(data.busy){
        $('statusLeft').textContent=data.error||'Hệ thống đang chạy tác vụ khác; Refresh chưa được xếp hàng. Hãy thử lại sau.';
        button.disabled=false;button.textContent='↻';return;
      }
      if(!data.ok)throw new Error(data.error||'Không thể reload tủ.');
      if(!data.job_id)throw new Error('Máy chủ không trả về mã Refresh job.');
      pollRefreshJob(b,button,baseline,data.job_id,0);
    }).catch(function(err){
      $('statusLeft').textContent='Reload lỗi: '+String(err);
      button.disabled=false;button.textContent='↻';
    });
  }
'''.replace("__API_URL__", repr(api_url))

text = text[:start] + new_fn + text[next_fn:]
path.write_text(text, encoding="utf-8")
