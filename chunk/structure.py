import os
import re
import json
import uuid

class StructuralElement:
    def __init__(self, element_type, text, level=0, metadata=None):
        self.type = element_type
        self.text = text
        self.level = level
        self.metadata = metadata or {}

def is_heading(line, all_lines, index):
    # All caps line followed by blank line or just a short all caps line
    if line.isupper() and len(line) > 3:
        if index + 1 < len(all_lines) and not all_lines[index + 1].strip():
            return True
        if len(line) < 100:
            return True
    
    # Line ending with colon and short
    if line.endswith(":") and len(line) < 100:
        return True
    
    return False

def is_structure_element(line):
    return (
        line.startswith("#")
        or re.match(r"^[-*+]\s|^\d+\.\s", line)
        or line.startswith("```")
        or line.startswith("    ")
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
            
        # Detect headings (# for markdown)
        if line.startswith("#"):
            level = len(re.match(r"^#+", line).group())
            elements.append(StructuralElement("heading", line, level, {"line_number": i + 1}))
        
        # Detect all caps headings
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
    
    for element in elements:
        element_size = len(element.text)
        
        if current_size + element_size > max_chunk_size and current_elements:
            # Save current chunk
            chunk_content = "\n\n".join([e.text for e in current_elements])
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": chunk_content,
                "metadata": {
                    "doc_title": doc_title,
                    "hierarchy": {
                        "level_1": None,
                        "level_2": None,
                        "level_3": None,
                        "level_4": None
                    },
                    "extra": {
                        "type": "structural",
                        "element_count": len(current_elements)
                    }
                }
            })
            current_elements = []
            current_size = 0
            
        current_elements.append(element)
        current_size += element_size
        
        # Split on significant headers
        if element.type == "heading" and element.level <= 2 and len(current_elements) > 1:
            header = current_elements.pop()
            chunk_content = "\n\n".join([e.text for e in current_elements])
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": chunk_content,
                "metadata": {
                    "doc_title": doc_title,
                    "hierarchy": {
                        "level_1": None,
                        "level_2": None,
                        "level_3": None,
                        "level_4": None
                    },
                    "extra": {
                        "type": "structural",
                        "element_count": len(current_elements)
                    }
                }
            })
            current_elements = [header]
            current_size = len(header.text)
            
    if current_elements:
        chunk_content = "\n\n".join([e.text for e in current_elements])
        chunks.append({
            "id": str(uuid.uuid4()),
            "content": chunk_content,
            "metadata": {
                "doc_title": doc_title,
                "hierarchy": {
                    "level_1": None,
                    "level_2": None,
                    "level_3": None,
                    "level_4": None
                },
                "extra": {
                    "type": "structural",
                    "element_count": len(current_elements)
                }
            }
        })
        
    return chunks

def process_structure_chunking(content, doc_title, max_size=1500):
    elements = extract_structure(content)
    chunks = group_elements(elements, doc_title, max_size)
    return chunks
