#!/usr/bin/env python3
"""Finalize Story UI wording and TOC-ordinal jump semantics.

Run after scripts/postprocess_story.py and before
scripts/postprocess_story_current.py.
"""

from pathlib import Path

path = Path("docs/index.html")
text = path.read_text(encoding="utf-8")

replacements = {
    'Chọn chương ...': 'Đi đến',
    '<span>Tổng chương:</span>': '<span>Tổng mục lục:</span>',
    '<span>Chương hiện tại:</span>': '<span>Vị trí hiện tại:</span>',
    "var c=state.story&&(state.story.current_chapter||state.story.target_chapter_number);": "var c=state.story&&(state.story.current_toc_index||state.story.target_toc_index);",
    "var v=window.prompt('Đến chương số:',c||1); if(v===null)return;": "var v=window.prompt('Đến số thứ tự trong mục lục:\\nXem 0neStoryTOC để đối chiếu.',c||1); if(v===null)return;",
    "var n=parseInt(v,10); if(!Number.isFinite(n)||n<1){renderInfo('Số chương không hợp lệ.');return;}\n      trigger('jump',{chapter_number:n});": "var n=parseInt(v,10); if(!Number.isFinite(n)||n<1){renderInfo('Số thứ tự mục lục không hợp lệ.');return;}\n      trigger('jump',{toc_index:n});",
}

for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"Story TOC patch anchor missing: {old}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
