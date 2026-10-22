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
      var blocked=state.check && state.check.can_mutate===false;

      if(state.mode==='create'){
        btn.textContent='Tạo tủ';
        btn.disabled=!state.checkedId || !name;
      }else if(state.mode==='rename'){
        // DELETE is a second valid action while an existing shelf is selected.
        if(isDelete){
          btn.textContent='Xóa tủ';
          btn.disabled=!state.checkedId || blocked;
        }else{
          btn.textContent='Đổi tên';
          btn.disabled=!state.checkedId || !name || blocked;
        }
      }else if(state.mode==='delete'){
        btn.textContent='Xóa tủ';
        btn.disabled=!state.checkedId || blocked;
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

      if(!apiUrl || !id || id!==state.checkedId)return;

      var isDelete=!!state.found && name.toUpperCase()==='DELETE';
      var action=isDelete?'delete':state.mode;

      if(action==='create' && !name)return;
      if(action==='rename' && !name)return;
      if(action==='delete' && !isDelete)return;
      if(state.check && state.check.can_mutate===false){
        setMessage('Tủ này đang trong thời gian chờ 24 giờ.');
        updateAction();
        return;
      }

      if(action==='delete'){
        if(!window.confirm('Xóa tủ "'+(state.found ? state.found.name : '')+'" khỏi Tàng Thư?'))return;
      }

      var btn=$('shareBtn');
      var lookup=$('lookupBtn');
      btn.disabled=true;
      lookup.disabled=true;
      setMessage(action==='create'
        ? 'Đang tạo tủ...'
        : action==='rename'
          ? 'Đang đổi tên tủ...'
          : 'Đang xóa tủ...');

      // Use text/plain so the browser sends a CORS "simple request"
      // instead of an OPTIONS preflight. Apps Script Web Apps do not expose
      // an OPTIONS handler, so application/json would cause Failed to fetch.
      fetch(apiUrl,{
        method:'POST',
        headers:{'Content-Type':'text/plain;charset=utf-8'},
        body:JSON.stringify({
          action:action,
          drive_url:link,
          display_name:action==='delete' ? 'DELETE' : name
        })
      })
        .then(function(r){
          return r.text().then(function(t){
            var data={};
            try{data=JSON.parse(t||'{}')}catch(e){throw new Error('Apps Script trả về dữ liệu không hợp lệ: '+t)}
            if(!r.ok) throw new Error('HTTP '+r.status);
            return data;
          });
        })
        .then(function(data){
          if(!data.ok){
            setMessage(data.error||'Không thể thực hiện thao tác.');
            if(data.next_mutation_at){
              setMessage((data.error||'Không thể thực hiện thao tác.')+
                ' Có thể thử lại sau '+data.next_mutation_at+'.');
            }
            return;
          }

          var updateNotice='Nội dung cập nhật tủ sách sẽ xuất hiện sau khoảng 3 đến 5 phút, bạn vui lòng đợi sau đó tải lại trang.';

          setMessage(action==='create'
            ? 'Đã tạo tủ. '+updateNotice
            : action==='rename'
              ? 'Đã đổi tên tủ. '+updateNotice
              : 'Đã xóa tủ. '+updateNotice);

          setTimeout(function(){
            closeModal();
            location.reload();
          },1800);
        })
        .catch(function(err){
          setMessage('Lỗi: '+String(err));
        })
        .finally(function(){
          lookup.disabled=false;
          updateAction();
        });
    };
  }
"""

new_fn = new_fn.replace("__API_URL__", repr(APPS_SCRIPT_URL))
text = text[:start] + new_fn + text[end:]

# Inject shelf help UI into generated docs/index.html.
text = text.replace('</head>', '''
<style>
/* Shelf registration help */
.shelf-help-panel{margin:0 0 12px;padding:10px;background:#ffffcc;border:1px solid #888;line-height:1.5}
.shelf-help-panel p{margin:0 0 9px}
.shelf-help-panel p:last-child{margin-bottom:0}
.shelf-help-panel code{font-family:Consolas,monospace}

#shelfHelpBtn{
  min-width:28px;
  height:24px;
  padding:0 7px;
  margin-left:auto;
  margin-right:2px;
  background:#c0c0c0;
  color:#000;
  border:2px solid #fff;
  border-right-color:#555;
  border-bottom-color:#555;
  font-weight:bold;
  cursor:pointer
}

#shelfHelpBtn:active{
  border-color:#555 #fff #fff #555;
  padding:1px 6px 0 8px
}

.modal-title{
  justify-content:flex-start
}

.modal-title #modalTitle{
  margin-right:auto
}

.modal-title #shelfHelpBtn{
  margin-left:0;
  margin-right:4px
}
</style>
''' + '</head>', 1)
text = text.replace('</body>', '\n<script>\n(function(){\n  var HELP_ID=\'shelfHelpBtn\', PANEL_ID=\'shelfHelpPanel\';\n  function isShelfModal(){\n    var t=document.getElementById(\'modalTitle\');\n    if(!t)return false;\n    var s=(t.textContent||\'\').trim().toUpperCase();\n    return s.indexOf(\'ĐĂNG KÝ\')>=0 || s.indexOf(\'ĐỔI TÊN TỦ\')>=0;\n  }\n  function sync(){\n    var title=document.getElementById(\'modalTitle\'),body=document.getElementById(\'modalBody\'),close=document.getElementById(\'modalClose\');\n    if(!title||!body||!close)return;\n    var b=document.getElementById(HELP_ID),p=document.getElementById(PANEL_ID);\n    if(!isShelfModal()){if(b)b.remove();if(p)p.remove();return;}\n    if(!b){\n      b=document.createElement(\'button\');b.id=HELP_ID;b.type=\'button\';b.textContent=\'?\';\n      b.title=\'Hướng dẫn đăng ký tủ sách\';\n      b.onclick=function(){var x=document.getElementById(PANEL_ID);if(x)x.hidden=!x.hidden;};\n      close.parentNode.insertBefore(b,close);\n    }\n    if(!p){\n      p=document.createElement(\'div\');p.id=PANEL_ID;p.className=\'shelf-help-panel\';p.hidden=true;\n      p.innerHTML=\n        \'<p>Đăng ký tủ sách để có thể dễ dàng tải sách từ thư mục của bạn về máy đọc sách qua hệ thống OPDS.</p>\'+\n        \'<p><strong>Chuẩn bị:</strong> thư mục Google chia sẻ của bạn cần được để chế độ public (any one with the link can view), chép sách vào đó, chỉ EPUB, MOBI và AZW3 thôi nhé.</p>\'+\n        \'<p>Dán địa chỉ thư mục đó vào ô <strong>"Đường link"</strong>, đặt tên tủ sao cho dễ nhớ (trong ô <strong>"Tên tủ"</strong>).</p>\'+\n        \'<p>Bấm <strong>kiểm tra link</strong>, rồi bấm <strong>tạo tủ</strong>.</p>\'+\n        \'<p>Bạn có thể đổi tên/xóa tủ bằng cách dán lại địa chỉ thư mục Google vào ô <strong>"Đường link"</strong>.</p>\'+\n        \'<p>Trên máy đọc sách của bạn, trong cài đặt OPDS server điền địa chỉ: <code>https://tangthu.pages.dev/opds</code></p>\'+\n        \'<p>Truy cập OPDS trên máy đọc sách để tải sách về theo nhu cầu.</p>\'+\n        \'<p>Thư mục chứa sách của bạn hoàn toàn do bạn quản lý, không chia sẻ link với người khác, bạn nên sử dụng tài khoản Google phụ cho việc này.</p>\'+\n        \'<p>Happy reading<br>Zenkjt</p>\';\n      body.insertBefore(p,body.firstChild);\n    }\n  }\n  var obs=new MutationObserver(sync);\n  function start(){sync();var t=document.getElementById(\'modalTitle\');if(t)obs.observe(t,{childList:true,subtree:true,characterData:true});}\n  if(document.readyState===\'loading\')document.addEventListener(\'DOMContentLoaded\',start);else start();\n})();\n</script>\n' + '</body>', 1)
path.write_text(text, encoding="utf-8")

print(f"Đã tạo file hoàn chỉnh: {path}")
print("Đã thêm thông báo 3–5 phút cho cả Tạo tủ, Đổi tên và Xóa tủ.")
