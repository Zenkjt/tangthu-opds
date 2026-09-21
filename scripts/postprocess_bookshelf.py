#!/usr/bin/env python3
from pathlib import Path

INDEX = Path("docs/index.html")
text = INDEX.read_text(encoding="utf-8")

css_marker = "/* TANGTHU_BOOKSHELF_V7 */"
css = r'''
/* TANGTHU_BOOKSHELF_V7 */
.shelf-view{padding:12px;background:#fff;min-height:100%;overflow:hidden}
.shelf-row{position:relative;margin:0 0 18px;padding:10px 12px 44px;min-height:196px;background:#c0c0c0;overflow:hidden}
.shelf-row::after{content:"";position:absolute;left:0;right:0;bottom:12px;height:12px;background:linear-gradient(to bottom,#a66a1f 0,#d08a28 38%,#8a5416 62%,#5f3a0d 100%);border:2px solid #5b370c;box-sizing:border-box;box-shadow:0 2px 0 #2b1a07,0 -1px 0 #e2a34b;pointer-events:none}
.shelf-row:last-child{margin-bottom:0}
.shelf-books{display:flex;flex-wrap:wrap;justify-content:center;align-items:flex-end;gap:18px 18px;min-height:166px;width:100%}
.shelf-book{position:relative;width:220px;min-width:220px;display:grid;grid-template-columns:112px 1fr;grid-template-rows:132px auto;column-gap:10px;align-items:end;justify-content:center;padding:0;cursor:pointer;border:1px dotted transparent;background:transparent;color:#111}
.shelf-book:hover{background:#f5f5f5;border-color:#777}
.shelf-book:focus{outline:1px dotted #000;outline-offset:-1px}
.shelf-book-cover{position:relative;width:108px;height:132px;grid-column:1;grid-row:1;display:flex;align-items:center;justify-content:center}
.shelf-book img{width:108px;height:132px;object-fit:contain;display:block;image-rendering:auto}
.shelf-book-name{position:absolute;left:16px;right:16px;top:79px;margin:0;padding:0 7px;text-align:center;font-weight:bold;font-size:13px;line-height:1.12;color:#fff;background:transparent;border:0;box-shadow:none;text-shadow:-1px -1px 0 #000,1px -1px 0 #000,-1px 1px 0 #000,1px 1px 0 #000;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;min-height:0;z-index:2;box-sizing:border-box}
.shelf-book-stats{grid-column:2;grid-row:1;align-self:center;width:100%;margin:0;padding:4px 0;text-align:left;font-size:11px;line-height:1.35;color:#333;white-space:normal;overflow:visible}
.shelf-book-stats span{display:block}
.shelf-book::after{content:"";grid-column:1 / -1;grid-row:2;height:20px}
@media(max-width:1050px){.shelf-books{gap:18px 12px}.shelf-book{width:200px;min-width:200px;grid-template-columns:100px 1fr;column-gap:8px}.shelf-book-cover,.shelf-book img{width:100px;height:124px}.shelf-book-name{left:14px;right:14px;top:74px;font-size:12px;padding:0 6px}.shelf-book-stats{font-size:10px}}
@media(max-width:760px){.shelf-view{padding:8px}.shelf-row{padding-left:7px;padding-right:7px}.shelf-books{gap:16px 10px}.shelf-book{width:180px;min-width:180px;grid-template-columns:88px 1fr;column-gap:6px}.shelf-book-cover,.shelf-book img{width:82px;height:108px}.shelf-book-name{left:11px;right:11px;top:63px;font-size:11px;padding:0 5px}.shelf-book-stats{font-size:10px}}
@media(max-width:500px){.shelf-books{gap:12px 8px}.shelf-book{width:165px;min-width:165px;grid-template-columns:78px 1fr}.shelf-book-cover,.shelf-book img{width:78px;height:102px}.shelf-book-name{left:10px;right:10px;top:58px;font-size:10px;padding:0 4px}}
'''

# The generator recreates docs/index.html on every build, so the bookshelf CSS
# must not depend on a marker from a previous generated page. Replace our
# previous block when present; otherwise insert it at the end of <style>.
if css_marker in text:
    pos = text.find(css_marker)
    end = text.find("\n</style>", pos)
    if end < 0:
        raise SystemExit("Bookshelf patch anchor missing: </style>")
    text = text[:pos] + text[end + 1:]

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
    function statsLines(shelf){
      var files=shelfFiles(shelf), counts={};
      files.forEach(function(f){var e=extension(f.name);if(e)counts[e]=(counts[e]||0)+1;});
      return [
        files.length+' sách',
        'EPUB '+(counts.EPUB||0),
        'MOBI '+(counts.MOBI||0),
        'AZW3 '+(counts.AZW3||0)
      ];
    }
    function stats(shelf){return statsLines(shelf).join(' · ');}
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
        statsLines(shelf).forEach(function(line){
          var lineEl=document.createElement('span');
          lineEl.textContent=line;
          meta.appendChild(lineEl);
        });

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
print("Applied TANG THU bookshelf presentation V7.")
