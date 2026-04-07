import os
import re
import json
import uuid

# Robust National Motto Regex
QUOC_HIEU_REGEX = r"C[ỘOÔ]NG\s+H[ÒOÓÔ][AÀÁẠ]?\s+X[ÃAẢẠ]\s+H[ỘOÔ]I\s+CH[ỦUŨỦ]+\s+N\s*GH[ĨIÍÌỊA]+A?\s+V[IỆEÊÌÍỊ]+T\s+N[AÀÁẠ]M"

# Optimized patterns
EXCLUDE_REFS = r'(?!\s+(?:Thông tư|Luật|Nghị định|số|quy định tại|này|về))'

FOOTER_PATTERNS = [
    re.compile(r'Nơi nh[ậâ]n:', re.I),
    re.compile(r'KT\.\s*', re.I),
    re.compile(r'TM\.\s*', re.I),
    re.compile(r'THỐNG ĐỐC', re.I),
    re.compile(r'BỘ TRƯỞNG', re.I),
    re.compile(r'CHỦ TỊCH', re.I),
    re.compile(r'PHỤ LỤC', re.I),
    re.compile(r'Mẫu số:', re.I),
    re.compile(r'TỜ KHAI', re.I),
    re.compile(r'BIÊN BẢN', re.I),
]

def load_file(file_path):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def process_chunking(content, doc_title="TT48_2024"):
    # Normalize line endings
    content = content.replace('\r\n', '\n')
    
    # Pre-split into sub-documents using National Motto
    # Use capturing group to keep the Motto in the result
    sub_docs_parts = re.split(rf'({QUOC_HIEU_REGEX})', content)
    
    # If the regex didn't find anything, the first part is the whole content
    # If it found something, it splits into [Pre-doc, Motto, Content, Motto, Content...]
    sub_docs = []
    if len(sub_docs_parts) == 1:
        sub_docs.append(sub_docs_parts[0])
    else:
        # First part (Pre-doc) if not empty
        if sub_docs_parts[0].strip():
            sub_docs.append(sub_docs_parts[0])
        # Combine Motto with subsequent Content
        for i in range(1, len(sub_docs_parts), 2):
            motto = sub_docs_parts[i]
            body = sub_docs_parts[i+1] if i+1 < len(sub_docs_parts) else ""
            sub_docs.append(motto + body)

    all_chunks = []
    
    for idx, sub_doc in enumerate(sub_docs):
        current_doc_title = f"{doc_title}_part_{idx+1}" if len(sub_docs) > 1 else doc_title
        
        footer_markers_raw = [
            r'Nơi nh[ậâ]n:', r'KT\.\s*', r'TM\.\s*', r'THỐNG ĐỐC', r'BỘ TRƯỞNG', 
            r'CHỦ TỊCH', r'PHỤ LỤC', r'Mẫu số:', r'TỜ KHAI', r'BIÊN BẢN'
        ]
        footer_pattern_str = "|".join(footer_markers_raw)
        
        combined_pattern = re.compile(
            rf'((?:Chương|CHƯƠNG)\s+[IVXLCDM\d]+\.?|(?:Mục|MỤC)\s+\d+\.?|(?:Điều|ĐIỀU)\s+\d+[a-z]?\.?|{footer_pattern_str})', 
            re.IGNORECASE
        )
        
        parts = combined_pattern.split(sub_doc)
        
        # Preamble for this sub-doc
        preamble = parts[0].strip()
        if preamble:
            all_chunks.append({
                "id": str(uuid.uuid4()),
                "content": preamble,
                "metadata": {
                    "doc_title": current_doc_title,
                    "hierarchy": {"level_1": None, "level_2": None, "level_3": "Preamble", "level_4": None},
                    "extra": {}
                }
            })

        current_chuong = current_muc = current_dieu = None

        for i in range(1, len(parts), 2):
            marker = parts[i].strip()
            body = parts[i+1] if i+1 < len(parts) else ""
            is_footer = any(fp.match(marker) for fp in FOOTER_PATTERNS)
            
            if is_footer:
                current_chuong = current_muc = current_dieu = None
                full_text = (marker + body).strip()
                if full_text:
                    all_chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": full_text,
                        "metadata": {
                            "doc_title": current_doc_title,
                            "hierarchy": {"level_1": None, "level_2": None, "level_3": None, "level_4": None},
                            "extra": {}
                        }
                    })
                continue

            if re.match(r'Chương|CHƯƠNG', marker, re.I):
                current_chuong = marker
                current_muc = current_dieu = None
            elif re.match(r'Mục|MỤC', marker, re.I):
                current_muc = marker
                current_dieu = None
            elif re.match(r'Điều|ĐIỀU', marker, re.I):
                current_dieu = marker
            
            full_text = (marker + body).strip()
            if not full_text: continue

            if current_dieu == marker:
                khoan_parts = re.split(r'(\s\d+\.\s)', body)
                if len(khoan_parts) > 1:
                    intro = marker + khoan_parts[0].strip()
                    if intro:
                        all_chunks.append({
                            "id": str(uuid.uuid4()),
                            "content": intro,
                            "metadata": {
                                "doc_title": current_doc_title,
                                "hierarchy": {"level_1": current_chuong, "level_2": current_muc, "level_3": current_dieu, "level_4": None},
                                "extra": {}
                            }
                        })
                    for j in range(1, len(khoan_parts), 2):
                        k_num = khoan_parts[j].strip()
                        k_text = khoan_parts[j+1].strip() if j+1 < len(khoan_parts) else ""
                        all_chunks.append({
                            "id": str(uuid.uuid4()),
                            "content": f"{current_dieu}: {k_num} {k_text}",
                            "metadata": {
                                "doc_title": current_doc_title,
                                "hierarchy": {"level_1": current_chuong, "level_2": current_muc, "level_3": current_dieu, "level_4": f"Khoản {k_num}"},
                                "extra": {}
                            }
                        })
                    continue

            all_chunks.append({
                "id": str(uuid.uuid4()),
                "content": full_text,
                "metadata": {
                    "doc_title": current_doc_title,
                    "hierarchy": {"level_1": current_chuong, "level_2": current_muc, "level_3": current_dieu, "level_4": None},
                    "extra": {}
                }
            })

    return all_chunks
