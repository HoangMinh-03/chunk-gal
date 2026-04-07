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
    # We maintain the start/end indices for each atom
    lines = text.split('\n')
    atoms = []
    
    current_pos = 0
    for line in lines:
        stripped = line.strip()
        line_len = len(line)
        
        if not stripped:
            current_pos += line_len + 1 # +1 for \n
            continue
            
        # For long lines, split them into sentence atoms immediately
        if len(stripped) > expected_size:
            # Split by sentence boundaries but keep the punctuation
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
            # Regular atom
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
        
        # Check if adding this atom exceeds max_size
        # We allow adding it if the current chunk is empty, or if we haven't reached expected_size
        if current_chunk_atoms and (current_chunk_size + atom_size + 2 > max_size or current_chunk_size >= expected_size):
            # Save current chunk
            chunk_content = "\n\n".join([a["text"] for a in current_chunk_atoms])
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": chunk_content,
                "metadata": {
                    "doc_title": doc_title,
                    "type": "overlap_optimized",
                    "size": len(chunk_content),
                    "start_index": current_chunk_atoms[0]["start"],
                    "end_index": current_chunk_atoms[-1]["end"]
                }
            })
            
            # Create overlap: find how many atoms from the end fit in 'overlap'
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

        # If a single atom is STILL bigger than max_size (unlikely after sentence splitting)
        # We must force split it
        if atom_size > max_size:
            start = 0
            while start < atom_size:
                end = start + expected_size
                if end < atom_size:
                    # Look for space
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
                            "type": "overlap_forced_split",
                            "size": len(sub_text),
                            "start_index": atom["start"] + start,
                            "end_index": atom["start"] + end
                        }
                    })
                start = end - overlap
                if start < 0: start = 0
                if end >= atom_size: break
            
            # After forced split, we don't carry over anything to next atom to keep it simple
            current_chunk_atoms = []
            current_chunk_size = 0
            atom_idx += 1
            continue

        current_chunk_atoms.append(atom)
        current_chunk_size += atom_size + (2 if len(current_chunk_atoms) > 1 else 0)
        atom_idx += 1

    # Final chunk
    if current_chunk_atoms:
        chunk_content = "\n\n".join([a["text"] for a in current_chunk_atoms])
        chunks.append({
            "id": str(uuid.uuid4()),
            "content": chunk_content,
            "metadata": {
                "doc_title": doc_title,
                "type": "overlap_optimized",
                "size": len(chunk_content),
                "start_index": current_chunk_atoms[0]["start"],
                "end_index": current_chunk_atoms[-1]["end"]
            }
        })
            
    return chunks
