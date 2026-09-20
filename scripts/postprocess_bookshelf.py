#!/usr/bin/env python3
from pathlib import Path

INDEX = Path("docs/index.html")
text = INDEX.read_text(encoding="utf-8")

css_marker = "/* TANGTHU_BOOKSHELF_V4 */"
css = r'''
/* TANGTHU_BOOKSHELF_V4 */
.shelf-view{padding:12px;background:#fff;min-height:100%}
.shelf-row{position:relative;margin:0 0 18px;padding:8px 12px 34px;min-height:190px;background-color:#c0c0c0;background-image:url('assets/bookshelf/shelf-row.png');background-repeat:repeat-x;background-position:left bottom;background-size:auto 34px}
.shelf-row:last-child{margin-bottom:0}
.shelf-books{display:flex;justify-content:center;align-items:flex-end;gap:42px;min-height:150px}
.shelf-book{position:relative;width:132px;min-width:132px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;padding:4px 5px 0;cursor:pointer;border:1px dotted transparent;background:transparent;color:#111}
.shelf-book:hover{background:#f5f5f5;border-color:#777}
.shelf-book:focus{outline:1px dotted #000;outline-offset:-1px}
.shelf-book-cover{position:relative;width:108px;height:132px;display:flex;align-items:center;justify-content:center}
.shelf-book img{width:108px;height:132px;object-fit:contain;display:block;image-rendering:auto}
.shelf-book-name{position:absolute;left:14px;right:14px;top:76px;margin:0;padding:0;text-align:center;font-weight:bold;font-size:13px;line-height:1.12;color:#111;background:transparent;border:0;box-shadow:none;text-shadow:0 1px 0 rgba(255,255,255,.7);display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;min-height:0;z-index:2}
.shelf-book-stats{width:100%;margin-top:5px;text-align:center;font-size:11px;line-height:1.15;color:#333;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:1050px){.shelf-books{gap:30px}.shelf-book{width:122px;min-width:122px}.shelf-book-cover,.shelf-book img{width:100px;height:124px}.shelf-book-name{left:13px;right:13px;top:71px;font-size:12px}}
@media(max-width:760px){.shelf-view{padding:8px}.shelf-row{padding-left:7px;padding-right:7px}.shelf-books{gap:16px;flex-wrap:wrap}.shelf-book{width:100px;min-width:100px}.shelf-book-cover,.shelf-book img{width:82px;height:108px}.shelf-book-name{left:12px;right:12px;top:62px;font-size:11px}.shelf-book-stats{font-size:10px}}
@media(max-width:500px){.shelf-books{gap:8px}.shelf-book{width:92px;min-width:92px}.shelf-book-cover,.shelf-book img{width:78px;height:102px}.shelf-book-name{left:10px;right:10px;top:58px;font-size:10px}}
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

renderer = r'''  function renderShelfStats(){
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

        /* Use the PNG directly. No canvas and no erased/grey rectangle. */
        var img=document.createElement('img');
        img.src='assets/bookshelf/'+iconNames[(i+index)%iconNames.length];
        img.alt='';
        img.draggable=false;

        /* Name is rendered directly over the clean book face. */
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
print("Applied TANG THU bookshelf presentation V4.")
