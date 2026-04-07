import os
import re
import json
import uuid
from chunk.table import contains_table, split_table, process_content_with_tables

# Robust National Motto Regex
QUOC_HIEU_REGEX = r"C[ỘOÔ]NG\s+H[ÒOÓÔ][AÀÁẠ]?\s+X[ÃAẢẠ]\s+H[ỘOÔ]I\s+CH[ỦUŨỦ]+\s+N\s*GH[ĨIÍÌỊA]+A?\s+V[IỆEÊÌÍỊ]+T\s+N[AÀÁẠ]M"

class StructuralElement:
    def __init__(self, element_type, text, level=0, metadata=None):
        self.type = element_type
        self.text = text
        self.level = level
        self.metadata = metadata or {}

def is_heading(line, all_lines, index):
    if line.isupper() and len(line) > 3:
        if index + 1 < len(all_lines) and not all_lines[index + 1].strip():
            return True
        if len(line) < 100:
            return True
    if line.endswith(":") and len(line) < 100:
        return True
    return False

def is_structure_element(line):
    return (
        line.startswith("#")
        or re.match(r"^[-*+]\s|^\d+\.\s", line)
        or line.startswith("```")
        or line.startswith("    ")
        or line.strip().startswith("|")
        or line == "</end-of-page>"
    )

def extract_structure(text):
    elements = []
    lines = text.split("\n")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
            
        # Detect page break
        if line == "</end-of-page>":
            elements.append(StructuralElement("page_break", line, 0, {"line_number": i + 1}))
            i += 1
            continue

        # Detect table (more flexible)
        if line.startswith("|") or (line == "" and i+1 < len(lines) and lines[i+1].strip().startswith("|")):
            # If current line is empty, skip to next
            start_i = i if line.startswith("|") else i+1
            table_lines = []
            j = start_i
            while j < len(lines) and (lines[j].strip().startswith("|") or lines[j].strip() == ""):
                if lines[j].strip() == "" and (j+1 >= len(lines) or not lines[j+1].strip().startswith("|")):
                    break
                table_lines.append(lines[j])
                j += 1
            
            table_text = "\n".join(table_lines).strip()
            if contains_table(table_text):
                elements.append(StructuralElement("table", table_text, 0, {"line_number": start_i + 1}))
                i = j - 1
                i += 1
                continue

        # Detect headings
        if line.startswith("#"):
            match = re.match(r"^(#+)", line)
            level = len(match.group(1)) if match else 1
            elements.append(StructuralElement("heading", line, level, {"line_number": i + 1}))
        
        elif is_heading(line, lines, i):
            elements.append(StructuralElement("heading", line, 1, {"line_number": i + 1}))
            
        # Detect lists
        elif re.match(r"^[-*+]\s|^\d+\.\s", line):
            list_items = [line]
            j = i + 1
            while j < len(lines) and (re.match(r"^[-*+]\s|^\d+\.\s", lines[j].strip()) or not lines[j].strip()):
                if lines[j].strip():
                    list_items.append(lines[j].strip())
                j += 1
            elements.append(StructuralElement("list", "\n".join(list_items), 0, {"item_count": len(list_items), "line_number": i + 1}))
            i = j - 1
            
        # Detect code blocks
        elif line.startswith("```"):
            code_lines = [line]
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code_lines.append(lines[j])
                j += 1
            if j < len(lines):
                code_lines.append(lines[j])
                j += 1
            elements.append(StructuralElement("code_block", "\n".join(code_lines), 0, {"line_number": i + 1}))
            i = j - 1
            
        # Regular paragraph
        else:
            para_lines = [line]
            j = i + 1
            while j < len(lines) and lines[j].strip() and not is_structure_element(lines[j].strip()):
                if not is_heading(lines[j].strip(), lines, j):
                    para_lines.append(lines[j].strip())
                    j += 1
                else:
                    break
            
            paragraph_text = "\n".join(para_lines)
            elements.append(StructuralElement("paragraph", paragraph_text, 0, {"line_number": i + 1}))
            i = j - 1
            
        i += 1
    return elements

def group_elements(elements, doc_title, max_chunk_size=1500):
    chunks = []
    current_elements = []
    current_size = 0
    hierarchy = {"level_1": None, "level_2": None, "level_3": None, "level_4": None}
    
    for element in elements:
        if element.type == "table":
            if current_elements:
                chunk_content = "\n\n".join([e.text for e in current_elements if e.type != "page_break"])
                if chunk_content:
                    chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
                current_elements = []
                current_size = 0
            
            chunks.extend(process_content_with_tables(element.text, doc_title, hierarchy))
            continue

        element_size = len(element.text)
        
        # Check for heading split trigger
        if element.type == "heading" and element.level <= 2 and len(current_elements) > 1:
            # Search for the last page_break in current_elements
            split_idx = -1
            for idx in range(len(current_elements) - 1, -1, -1):
                if current_elements[idx].type == "page_break":
                    split_idx = idx
                    break
            
            if split_idx != -1:
                # Elements before split_idx go to current chunk
                before_elements = current_elements[:split_idx]
                # Elements after split_idx (excluding page_break) go to next chunk
                after_elements = current_elements[split_idx + 1:]
                
                if before_elements:
                    chunk_content = "\n\n".join([e.text for e in before_elements if e.type != "page_break"])
                    if chunk_content:
                        chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
                
                current_elements = after_elements + [element]
                current_size = sum(len(e.text) for e in current_elements if e.type != "page_break")
                continue
            else:
                # Standard heading split
                chunk_content = "\n\n".join([e.text for e in current_elements if e.type != "page_break"])
                if chunk_content:
                    chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
                current_elements = [element]
                current_size = element_size
                continue

        # Standard size-based split
        if current_size + element_size > max_chunk_size and current_elements:
            chunk_content = "\n\n".join([e.text for e in current_elements if e.type != "page_break"])
            if chunk_content:
                chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
            current_elements = []
            current_size = 0
            
        current_elements.append(element)
        if element.type != "page_break":
            current_size += element_size
            
    if current_elements:
        chunk_content = "\n\n".join([e.text for e in current_elements if e.type != "page_break"])
        if chunk_content:
            chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
        
    return chunks

def process_structure_chunking(content, doc_title, max_size=1500):
    # Normalize line endings
    content = content.replace('\r\n', '\n')
    
    # Pre-split into sub-documents using National Motto and </end-of-page> tag
    motto_matches = list(re.finditer(QUOC_HIEU_REGEX, content))
    
    sub_docs = []
    if not motto_matches:
        sub_docs.append(content)
    else:
        last_split_pos = 0
        tag = "</end-of-page>"
        
        for i, match in enumerate(motto_matches):
            motto_pos = match.start()
            # Search for </end-of-page> between last split and this motto
            search_area = content[last_split_pos:motto_pos]
            tag_pos = search_area.rfind(tag)
            
            if tag_pos != -1:
                # Split at the tag and remove it
                split_at = last_split_pos + tag_pos
                part = content[last_split_pos:split_at].strip()
                if part:
                    sub_docs.append(part)
                last_split_pos = split_at + len(tag)
            elif i > 0:
                # No tag found, but not the first motto. 
                # Split at the motto start to separate from previous document.
                part = content[last_split_pos:motto_pos].strip()
                if part:
                    sub_docs.append(part)
                last_split_pos = motto_pos
        
        # Add the remaining content
        final_part = content[last_split_pos:].strip()
        if final_part:
            sub_docs.append(final_part)

    all_chunks = []
    for sub_doc in sub_docs:
        elements = extract_structure(sub_doc)
        all_chunks.extend(group_elements(elements, doc_title, max_size))
    return all_chunks
