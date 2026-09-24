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
  /* Font preview — standalone Tàng Thư window. */
  var CPFONT_WASM_URL = __WASM_URL__;
  var CPFONT_WORKER_URL = __WORKER_URL__;
  var CPFONT_SAMPLE =
    'Buổi sáng hôm nay, mùa đông đột nhiên đến, không báo trước. Vừa mới ngày hôm qua giời hãy còn nắng ấm và hanh, cái nắng về cuối tháng mười làm nứt nẻ đất ruộng, và làm giòn khô những chiếc lá rơi. Sơn và chị chơi cỏ gà ở ngoài cánh đồng còn thấy nóng bức, chảy mồ hôi.\\n\\n' +
    'Thế mà qua một đêm mưa rào, trời bỗng đổi ra gió bấc, rồi cái lạnh ở đâu đến làm cho người ta tưởng đang ở giữa mùa đông rét mướt. Sơn tung chăn tỉnh dậy, nhưng không bước xuống giường ngay như mọi khi, còn ngồi thu tay vào trong bọc, bên cạnh đứa em bé vẫn nắm tay ngủ kỹ. Chị Sơn và mẹ Sơn đã trở dậy, đang ngồi quạt hỏa lò để pha nước chè uống. Sơn nhìn thấy mọi người đã mặc áo rét cả rồi.';

  var CPFONT_DEVICES = [
    {id: 1, name: 'X3', size: '528 × 792'},
    {id: 0, name: 'X4', size: '480 × 800'}
  ];
  var CPFONT_STATE = {file:null, bytes:null, busy:false, token:0, device:0, browserUrl:null, browserFamily:null};

  function fontPreviewIsFile(f){
    return !!f && !f.folder && /\\.(cpfont|ttf|otf)$/i.test(String(f.name||'')) && Number(f.size||0)<=25*1024*1024;
  }
  function cpfontIsFile(f){
    return !!f && !f.folder && /\\.cpfont$/i.test(String(f.name||'')) && Number(f.size||0)<=25*1024*1024;
  }
  function escFontName(s){return String(s||'').replace(/[&<>\"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c];});}
  function cpfontImports(){return {wasi_snapshot_preview1:{fd_close:function(){return 0},fd_seek:function(){return 0n},fd_write:function(){return 0}}};}
  function cpfontTitle(s){var e=document.getElementById('cpfontWindowTitle');if(e)e.innerHTML=s;}
  function cpfontButtons(id){document.querySelectorAll('#cpfontWindow .cpfont-device-btn').forEach(function(b){b.classList.toggle('cpfont-device-active',Number(b.dataset.device)===Number(id));});}
  function cpfontClose(){CPFONT_STATE.token++;CPFONT_STATE.busy=false;if(CPFONT_STATE.browserUrl){URL.revokeObjectURL(CPFONT_STATE.browserUrl);CPFONT_STATE.browserUrl=null;}CPFONT_STATE.file=null;CPFONT_STATE.bytes=null;var e=document.getElementById('cpfontWindow');if(e)e.remove();}

  async function cpfontRender(deviceId,token){
    if(!CPFONT_STATE.bytes||!CPFONT_STATE.file||token!==CPFONT_STATE.token)return;
    var d=CPFONT_DEVICES.find(function(x){return Number(x.id)===Number(deviceId)});if(!d)return;
    CPFONT_STATE.busy=true;CPFONT_STATE.device=deviceId;cpfontButtons(deviceId);cpfontTitle(escFontName(CPFONT_STATE.file.name)+' · '+d.name+' · đang render…');
    try{
      var wr=await fetch(CPFONT_WASM_URL,{cache:'force-cache'});if(!wr.ok)throw new Error('CrossGlyph WASM HTTP '+wr.status);
      var inst=(await WebAssembly.instantiate(await wr.arrayBuffer(),cpfontImports())).instance;if(token!==CPFONT_STATE.token)return;
      var ex=inst.exports,mem=ex.memory;if(!mem)throw new Error('CrossGlyph WASM không export memory');
      ex.rc_init();if(!ex.rc_set_device(d.id))throw new Error('Không chọn được '+d.name);
      var bytes=new Uint8Array(CPFONT_STATE.bytes),ptr=ex.malloc(bytes.length);new Uint8Array(mem.buffer,ptr,bytes.length).set(bytes);
      if(!ex.rc_font_load(ptr,bytes.length))throw new Error('File CPFont không hợp lệ');
      ex.rc_page_set_spec(5,0,0,1,100);var tb=new TextEncoder().encode(CPFONT_SAMPLE+'\\0'),tp=ex.malloc(tb.length);new Uint8Array(mem.buffer,tp,tb.length).set(tb);
      var lines=ex.rc_page_render(tp,0,0,0,0xFF);if(lines<0)throw new Error('CrossPoint render thất bại');
      var pw=ex.rc_panel_width(),ph=ex.rc_panel_height(),sw=ex.rc_screen_width(),sh=ex.rc_screen_height();
      var fb=new Uint8Array(mem.buffer,ex.rc_framebuffer(),ex.rc_framebuffer_size()),image=new ImageData(sw,sh);
      for(var y=0;y<sh;y++)for(var x=0;x<sw;x++){var phyX=y,phyY=ph-1-x,bit=phyY*pw+phyX,on=(fb[bit>>3]&(0x80>>(bit&7)))!==0,v=on?255:0,i=(y*sw+x)*4;image.data[i]=v;image.data[i+1]=v;image.data[i+2]=v;image.data[i+3]=255;}
      if(token!==CPFONT_STATE.token)return;var c=document.getElementById('cpfontCanvas');if(!c)return;c.width=sw;c.height=sh;c.getContext('2d').putImageData(image,0,0);cpfontTitle(escFontName(CPFONT_STATE.file.name)+' · '+d.name+' · '+lines+' dòng');
    }catch(e){if(token===CPFONT_STATE.token){cpfontTitle(escFontName(CPFONT_STATE.file.name)+' · '+d.name+' · lỗi render');console.error('[CPFont]',e);}}finally{if(token===CPFONT_STATE.token)CPFONT_STATE.busy=false;}
  }

  async function browserFontRender(deviceId,token){
    if(!CPFONT_STATE.bytes||!CPFONT_STATE.file||token!==CPFONT_STATE.token)return;
    var d=CPFONT_DEVICES.find(function(x){return Number(x.id)===Number(deviceId)});if(!d)return;
    CPFONT_STATE.busy=true;CPFONT_STATE.device=deviceId;cpfontButtons(deviceId);cpfontTitle(escFontName(CPFONT_STATE.file.name)+' · '+d.name+' · đang render…');
    try{
      if(!CPFONT_STATE.browserUrl){CPFONT_STATE.browserUrl=URL.createObjectURL(new Blob([CPFONT_STATE.bytes]));CPFONT_STATE.browserFamily='TangThuFont_'+Date.now();var face=new FontFace(CPFONT_STATE.browserFamily,'url("'+CPFONT_STATE.browserUrl+'")');await face.load();document.fonts.add(face);}
      if(token!==CPFONT_STATE.token)return;var c=document.getElementById('cpfontCanvas');if(!c)return;
      var parts=d.size.split('×');c.width=Number(parts[0]);c.height=Number(parts[1]);var ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle='#000';
      var fontSize=Math.max(16,Math.round(c.width*0.052)),lineHeight=Math.round(fontSize*1.42);ctx.font=fontSize+'px "'+CPFONT_STATE.browserFamily+'"';ctx.textBaseline='top';var maxWidth=c.width-32,y=18,lines=0;
      CPFONT_SAMPLE.split('\\n').forEach(function(paragraph){if(!paragraph){y+=Math.round(lineHeight*.55);return;}var words=paragraph.split(/\s+/),line='';words.forEach(function(word){var test=line?line+' '+word:word;if(ctx.measureText(test).width>maxWidth&&line){ctx.fillText(line,16,y);y+=lineHeight;lines++;line=word;}else line=test;});if(line){ctx.fillText(line,16,y);y+=lineHeight;lines++;}});
      cpfontTitle(escFontName(CPFONT_STATE.file.name)+' · '+d.name+' · '+lines+' dòng');
    }catch(e){if(token===CPFONT_STATE.token){cpfontTitle(escFontName(CPFONT_STATE.file.name)+' · '+d.name+' · lỗi render');console.error('[Font preview]',e);}}finally{if(token===CPFONT_STATE.token)CPFONT_STATE.busy=false;}
  }

  function cpfontSelectDevice(deviceId){if(!CPFONT_STATE.bytes||!CPFONT_STATE.file||CPFONT_STATE.busy)return;var token=++CPFONT_STATE.token;if(cpfontIsFile(CPFONT_STATE.file))cpfontRender(deviceId,token);else browserFontRender(deviceId,token);}

  async function showCPFontPreview(f){
    if(!fontPreviewIsFile(f))return;cpfontClose();var isCP=cpfontIsFile(f),downloadUrl=CPFONT_WORKER_URL+'/download/'+encodeURIComponent(f.id);
    var w=document.createElement('div');w.id='cpfontWindow';w.className='cpfont-window';
    w.innerHTML='<div class="cpfont-window-box">' +
      '<div class="cpfont-window-head"><div id="cpfontWindowTitle">Đang tải '+escFontName(f.name)+'…</div><div class="cpfont-head-actions"><a class="cpfont-download" href="'+downloadUrl+'" target="_blank" rel="noopener">Download</a><button type="button" class="cpfont-close" aria-label="Đóng">×</button></div></div>'+
      '<div class="cpfont-render-area"><div class="cpfont-loading" id="cpfontLoading">Đang tải '+(isCP?'CPFont':'font')+'…</div><canvas id="cpfontCanvas" class="cpfont-canvas"></canvas></div>'+
      '<div class="cpfont-controls"><button type="button" class="cpfont-device-btn" data-device="1">X3<small>528 × 792</small></button><button type="button" class="cpfont-device-btn cpfont-device-active" data-device="0">X4<small>480 × 800</small></button></div></div>';
    document.body.appendChild(w);w.querySelector('.cpfont-close').addEventListener('click',cpfontClose);w.querySelectorAll('.cpfont-device-btn').forEach(function(b){b.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();cpfontSelectDevice(Number(b.dataset.device));});});w.addEventListener('click',function(e){if(e.target===w)cpfontClose();});
    CPFONT_STATE.file=f;CPFONT_STATE.bytes=null;CPFONT_STATE.busy=false;CPFONT_STATE.device=0;CPFONT_STATE.token++;
    try{
      var r=await fetch(CPFONT_WORKER_URL+'/download/'+encodeURIComponent(f.id),{method:'GET',cache:'no-store'});if(!r.ok)throw new Error('Download Worker HTTP '+r.status);var bytes=await r.arrayBuffer();
      if(!bytes.byteLength)throw new Error('Worker trả về file rỗng');if(bytes.byteLength>25*1024*1024)throw new Error('File vượt giới hạn 25 MB');if(!document.getElementById('cpfontWindow'))return;
      CPFONT_STATE.bytes=bytes;var loading=document.getElementById('cpfontLoading');if(loading)loading.remove();var token=++CPFONT_STATE.token;if(isCP)cpfontRender(0,token);else browserFontRender(0,token);
    }catch(e){if(!document.getElementById('cpfontWindow'))return;cpfontTitle(escFontName(f.name)+' · lỗi');var loading=document.getElementById('cpfontLoading');if(loading)loading.textContent='Không thể xem trước font: '+(e.message||e);console.error('[Font preview]',e);}
  }

  var oldShowBook=showBook;
  showBook=function(f){if(fontPreviewIsFile(f)){showCPFontPreview(f);return;}oldShowBook(f);};
'''
inject = inject.replace("__WASM_URL__", repr(WASM_URL)).replace("__WORKER_URL__", repr(worker))
text = text.replace(anchor, inject + anchor, 1)

css_anchor = ".modal-body{padding:14px}"
if css_anchor not in text:
    raise SystemExit("CPFont patch anchor missing: modal CSS")
css = (
    ".cpfont-window{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;padding:8px;box-sizing:border-box;background:rgba(0,0,0,.35)}"
    ".cpfont-window-box{width:min(620px,calc(100vw - 16px));max-height:calc(100vh - 16px);display:flex;flex-direction:column;overflow:hidden;background:#c0c0c0;color:#000;font-family:Arial,sans-serif;border:2px solid #fff;border-right-color:#404040;border-bottom-color:#404040;box-sizing:border-box}"
    ".cpfont-window-head{flex:0 0 auto;min-height:36px;display:flex;align-items:center;justify-content:space-between;gap:7px;padding:3px 5px 3px 8px;background:#d8d8d8;border-bottom:1px solid #808080;font-size:14px;font-weight:700;box-sizing:border-box}"
    ".cpfont-head-actions{display:flex;align-items:center;gap:8px;white-space:nowrap}.cpfont-download{color:#000;text-decoration:underline;font-weight:700;font-size:13px}"
    ".cpfont-close{width:29px;height:29px;padding:0;flex:0 0 29px;font-size:21px;line-height:24px;font-weight:700;background:#c0c0c0;color:#000;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;cursor:pointer}"
    ".cpfont-close:active{border-color:#555;border-right-color:#fff;border-bottom-color:#fff}.cpfont-render-area{min-height:0;flex:1 1 auto;display:flex;align-items:center;justify-content:center;overflow:hidden;padding:3px;background:#c0c0c0;box-sizing:border-box}"
    ".cpfont-canvas{display:block;width:auto;height:auto;max-width:100%;max-height:calc(100vh - 105px);background:#fff;border:1px solid #555;box-sizing:border-box;image-rendering:pixelated}.cpfont-loading{position:absolute;padding:6px 9px;background:#ffffcc;border:1px solid #808080;font-size:13px;font-weight:700}"
    ".cpfont-controls{flex:0 0 auto;display:flex;gap:7px;padding:5px 6px 6px;background:#c0c0c0;border-top:1px solid #808080;box-sizing:border-box}.cpfont-device-btn{flex:1 1 0;min-width:0;height:42px;padding:2px 8px;background:#c0c0c0;color:#000;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;cursor:pointer;font:700 15px/16px Arial,sans-serif;text-align:center;box-sizing:border-box}"
    ".cpfont-device-btn small{display:block;font-size:11px;line-height:11px;font-weight:400}.cpfont-device-btn:active{border-color:#555;border-right-color:#fff;border-bottom-color:#fff}.cpfont-device-btn.cpfont-device-active{border-color:#555;border-right-color:#fff;border-bottom-color:#fff}"
    "@media(max-width:600px){.cpfont-window{padding:4px}.cpfont-window-box{width:calc(100vw - 8px);max-height:calc(100vh - 8px)}.cpfont-canvas{max-height:calc(100vh - 101px)}}"
)
text = text.replace(css_anchor, css_anchor + css, 1)
HTML.write_text(text, encoding="utf-8")
