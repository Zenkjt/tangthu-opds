#!/usr/bin/env python3
"""Add persistent shelf URL memory shared by News and Story GUIs.

Run after all GUI postprocessors so the final docs/index.html contains
the common shelf URL memory layer.
"""

from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

SCRIPT_ID = "tangthu-shelf-url-memory"

# Keep exactly one copy when the postprocessor is rerun.
import re
text = re.sub(
    rf'\s*<script id="{SCRIPT_ID}">.*?</script>\s*',
    "\n",
    text,
    count=1,
    flags=re.DOTALL,
)

script = r"""
<script id="tangthu-shelf-url-memory">
(function(){
  var KEY='tangthu.shelfUrl';
  var INPUT_IDS=['newsShelfUrl','storyShelfUrl'];

  function getSaved(){
    try{return localStorage.getItem(KEY)||'';}
    catch(e){return '';}
  }

  function save(value){
    var url=String(value||'').trim();
    try{
      if(url)localStorage.setItem(KEY,url);
      else localStorage.removeItem(KEY);
    }catch(e){}
  }

  function findInput(){
    for(var i=0;i<INPUT_IDS.length;i++){
      var el=document.getElementById(INPUT_IDS[i]);
      if(el)return el;
    }
    return null;
  }

  function fill(){
    var input=findInput();
    if(!input)return;
    if(!String(input.value||'').trim()){
      var saved=getSaved();
      if(saved)input.value=saved;
    }
    if(input.dataset.tangthuShelfMemoryBound==='1')return;
    input.dataset.tangthuShelfMemoryBound='1';

    input.addEventListener('input',function(){
      save(input.value);
    });
    input.addEventListener('change',function(){
      save(input.value);
    });
  }

  function sync(){
    fill();
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',sync);
  }else{
    sync();
  }

  var observer=new MutationObserver(sync);
  observer.observe(document.body,{childList:true,subtree:true});
})();
</script>
"""

if "</body>" not in text:
    raise SystemExit("Shelf URL memory patch anchor missing: </body>")

text = text.replace("</body>", script + "\n</body>", 1)
path.write_text(text, encoding="utf-8")
