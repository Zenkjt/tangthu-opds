#!/usr/bin/env python3
import os
from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

# The Web App URL is injected at build time from the repository variable:
# TANGTHU_APPS_SCRIPT_URL
APPS_SCRIPT_URL = os.environ.get("TANGTHU_APPS_SCRIPT_URL", "").strip()

start = text.find("  function showShelf(){")
if start < 0:
    raise SystemExit("Registration patch anchor missing: showShelf")

end = text.find("\n  function runSearch(){", start)
if end < 0:
    raise SystemExit("Registration patch anchor missing: showShelf end")

new_fn = r"""
  function showShelf(){
    var apiUrl=__API_URL__;
    var state={mode:'none',found:null,checkedId:'',folderName:'',check:null};

    modal('ĐĂNG KÝ / ĐỔI TÊN TỦ SÁCH',
      '<fieldset><legend>Google Drive</legend>'+
      '<label for="driveLink">Đường link thư mục</label>'+
      '<input id="driveLink" type="url" placeholder="https://drive.google.com/drive/folders/..." value="">'+
      '<div class="lookup-state" id="folderInfo">Chưa kiểm tra link.</div>'+
      '</fieldset>'+
      '<fieldset><legend>Tên hiển thị</legend>'+
      '<label for="shelfName">Tên tủ sách</label>'+
      '<input id="shelfName" type="text" placeholder="Tên muốn hiển thị trên Tàng Thư" value="">'+
      '</fieldset>'+
      '<div class="note">Tên <strong>Folder Google Drive</strong> là tên thật của thư mục trên Drive. Tên <strong>Tủ sách</strong> là tên hiển thị trong Tàng Thư và có thể đặt khác.</div>'+
      '<div class="lookup-state" id="shelfMsg">Chưa kiểm tra link.</div>'+
      '<div class="modal-actions"><button id="lookupBtn">Kiểm tra link</button><button id="shareBtn" disabled>Kiểm tra link trước</button></div>');

    var setMessage=function(s){$('shelfMsg').textContent=s};
    var setFolder=function(s){$('folderInfo').textContent=s};

    var updateAction=function(){
      var name=$('shelfName').value.trim();
      var isDelete=!!state.found && name.toUpperCase()==='DELETE';
      var btn=$('shareBtn');

      if(state.mode==='create'){
        btn.textContent='Tạo tủ';
        btn.disabled=!state.checkedId || !name;
      }else if(state.mode==='rename'){
        // Important: DELETE is a second valid action while an existing
        // shelf is selected. Do not disable the button here.
        if(isDelete){
          btn.textContent='Xóa tủ';
          btn.disabled=!state.checkedId;
        }else{
          btn.textContent='Đổi tên';
          btn.disabled=!state.checkedId || !name;
        }
      }else if(state.mode==='delete'){
        btn.textContent='Xóa tủ';
        btn.disabled=!state.checkedId;
      }else{
        btn.textContent='Kiểm tra link trước';
        btn.disabled=true;
      }
    };

    var localLookup=function(id){
      return branches().find(function(x){
        return String(x.root_folder_id)===String(id);
      }) || null;
    };

    $('lookupBtn').onclick=function(){
      var link=$('driveLink').value.trim();
      var id=parseDriveId(link);

      if(!id){
        state={mode:'none',found:null,checkedId:'',folderName:'',check:null};
        setFolder('Không nhận ra Folder ID từ đường link Google Drive này.');
        setMessage('Hãy kiểm tra lại đường link.');
        $('shelfName').value='';
        updateAction();
        return;
      }

      if(!apiUrl){
        // Temporary fallback while the Apps Script URL has not yet been
        // configured. This still fixes the DELETE UI bug.
        var local=localLookup(id);
        state.checkedId=id;
        state.mode=local?'rename':'create';
        state.folderName='';
        state.found=local;
        setFolder(local
          ? 'Folder đã đăng ký trong Tàng Thư.'
          : 'Apps Script chưa được cấu hình.');
        $('shelfName').value=local?local.name:'';
        setMessage(local
          ? 'Đã nhận ra tủ hiện tại. Đổi tên hoặc nhập DELETE để xóa.'
          : 'Link hợp lệ về cú pháp nhưng cần Apps Script để kiểm tra folder thật.');
        updateAction();
        return;
      }

      setFolder('Đang kiểm tra Google Drive...');
      setMessage('Đang kiểm tra link...');
      $('lookupBtn').disabled=true;

      var url=apiUrl+'?action=check&drive='+encodeURIComponent(link);

      fetch(url,{method:'GET',redirect:'follow'})
        .then(function(r){
          if(!r.ok) throw new Error('HTTP '+r.status);
          return r.json();
        })
        .then(function(data){
          if(!data.ok){
            state={mode:'none',found:null,checkedId:'',folderName:'',check:data};
            setFolder(data.error||'Không thể kiểm tra folder.');
            setMessage('Link chưa sẵn sàng để đăng ký.');
            $('shelfName').value='';
            updateAction();
            return;
          }

          var found=localLookup(data.folder_id);
          state.checkedId=data.folder_id;
          state.folderName=data.folder_name||'';
          state.found=found;

          if(found){
            state.mode='rename';
            $('shelfName').value=found.name;
            setFolder('Folder Google Drive: '+(data.folder_name||'—'));
            setMessage('Đã nhận ra tủ "'+found.name+'". Đổi tên hoặc nhập DELETE để xóa.');
          }else{
            state.mode='create';
            $('shelfName').value='';
            setFolder('Folder Google Drive: '+(data.folder_name||'—'));
            setMessage('Folder chưa đăng ký. Nhập tên tủ rồi bấm Tạo tủ.');
          }

          updateAction();
        })
        .catch(function(err){
          state={mode:'none',found:null,checkedId:'',folderName:'',check:null};
          setFolder('Không gọi được Apps Script.');
          setMessage(String(err));
          updateAction();
        })
        .finally(function(){
          $('lookupBtn').disabled=false;
        });
    };

    $('shelfName').oninput=updateAction;

    $('driveLink').oninput=function(){
      state={mode:'none',found:null,checkedId:'',folderName:'',check:null};
      setFolder('Đã thay đổi link. Bấm Kiểm tra link.');
      setMessage('Chưa kiểm tra link.');
      updateAction();
    };

    $('shareBtn').onclick=function(){
      var link=$('driveLink').value.trim();
      var id=parseDriveId(link);
      var name=$('shelfName').value.trim();

      if(!id || id!==state.checkedId)return;

      var isDelete=!!state.found && name.toUpperCase()==='DELETE';
      var action=isDelete?'delete':state.mode;

      if(action==='create' && !name)return;
      if(action==='rename' && !name)return;
      if(action==='delete' && !isDelete)return;

      // Stage 1 only: verify the folder through Apps Script.
      // CREATE/RENAME/DELETE will be wired after this check endpoint is
      // deployed and tested from the live GitHub Pages site.
      setMessage('Kiểm tra OK. Mutation API sẽ được bật ở bước tiếp theo.');
    };
  }
"""

new_fn = new_fn.replace("__API_URL__", repr(APPS_SCRIPT_URL))
text = text[:start] + new_fn + text[end:]
path.write_text(text, encoding="utf-8")
print("Wrote:", path)
print("Apps Script URL configured from environment:", bool(APPS_SCRIPT_URL))
