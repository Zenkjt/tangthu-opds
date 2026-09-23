
#!/usr/bin/env python3
from pathlib import Path
import os

HTML = Path("docs/index.html")
WASM_URL = "https://raw.githubusercontent.com/CrazyCoder/crossglyph/master/src/crossglyph/render/render.wasm"

worker = os.environ.get("TANGTHU_DOWNLOAD_WORKER_URL", "").strip().rstrip("/")
if not worker:
    raise SystemExit("TANGTHU_DOWNLOAD_WORKER_URL is required")

text = HTML.read_text(encoding="utf-8")

anchor = "  fetch('catalog.json',{cache:'no-store'}).then(function(r){"
if anchor not in text:
    raise SystemExit("CPFont patch anchor missing: catalog bootstrap")

inject = r'''
  /* CPFont preview: reuse the existing Tàng Thư download Worker.
     The browser never talks to Google Drive directly. */
  var CPFONT_WASM_URL = __WASM_URL__;
  var CPFONT_WORKER_URL = __WORKER_URL__;

  function cpfontIsFile(f){
    return !!f && !f.folder && /\.cpfont$/i.test(String(f.name||'')) &&
      Number(f.size||0) <= 25*1024*1024;
  }

  function cpfontImports(memoryRef){
    return {wasi_snapshot_preview1:{
      fd_close:function(){return 0},
      fd_seek:function(){return 0n},
      fd_write:function(fd,iovs,len,nwritten){
        if(memoryRef) new DataView(memoryRef.buffer).setUint32(nwritten,0,true);
        return 0;
      }
    }};
  }

  async function cpfontRender(bytes, canvas){
    var wasmResponse=await fetch(CPFONT_WASM_URL,{cache:'force-cache'});
    if(!wasmResponse.ok) throw new Error('CrossGlyph WASM HTTP '+wasmResponse.status);
    var instance=(await WebAssembly.instantiate(
      await wasmResponse.arrayBuffer(),cpfontImports(null)
    )).instance;
    var ex=instance.exports, memory=ex.memory;
    if(!memory) throw new Error('CrossGlyph WASM không export memory');
    ex.rc_init();
    if(!ex.rc_set_device(0)) throw new Error('Không chọn được X4/X4 Pro');

    var fontBytes=new Uint8Array(bytes);
    var ptr=ex.malloc(fontBytes.length);
    new Uint8Array(memory.buffer,ptr,fontBytes.length).set(fontBytes);
    if(!ex.rc_font_load(ptr,fontBytes.length))
      throw new Error('File không phải CPFont hợp lệ hoặc bị lỗi');

    ex.rc_page_set_spec(5,0,0,1,100);

    var sample='Buổi sáng hôm nay, mùa đông đột nhiên đến, không báo trước. Vừa mới ngày hôm qua giời hãy còn nắng ấm và hanh, cái nắng về cuối tháng mười làm nứt nẻ đất ruộng, và làm giòn khô những chiếc lá rơi. Sơn và chị chơi cỏ gà ở ngoài cánh đồng còn thấy nóng bức, chảy mồ hôi.';
    var textBytes=new TextEncoder().encode(sample+'\0');
    var textPtr=ex.malloc(textBytes.length);
    new Uint8Array(memory.buffer,textPtr,textBytes.length).set(textBytes);

    var lines=ex.rc_page_render(textPtr,0,0,0,0xFF);
    if(lines<0) throw new Error('CrossPoint render thất bại: '+lines);

    var pw=ex.rc_panel_width(), ph=ex.rc_panel_height();
    var sw=ex.rc_screen_width(), sh=ex.rc_screen_height();
    var fb=new Uint8Array(memory.buffer,ex.rc_framebuffer(),ex.rc_framebuffer_size());
    var image=new ImageData(sw,sh);

    for(var y=0;y<sh;y++){
      for(var x=0;x<sw;x++){
        var phyX=y,phyY=ph-1-x;
        var bit=phyY*pw+phyX;
        var on=(fb[bit>>3]&(0x80>>(bit&7)))!==0;
        var v=on?0:255, i=(y*sw+x)*4;
        image.data[i]=image.data[i+1]=image.data[i+2]=v;
        image.data[i+3]=255;
      }
    }

    canvas.width=sw;
    canvas.height=sh;
    canvas.getContext('2d').putImageData(image,0,0);
    return lines;
  }

  async function showCPFontPreview(f){
    if(!cpfontIsFile(f)) return;

    modal('XEM CPFONT',
      '<div class="cpfont-preview-status" id="cpfontStatus">Đang lấy font từ Tàng Thư…</div>'+
      '<canvas id="cpfontCanvas" class="cpfont-canvas"></canvas>');

    try{
      var response=await fetch(CPFONT_WORKER_URL+'/download/'+encodeURIComponent(f.id),{
        method:'GET',
        cache:'no-store'
      });
      if(!response.ok)
        throw new Error('Tàng Thư download Worker HTTP '+response.status);

      var bytes=await response.arrayBuffer();
      if(!bytes.byteLength) throw new Error('Worker trả về file rỗng');
      if(bytes.byteLength>25*1024*1024)
        throw new Error('File vượt giới hạn 25 MB');

      var lines=await cpfontRender(bytes,$('cpfontCanvas'));
      $('cpfontStatus').textContent=
        f.name+' · '+bytes.byteLength+' bytes · '+lines+' dòng';
    }catch(e){
      $('cpfontStatus').textContent='Không thể xem CPFont: '+e.message;
    }
  }

  var oldShowBook=showBook;
  showBook=function(f){
    oldShowBook(f);
    if(cpfontIsFile(f)){
      var body=$('modalBody');
      var actions=document.createElement('div');
      actions.className='modal-actions';
      actions.innerHTML='<button id="cpfontPreviewBtn">Xem CPFont</button>';
      body.appendChild(actions);
      $('cpfontPreviewBtn').onclick=function(){showCPFontPreview(f)};
    }
  };

'''
inject = inject.replace("__WASM_URL__", repr(WASM_URL)).replace("__WORKER_URL__", repr(worker))
text = text.replace(anchor, inject + anchor, 1)

css_anchor = ".modal-body{padding:14px}"
if css_anchor not in text:
    raise SystemExit("CPFont patch anchor missing: modal CSS")
css = ".cpfont-preview-status{margin-bottom:10px;padding:7px 9px;background:#ffffcc;border:1px solid #888}.cpfont-canvas{display:block;max-width:100%;height:auto;background:#fff;border:1px solid #555;image-rendering:pixelated;margin:0 auto}"
text = text.replace(css_anchor, css_anchor + css, 1)

HTML.write_text(text, encoding="utf-8")
print("CPFont preview injector ready.")
