import re
import uuid

def contains_table(text):
    """Kiểm tra xem văn bản có chứa bảng Markdown không."""
    # Tìm dòng phân cách |---|
    return bool(re.search(r'^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$', text, re.MULTILINE))

def split_table(table_text, max_rows=30):
    """Chia nhỏ bảng dài và lặp lại Header."""
    lines = table_text.strip().split('\n')
    
    # Tìm dòng phân cách để xác định header
    sep_idx = -1
    for i, line in enumerate(lines):
        if re.match(r'^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$', line):
            sep_idx = i
            break
            
    if sep_idx <= 0: return [table_text]

    header_lines = lines[:sep_idx + 1]
    data_lines = lines[sep_idx + 1:]
    
    if len(data_lines) <= max_rows:
        return [table_text]
        
    chunks = []
    for i in range(0, len(data_lines), max_rows):
        part = "\n".join(header_lines + data_lines[i : i + max_rows])
        chunks.append(part)
    return chunks

def process_content_with_tables(content, doc_title, hierarchy):
    """
    Tách bảng ra khỏi văn bản và trả về các chunk chuẩn hóa.
    Nếu không có bảng, trả về nội dung gốc dưới dạng 1 chunk.
    """
    if not contains_table(content):
        return [{
            "id": str(uuid.uuid4()),
            "content": content.strip(),
            "metadata": {
                "doc_title": doc_title,
                "hierarchy": hierarchy,
                "extra": {"length": len(content)}
            }
        }]

    # Regex nhận diện khối bảng Markdown (các dòng liên tiếp bắt đầu bằng |)
    # Cho phép có khoảng trắng ở đầu dòng
    table_regex = re.compile(r'((?:^\s*\|.*\|(?:\n|$))+)', re.MULTILINE)
    
    parts = table_regex.split(content)
    chunks = []
    
    for part in parts:
        part = part.strip()
        if not part: continue
        
        # Kiểm tra xem phần này có phải là bảng không
        if contains_table(part) and part.startswith('|'):
            table_parts = split_table(part)
            for tp in table_parts:
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "content": tp,
                    "metadata": {
                        "doc_title": doc_title,
                        "hierarchy": hierarchy,
                        "extra": {"type": "table", "length": len(tp)}
                    }
                })
        else:
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": part,
                "metadata": {
                    "doc_title": doc_title,
                    "hierarchy": hierarchy,
                    "extra": {"length": len(part)}
                }
            })
    return chunks
