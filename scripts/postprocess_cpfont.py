#!/usr/bin/env python3
from pathlib import Path
import json
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
  /* Font preview — CPFont via CrossPoint WASM; TTF/OTF via browser FontFace. */
  var FONT_PREVIEW_WASM_URL = __WASM_URL__;
  var FONT_PREVIEW_WORKER_URL = __WORKER_URL__;
  var FONT_PREVIEW_SAMPLE =
    'Buổi sáng hôm nay, mùa đông đột nhiên đến, không báo trước. Vừa mới ngày hôm qua giời hãy còn nắng ấm và hanh, cái nắng về cuối tháng mười làm nứt nẻ đất ruộng, và làm giòn khô những chiếc lá rơi. Sơn và chị chơi cỏ gà ở ngoài cánh đồng còn thấy nóng bức, chảy mồ hôi.\n\n' +
    'Thế mà qua một đêm mưa rào, trời bỗng đổi ra gió bấc, rồi cái lạnh ở đâu đến làm cho người ta tưởng đang ở giữa mùa đông rét mướt. Sơn tung chăn tỉnh dậy, nhưng không bước xuống giường ngay như mọi khi, còn ngồi thu tay vào trong bọc, bên cạnh đứa em bé vẫn nắm tay ngủ kỹ. Chị Sơn và mẹ Sơn đã trở dậy, đang ngồi quạt hỏa lò để pha nước chè uống. Sơn nhìn thấy mọi người đã mặc áo rét cả rồi.';
  var FONT_PREVIEW_DEVICES = [
    {id: 1, name: 'X3', size: '528 × 792'},
    {id: 0, name: 'X4', size: '480 × 800'}
  ];
  var FONT_PREVIEW_STATE = {file:null, bytes:null, busy:false, token:0, device:0, kind:null, fontFamily:null};

  function fontPreviewIsFile(f){
    return !!f && !f.folder && /\.(cpfont|ttf|otf)$/i.test(String(f.name||'')) && Number(f.size||0)<=25*1024*1024;
  }
  function cpfontImports(){return {wasi_snapshot_preview1:{fd_close:function(){return 0},fd_seek:function(){return 0n},fd_write:function(){return 0}}};}
  function fontPreviewTitle(s){var e=document.getElementById('cpfontWindowTitle');if(e)e.textContent=s;}
  function fontPreviewButtons(id){document.querySelectorAll('#cpfontWindow .cpfont-device-btn').forEach(function(b){b.classList.toggle('cpfont-device-active',Number(b.dataset.device)===Number(id));});}
  function fontPreviewEsc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  function fontPreviewDownloadURL(f){return FONT_PREVIEW_WORKER_URL+'/download/'+encodeURIComponent(f.id);}
  function fontPreviewClose(){
    FONT_PREVIEW_STATE.token++;FONT_PREVIEW_STATE.busy=false;
    if(FONT_PREVIEW_STATE.fontFamily){try{document.fonts.delete(FONT_PREVIEW_STATE.fontFamily);}catch(e){}}
    FONT_PREVIEW_STATE.file=null;FONT_PREVIEW_STATE.bytes=null;FONT_PREVIEW_STATE.fontFamily=null;
    var e=document.getElementById('cpfontWindow');if(e)e.remove();
  }

  async function cpfontRender(deviceId,token){
    if(!FONT_PREVIEW_STATE.bytes||!FONT_PREVIEW_STATE.file||token!==FONT_PREVIEW_STATE.token)return;
    var d=FONT_PREVIEW_DEVICES.find(function(x){return Number(x.id)===Number(deviceId)});if(!d)return;
    FONT_PREVIEW_STATE.busy=true;FONT_PREVIEW_STATE.device=deviceId;FONT_PREVIEW_STATE.kind='cpfont';fontPreviewButtons(deviceId);
    fontPreviewTitle(FONT_PREVIEW_STATE.file.name+' · '+d.name+' · đang render…');
    try{
      var wr=await fetch(FONT_PREVIEW_WASM_URL,{cache:'force-cache'});if(!wr.ok)throw new Error('CrossGlyph WASM HTTP '+wr.status);
      var inst=(await WebAssembly.instantiate(await wr.arrayBuffer(),cpfontImports())).instance;if(token!==FONT_PREVIEW_STATE.token)return;
      var ex=inst.exports,mem=ex.memory;if(!mem)throw new Error('CrossGlyph WASM không export memory');ex.rc_init();
      if(!ex.rc_set_device(d.id))throw new Error('Không chọn được '+d.name);
      var bytes=new Uint8Array(FONT_PREVIEW_STATE.bytes),ptr=ex.malloc(bytes.length);new Uint8Array(mem.buffer,ptr,bytes.length).set(bytes);
      if(!ex.rc_font_load(ptr,bytes.length))throw new Error('File CPFont không hợp lệ');
      ex.rc_page_set_spec(5,0,0,1,100);
      var tb=new TextEncoder().encode(FONT_PREVIEW_SAMPLE+'\0'),tp=ex.malloc(tb.length);new Uint8Array(mem.buffer,tp,tb.length).set(tb);
      var lines=ex.rc_page_render(tp,0,0,0,0xFF);if(lines<0)throw new Error('CrossPoint render thất bại');
      var pw=ex.rc_panel_width(),ph=ex.rc_panel_height(),sw=ex.rc_screen_width(),sh=ex.rc_screen_height();
      var fb=new Uint8Array(mem.buffer,ex.rc_framebuffer(),ex.rc_framebuffer_size()),image=new ImageData(sw,sh);
      for(var y=0;y<sh;y++)for(var x=0;x<sw;x++){var phyX=y,phyY=ph-1-x,bit=phyY*pw+phyX,on=(fb[bit>>3]&(0x80>>(bit&7)))!==0,v=on?255:0,i=(y*sw+x)*4;image.data[i]=v;image.data[i+1]=v;image.data[i+2]=v;image.data[i+3]=255;}
      if(token!==FONT_PREVIEW_STATE.token)return;var c=document.getElementById('cpfontCanvas');if(!c)return;c.width=sw;c.height=sh;c.getContext('2d').putImageData(image,0,0);
      fontPreviewTitle(FONT_PREVIEW_STATE.file.name+' · '+d.name+' · '+lines+' dòng');
    }catch(e){if(token===FONT_PREVIEW_STATE.token){fontPreviewTitle(FONT_PREVIEW_STATE.file.name+' · '+d.name+' · lỗi render');console.error('[FontPreview]',e);}}
    finally{if(token===FONT_PREVIEW_STATE.token)FONT_PREVIEW_STATE.busy=false;}
  }

  function fontPreviewWrap(ctx,text,maxWidth){
    var out=[];text.split('\n').forEach(function(p,pi){if(!p){out.push('');return;}var words=p.split(/\s+/),line='';words.forEach(function(w){var t=line?line+' '+w:w;if(line&&ctx.measureText(t).width>maxWidth){out.push(line);line=w;}else line=t;});if(line)out.push(line);if(pi<text.split('\n').length-1)out.push('');});return out;
  }
  async function ttfOtfRender(deviceId,token){
    if(!FONT_PREVIEW_STATE.bytes||!FONT_PREVIEW_STATE.file||token!==FONT_PREVIEW_STATE.token)return;
    var d=FONT_PREVIEW_DEVICES.find(function(x){return Number(x.id)===Number(deviceId)});if(!d)return;
    FONT_PREVIEW_STATE.busy=true;FONT_PREVIEW_STATE.device=deviceId;FONT_PREVIEW_STATE.kind='ttf-otf';fontPreviewButtons(deviceId);
    fontPreviewTitle(FONT_PREVIEW_STATE.file.name+' · '+d.name+' · đang render…');
    try{
      var family='TangThuPreview_'+Date.now()+'_'+Math.random().toString(36).slice(2),face=new FontFace(family,FONT_PREVIEW_STATE.bytes);await face.load();if(token!==FONT_PREVIEW_STATE.token)return;
      document.fonts.add(face);FONT_PREVIEW_STATE.fontFamily=family;
      var c=document.getElementById('cpfontCanvas');if(!c)return;var parts=d.size.split(' × ');c.width=Number(parts[0]);c.height=Number(parts[1]);
      var ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle='#000';
      var fontSize=Math.max(16,Math.round(c.width*0.046)),lineHeight=Math.round(fontSize*1.45),margin=Math.max(18,Math.round(c.width*0.055));
      ctx.font=fontSize+'px "'+family+'"';ctx.textBaseline='top';var lines=fontPreviewWrap(ctx,FONT_PREVIEW_SAMPLE,c.width-margin*2),y=margin,drawn=0;
      for(var i=0;i<lines.length;i++){if(y+lineHeight>c.height-margin)break;ctx.fillText(lines[i],margin,y);y+=lineHeight;drawn++;}
      if(token!==FONT_PREVIEW_STATE.token)return;fontPreviewTitle(FONT_PREVIEW_STATE.file.name+' · '+d.name+' · '+drawn+' dòng');
    }catch(e){if(token===FONT_PREVIEW_STATE.token){fontPreviewTitle(FONT_PREVIEW_STATE.file.name+' · '+d.name+' · lỗi render');console.error('[FontPreview]',e);}}
    finally{if(token===FONT_PREVIEW_STATE.token)FONT_PREVIEW_STATE.busy=false;}
  }
  function fontPreviewSelectDevice(deviceId){
    if(!FONT_PREVIEW_STATE.bytes||!FONT_PREVIEW_STATE.file||FONT_PREVIEW_STATE.busy)return;var token=++FONT_PREVIEW_STATE.token;
    if(FONT_PREVIEW_STATE.kind==='cpfont')cpfontRender(deviceId,token);else ttfOtfRender(deviceId,token);
  }
  async function showFontPreview(f){
    if(!fontPreviewIsFile(f))return;fontPreviewClose();var isCP=/\.cpfont$/i.test(String(f.name||''));
    var w=document.createElement('div');w.id='cpfontWindow';w.className='cpfont-window';
    w.innerHTML='<div class="cpfont-window-box"><div class="cpfont-window-head"><div id="cpfontWindowTitle">Đang tải '+fontPreviewEsc(f.name)+'…</div><a class="cpfont-download" href="'+fontPreviewDownloadURL(f)+'" target="_blank" rel="noopener">Download</a><button type="button" class="cpfont-close" aria-label="Đóng">×</button></div><div class="cpfont-render-area"><div class="cpfont-loading" id="cpfontLoading">Đang tải '+(isCP?'CPFont':'font')+'…</div><canvas id="cpfontCanvas" class="cpfont-canvas"></canvas></div><div class="cpfont-controls"><button type="button" class="cpfont-device-btn" data-device="1">X3<small>528 × 792</small></button><button type="button" class="cpfont-device-btn cpfont-device-active" data-device="0">X4<small>480 × 800</small></button></div></div>';
    document.body.appendChild(w);w.querySelector('.cpfont-close').addEventListener('click',fontPreviewClose);
    w.querySelectorAll('.cpfont-device-btn').forEach(function(b){b.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();fontPreviewSelectDevice(Number(b.dataset.device));});});
    w.addEventListener('click',function(e){if(e.target===w)fontPreviewClose();});
    FONT_PREVIEW_STATE.file=f;FONT_PREVIEW_STATE.bytes=null;FONT_PREVIEW_STATE.busy=false;FONT_PREVIEW_STATE.device=0;FONT_PREVIEW_STATE.kind=isCP?'cpfont':'ttf-otf';FONT_PREVIEW_STATE.fontFamily=null;FONT_PREVIEW_STATE.token++;
    try{
      var r=await fetch(FONT_PREVIEW_WORKER_URL+'/download/'+encodeURIComponent(f.id),{method:'GET',cache:'no-store'});if(!r.ok)throw new Error('Download Worker HTTP '+r.status);
      var bytes=await r.arrayBuffer();if(!bytes.byteLength)throw new Error('Worker trả về file rỗng');if(bytes.byteLength>25*1024*1024)throw new Error('File vượt giới hạn 25 MB');
      if(!document.getElementById('cpfontWindow'))return;FONT_PREVIEW_STATE.bytes=bytes;var loading=document.getElementById('cpfontLoading');if(loading)loading.remove();var token=++FONT_PREVIEW_STATE.token;
      if(isCP)cpfontRender(0,token);else ttfOtfRender(0,token);
    }catch(e){if(!document.getElementById('cpfontWindow'))return;fontPreviewTitle(String(f.name)+' · lỗi');var loading=document.getElementById('cpfontLoading');if(loading)loading.textContent='Không thể xem trước font: '+(e.message||e);console.error('[FontPreview]',e);}
  }
  var oldShowBook=showBook;
  showBook=function(f){if(fontPreviewIsFile(f)){showFontPreview(f);return;}oldShowBook(f);};
'''
inject = inject.replace("__WASM_URL__", json.dumps(WASM_URL)).replace("__WORKER_URL__", json.dumps(worker))
text = text.replace(anchor, inject + anchor, 1)

css_anchor = ".modal-body{padding:14px}"
if css_anchor not in text:
    raise SystemExit("CPFont patch anchor missing: modal CSS")
css = (
    ".cpfont-window{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;padding:8px;box-sizing:border-box;background:rgba(0,0,0,.35)}"
    ".cpfont-window-box{width:min(620px,calc(100vw - 16px));max-height:calc(100vh - 16px);display:flex;flex-direction:column;overflow:hidden;background:#c0c0c0;color:#000;font-family:Arial,sans-serif;border:2px solid #fff;border-right-color:#404040;border-bottom-color:#404040;box-sizing:border-box}"
    ".cpfont-window-head{flex:0 0 auto;min-height:36px;display:flex;align-items:center;gap:8px;padding:3px 5px 3px 8px;background:#d8d8d8;border-bottom:1px solid #808080;font-size:14px;font-weight:700;box-sizing:border-box}.cpfont-window-head>div{min-width:0;flex:1 1 auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cpfont-download{flex:0 0 auto;color:#000;text-decoration:underline;font-weight:400;white-space:nowrap}"
    ".cpfont-close{width:29px;height:29px;padding:0;flex:0 0 29px;font-size:21px;line-height:24px;font-weight:700;background:#c0c0c0;color:#000;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;cursor:pointer}.cpfont-close:active{border-color:#555;border-right-color:#fff;border-bottom-color:#fff}"
    ".cpfont-render-area{min-height:0;flex:1 1 auto;display:flex;align-items:center;justify-content:center;overflow:hidden;padding:3px;background:#c0c0c0;box-sizing:border-box}.cpfont-canvas{display:block;width:auto;height:auto;max-width:100%;max-height:calc(100vh - 105px);background:#fff;border:1px solid #555;box-sizing:border-box;image-rendering:pixelated}.cpfont-loading{position:absolute;padding:6px 9px;background:#ffffcc;border:1px solid #808080;font-size:13px;font-weight:700}"
    ".cpfont-controls{flex:0 0 auto;display:flex;gap:7px;padding:5px 6px 6px;background:#c0c0c0;border-top:1px solid #808080;box-sizing:border-box}.cpfont-device-btn{flex:1 1 0;min-width:0;height:42px;padding:2px 8px;background:#c0c0c0;color:#000;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;cursor:pointer;font:700 15px/16px Arial,sans-serif;text-align:center;box-sizing:border-box}.cpfont-device-btn small{display:block;font-size:11px;line-height:11px;font-weight:400}.cpfont-device-btn:active,.cpfont-device-btn.cpfont-device-active{border-color:#555;border-right-color:#fff;border-bottom-color:#fff}@media(max-width:600px){.cpfont-window{padding:4px}.cpfont-window-box{width:calc(100vw - 8px);max-height:calc(100vh - 8px)}.cpfont-canvas{max-height:calc(100vh - 101px)}}"
)
text = text.replace(css_anchor, css_anchor + css, 1)
HTML.write_text(text, encoding="utf-8")
