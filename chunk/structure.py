import os
import re
import json
import uuid
from chunk.table import contains_table, split_table, process_content_with_tables

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
            level = len(re.match(r"^#+", line).group())
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
                chunk_content = "\n\n".join([e.text for e in current_elements])
                chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
                current_elements = []
                current_size = 0
            
            chunks.extend(process_content_with_tables(element.text, doc_title, hierarchy))
            continue

        element_size = len(element.text)
        
        if current_size + element_size > max_chunk_size and current_elements:
            chunk_content = "\n\n".join([e.text for e in current_elements])
            chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
            current_elements = []
            current_size = 0
            
        current_elements.append(element)
        current_size += element_size
        
        if element.type == "heading" and element.level <= 2 and len(current_elements) > 1:
            header = current_elements.pop()
            chunk_content = "\n\n".join([e.text for e in current_elements])
            chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
            current_elements = [header]
            current_size = len(header.text)
            
    if current_elements:
        chunk_content = "\n\n".join([e.text for e in current_elements])
        chunks.extend(process_content_with_tables(chunk_content, doc_title, hierarchy))
        
    return chunks

def process_structure_chunking(content, doc_title, max_size=1500):
    elements = extract_structure(content)
    chunks = group_elements(elements, doc_title, max_size)
    return chunks
