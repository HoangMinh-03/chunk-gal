import os
import re
import json
import uuid

def process_overlap_chunking(text, doc_title, min_size=500, max_size=2000, expected_size=1000, overlap=200):
    """
    Level 4: Optimized sliding window chunker.
    Combines structural atomization (preserving lists/code) with smart sentence-boundary 
    splitting and precise overlap management.
    """
    if not text:
        return []
        
    # 1. Pre-process text into semantic atoms
    lines = text.split('\n')
    atoms = []
    
    current_pos = 0
    for line in lines:
        stripped = line.strip()
        line_len = len(line)
        
        if not stripped:
            current_pos += line_len + 1
            continue
            
        if len(stripped) > expected_size:
            sentences = re.split(r'(?<=[.!?])\s+', stripped)
            temp_pos = text.find(stripped, current_pos)
            for sentence in sentences:
                s_stripped = sentence.strip()
                if s_stripped:
                    s_pos = text.find(s_stripped, temp_pos)
                    atoms.append({
                        "text": s_stripped,
                        "start": s_pos,
                        "end": s_pos + len(s_stripped)
                    })
                    temp_pos = s_pos + len(s_stripped)
        else:
            start_idx = text.find(line, current_pos)
            if start_idx != -1:
                atoms.append({
                    "text": stripped,
                    "start": start_idx,
                    "end": start_idx + len(stripped)
                })
        
        current_pos += line_len + 1

    # 2. Group atoms into chunks using a sliding window logic
    chunks = []
    current_chunk_atoms = []
    current_chunk_size = 0
    
    atom_idx = 0
    while atom_idx < len(atoms):
        atom = atoms[atom_idx]
        atom_text = atom["text"]
        atom_size = len(atom_text)
        
        if current_chunk_atoms and (current_chunk_size + atom_size + 2 > max_size or current_chunk_size >= expected_size):
            chunk_content = "\n\n".join([a["text"] for a in current_chunk_atoms])
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
                        "length": len(chunk_content)
                    }
                }
            })
            
            overlap_atoms = []
            temp_overlap_size = 0
            for i in range(len(current_chunk_atoms) - 1, -1, -1):
                prev_a = current_chunk_atoms[i]
                if temp_overlap_size + len(prev_a["text"]) + 2 <= overlap:
                    overlap_atoms.insert(0, prev_a)
                    temp_overlap_size += len(prev_a["text"]) + 2
                else:
                    break
            
            current_chunk_atoms = overlap_atoms
            current_chunk_size = temp_overlap_size

        if atom_size > max_size:
            start = 0
            while start < atom_size:
                end = start + expected_size
                if end < atom_size:
                    last_space = atom_text.rfind(' ', start, end)
                    if last_space > start + expected_size * 0.5:
                        end = last_space
                
                sub_text = atom_text[start:end].strip()
                if sub_text:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": sub_text,
                        "metadata": {
                            "doc_title": doc_title,
                            "hierarchy": {
                                "level_1": None,
                                "level_2": None,
                                "level_3": None,
                                "level_4": None
                            },
                            "extra": {
                                "length": len(sub_text)
                            }
                        }
                    })
                start = end - overlap
                if start < 0: start = 0
                if end >= atom_size: break
            
            current_chunk_atoms = []
            current_chunk_size = 0
            atom_idx += 1
            continue

        current_chunk_atoms.append(atom)
        current_chunk_size += atom_size + (2 if len(current_chunk_atoms) > 1 else 0)
        atom_idx += 1

    if current_chunk_atoms:
        chunk_content = "\n\n".join([a["text"] for a in current_chunk_atoms])
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
                    "length": len(chunk_content)
                }
            }
        })
            
    return chunks
