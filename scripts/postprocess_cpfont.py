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
  /* CPFont preview — Tàng Thư UI.
     .cpfont opens directly in the preview modal, not the book-info modal. */
  var CPFONT_WASM_URL = __WASM_URL__;
  var CPFONT_WORKER_URL = __WORKER_URL__;
  var CPFONT_SAMPLE =
    'Buổi sáng hôm nay, mùa đông đột nhiên đến, không báo trước. Vừa mới ngày hôm qua giời hãy còn nắng ấm và hanh, cái nắng về cuối tháng mười làm nứt nẻ đất ruộng, và làm giòn khô những chiếc lá rơi. Sơn và chị chơi cỏ gà ở ngoài cánh đồng còn thấy nóng bức, chảy mồ hôi.\n\n' +
    'Thế mà qua một đêm mưa rào, trời bỗng đổi ra gió bấc, rồi cái lạnh ở đâu đến làm cho người ta tưởng đang ở giữa mùa đông rét mướt. Sơn tung chăn tỉnh dậy, nhưng không bước xuống giường ngay như mọi khi, còn ngồi thu tay vào trong bọc, bên cạnh đứa em bé vẫn nắm tay ngủ kỹ. Chị Sơn và mẹ Sơn đã trở dậy, đang ngồi quạt hỏa lò để pha nước chè uống. Sơn nhìn thấy mọi người đã mặc áo rét cả rồi.\n\n' +
    'Nhìn ra ngoài sân, Sơn thấy đất khô trắng, luôn luôn cơn gió vi vu làm bốc lên những màn bụi nhỏ, thổi lăn những cái lá khô lạo xạo. Trời không u ám, toàn một màu trắng đục. Những cây lan trông chậu, lá rung động và hình như sắt lại vì rét.';

  var CPFONT_DEVICES = [
    {id: 1, name: 'X3', size: '528 × 792'},
    {id: 0, name: 'X4', size: '480 × 800'}
  ];

  var CPFONT_CURRENT = null;
  var CPFONT_BYTES = null;
  var CPFONT_RENDERING = false;

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

  function cpfontLog(msg){
    console.log('[CPFont]',msg);
  }

  function cpfontSetStatus(msg){
    var el=$('cpfontStatus');
    if(el) el.textContent=msg;
  }

  function cpfontSetActiveButton(deviceIndex){
    document.querySelectorAll('.cpfont-device-btn').forEach(function(btn){
      btn.classList.toggle('cpfont-device-active',
        Number(btn.getAttribute('data-index'))===Number(deviceIndex));
    });
  }

  async function cpfontRender(bytes, canvas, deviceIndex){
    if(CPFONT_RENDERING) return;
    CPFONT_RENDERING=true;

    var d=CPFONT_DEVICES[deviceIndex];
    try{
      cpfontSetActiveButton(deviceIndex);
      cpfontSetStatus('Đang tải bộ render…');
      var wasmResponse=await fetch(CPFONT_WASM_URL,{cache:'force-cache'});
      if(!wasmResponse.ok)
        throw new Error('CrossGlyph WASM HTTP '+wasmResponse.status);

      var instance=(await WebAssembly.instantiate(
        await wasmResponse.arrayBuffer(),cpfontImports(null)
      )).instance;
      var ex=instance.exports, memory=ex.memory;
      if(!memory) throw new Error('CrossGlyph WASM không export memory');

      ex.rc_init();

      if(!ex.rc_set_device(d.id))
        throw new Error('Không chọn được thiết bị '+d.name);

      var fontBytes=new Uint8Array(bytes);

      var ptr=ex.malloc(fontBytes.length);
      new Uint8Array(memory.buffer,ptr,fontBytes.length).set(fontBytes);

      if(!ex.rc_font_load(ptr,fontBytes.length))
        throw new Error('File không phải CPFont hợp lệ hoặc bị lỗi');

      ex.rc_page_set_spec(5,0,0,1,100);

      var textBytes=new TextEncoder().encode(CPFONT_SAMPLE+'\0');
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

      cpfontSetStatus(CPFONT_CURRENT.name+' · '+d.name+' · '+lines+' dòng');
    } finally {
      CPFONT_RENDERING=false;
    }
  }

  async function cpfontSelectDevice(deviceIndex){
    if(!CPFONT_BYTES || !CPFONT_CURRENT || CPFONT_RENDERING) return;

    var d=CPFONT_DEVICES[deviceIndex];
    if(!d) return;

    try{
      await cpfontRender(CPFONT_BYTES,$('cpfontCanvas'),deviceIndex);
    }catch(e){
      cpfontSetStatus('Không thể render: '+e.message);
      cpfontLog('FAIL: '+(e.stack || e.message || String(e)));
    }
  }

  async function showCPFontPreview(f){
    if(!cpfontIsFile(f)) return;

    modal('XEM CPFONT',
      '<div class="cpfont-controls">'+
        '<span class="cpfont-device-label">MÀN HÌNH</span>'+
        '<button type="button" class="cpfont-device-btn" data-index="0" onclick="cpfontSelectDevice(0);return false">X3<br><small>528 × 792</small></button>'+
        '<button type="button" class="cpfont-device-btn cpfont-device-active" data-index="1" onclick="cpfontSelectDevice(1);return false">X4<br><small>480 × 800</small></button>'+
      '</div>'+
      '<div class="cpfont-preview-frame">'+
        '<div class="cpfont-preview-status" id="cpfontStatus">Đang tải CPFont…</div>'+
        '<div class="cpfont-canvas-wrap"><canvas id="cpfontCanvas" class="cpfont-canvas"></canvas></div>'+
      '</div>');

    CPFONT_CURRENT=f;
    CPFONT_BYTES=null;

    cpfontSetStatus('Đang tải CPFont…');

    try{
      var response=await fetch(CPFONT_WORKER_URL+'/download/'+encodeURIComponent(f.id),{
        method:'GET',
        cache:'no-store'
      });

      if(!response.ok)
        throw new Error('Tàng Thư download Worker HTTP '+response.status);

      CPFONT_BYTES=await response.arrayBuffer();

      if(!CPFONT_BYTES.byteLength) throw new Error('Worker trả về file rỗng');
      if(CPFONT_BYTES.byteLength>25*1024*1024)
        throw new Error('File vượt giới hạn 25 MB');

      await cpfontSelectDevice(1);
    }catch(e){
      cpfontSetStatus('Không thể xem CPFont: '+e.message);
    }
  }

  var oldShowBook=showBook;
  showBook=function(f){
    if(cpfontIsFile(f)){
      showCPFontPreview(f);
      return;
    }
    oldShowBook(f);
  };

'''

inject = inject.replace("__WASM_URL__", repr(WASM_URL)).replace("__WORKER_URL__", repr(worker))
text = text.replace(anchor, inject + anchor, 1)

css_anchor = ".modal-body{padding:14px}"
if css_anchor not in text:
    raise SystemExit("CPFont patch anchor missing: modal CSS")

css = (
    ".cpfont-controls{display:flex;align-items:center;justify-content:center;gap:8px;"
    "margin:0 0 8px;padding:0;background:transparent}"
    ".cpfont-device-label{font-weight:bold;margin-right:2px}"
    ".cpfont-device-btn{font:700 14px/1.15 Arial,sans-serif;padding:6px 12px;"
    "min-width:82px;background:#ddd;color:#000;border:2px solid #fff;"
    "border-right-color:#555;border-bottom-color:#555;cursor:pointer;text-align:center}"
    ".cpfont-device-btn:active,.cpfont-device-active{border:2px solid #555;"
    "border-right-color:#fff;border-bottom-color:#fff;background:#c0c0c0}"
    ".cpfont-device-btn small{font-weight:normal}"
    ".cpfont-preview-frame{display:flex;flex-direction:column;align-items:center;"
    "padding:6px;background:#c0c0c0;border:2px solid #fff;"
    "border-right-color:#555;border-bottom-color:#555;box-sizing:border-box;"
    "overflow:auto}"
    ".cpfont-preview-status{margin:0 0 6px;padding:4px 7px;background:#ffffcc;"
    "border:1px solid #808080;font-weight:bold;color:#000;box-sizing:border-box;"
    "max-width:100%;font:700 13px/1.2 Arial,sans-serif}"
    ".cpfont-canvas-wrap{display:flex;justify-content:center;align-items:flex-start;"
    "background:#fff;border:1px solid #555;overflow:auto;max-width:100%;"
    "box-sizing:border-box}"
    ".cpfont-canvas{display:block;max-width:100%;height:auto;background:#fff;"
    "image-rendering:pixelated;margin:0}"
)
text = text.replace(css_anchor, css_anchor + css, 1)

HTML.write_text(text, encoding="utf-8")
