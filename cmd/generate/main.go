package main

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/Zenkjt/tangthu-opds/internal/drive"
)

type BranchConfig struct {
	ID           string `json:"id"`
	DisplayName  string `json:"display_name"`
	RootFolderID string `json:"root_folder_id"`
	Enabled      bool   `json:"enabled"`
}

type Config struct {
	Branches []BranchConfig `json:"branches"`
}

type FileEntry struct {
	ID       string
	ParentID string
	Name     string
	MIME     string
	Size     int64
	Modified string
	Checksum string
	IsFolder bool
}

type Branch struct {
	Config          BranchConfig
	DriveFolderName string
	Files           []FileEntry
}

func main() {
	apiKey := strings.TrimSpace(os.Getenv("TANGTHU_GOOGLE_API_KEY"))
	if apiKey == "" {
		fatal("TANGTHU_GOOGLE_API_KEY is required")
	}
	cfgPath := getenv("TANGTHU_BRANCH_CONFIG", "config/branches.json")
	outDir := getenv("TANGTHU_OUTPUT_DIR", "docs")
	baseURL := strings.TrimRight(getenv("TANGTHU_BASE_URL", "https://zenkjt.github.io/tangthu-opds"), "/")

	data, err := os.ReadFile(cfgPath)
	if err != nil {
		fatal(err.Error())
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		fatal(err.Error())
	}

	client, err := drive.NewClient(apiKey)
	if err != nil {
		fatal(err.Error())
	}
	ctx := context.Background()
	var branches []Branch
	for _, bc := range cfg.Branches {
		if !bc.Enabled {
			continue
		}
		folder, err := client.GetFolder(ctx, bc.RootFolderID)
		if err != nil {
			fatal(fmt.Sprintf("branch %s: %v", bc.ID, err))
		}
		files, err := client.Scan(ctx, bc.RootFolderID)
		if err != nil {
			fatal(fmt.Sprintf("scan %s: %v", bc.ID, err))
		}
		converted := make([]FileEntry, 0, len(files))
		for _, f := range files {
			converted = append(converted, FileEntry{
				f.ID, f.ParentID, f.Name, f.MIMEType, f.Size,
				f.ModifiedTime, f.MD5Checksum, drive.IsFolder(f),
			})
		}
		branches = append(branches, Branch{bc, folder.Name, converted})
	}
	sort.SliceStable(branches, func(i, j int) bool {
		return branchLess(branches[i].Config.DisplayName, branches[j].Config.DisplayName)
	})

	if err := os.RemoveAll(outDir); err != nil {
		fatal(err.Error())
	}
	if err := os.MkdirAll(filepath.Join(outDir, "opds"), 0755); err != nil {
		fatal(err.Error())
	}
	if err := writeWeb(outDir, baseURL, branches); err != nil {
		fatal(err.Error())
	}
	if err := writeCatalogJSON(outDir, branches); err != nil {
		fatal(err.Error())
	}
	if err := writeOPDS(outDir, baseURL, branches); err != nil {
		fatal(err.Error())
	}
	fmt.Printf("Generated %d branches at %s (%s)\n", len(branches), outDir, time.Now().Format(time.RFC3339))
}

func getenv(k, d string) string {
	if v := strings.TrimSpace(os.Getenv(k)); v != "" {
		return v
	}
	return d
}

func fatal(s string) {
	fmt.Fprintln(os.Stderr, s)
	os.Exit(1)
}

func branchLess(a, b string) bool {
	av := strings.HasPrefix(a, "VN")
	bv := strings.HasPrefix(b, "VN")
	if av != bv {
		return av
	}
	return strings.ToLower(a) < strings.ToLower(b)
}

func esc(s string) string  { return html.EscapeString(s) }
func safe(s string) string { return url.PathEscape(s) }

func mime(s string) string {
	if s != "" {
		return s
	}
	return "application/octet-stream"
}

func children(b Branch, parent string) []FileEntry {
	var out []FileEntry
	for _, f := range b.Files {
		if f.ParentID == parent {
			out = append(out, f)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].IsFolder != out[j].IsFolder {
			return out[i].IsFolder
		}
		return strings.ToLower(out[i].Name) < strings.ToLower(out[j].Name)
	})
	return out
}

func acquisitionURL(f FileEntry) string {
	return "https://drive.google.com/uc?export=download&id=" + url.QueryEscape(f.ID)
}

func writeWeb(out, base string, branches []Branch) error {
	// The catalog is rendered client-side from catalog.json. The generated HTML
	// is intentionally self-contained: no framework, no external CSS, no JS CDN.
	// This keeps the GitHub Pages site small and friendly to older e-readers/mobile browsers.
	var b strings.Builder
	b.WriteString(`<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Tàng Thư — thư viện sách phân tán theo chuẩn OPDS">
<title>TÀNG THƯ — Thư viện sách phân tán</title>
<style>
:root{--blue:#000080;--blue2:#0000a0;--gray:#c0c0c0;--light:#dfdfdf;--white:#fff;--dark:#404040;--black:#000;--select:#d8d8d8;--text:#111}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#c0c0c0;color:var(--text);font-family:Tahoma,Arial,sans-serif;font-size:14px}
body{min-height:100vh;padding:7px}
button,input{font:inherit}
button{cursor:pointer;color:#000;background:#c0c0c0}
.win{max-width:1500px;margin:0 auto;border:2px solid #fff;border-right-color:#404040;border-bottom-color:#404040;background:#c0c0c0;box-shadow:1px 1px 0 #000}
.titlebar{height:34px;display:flex;align-items:center;gap:8px;padding:3px 7px;background:#000080;color:#fff;font-weight:bold;font-size:17px}
.titlebar .appicon{width:24px;height:24px;display:grid;place-items:center;background:#fff;color:#000;border:1px solid #000;font-size:15px}
.titlebar .caption{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.toolbar{display:flex;gap:4px;padding:5px;border-bottom:1px solid #808080;overflow-x:auto}
.tool{flex:0 0 auto;min-width:90px;height:70px;padding:4px 7px;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px}
.tool:active{border-color:#555 #fff #fff #555;padding:5px 6px 3px 8px}
.tool .ico{font-size:26px;line-height:28px}.tool .lbl{font-size:13px}
.brand{margin-left:auto;min-width:255px;height:70px;padding:6px 16px;border:2px solid #808080;border-right-color:#fff;border-bottom-color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.brand strong{font-size:21px}.brand em{font-family:Georgia,serif;font-size:15px;margin-top:3px}
.main{display:grid;grid-template-columns:300px minmax(0,1fr);gap:7px;padding:5px}
.panel{min-width:0;border:2px solid #808080;border-right-color:#fff;border-bottom-color:#fff;background:#fff;display:flex;flex-direction:column;overflow:hidden}
.panel-title{height:35px;display:flex;align-items:center;padding:5px 9px;background:#000080;color:#fff;font-weight:bold;font-size:16px}
.panel-title .count{margin-left:auto;font-weight:normal;font-size:13px}
.panel-body{min-height:0;overflow:auto;background:#fff}
.library-list{list-style:none;margin:0;padding:4px}
.branch{padding:7px 8px;display:flex;align-items:center;gap:7px;border:1px dotted transparent;cursor:pointer}
.branch:hover{background:#eee}
.branch.active{background:var(--select);border:1px dotted #555}
.folder-icon{width:25px;text-align:center;font-size:20px;flex:0 0 25px}.branch-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sidebar-foot{margin-top:auto;border-top:2px solid #808080;padding:7px;background:#c0c0c0}
.content-path{padding:7px 10px;background:#dfdfdf;border-bottom:1px solid #888;font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.books{width:100%;border-collapse:collapse;table-layout:fixed}
.books th{position:sticky;top:0;z-index:2;background:#dfdfdf;border:1px solid #888;padding:5px;text-align:left;font-weight:bold}
.books td{border-bottom:1px solid #ccc;padding:5px 6px;vertical-align:middle;overflow:hidden;text-overflow:ellipsis}
.book-row{cursor:pointer}.book-row:hover{background:#f0f0f0}.book-row.selected{background:var(--select);outline:1px dotted #555;outline-offset:-2px}
.cover{width:44px;height:58px;object-fit:cover;display:block;background:#eee;border:1px solid #777}
.cover-fallback{width:44px;height:58px;display:grid;place-items:center;background:#ddd;border:1px solid #777;font-weight:bold;font-size:11px;text-align:center}
.name-cell strong{display:block;font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.name-cell small{display:block;color:#444;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.searchbar{display:flex;gap:5px;align-items:center;padding:7px;border-top:1px solid #808080;background:#c0c0c0}.searchbar label{font-weight:bold;white-space:nowrap}.searchbar input{min-width:0;flex:1;height:34px;padding:5px 8px;background:#fff;border:2px solid #777;border-right-color:#fff;border-bottom-color:#fff}.searchbar button{height:34px;min-width:80px;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}.searchbar select{height:34px;max-width:190px}
.status{display:flex;justify-content:space-between;gap:8px;padding:5px 9px;border-top:2px solid #808080;background:#c0c0c0}.status span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.22);display:none;align-items:center;justify-content:center;padding:12px;z-index:20}.modal-backdrop.open{display:flex}.modal{width:min(680px,100%);max-height:90vh;overflow:auto;background:#c0c0c0;border:2px solid #fff;border-right-color:#404040;border-bottom-color:#404040;box-shadow:3px 3px 0 #000}.modal-title{display:flex;align-items:center;justify-content:space-between;background:#000080;color:#fff;padding:5px 8px;font-weight:bold}.close{min-width:28px;height:24px;padding:0;background:#c0c0c0;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}.modal-body{padding:14px}.modal-body p{line-height:1.5}.modal-body fieldset{border:2px groove #ddd;margin:0 0 12px;padding:12px}.modal-body legend{font-weight:bold}.modal-body label{display:block;font-weight:bold;margin-bottom:5px}.modal-body input[type=text],.modal-body input[type=url]{width:100%;height:34px;padding:5px 7px;border:2px solid #777;border-right-color:#fff;border-bottom-color:#fff;background:#fff}.modal-actions{display:flex;justify-content:flex-end;gap:6px;margin-top:12px}.modal-actions button{min-width:120px;height:34px;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}.note{background:#ffffcc;border:1px solid #888;padding:8px}.muted{color:#555}.detail{display:grid;grid-template-columns:90px 1fr;gap:6px 12px}.detail dt{font-weight:bold}.detail dd{margin:0;word-break:break-word}
.empty{padding:30px;text-align:center;color:#555}.folder-row td{font-weight:bold}.folder-row:hover{background:#eee}
@media(max-width:850px){body{padding:3px}.titlebar{height:31px;font-size:15px}.toolbar{display:grid;grid-template-columns:repeat(4,minmax(70px,1fr));overflow:visible}.tool{min-width:0;width:auto;height:58px}.tool .ico{font-size:22px;line-height:22px}.brand{grid-column:1/-1;margin:0;height:52px;min-width:0}.brand strong{font-size:17px}.brand em{font-size:13px}.main{grid-template-columns:1fr;gap:5px}.panel:first-child{max-height:230px}.panel:nth-child(2){min-height:430px}.books th:nth-child(3),.books td:nth-child(3),.books th:nth-child(5),.books td:nth-child(5){display:none}.books th:nth-child(1),.books td:nth-child(1){width:54px}.books th:nth-child(2),.books td:nth-child(2){width:auto}.books th:nth-child(4),.books td:nth-child(4){width:68px}.searchbar{flex-wrap:wrap}.searchbar label{width:100%}.searchbar input{width:100%;flex-basis:calc(100% - 86px)}.searchbar select{max-width:none;flex:1}.status{font-size:12px}}
@media(max-width:430px){.toolbar{grid-template-columns:repeat(3,minmax(70px,1fr))}.tool{height:54px}.tool .lbl{font-size:12px}.panel:first-child{max-height:190px}.books th:nth-child(4),.books td:nth-child(4){display:none}.cover{width:38px;height:52px}.cover-fallback{width:38px;height:52px}.name-cell strong{font-size:13px}.name-cell small{font-size:11px}.modal-body{padding:10px}}
</style>
</head>
<body>
<div class="win">
  <div class="titlebar"><div class="appicon">📖</div><div class="caption">TÀNG THƯ — Thư viện sách phân tán (OPDS)</div></div>
  <div class="toolbar">
    <button class="tool" id="upBtn"><span class="ico">📁</span><span class="lbl">Up</span></button>
    <button class="tool" id="homeBtn"><span class="ico">⌂</span><span class="lbl">Home</span></button>
    <button class="tool" id="refreshBtn"><span class="ico">⟳</span><span class="lbl">Refresh</span></button>
    <button class="tool" id="searchBtn"><span class="ico">🔎</span><span class="lbl">Search</span></button>
    <button class="tool" id="shelfBtn"><span class="ico">📚</span><span class="lbl">Tủ sách</span></button>
    <button class="tool" id="viewsBtn"><span class="ico">▤</span><span class="lbl">Views</span></button>
    <button class="tool" id="infoBtn"><span class="ico">ℹ</span><span class="lbl">Info</span></button>
    <div class="brand"><strong>TÀNG THƯ</strong><em>A book is a dream holding in your hands.</em></div>
  </div>
  <div class="main">
    <section class="panel" id="shelfPanel">
      <div class="panel-title">TỦ SÁCH <span class="count" id="branchCount"></span></div>
      <div class="panel-body"><ul class="library-list" id="branchList"></ul></div>
      <div class="sidebar-foot" id="sidebarFoot">Đang tải...</div>
    </section>
    <section class="panel" id="contentPanel">
      <div class="panel-title">NỘI DUNG <span class="count" id="itemCount"></span></div>
      <div class="content-path" id="pathBar">Tàng Thư</div>
      <div class="panel-body" id="contentBody"></div>
    </section>
  </div>
  <div class="searchbar">
    <label for="searchInput">🔎 Tìm kiếm:</label>
    <input id="searchInput" type="search" placeholder="Nhập tên sách, tác giả, từ khóa..." autocomplete="off">
    <button id="searchDo">Tìm</button>
    <select id="searchScope" title="Phạm vi tìm kiếm"><option value="all">Tất cả tủ sách</option><option value="current">Tủ đang mở</option></select>
  </div>
  <div class="status"><span id="statusLeft">Sẵn sàng.</span><span>TÀNG THƯ | OPDS | 2026</span></div>
</div>

<div class="modal-backdrop" id="modalBackdrop">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-title"><span id="modalTitle">Thông tin</span><button class="close" id="modalClose">×</button></div>
    <div class="modal-body" id="modalBody"></div>
  </div>
</div>

<script>
(function(){
  'use strict';
  var state={catalog:null,branch:null,parent:null,view:'list',selected:null,search:''};
  var $=function(id){return document.getElementById(id)};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})};
  var size=function(n){n=Number(n)||0;if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';if(n<1073741824)return (n/1048576).toFixed(1)+' MB';return (n/1073741824).toFixed(2)+' GB'};
  var ext=function(n){var m=String(n||'').toLowerCase().match(/\.([^.]+)$/);return m?m[1].toUpperCase():'FILE'};
  var modal=function(title,body){$('modalTitle').textContent=title;$('modalBody').innerHTML=body;$('modalBackdrop').classList.add('open')};
  var closeModal=function(){$('modalBackdrop').classList.remove('open')};
  $('modalClose').onclick=closeModal;$('modalBackdrop').onclick=function(e){if(e.target===$('modalBackdrop'))closeModal()};

  function branches(){return state.catalog&&state.catalog.branches||[]}
  function currentBranch(){return branches().find(function(b){return b.id===state.branch})}
  function filesOf(b){return b&&b.files||[]}
  function children(b,parent){return filesOf(b).filter(function(f){return f.parent_id===parent}).sort(function(a,c){if(!!a.folder!==!!c.folder)return a.folder?-1:1;return a.name.localeCompare(c.name,'vi',{sensitivity:'base'})})}
  function findFile(b,id){return filesOf(b).find(function(f){return f.id===id})}
  function folderPath(b,id){var out=[];var guard=0;while(id&&id!==b.root_folder_id&&guard++<100){var f=findFile(b,id);if(!f)break;out.unshift(f.name);id=f.parent_id}return out}
  function displayDate(s){if(!s)return '';var d=new Date(s);return isNaN(d)?s:d.toLocaleString('vi-VN',{dateStyle:'short',timeStyle:'short'})}
  function acquisition(id){return 'https://drive.google.com/uc?export=download&id='+encodeURIComponent(id)}
  function cover(id){return 'https://drive.google.com/thumbnail?id='+encodeURIComponent(id)+'&sz=w120-h160'}

  function renderBranches(){
    var list=$('branchList');list.innerHTML='';
    branches().forEach(function(b){
      var li=document.createElement('li');li.className='branch'+(state.branch===b.id?' active':'');
      li.innerHTML='<span class="folder-icon">📚</span><span class="branch-name">'+esc(b.name)+'</span>';
      li.onclick=function(){state.branch=b.id;state.parent=b.root_folder_id;state.selected=null;renderBranches();renderContent()};
      list.appendChild(li);
    });
    $('branchCount').textContent=branches().length+' tủ';
    $('sidebarFoot').textContent=branches().length+' tủ sách';
  }

  function renderContent(){
    var b=currentBranch();var body=$('contentBody');body.innerHTML='';
    if(!b){$('pathBar').textContent='Tàng Thư';$('itemCount').textContent='';body.innerHTML='<div class="empty">Chưa có tủ sách.</div>';return}
    var path=[b.name].concat(folderPath(b,state.parent));$('pathBar').textContent=path.join('  ›  ');
    var rows=children(b,state.parent);
    var q=state.search.trim().toLocaleLowerCase('vi-VN');
    if(q){
      rows=filesOf(b).filter(function(f){return !f.folder && (f.name+' '+(f.mime||'')).toLocaleLowerCase('vi-VN').indexOf(q)>=0});
    }
    $('itemCount').textContent=rows.length+(q?' kết quả':' mục');
    if(!rows.length){body.innerHTML='<div class="empty">'+(q?'Không tìm thấy sách phù hợp.':'Thư mục này chưa có nội dung.')+'</div>';return}
    var table=document.createElement('table');table.className='books';
    table.innerHTML='<thead><tr><th style="width:58px">Bìa</th><th>Tên sách</th><th style="width:190px">Tác giả</th><th style="width:90px">Định dạng</th><th style="width:105px">Dung lượng</th><th style="width:85px">Ngày</th></tr></thead>';
    var tb=document.createElement('tbody');
    rows.forEach(function(f){
      var tr=document.createElement('tr');tr.className=(f.folder?'folder-row ':'book-row ')+(state.selected===f.id?'selected':'');
      if(f.folder){tr.innerHTML='<td>📁</td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>Thư mục</small></td><td></td><td>DIR</td><td></td><td></td>';tr.onclick=function(){state.parent=f.id;state.selected=f.id;renderContent()};}
      else {tr.innerHTML='<td><img class="cover" loading="lazy" src="'+cover(f.id)+'" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\'"/><span class="cover-fallback" style="display:none">'+esc(ext(f.name))+'</span></td><td class="name-cell"><strong>'+esc(f.name)+'</strong><small>'+esc(displayDate(f.modified))+'</small></td><td>'+esc('')+'</td><td>'+esc(ext(f.name))+'</td><td>'+esc(size(f.size))+'</td><td>'+esc(displayDate(f.modified))+'</td>';tr.onclick=function(){state.selected=f.id;renderContent();showBook(f,b)};}
      tb.appendChild(tr);
    });
    table.appendChild(tb);body.appendChild(table);
  }

  function showBook(f,b){
    var body='<div class="detail"><dt>Tên file</dt><dd>'+esc(f.name)+'</dd><dt>Định dạng</dt><dd>'+esc(ext(f.name))+'</dd><dt>Dung lượng</dt><dd>'+esc(size(f.size))+'</dd><dt>Cập nhật</dt><dd>'+esc(displayDate(f.modified))+'</dd><dt>MIME</dt><dd>'+esc(f.mime||'')+'</dd><dt>Checksum</dt><dd>'+esc(f.checksum||'—')+'</dd></div><div class="modal-actions"><button id="downloadBtn">Truy cập / tải</button><button id="opdsBtn">Mở OPDS</button></div>';
    modal('THÔNG TIN SÁCH',body);
    $('downloadBtn').onclick=function(){window.open(acquisition(f.id),'_blank','noopener')};
    $('opdsBtn').onclick=function(){window.open('opds/branch/'+encodeURIComponent(b.id)+'/index.xml','_blank','noopener')};
  }

  function showInfo(){
    modal('GIỚI THIỆU TÀNG THƯ','<p><strong>Tàng Thư là thư viện phân tán</strong>, sách được liệt kê theo chuẩn OPDS. Bạn chép đường dẫn <code>https://...</code> vào danh sách OPDS của máy đọc sách để truy cập.</p><p>Tàng Thư có nhiều <strong>“tủ sách”</strong>, mỗi tủ sách là một thư mục đã được chia sẻ trên Google Drive của người chia sẻ. Không nên dùng tài khoản Google chính cho việc này.</p><p>Bạn có thể đặt tên/đổi tên tủ mà bạn chia sẻ. Các tên bắt đầu bằng <strong>VN</strong> sẽ được ưu tiên hiển thị.</p><p>Vì các hạn chế của máy đọc sách nên mỗi tủ sách không nên để quá nhiều sách.</p><p style="text-align:center;font-family:Georgia,serif"><strong>Happy reading.</strong><br><em>A book is a dream holding in your hands.</em></p>');
  }

  function showShelf(){
    var checked=false;
    var matched=false;
    var matchedName='';

    modal(
      'ĐĂNG KÝ / ĐỔI TÊN / XÓA TỦ SÁCH',
      '<fieldset>' +
        '<legend>Google Drive</legend>' +
        '<label for="driveLink">Đường link thư mục</label>' +
        '<input id="driveLink" type="url" placeholder="https://drive.google.com/drive/folders/..." value="">' +
      '</fieldset>' +

      '<fieldset>' +
        '<legend>Tên hiển thị</legend>' +
        '<label for="shelfName">Tên tủ sách</label>' +
        '<input id="shelfName" type="text" placeholder="Tên muốn hiển thị trên Tàng Thư">' +
      '</fieldset>' +

      '<div class="note" id="shelfNote">' +
        'Dán link Google Drive rồi bấm <strong>Kiểm tra link</strong> để nhận diện tủ.' +
      '</div>' +

      '<div class="modal-actions">' +
        '<button id="lookupBtn">Kiểm tra link</button>' +
        '<button id="shareBtn" disabled>Tạo tủ</button>' +
      '</div>' +

      '<p class="muted" id="shelfMsg">' +
        'Tên hiển thị trên Tàng Thư độc lập với tên thư mục thật trên Google Drive.' +
      '</p>'
    );

    function setAction(label,enabled){
      var btn=$('shareBtn');
      btn.textContent=label;
      btn.disabled=!enabled;
    }

    function resetCheck(){
      checked=false;
      matched=false;
      matchedName='';
      setAction('Tạo tủ',false);
    }

    $('driveLink').oninput=resetCheck;
    $('shelfName').oninput=function(){
      if(!checked)return;

      var name=$('shelfName').value.trim();

      if(matched && name.toUpperCase()==='DELETE'){
        setAction('Xóa tủ',true);
        $('shelfNote').innerHTML=
          '<strong>⚠ XÓA TỦ:</strong> Tủ <strong>'+esc(matchedName)+
          '</strong> sẽ bị xóa khỏi Tàng Thư. '+
          '<strong>Google Drive và toàn bộ sách sẽ không bị xóa.</strong>';
      }else if(matched){
        setAction('Đổi tên',!!name);
        $('shelfNote').textContent=
          'Đã nhận ra tủ hiện tại: '+matchedName+
          '. Thay đổi tên ở đây chỉ đổi tên hiển thị trên Tàng Thư.';
      }else{
        setAction('Tạo tủ',!!name);
      }
    };

    $('lookupBtn').onclick=function(){
      var link=$('driveLink').value.trim();
      var id=parseDriveId(link);

      if(!id){
        checked=false;
        matched=false;
        setAction('Tạo tủ',false);
        $('shelfMsg').textContent='Không nhận ra Folder ID từ đường link này.';
        $('shelfNote').textContent='Hãy dán đúng link thư mục Google Drive.';
        return;
      }

      var found=branches().find(function(x){
        return x.root_folder_id===id;
      });

      checked=true;

      if(found){
        matched=true;
        matchedName=found.name;
        $('shelfName').value=found.name;

        $('shelfMsg').textContent=
          'Đã nhận ra tủ: '+found.name+'.';

        $('shelfNote').textContent=
          'Tủ này đã tồn tại trên Tàng Thư. '+
          'Đổi tên bên dưới để sửa tên hiển thị, hoặc nhập DELETE để xóa tủ khỏi Tàng Thư.';

        setAction('Đổi tên',true);
      }else{
        matched=false;
        matchedName='';
        $('shelfName').value='';

        $('shelfMsg').textContent=
          'Link hợp lệ nhưng đây là một tủ mới.';

        $('shelfNote').textContent=
          'Nhập tên muốn hiển thị trên Tàng Thư rồi bấm Tạo tủ.';

        setAction('Tạo tủ',false);
      }
    };

    $('shareBtn').onclick=function(){
      if(!checked){
        $('shelfMsg').textContent='Hãy bấm Kiểm tra link trước.';
        return;
      }

      var link=$('driveLink').value.trim();
      var id=parseDriveId(link);

      if(!id){
        $('shelfMsg').textContent='Link Google Drive không hợp lệ.';
        return;
      }

      var name=$('shelfName').value.trim();

      if(!name){
        $('shelfMsg').textContent='Hãy nhập tên tủ sách.';
        return;
      }

      var isDelete=name.toUpperCase()==='DELETE';

      if(isDelete && !matched){
        $('shelfMsg').textContent=
          'Không thể xóa: link này chưa phải là một tủ đã đăng ký.';
        return;
      }

      var action=isDelete?'delete':(matched?'rename':'create');

      var title='[TANGTHU] '+
        (isDelete?'DELETE':name);

      var body=
        '- Google Drive: '+link+'\n'+
        '- Tên tủ: '+name+'\n'+
        '- Hành động: '+action+'\n'+
        '- Folder ID: '+id+'\n\n'+
        'Yêu cầu được tạo từ trang TÀNG THƯ.';

      var issueURL=
        'https://github.com/Zenkjt/tangthu-opds/issues/new'+
        '?title='+encodeURIComponent(title)+
        '&body='+encodeURIComponent(body);

      closeModal();
      window.open(issueURL,'_blank','noopener');
    };
  }
  function parseDriveId(s){var m=String(s||'').match(/\/folders\/([a-zA-Z0-9_-]+)/);if(m)return m[1];m=String(s||'').match(/[?&]id=([a-zA-Z0-9_-]+)/);return m?m[1]:''}
  function runSearch(){state.search=$('searchInput').value;renderContent()}

  $('upBtn').onclick=function(){var b=currentBranch();if(!b)return;if(state.search){state.search='';$('searchInput').value='';}if(state.parent!==b.root_folder_id){var f=findFile(b,state.parent);state.parent=f?f.parent_id:b.root_folder_id;state.selected=null;renderContent()}};
  $('homeBtn').onclick=function(){state.search='';$('searchInput').value='';state.selected=null;if(branches().length){state.branch=branches()[0].id;state.parent=branches()[0].root_folder_id}renderBranches();renderContent()};
  $('refreshBtn').onclick=function(){location.reload()};
  $('searchBtn').onclick=function(){$('searchInput').focus();$('searchInput').select()};
  $('searchDo').onclick=runSearch;$('searchInput').onkeydown=function(e){if(e.key==='Enter')runSearch()};
  $('shelfBtn').onclick=showShelf;$('infoBtn').onclick=showInfo;
  $('viewsBtn').onclick=function(){state.view=state.view==='list'?'compact':'list';$('viewsBtn').querySelector('.lbl').textContent=state.view==='list'?'Views':'List';};

  fetch('catalog.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('catalog '+r.status);return r.json()}).then(function(c){state.catalog=c;var bs=branches();if(bs.length){state.branch=bs[0].id;state.parent=bs[0].root_folder_id}renderBranches();renderContent();$('statusLeft').textContent='Sẵn sàng. '+bs.length+' tủ sách.'}).catch(function(e){$('statusLeft').textContent='Không tải được catalog.json';$('contentBody').innerHTML='<div class="empty">Không thể tải danh mục sách.<br><small>'+esc(e.message)+'</small></div>'});
})();
</script>
</body>
</html>`)
	return os.WriteFile(filepath.Join(out, "index.html"), []byte(b.String()), 0644)
}

func writeCatalogJSON(out string, branches []Branch) error {
	type JFile struct {
		ID       string `json:"id"`
		ParentID string `json:"parent_id"`
		Name     string `json:"name"`
		MIME     string `json:"mime"`
		Size     int64  `json:"size"`
		Modified string `json:"modified"`
		Checksum string `json:"checksum,omitempty"`
		Folder   bool   `json:"folder"`
	}
	type JBranch struct {
		ID           string  `json:"id"`
		Name         string  `json:"name"`
		RootFolderID string  `json:"root_folder_id"`
		DriveName    string  `json:"drive_name"`
		Files        []JFile `json:"files"`
	}
	var rows []JBranch
	for _, br := range branches {
		jb := JBranch{ID: br.Config.ID, Name: br.Config.DisplayName, RootFolderID: br.Config.RootFolderID, DriveName: br.DriveFolderName}
		for _, f := range br.Files {
			jb.Files = append(jb.Files, JFile{f.ID, f.ParentID, f.Name, f.MIME, f.Size, f.Modified, f.Checksum, f.IsFolder})
		}
		rows = append(rows, jb)
	}
	data, err := json.MarshalIndent(struct {
		Branches []JBranch `json:"branches"`
	}{rows}, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(out, "catalog.json"), data, 0644)
}

func writeOPDS(out, base string, branches []Branch) error {
	var root strings.Builder
	root.WriteString(xmlHead("TÀNG THƯ"))
	for _, br := range branches {
		root.WriteString(`<entry><title>` + esc(br.Config.DisplayName) + `</title><link rel="subsection" href="` + base + `/opds/branch/` + safe(br.Config.ID) + `/index.xml" type="application/atom+xml;profile=opds-catalog"/></entry>`)
	}
	root.WriteString(`</feed>`)
	if err := writeFile(filepath.Join(out, "opds", "index.xml"), root.String()); err != nil {
		return err
	}
	for _, br := range branches {
		dir := filepath.Join(out, "opds", "branch", br.Config.ID)
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}
		if err := writeBranchOPDS(dir, base, br); err != nil {
			return err
		}
	}
	return nil
}

func xmlHead(title string) string {
	return `<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>` + esc(title) + `</title>`
}

func writeBranchOPDS(dir, base string, br Branch) error {
	return writeFolder(dir, base, br, br.Config.RootFolderID, true)
}

func writeFolder(dir, base string, br Branch, folderID string, root bool) error {
	rows := children(br, folderID)
	relName := "index.xml"
	if !root {
		relName = safe(folderID) + ".xml"
	}
	var x strings.Builder
	title := br.Config.DisplayName
	if !root {
		for _, f := range br.Files {
			if f.ID == folderID {
				title += " / " + f.Name
				break
			}
		}
	}
	x.WriteString(xmlHead(title))
	if root {
		x.WriteString(`<link rel="start" href="` + base + `/opds/index.xml" type="application/atom+xml;profile=opds-catalog"/>`)
	}
	for _, f := range rows {
		if f.IsFolder {
			x.WriteString(`<entry><title>` + esc(f.Name) + `</title><link rel="subsection" href="` + base + `/opds/branch/` + safe(br.Config.ID) + `/` + safe(f.ID) + `.xml" type="application/atom+xml;profile=opds-catalog"/></entry>`)
			if err := writeFolder(dir, base, br, f.ID, false); err != nil {
				return err
			}
		} else {
			acq := acquisitionURL(f)
			modified := f.Modified
			x.WriteString(`<entry><title>` + esc(f.Name) + `</title>`)
			x.WriteString(`<updated>` + esc(modified) + `</updated>`)
			x.WriteString(`<content type="text">` + esc(formatFileInfo(f)) + `</content>`)
			x.WriteString(`<link rel="http://opds-spec.org/acquisition" href="` + esc(acq) + `" length="` + fmt.Sprint(f.Size) + `" mtime="` + esc(modified) + `" type="` + esc(mime(f.MIME)) + `"/></entry>`)
		}
	}
	x.WriteString(`</feed>`)
	return writeFile(filepath.Join(dir, relName), x.String())
}

func formatFileInfo(f FileEntry) string {
	return fmt.Sprintf("%s · %s · Modified: %s", formatSize(f.Size), displayType(f.MIME, f.Name), formatModified(f.Modified))
}
func formatSize(size int64) string {
	if size < 1024 {
		return fmt.Sprintf("%d B", size)
	}
	if size < 1024*1024 {
		return fmt.Sprintf("%.1f KB", float64(size)/1024)
	}
	if size < 1024*1024*1024 {
		return fmt.Sprintf("%.1f MB", float64(size)/(1024*1024))
	}
	return fmt.Sprintf("%.2f GB", float64(size)/(1024*1024*1024))
}
func displayType(mimeType, name string) string {
	ext := strings.ToLower(filepath.Ext(name))
	switch ext {
	case ".epub":
		return "EPUB"
	case ".pdf":
		return "PDF"
	case ".azw3":
		return "AZW3"
	case ".azw":
		return "AZW"
	case ".mobi":
		return "MOBI"
	case ".fb2":
		return "FB2"
	case ".cbz":
		return "CBZ"
	case ".cbr":
		return "CBR"
	case ".txt":
		return "TXT"
	case ".doc":
		return "DOC"
	case ".docx":
		return "DOCX"
	case ".rtf":
		return "RTF"
	case ".zip":
		return "ZIP"
	default:
		if mimeType != "" {
			return mimeType
		}
		return "FILE"
	}
}
func formatModified(s string) string {
	if t, err := time.Parse(time.RFC3339, s); err == nil {
		return t.Local().Format("02/01/2006 15:04")
	}
	return s
}
func writeFile(path, s string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(s), 0644)
}
