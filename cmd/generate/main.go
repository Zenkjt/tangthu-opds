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
	ID             string
	ParentID       string
	Name           string
	MIME           string
	Size           int64
	Modified       string
	Checksum       string
	IsFolder       bool
	WebContentLink string
}

type Branch struct {
	Config          BranchConfig
	DriveFolderName string
	Files           []FileEntry
	DriveFiles      []drive.File
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
				ID: f.ID, ParentID: f.ParentID, Name: f.Name, MIME: f.MIMEType, Size: f.Size,
				Modified: f.ModifiedTime, Checksum: f.MD5Checksum, IsFolder: drive.IsFolder(f), WebContentLink: f.WebContentLink,
			})
		}
		branches = append(branches, Branch{Config: bc, DriveFolderName: folder.Name, Files: converted, DriveFiles: files})
	}

	sort.SliceStable(branches, func(i, j int) bool {
		return branchLess(branches[i].Config.DisplayName, branches[j].Config.DisplayName)
	})

	// Keep repository-managed static assets (including docs/assets/bookshelf)
	// and replace only generated output.
	for _, path := range []string{
		filepath.Join(outDir, "index.html"),
		filepath.Join(outDir, "catalog.json"),
		filepath.Join(outDir, "opds"),
		filepath.Join(outDir, "covers"),
	} {
		if err := os.RemoveAll(path); err != nil {
			fatal(err.Error())
		}
	}
	for _, dir := range []string{
		filepath.Join(outDir, "opds"),
		filepath.Join(outDir, "covers"),
	} {
		if err := os.MkdirAll(dir, 0755); err != nil {
			fatal(err.Error())
		}
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
	return "https://drive.usercontent.google.com/download?id=" +
		url.QueryEscape(f.ID) +
		"&export=download&confirm=t"
}

func branchBookStats(b Branch) string {
	counts := map[string]int{}
	total := 0
	for _, f := range b.Files {
		if f.IsFolder {
			continue
		}
		total++
		ext := strings.ToLower(filepath.Ext(f.Name))
		switch ext {
		case ".epub":
			counts["EPUB"]++
		case ".mobi":
			counts["MOBI"]++
		case ".azw3", ".azw":
			counts["AZW3"]++
		case ".pdf":
			counts["PDF"]++
		case ".fb2":
			counts["FB2"]++
		case ".cbz":
			counts["CBZ"]++
		case ".cbr":
			counts["CBR"]++
		}
	}
	parts := []string{fmt.Sprintf("%d sách", total)}
	for _, k := range []string{"EPUB", "MOBI", "AZW3", "PDF", "FB2", "CBZ", "CBR"} {
		if counts[k] > 0 {
			parts = append(parts, fmt.Sprintf("%s %d", k, counts[k]))
		}
	}
	return strings.Join(parts, " · ")
}

func bookAsset(i int) string {
	names := []string{"red", "blue", "green", "brown", "purple", "teal"}
	if i < 0 {
		i = 0
	}
	return "/tangthu-opds/assets/bookshelf/book-" + names[i%len(names)] + ".png"
}

func titleClass(s string) string {
	n := len([]rune(strings.TrimSpace(s)))
	switch {
	case n > 28:
		return "xxlong"
	case n > 20:
		return "xlong"
	case n > 13:
		return "long"
	default:
		return ""
	}
}

func writeWeb(out, base string, branches []Branch) error {
	var b strings.Builder
	b.WriteString(`<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Tàng Thư — thư viện sách phân tán theo chuẩn OPDS">
<title>TÀNG THƯ — Thư viện sách phân tán</title>
<style>
:root{--gray:#c0c0c0;--light:#dfdfdf;--white:#fff;--dark:#404040;--black:#000;--select:#e6e6e6;--text:#111;--yellow:#ffffcc}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#c0c0c0;color:var(--text);font-family:Tahoma,Arial,sans-serif;font-size:14px}
body{min-height:100vh;padding:7px}
button{font:inherit;cursor:pointer;color:#000;background:#c0c0c0}
button:disabled{cursor:default;color:#777}
.win{max-width:1500px;margin:0 auto;border:2px solid #fff;border-right-color:#404040;border-bottom-color:#404040;background:#c0c0c0;box-shadow:1px 1px 0 #000}
.titlebar{height:34px;display:flex;align-items:center;gap:8px;padding:3px 7px;background:#dfdfdf;border-bottom:2px solid #808080;font-weight:bold;font-size:17px}
.titlebar .appicon{width:24px;height:24px;display:grid;place-items:center;background:#ffffcc;border:1px solid #777;font-size:15px}
.titlebar .caption{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.toolbar{display:flex;gap:4px;padding:5px;border-bottom:1px solid #808080;overflow-x:auto}
.tool{flex:0 0 auto;min-width:90px;height:70px;padding:4px 7px;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px}
.tool:active{border-color:#555 #fff #fff #555;padding:5px 6px 3px 8px}
.tool .ico{font-size:26px;line-height:28px}.tool .lbl{font-size:13px}
.brand{margin-left:auto;min-width:255px;height:70px;padding:6px 16px;border:2px solid #808080;border-right-color:#fff;border-bottom-color:#fff;background:#ffffcc;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.brand strong{font-size:21px}.brand em{font-family:Georgia,serif;font-size:15px;margin-top:3px}
.main{padding:5px}
.panel{min-width:0;border:2px solid #808080;border-right-color:#fff;border-bottom-color:#fff;background:#fff;overflow:hidden}
.panel-title{height:35px;display:flex;align-items:center;padding:5px 9px;background:#dfdfdf;border-bottom:1px solid #888;font-weight:bold;font-size:16px}
.panel-title .count{margin-left:auto;font-weight:normal;font-size:13px}
.content-path{padding:7px 10px;background:#ffffcc;border-bottom:1px solid #888;font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.panel-body{background:#fff}
.books{width:100%;border-collapse:collapse;table-layout:fixed}
.books th{position:sticky;top:0;z-index:2;background:#dfdfdf;border:1px solid #888;padding:5px;text-align:left}
.books td{border-bottom:1px solid #ccc;padding:6px 7px;vertical-align:middle;overflow:hidden;text-overflow:ellipsis}
.book-row{cursor:pointer}.book-row:hover{background:#f5f5f5}
.cover-fallback{width:58px;height:82px;display:grid;place-items:center;background:#ddd;border:1px solid #777;font-weight:bold;font-size:12px;text-align:center}
.name-cell strong{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.name-cell small{display:block;color:#444;margin-top:3px}
.folder-row td{font-weight:bold}
.searchbar{display:flex;gap:5px;align-items:center;padding:7px;border-top:1px solid #808080;background:#c0c0c0}
.searchbar label{font-weight:bold;white-space:nowrap}.searchbar input{min-width:0;flex:1;height:34px;padding:5px 8px;background:#fff;border:2px solid #777;border-right-color:#fff;border-bottom-color:#fff}
.searchbar button,.searchbar select{height:34px;min-width:80px;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}
.status{display:flex;justify-content:space-between;gap:8px;padding:5px 9px;border-top:2px solid #808080;background:#c0c0c0}
.status span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.empty{padding:30px;text-align:center;color:#555}
.modal-backdrop{display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.25);align-items:center;justify-content:center;padding:14px}
.modal-backdrop.open{display:flex}
.modal{width:min(620px,96vw);max-height:90vh;overflow:auto;background:#c0c0c0;border:2px solid #fff;border-right-color:#404040;border-bottom-color:#404040;box-shadow:3px 3px 0 #000}
.modal-title{height:34px;display:flex;align-items:center;padding:4px 6px;background:#000080;color:#fff;font-weight:bold}
.modal-title .close{margin-left:auto;min-width:28px;height:25px;border:2px solid #fff;border-right-color:#404040;border-bottom-color:#404040;background:#c0c0c0;color:#000;font-weight:bold}
.modal-body{padding:10px;background:#c0c0c0}
.modal-body fieldset{margin:0 0 10px;padding:9px;border:2px groove #fff}
.modal-body legend{padding:0 5px;font-weight:bold}
.modal-body label{display:block;margin-bottom:4px;font-weight:bold}
.modal-body input{width:100%;height:34px;padding:5px 7px;background:#fff;border:2px solid #777;border-right-color:#fff;border-bottom-color:#fff}
.modal-body .note{padding:8px;margin:8px 0;background:#ffffcc;border:1px solid #888;line-height:1.45}
.lookup-state{margin-top:7px;padding:6px;background:#dfdfdf;border:1px solid #888;min-height:30px}
.modal-actions{display:flex;justify-content:flex-end;gap:6px;margin-top:10px}
.modal-actions button{min-width:110px;height:34px;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}
.shelf-view{display:none;background:#cdcdcd;overflow:auto;max-height:calc(100vh - 255px);border:2px inset #eee}
.shelf-view.active{display:block}
.list-view.hidden{display:none}
.shelfrow{height:300px;min-width:900px;position:relative;background:#cdcdcd url("/tangthu-opds/assets/bookshelf/shelf-row.png") center bottom/100% 300px no-repeat}
.bookshelf-row{height:285px;padding:10px 42px 42px;display:grid;grid-template-columns:repeat(6,minmax(105px,1fr));gap:18px;align-items:end}
.booklink{height:235px;display:flex;justify-content:center;align-items:flex-end;position:relative;text-decoration:none;color:#111}
.bookimg{display:block;width:min(142px,100%);max-height:195px;object-fit:contain;filter:drop-shadow(2px 2px 0 rgba(0,0,0,.35))}
.booklabel{position:absolute;left:50%;transform:translateX(-50%);bottom:44px;width:min(108px,78%);min-height:46px;padding:4px;background:#e8e5d5;border:2px solid #222;box-shadow:1px 1px 0 #777;text-align:center;font-weight:bold;font-size:15px;line-height:17px;display:flex;align-items:center;justify-content:center;overflow-wrap:anywhere}
.booklabel.long{font-size:13px;line-height:15px}.booklabel.xlong{font-size:11px;line-height:13px}.booklabel.xxlong{font-size:10px;line-height:12px}
.bookstats{position:absolute;left:50%;transform:translateX(-50%);bottom:6px;width:min(160px,100%);font-size:10px;line-height:12px;text-align:center;font-weight:bold;text-shadow:0 1px #fff}
.booklink:hover .bookimg{filter:drop-shadow(3px 3px 0 #000080)}.booklink:hover .booklabel{background:#ffffcc}
@media(max-width:850px){
 body{padding:3px}.titlebar{height:31px;font-size:15px}.toolbar{display:grid;grid-template-columns:repeat(3,minmax(70px,1fr));overflow:visible}.tool{min-width:0;width:auto;height:58px}.brand{grid-column:1/-1;margin:0;height:52px;min-width:0}.brand strong{font-size:17px}.brand em{font-size:13px}.shelf-view{max-height:none}
 .bookshelf-row{grid-template-columns:repeat(3,minmax(110px,1fr));gap:12px;padding-left:25px;padding-right:25px}.shelfrow{min-width:520px;height:285px;background-size:100% 285px}.booklink{height:225px}.bookimg{max-height:185px}.bookstats{font-size:9px}
}
@media(max-width:430px){
 .bookshelf-row{grid-template-columns:repeat(2,minmax(125px,1fr));padding-left:18px;padding-right:18px}.shelfrow{min-width:390px;height:290px;background-size:100% 290px}.booklabel{width:100px}
}
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
    <button class="tool" id="viewBtn"><span class="ico">▥</span><span class="lbl">View</span></button>
    <button class="tool" id="infoBtn"><span class="ico">ℹ</span><span class="lbl">Info</span></button>
    <div class="brand"><strong>Bookshelves</strong><em>A book is a dream holding in your hands.</em></div>
  </div>

  <div class="main">
    <section class="panel list-view" id="listView">
      <div class="panel-title">TỦ SÁCH <span class="count" id="branchCount"></span></div>
      <div class="panel-body" id="listBody"></div>
    </section>

    <section class="panel shelf-view" id="shelfView">
      <div class="panel-title">TỦ SÁCH <span class="count" id="shelfCount"></span></div>
      <div id="shelfBody"></div>
    </section>
  </div>

  <div class="searchbar">
    <label for="searchInput">🔎 Tìm kiếm:</label>
    <input id="searchInput" type="search" placeholder="Nhập tên sách, tác giả, từ khóa..." autocomplete="off">
    <button id="searchDo">Tìm</button>
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
var state={catalog:null,branch:null,parent:null,search:'',shelf:false};
var $=function(id){return document.getElementById(id)};
var modal=function(title,body){$('modalTitle').textContent=title;$('modalBody').innerHTML=body;$('modalBackdrop').classList.add('open')};
var closeModal=function(){$('modalBackdrop').classList.remove('open')};
$('modalClose').onclick=closeModal;
$('modalBackdrop').onclick=function(e){if(e.target===$('modalBackdrop'))closeModal()};
var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})};
var ext=function(n){var m=String(n||'').toLowerCase().match(/\.([^.]+)$/);return m?m[1].toUpperCase():'FILE'};
function branches(){return state.catalog&&state.catalog.branches||[]}
function currentBranch(){return branches().find(function(b){return b.id===state.branch})}
function filesOf(b){return b&&b.files||[]}
function children(b,parent){return filesOf(b).filter(function(f){return f.parent_id===parent}).sort(function(a,c){if(!!a.folder!==!!c.folder)return a.folder?-1:1;return a.name.localeCompare(c.name,'vi',{sensitivity:'base'})})}
function findFile(b,id){return filesOf(b).find(function(f){return f.id===id})}
function folderPath(b,id){var out=[],guard=0;while(id&&id!==b.root_folder_id&&guard++<100){var f=findFile(b,id);if(!f)break;out.unshift(f.name);id=f.parent_id}return out}
function size(n){n=Number(n)||0;if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';if(n<1073741824)return (n/1048576).toFixed(1)+' MB';return (n/1073741824).toFixed(2)+' GB'}
function displayDate(s){if(!s)return '';var d=new Date(s);return isNaN(d)?s:d.toLocaleDateString('vi-VN')}
function branchStats(b){
 var counts={},total=0;
 filesOf(b).forEach(function(f){if(f.folder)return;total++;var e=ext(f.name);counts[e]=(counts[e]||0)+1});
 var p=[total+' sách'];['EPUB','MOBI','AZW3','PDF','FB2','CBZ','CBR'].forEach(function(k){if(counts[k])p.push(k+' '+counts[k])});
 return p.join(' · ');
}
function titleClass(s){var n=Array.from(String(s||'').trim()).length;return n>28?'xxlong':n>20?'xlong':n>13?'long':''}

function renderList(){
 var b=currentBranch(),body=$('listBody');
 if(!b){body.innerHTML='<div class="empty">Chưa có tủ sách.</div>';return}
 var rows=children(b,state.parent),q=state.search.trim().toLocaleLowerCase('vi-VN');
 if(q)rows=filesOf(b).filter(function(f){return !f.folder&&String(f.name).toLocaleLowerCase('vi-VN').indexOf(q)>=0});
 var html='<div class="content-path">'+esc([b.name].concat(folderPath(b,state.parent)).join(' › '))+'</div>';
 if(!rows.length){body.innerHTML=html+'<div class="empty">Thư mục này chưa có nội dung.</div>';return}
 html+='<table class="books"><thead><tr><th>Tên</th><th style="width:95px">Định dạng</th><th style="width:110px">Dung lượng</th><th style="width:100px">Ngày</th></tr></thead><tbody>';
 rows.forEach(function(f){
   if(f.folder)html+='<tr class="folder-row" data-folder="'+esc(f.id)+'"><td>📁 '+esc(f.name)+'</td><td>DIR</td><td></td><td></td></tr>';
   else html+='<tr class="book-row" data-file="'+esc(f.id)+'"><td><strong>'+esc(f.name)+'</strong></td><td>'+esc(ext(f.name))+'</td><td>'+size(f.size)+'</td><td>'+esc(displayDate(f.modified))+'</td></tr>';
 });
 html+='</tbody></table>';body.innerHTML=html;
 Array.from(body.querySelectorAll('[data-folder]')).forEach(function(el){el.onclick=function(){state.parent=el.getAttribute('data-folder');renderList()}});
}

function renderShelf(){
 var bs=branches(),body=$('shelfBody');$('shelfCount').textContent=bs.length+' tủ';
 if(!bs.length){body.innerHTML='<div class="empty">Chưa có tủ sách.</div>';return}
 var html='';
 for(var start=0;start<bs.length;start+=6){
   html+='<div class="shelfrow"><div class="bookshelf-row">';
   bs.slice(start,start+6).forEach(function(br,i){
     var idx=start+i;
     html+='<a class="booklink" href="#" data-branch="'+esc(br.id)+'" title="'+esc(br.name)+'">';
     html+='<img class="bookimg" src="/tangthu-opds/assets/bookshelf/book-'+['red','blue','green','brown','purple','teal'][idx%6]+'.png" alt="">';
     html+='<span class="booklabel '+titleClass(br.name)+'">'+esc(br.name)+'</span>';
     html+='<span class="bookstats">'+esc(branchStats(br))+'</span></a>';
   });
   html+='</div></div>';
 }
 body.innerHTML=html;
 Array.from(body.querySelectorAll('[data-branch]')).forEach(function(el){el.onclick=function(e){e.preventDefault();state.branch=el.getAttribute('data-branch');state.parent=currentBranch().root_folder_id;state.shelf=false;state.search='';$('searchInput').value='';updateView();renderList()}});
}

function updateView(){
 $('listView').classList.toggle('hidden',state.shelf);
 $('shelfView').classList.toggle('active',state.shelf);
 $('viewBtn').querySelector('.lbl').textContent=state.shelf?'List':'View';
 if(state.shelf)renderShelf();else renderList();
}
function selectBranch(id){state.branch=id;var b=currentBranch();state.parent=b?b.root_folder_id:null;state.search='';$('searchInput').value='';updateView()}
$('viewBtn').onclick=function(){state.shelf=!state.shelf;updateView()};
$('refreshBtn').onclick=function(){location.reload()};
$('homeBtn').onclick=function(){var bs=branches();if(bs.length)selectBranch(bs[0].id)};
$('upBtn').onclick=function(){var b=currentBranch();if(!b)return;if(state.parent!==b.root_folder_id){var f=findFile(b,state.parent);state.parent=f?f.parent_id:b.root_folder_id;renderList()}};
$('searchBtn').onclick=function(){$('searchInput').focus()};
// Registration UI is injected by scripts/postprocess_registration.py.
// Keep these anchors stable; the generated bookshelf view is controlled by View.
  function showShelf(){}
  function runSearch(){
 state.search=$('searchInput').value;
 state.shelf=false;
 updateView();
}
$('searchDo').onclick=runSearch;
$('searchInput').onkeydown=function(e){if(e.key==='Enter')runSearch()};
$('shelfBtn').onclick=showShelf;
$('infoBtn').onclick=function(){alert('Tàng Thư — thư viện sách phân tán theo chuẩn OPDS.')};

fetch('catalog.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('catalog '+r.status);return r.json()}).then(function(c){
 state.catalog=c;var bs=branches();if(bs.length){state.branch=bs[0].id;state.parent=bs[0].root_folder_id}
 $('branchCount').textContent=bs.length+' tủ';$('statusLeft').textContent='Sẵn sàng. '+bs.length+' tủ sách.';
 renderList();
}).catch(function(e){$('statusLeft').textContent='Không tải được catalog.json';$('listBody').innerHTML='<div class="empty">Không thể tải danh mục sách.<br><small>'+esc(e.message)+'</small></div>'});
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
			jb.Files = append(jb.Files, JFile{ID: f.ID, ParentID: f.ParentID, Name: f.Name, MIME: f.MIME, Size: f.Size, Modified: f.Modified, Checksum: f.Checksum, Folder: f.IsFolder})
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
