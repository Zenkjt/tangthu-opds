#!/usr/bin/env python3
from pathlib import Path

INDEX = Path("docs/index.html")
text = INDEX.read_text(encoding="utf-8")

css_marker = "/* TANGTHU_BOOKSHELF_V7 */"
css = r'''
/* TANGTHU_BOOKSHELF_V7 */
.shelf-view{padding:12px;background:#fff;min-height:100%}
.shelf-row{position:relative;margin:0 0 18px;padding:8px 12px 40px;min-height:220px;box-sizing:border-box;background-color:#c0c0c0;position:relative}
.shelf-row:last-child{margin-bottom:0}
.shelf-books{position:absolute;left:12px;right:12px;top:8px;bottom:40px;display:flex;justify-content:center;align-items:flex-end;gap:34px}
.shelf-book{position:relative;width:132px;min-width:132px;height:174px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;padding:0 5px;box-sizing:border-box;cursor:pointer;border:1px dotted transparent;background:transparent;color:#111}
.shelf-book:hover{background:transparent;border-color:#777}
.shelf-book:focus{outline:1px dotted #000;outline-offset:-1px}
.shelf-book-cover{position:relative;width:114px;height:140px;display:flex;align-items:center;justify-content:center;flex:none}
.shelf-book img{width:114px;height:140px;object-fit:contain;display:block;image-rendering:auto}
.shelf-book-name{position:absolute;left:18px;right:18px;top:80px;margin:0;padding:0;text-align:center;font-weight:bold;font-size:12px;line-height:1.16;color:#fff;background:transparent!important;border:0!important;box-shadow:none!important;text-shadow:1px 0 0 #000,-1px 0 0 #000,0 1px 0 #000,0 -1px 0 #000,1px 1px 0 #000,-1px -1px 0 #000,1px -1px 0 #000,-1px 1px 0 #000;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;min-height:0;z-index:2}
.shelf-book-stats{width:100%;height:22px;margin-top:4px;text-align:center;font-size:11px;line-height:22px;color:#333;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:none}
@media(max-width:1050px){
  .shelf-books{gap:26px}
  .shelf-book{width:122px;min-width:122px;height:164px}
  .shelf-book-cover,.shelf-book img{width:106px;height:130px}
  .shelf-book-name{left:16px;right:16px;top:75px;font-size:11.5px}
}
@media(max-width:760px){
  .shelf-view{padding:8px}
  .shelf-row{padding-left:7px;padding-right:7px;min-height:190px}
  .shelf-books{left:7px;right:7px;bottom:36px;gap:16px;flex-wrap:wrap}
  .shelf-book{width:100px;min-width:100px;height:142px}
  .shelf-book-cover,.shelf-book img{width:82px;height:108px}
  .shelf-book-name{left:14px;right:14px;top:61px;font-size:10.5px}
  .shelf-book-stats{height:20px;line-height:20px;font-size:10px}
}
@media(max-width:500px){
  .shelf-row{min-height:180px}
  .shelf-books{gap:8px}
  .shelf-book{width:92px;min-width:92px;height:132px}
  .shelf-book-cover,.shelf-book img{width:78px;height:102px}
  .shelf-book-name{left:12px;right:12px;top:57px;font-size:9.5px}
}
'''

if css_marker not in text:
    pos = text.rfind("</style>")
    if pos < 0:
        raise SystemExit("Bookshelf patch anchor missing: </style>")
    text = text[:pos] + css + "\n" + text[pos:]


start = text.find("  function renderShelfStats(){")
if start < 0:
    raise SystemExit("Bookshelf patch anchor missing: renderShelfStats")
end = text.find("  function renderContent(){", start)
if end < 0:
    raise SystemExit("Bookshelf patch anchor missing: renderContent")

renderer = r'''
  function renderShelfStats(){
    var body=$('contentBody');
    body.innerHTML='';
    $('pathBar').textContent='Tất cả tủ sách';
    var bs=branches();
    $('itemCount').textContent=bs.length+' tủ';
    if(!bs.length){body.innerHTML='<div class="empty">Chưa có tủ sách.</div>';return}

    var view=document.createElement('div');
    view.className='shelf-view';
    var iconNames=['book-blue.png','book-brown.png','book-green.png','book-purple.png','book-red.png','book-teal.png'];
    var perShelf=5;

    function shelfFiles(shelf){return filesOf(shelf).filter(function(f){return !f.folder;});}
    function extension(name){var p=String(name||'').lastIndexOf('.');return p<0?'':String(name).slice(p+1).toUpperCase();}
    function stats(shelf){
      var files=shelfFiles(shelf), counts={};
      files.forEach(function(f){var e=extension(f.name);if(e)counts[e]=(counts[e]||0)+1;});
      var parts=[files.length+' sách'];
      ['EPUB','MOBI','AZW3','PDF'].forEach(function(e){if(counts[e])parts.push(e+' '+counts[e]);});
      return parts.join(' · ');
    }
    function openShelf(shelf){
      state.view='list';
      state.branch=shelf.id;
      state.parent=shelf.root_folder_id;
      state.selected=null;
      $('viewsBtn').querySelector('.lbl').textContent='Views';
      renderBranches();
      renderContent();
    }

    for(var i=0;i<bs.length;i+=perShelf){
      var row=document.createElement('div');
      row.className='shelf-row';
      var books=document.createElement('div');
      books.className='shelf-books';

      bs.slice(i,i+perShelf).forEach(function(shelf,index){
        var item=document.createElement('button');
        item.type='button';
        item.className='shelf-book';
        item.title=shelf.display_name||shelf.name||'';
        item.setAttribute('aria-label',(shelf.display_name||shelf.name||'')+' — '+stats(shelf));

        var cover=document.createElement('div');
        cover.className='shelf-book-cover';

        /* PNG is artwork only. No canvas, no mask, no placeholder. */
        var img=document.createElement('img');
        img.src='assets/bookshelf/'+iconNames[(i+index)%iconNames.length];
        img.alt='';
        img.draggable=false;

        /* Transparent text overlay: white type with a black outline. */
        var name=document.createElement('div');
        name.className='shelf-book-name';
        name.textContent=shelf.display_name||shelf.name||'';

        cover.appendChild(img);
        cover.appendChild(name);

        var meta=document.createElement('div');
        meta.className='shelf-book-stats';
        meta.textContent=stats(shelf);

        item.appendChild(cover);
        item.appendChild(meta);
        item.onclick=(function(s){return function(){openShelf(s);};})(shelf);
        books.appendChild(item);
      });

      row.appendChild(books);
      view.appendChild(row);
    }
    body.appendChild(view);
  }

'''

text = text[:start] + renderer + text[end:]
INDEX.write_text(text, encoding="utf-8")
print("Applied TANG THU bookshelf presentation V5.")
