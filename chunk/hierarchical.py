import os
import re
import json
import uuid

# Optimized patterns to handle Markdown headers, bolding, and multi-line matching
HIERARCHY_CONFIG = [
    {"name": "chuong", "label": "Chương", "pattern": re.compile(r'^(?:#+\s*)?(?:\**)(?:Chương|CHƯƠNG)\s+([IVXLCDM\d]+)', re.I | re.M)},
    {"name": "muc", "label": "Mục", "pattern": re.compile(r'^(?:#+\s*)?(?:\**)(?:Mục|MỤC)\s+(\d+)', re.I | re.M)},
    {"name": "dieu", "label": "Điều", "pattern": re.compile(r'^(?:#+\s*)?(?:\**)(?:Điều|ĐIỀU)\s+(\d+[a-z]?)\.?\s*(?!\s+(?:Thông tư|Luật|Nghị định|số|quy định tại|này|về))', re.I | re.M)},
    {"name": "khoan", "label": "Khoản", "pattern": re.compile(r'^(?:#+\s*)?(?:- )?(?:\**)(?:\d+)\.\s+', re.I | re.M)}
]

# Optimized patterns for bad OCR cases (flexible spaces, common typos)
FOOTER_PATTERNS = [
    re.compile(r'Nơi nh[ậâ]n:', re.I | re.M),
    re.compile(r'KT\.\s*', re.I | re.M),
    re.compile(r'TM\.\s*', re.I | re.M),
    re.compile(r'THỐNG ĐỐC', re.I | re.M),
    re.compile(r'BỘ TRƯỞNG', re.I | re.M),
    re.compile(r'CHỦ TỊCH', re.I | re.M),
    re.compile(r'PHỤ LỤC', re.I | re.M),
    re.compile(r'Mẫu số:', re.I | re.M),
    re.compile(r'TỜ KHAI', re.I | re.M),
    re.compile(r'BIÊN BẢN', re.I | re.M),
]

def process_hierarchical_chunking(content, doc_title, config):
    # Normalize line endings
    content = content.replace('\r\n', '\n')
    
    # Granular split: split before any major marker
    # Added comprehensive footer markers to the split pattern (matching patterns above)
    footer_markers = r'Nơi nh[ậâ]n:|KT\.\s*|TM\.\s*|THỐNG ĐỐC|BỘ TRƯỞNG|CHỦ TỊCH|PHỤ LỤC|Mẫu số:|TỜ KHAI|BIÊN BẢN'
    split_pattern = rf'\n(?=(?:#+\s*)?(?:\**)(?:Điều|Mục|Chương|{footer_markers}))'
    blocks = re.split(split_pattern, content)
    
    chunks = []
    current_state = {level["name"]: None for level in config}
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        # 1. Check for Footer to reset context
        is_footer = False
        for fp in FOOTER_PATTERNS:
            if fp.search(block):
                current_state = {level["name"]: None for level in config}
                is_footer = True
                break
            
        # 2. Check for hierarchy level updates
        matched_level_idx = -1
        for idx, level in enumerate(config):
            # Only update if the marker is at the very beginning of this block
            match = level["pattern"].match(block)
            if match:
                val = match.group(1) if match.groups() else ""
                # Handle cases like 'Khoản' where we might not capture a value in the first group easily
                if not val and level["name"] == "khoan":
                    k_num = re.search(r'(\d+)\.', block)
                    val = k_num.group(1) if k_num else ""
                
                current_state[level["name"]] = f"{level['label']} {val}" if val else level['label']
                matched_level_idx = idx
                break
        
        # 3. Reset lower levels if a higher level matched
        if matched_level_idx != -1:
            for i in range(matched_level_idx + 1, len(config)):
                current_state[config[i]["name"]] = None
        
        # 4. Handle internal splitting for 'Khoản' within a 'Điều'
        # If the block is a 'Điều' and contains multiple 'Khoản', we split it
        if current_state.get("dieu") and not is_footer:
            # Look for 'Khoản' markers (e.g., '1.', '2.' or '- 1.')
            khoan_split_pattern = r'\n(?=(?:#+\s*)?(?:- )?(?:\**)\d+\.\s)'
            sub_blocks = re.split(khoan_split_pattern, block)
            
            if len(sub_blocks) > 1:
                for i, sb in enumerate(sub_blocks):
                    sb = sb.strip()
                    if not sb: continue
                    
                    # Detect 'Khoản' for this specific sub-block
                    k_match = config[3]["pattern"].match(sb)
                    if k_match:
                        k_num = re.search(r'(\d+)\.', sb)
                        if k_num:
                            current_state["khoan"] = f"Khoản {k_num.group(1)}"
                    elif i == 0:
                        current_state["khoan"] = None # Intro of Điều
                        
                    # Create summary context
                    context_parts = [doc_title]
                    for level in config:
                        if current_state[level["name"]]:
                            context_parts.append(current_state[level["name"]])
                    
                    summary_context = " - ".join(context_parts)
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": sb,
                        "metadata": {
                            "doc_title": doc_title,
                            "hierarchy": current_state.copy(),
                            "summary_context": summary_context
                        }
                    })
                continue

        # 5. Default chunk creation
        context_parts = [doc_title]
        for level in config:
            if current_state[level["name"]]:
                context_parts.append(current_state[level["name"]])
        
        if is_footer and not any(current_state.values()):
            context_parts.append("Kết bài")
            
        summary_context = " - ".join(context_parts)
        
        chunks.append({
            "id": str(uuid.uuid4()),
            "content": block,
            "metadata": {
                "doc_title": doc_title,
                "hierarchy": current_state.copy(),
                "summary_context": summary_context
            }
        })
        
    return chunks
