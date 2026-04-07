import os
import re
import json
import uuid

# Robust National Motto Regex
QUOC_HIEU_REGEX = r"C[ỘOÔ]NG\s+H[ÒOÓÔ][AÀÁẠ]?\s+X[ÃAẢẠ]\s+H[ỘOÔ]I\s+CH[ỦUŨỦ]+\s+N\s*GH[ĨIÍÌỊA]+A?\s+V[IỆEÊÌÍỊ]+T\s+N[AÀÁẠ]M"

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
    
    # Pre-split into sub-documents using National Motto
    sub_docs_parts = re.split(rf'({QUOC_HIEU_REGEX})', content)
    
    sub_docs = []
    if len(sub_docs_parts) == 1:
        sub_docs.append(sub_docs_parts[0])
    else:
        if sub_docs_parts[0].strip():
            sub_docs.append(sub_docs_parts[0])
        for i in range(1, len(sub_docs_parts), 2):
            motto = sub_docs_parts[i]
            body = sub_docs_parts[i+1] if i+1 < len(sub_docs_parts) else ""
            sub_docs.append(motto + body)

    all_chunks = []
    
    for idx, sub_doc in enumerate(sub_docs):
        current_doc_title = f"{doc_title}_part_{idx+1}" if len(sub_docs) > 1 else doc_title
        
        # Granular split: split before any major marker
        footer_markers = r'Nơi nh[ậâ]n:|KT\.\s*|TM\.\s*|THỐNG ĐỐC|BỘ TRƯỞNG|CHỦ TỊCH|PHỤ LỤC|Mẫu số:|TỜ KHAI|BIÊN BẢN'
        split_pattern = rf'\n(?=(?:#+\s*)?(?:\**)(?:Điều|Mục|Chương|{footer_markers}))'
        blocks = re.split(split_pattern, sub_doc)
        
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
            for l_idx, level in enumerate(config):
                match = level["pattern"].match(block)
                if match:
                    val = match.group(1) if match.groups() else ""
                    if not val and level["name"] == "khoan":
                        k_num = re.search(r'(\d+)\.', block)
                        val = k_num.group(1) if k_num else ""
                    
                    current_state[level["name"]] = f"{level['label']} {val}" if val else level['label']
                    matched_level_idx = l_idx
                    break
            
            # 3. Reset lower levels if a higher level matched
            if matched_level_idx != -1:
                for i in range(matched_level_idx + 1, len(config)):
                    current_state[config[i]["name"]] = None
            
            # 4. Handle internal splitting for 'Khoản' within a 'Điều'
            if current_state.get("dieu") and not is_footer:
                khoan_split_pattern = r'\n(?=(?:#+\s*)?(?:- )?(?:\**)\d+\.\s)'
                sub_blocks = re.split(khoan_split_pattern, block)
                
                if len(sub_blocks) > 1:
                    for s_idx, sb in enumerate(sub_blocks):
                        sb = sb.strip()
                        if not sb: continue
                        
                        k_match = config[3]["pattern"].match(sb)
                        if k_match:
                            k_num = re.search(r'(\d+)\.', sb)
                            if k_num:
                                current_state["khoan"] = f"Khoản {k_num.group(1)}"
                        elif s_idx == 0:
                            current_state["khoan"] = None
                            
                        hierarchy = {
                            "level_1": current_state.get("chuong"),
                            "level_2": current_state.get("muc"),
                            "level_3": current_state.get("dieu"),
                            "level_4": current_state.get("khoan")
                        }
                        
                        all_chunks.append({
                            "id": str(uuid.uuid4()),
                            "content": sb,
                            "metadata": {
                                "doc_title": current_doc_title,
                                "hierarchy": hierarchy,
                                "extra": {}
                            }
                        })
                    continue

            # 5. Default chunk creation
            hierarchy = {
                "level_1": current_state.get("chuong"),
                "level_2": current_state.get("muc"),
                "level_3": current_state.get("dieu"),
                "level_4": current_state.get("khoan")
            }
            
            all_chunks.append({
                "id": str(uuid.uuid4()),
                "content": block,
                "metadata": {
                    "doc_title": current_doc_title,
                    "hierarchy": hierarchy,
                    "extra": {}
                }
            })
            
    return all_chunks
