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
     Clicking a .cpfont opens the renderer directly; no book-info screen. */
  var CPFONT_WASM_URL = __WASM_URL__;
  var CPFONT_WORKER_URL = __WORKER_URL__;

  var CPFONT_BYTES = null;
  var CPFONT_DEVICE_ID = 0;
  var CPFONT_DEVICE_LABEL = 'X4';
  var CPFONT_DEVICE_W = 480;
  var CPFONT_DEVICE_H = 800;

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
    var el=$('cpfontLog');
    if(el){
      el.textContent += (el.textContent ? '\n' : '') + msg;
      el.scrollTop=el.scrollHeight;
    }
    console.log('[CPFont]',msg);
  }

  async function cpfontRender(bytes, canvas){
    cpfontLog('WASM: tải CrossGlyph…');
    var wasmResponse=await fetch(CPFONT_WASM_URL,{cache:'force-cache'});
    cpfontLog('WASM: HTTP '+wasmResponse.status);
    if(!wasmResponse.ok) throw new Error('CrossGlyph WASM HTTP '+wasmResponse.status);

    var instance=(await WebAssembly.instantiate(
      await wasmResponse.arrayBuffer(),cpfontImports(null)
    )).instance;
    cpfontLog('WASM: instantiate OK');

    var ex=instance.exports, memory=ex.memory;
    if(!memory) throw new Error('CrossGlyph WASM không export memory');
    ex.rc_init();
    cpfontLog('WASM: init OK');

    if(!ex.rc_set_device(CPFONT_DEVICE_ID))
      throw new Error('Không chọn được thiết bị preview');

    cpfontLog('Thiết bị: '+CPFONT_DEVICE_LABEL+' — '+CPFONT_DEVICE_W+'×'+CPFONT_DEVICE_H);

    var fontBytes=new Uint8Array(bytes);
    cpfontLog('CPFont: '+fontBytes.length+' bytes');
    var ptr=ex.malloc(fontBytes.length);
    new Uint8Array(memory.buffer,ptr,fontBytes.length).set(fontBytes);

    if(!ex.rc_font_load(ptr,fontBytes.length))
      throw new Error('File không phải CPFont hợp lệ hoặc bị lỗi');
    cpfontLog('CPFont: load OK');

    ex.rc_page_set_spec(5,0,0,1,100);

    var sample=`Buổi sáng hôm nay, mùa đông đột nhiên đến, không báo trước. Vừa mới ngày hôm qua giời hãy còn nắng ấm và hanh, cái nắng về cuối tháng mười làm nứt nẻ đất ruộng, và làm giòn khô những chiếc lá rơi. Sơn và chị chơi cỏ gà ở ngoài cánh đồng còn thấy nóng bức, chảy mồ hôi.

Thế mà qua một đêm mưa rào, trời bỗng đổi ra gió bấc, rồi cái lạnh ở đâu đến làm cho người ta tưởng đang ở giữa mùa đông rét mướt. Sơn tung chăn tỉnh dậy, nhưng không bước xuống giường ngay như mọi khi, còn ngồi thu tay vào trong bọc, bên cạnh đứa em bé vẫn nắm tay ngủ kỹ. Chị Sơn và mẹ Sơn đã trở dậy, đang ngồi quạt hỏa lò để pha nước chè uống. Sơn nhìn thấy mọi người đã mặc áo rét cả rồi.

Nhìn ra ngoài sân, Sơn thấy đất khô trắng, luôn luôn cơn gió vi vu làm bốc lên những màn bụi nhỏ, thổi lăn những cái lá khô lạo xạo. Trời không u ám, toàn một màu trắng đục. Những cây lan trông chậu, lá rung động và hình như sắt lại vì rét.`;

    var textBytes=new TextEncoder().encode(sample+'\0');
    var textPtr=ex.malloc(textBytes.length);
    new Uint8Array(memory.buffer,textPtr,textBytes.length).set(textBytes);

    var lines=ex.rc_page_render(textPtr,0,0,0,0xFF);
    if(lines<0) throw new Error('CrossPoint render thất bại: '+lines);
    cpfontLog('Render: OK — '+lines+' dòng');

    var pw=ex.rc_panel_width(), ph=ex.rc_panel_height();
    var sw=ex.rc_screen_width(), sh=ex.rc_screen_height();
    var fb=new Uint8Array(memory.buffer,ex.rc_framebuffer(),ex.rc_framebuffer_size());
    var image=new ImageData(sw,sh);

    /* CPFont preview: black text on white background. */
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
    cpfontLog('Framebuffer: '+sw+'×'+sh);
    return lines;
  }

  async function cpfontRenderSelected(){
    if(!CPFONT_BYTES) return;

    var canvas=$('cpfontCanvas');
    var status=$('cpfontStatus');
    var buttons=document.querySelectorAll('.cpfont-device');

    buttons.forEach(function(b){
      b.classList.toggle('selected',Number(b.dataset.device)===CPFONT_DEVICE_ID &&
        String(b.dataset.label||'')===CPFONT_DEVICE_LABEL);
    });

    status.textContent='Đang render '+CPFONT_DEVICE_LABEL+'…';
    status.style.display='block';

    try{
      await cpfontRender(CPFONT_BYTES,canvas);
      status.textContent=CPFONT_DEVICE_LABEL+' · '+CPFONT_DEVICE_W+' × '+CPFONT_DEVICE_H;
      setTimeout(function(){
        if(status) status.style.display='none';
      },500);
      cpfontLog('HOÀN TẤT');
    }catch(e){
      status.textContent='Render lỗi: '+e.message;
      status.style.display='block';
      cpfontLog('FAIL: '+(e.stack || e.message || String(e)));
    }
  }

  async function showCPFontPreview(f){
    if(!cpfontIsFile(f)) return;

    modal('XEM CPFONT',
      '<div class="cpfont-toolbar">'+
        '<div class="cpfont-file">'+f.name+'</div>'+
        '<div class="cpfont-devices">'+
          '<button type="button" class="cpfont-device" data-device="1" data-label="X3" onclick="cpfontSelectDevice(1,\'X3\',528,792)">X3<br><small>528 × 792</small></button>'+
          '<button type="button" class="cpfont-device selected" data-device="0" data-label="X4" onclick="cpfontSelectDevice(0,\'X4\',480,800)">X4<br><small>480 × 800</small></button>'+
          '<button type="button" class="cpfont-device" data-device="0" data-label="X4 Pro" onclick="cpfontSelectDevice(0,\'X4 Pro\',480,800)">X4 Pro<br><small>480 × 800</small></button>'+
        '</div>'+
      '</div>'+
      '<div class="cpfont-preview-wrap">'+
        '<div class="cpfont-screen-frame">'+
          '<div class="cpfont-loading" id="cpfontStatus">Đang tải CPFont…</div>'+
          '<canvas id="cpfontCanvas" class="cpfont-canvas"></canvas>'+
        '</div>'+
        '<pre class="cpfont-log" id="cpfontLog"></pre>'+
      '</div>');

    CPFONT_BYTES=null;
    CPFONT_DEVICE_ID=0;
    CPFONT_DEVICE_LABEL='X4';
    CPFONT_DEVICE_W=480;
    CPFONT_DEVICE_H=800;

    cpfontLog('File: '+f.name);
    cpfontLog('ID: '+f.id);
    cpfontLog('Bắt đầu tải qua Tàng Thư Download Worker…');

    try{
      var response=await fetch(CPFONT_WORKER_URL+'/download/'+encodeURIComponent(f.id),{
        method:'GET',
        cache:'no-store'
      });
      cpfontLog('Worker: HTTP '+response.status);

      if(!response.ok)
        throw new Error('Tàng Thư download Worker HTTP '+response.status);

      var bytes=await response.arrayBuffer();
      cpfontLog('Worker: nhận '+bytes.byteLength+' bytes');

      if(!bytes.byteLength) throw new Error('Worker trả về file rỗng');
      if(bytes.byteLength>25*1024*1024)
        throw new Error('File vượt giới hạn 25 MB');

      CPFONT_BYTES=bytes;
      await cpfontRenderSelected();
    }catch(e){
      $('cpfontStatus').textContent='Không thể xem CPFont: '+e.message;
      $('cpfontStatus').style.display='block';
      cpfontLog('FAIL: '+(e.stack || e.message || String(e)));
    }
  }

  function cpfontSelectDevice(id,label,w,h){
    if(!CPFONT_BYTES) return;
    CPFONT_DEVICE_ID=id;
    CPFONT_DEVICE_LABEL=label;
    CPFONT_DEVICE_W=w;
    CPFONT_DEVICE_H=h;
    cpfontRenderSelected();
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
    ".cpfont-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;"
    "padding:8px 10px;margin-bottom:10px;border:1px solid #777;background:#ddd}"
    ".cpfont-file{font-weight:bold;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
    ".cpfont-devices{display:flex;gap:6px;flex-shrink:0}"
    ".cpfont-device{min-width:82px;padding:5px 8px;background:#eee;border:2px solid #888;"
    "box-shadow:2px 2px 0 #666;font-weight:bold;cursor:pointer}"
    ".cpfont-device.selected{background:#fff;border-color:#111;box-shadow:2px 2px 0 #111}"
    ".cpfont-device small{font-weight:normal;font-size:10px}"
    ".cpfont-preview-wrap{display:flex;flex-direction:column;gap:10px}"
    ".cpfont-screen-frame{position:relative;display:flex;justify-content:center;align-items:flex-start;"
    "min-height:180px;padding:10px;background:#bbb;border:2px solid #666;overflow:auto}"
    ".cpfont-canvas{display:block;max-width:100%;max-height:62vh;width:auto;height:auto;"
    "background:#fff;border:1px solid #555;image-rendering:pixelated}"
    ".cpfont-loading{position:absolute;top:16px;left:50%;transform:translateX(-50%);"
    "padding:6px 9px;background:#fff;border:1px solid #777;font-weight:bold;z-index:2}"
    ".cpfont-log{height:120px;overflow:auto;margin:0;padding:7px 9px;background:#111;color:#fff;"
    "border:1px solid #555;font:12px/1.35 monospace;white-space:pre-wrap}"
)

text = text.replace(css_anchor, css_anchor + css, 1)

out = Path("/mnt/data/postprocess_cpfont.py")
out.write_text(text, encoding="utf-8")
print(f"Đã tạo: {out}")
