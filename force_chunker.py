import os
import re
import json
import uuid

# Optimized patterns inspired by thamkhao.md and iterative testing
# Strictly exclude references and ensure we are at a probable line start
EXCLUDE_REFS = r'(?!\s+(?:Thông tư|Luật|Nghị định|số|quy định tại|này|về))'

PATTERNS = {
    "chuong": re.compile(r'^\s*((?:Chương|CHƯƠNG)\s+([IVXLCDM\d]+)\.?\s*(.*?))$', re.IGNORECASE | re.MULTILINE),
    "muc": re.compile(r'^\s*((?:Mục|MỤC)\s+(\d+)\.?\s*(.*?))$', re.IGNORECASE | re.MULTILINE),
    "dieu": re.compile(r'^\s*((?:Điều|ĐIỀU)\s+(\d+[a-z]?)\.?\s*' + EXCLUDE_REFS + r'(.*?))$', re.IGNORECASE | re.MULTILINE)
}

FOOTER_PATTERNS = [
    re.compile(r'^Nơi nhận:', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^KT\.\s+', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^TM\.\s+', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^THỐNG ĐỐC', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^BỘ TRƯỞNG', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^CHỦ TỊCH', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^PHỤ LỤC', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^Mẫu số:', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^TỜ KHAI', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^BIÊN BẢN', re.IGNORECASE | re.MULTILINE),
]

def load_file(file_path):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def process_chunking(content, doc_title="TT48_2024"):
    # Normalize line endings
    content = content.replace('\r\n', '\n')
    
    # RELAXED combined pattern: catch structural markers and footer markers anywhere
    # Capture the marker to keep it in the split results
    footer_markers = r'Nơi nhận:|KT\.|TM\.|THỐNG ĐỐC|BỘ TRƯỞNG|CHỦ TỊCH|PHỤ LỤC|Mẫu số:|TỜ KHAI|BIÊN BẢN'
    combined_pattern = re.compile(rf'((?:Chương|CHƯƠNG)\s+[IVXLCDM\d]+\.?|(?:Mục|MỤC)\s+\d+\.?|(?:Điều|ĐIỀU)\s+\d+[a-z]?\.?|{footer_markers})', re.IGNORECASE)
    
    # Split the content by markers
    parts = combined_pattern.split(content)
    
    chunks = []
    
    # First part is Preamble
    preamble = parts[0].strip()
    if preamble:
        chunks.append({
            "id": str(uuid.uuid4()),
            "content": preamble,
            "metadata": {
                "doc_title": doc_title,
                "hierarchy": {"chapter": None, "section": None, "article": "Preamble"},
                "summary_context": f"{doc_title} - Phần mở đầu"
            }
        })

    current_chuong = None
    current_muc = None
    current_dieu = None

    # Process markers and their subsequent bodies
    # parts[1] is marker, parts[2] is body, parts[3] is marker...
    for i in range(1, len(parts), 2):
        marker = parts[i].strip()
        body = parts[i+1] if i+1 < len(parts) else ""
        
        # Check if marker is a footer
        is_footer = any(fp.match(marker) for fp in FOOTER_PATTERNS)
        
        if is_footer:
            # Reset hierarchy for footer
            current_chuong = current_muc = current_dieu = None
            full_text = (marker + body).strip()
            if full_text:
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "content": full_text,
                    "metadata": {
                        "doc_title": doc_title,
                        "hierarchy": {"chapter": None, "section": None, "article": "Footer"},
                        "summary_context": f"{doc_title} - Kết bài/Phụ lục"
                    }
                })
            continue

        # Update hierarchy based on marker
        if re.match(r'Chương|CHƯƠNG', marker, re.I):
            current_chuong = marker
            current_muc = current_dieu = None
        elif re.match(r'Mục|MỤC', marker, re.I):
            current_muc = marker
            current_dieu = None
        elif re.match(r'Điều|ĐIỀU', marker, re.I):
            # Check if this is a reference or a new Article
            # Since we split, we check the end of the PREVIOUS body (parts[i-1]) or preamble if i=1
            prev_part = parts[i-1].strip()
            prev_text = prev_part[-20:].lower() if prev_part else ""
            is_ref = any(x in prev_text for x in ['tại', 'theo', 'khoản', 'số', 'quy định'])
            
            if is_ref:
                # If it's a reference, we might have split incorrectly or it's just a mention.
                # In force_chunker, we typically want to split on every 'Điều' unless it's obviously a ref.
                pass
            else:
                current_dieu = marker
        
        full_text = (marker + body).strip()
        
        if not full_text: continue

        # Split by 'Khoản' if it's a 'Điều' and not a reference
        if current_dieu == marker:
            khoan_parts = re.split(r'(\s\d+\.\s)', body)
            if len(khoan_parts) > 1:
                intro = marker + khoan_parts[0].strip()
                if intro:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": intro,
                        "metadata": {
                            "doc_title": doc_title,
                            "hierarchy": {"chapter": current_chuong, "section": current_muc, "article": current_dieu},
                            "summary_context": f"{doc_title} - {current_dieu} (Mở đầu)"
                        }
                    })
                for j in range(1, len(khoan_parts), 2):
                    k_num = khoan_parts[j].strip()
                    k_text = khoan_parts[j+1].strip() if j+1 < len(khoan_parts) else ""
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": f"{current_dieu}: {k_num} {k_text}",
                        "metadata": {
                            "doc_title": doc_title,
                            "hierarchy": {"chapter": current_chuong, "section": current_muc, "article": current_dieu},
                            "summary_context": f"{doc_title} - {current_dieu} - Khoản {k_num}"
                        }
                    })
                continue

        # Default
        chunks.append({
            "id": str(uuid.uuid4()),
            "content": full_text,
            "metadata": {
                "doc_title": doc_title,
                "hierarchy": {"chapter": current_chuong, "section": current_muc, "article": current_dieu},
                "summary_context": f"{doc_title} - {current_dieu or current_muc or current_chuong or 'Nội dung'}"
            }
        })

    return chunks
