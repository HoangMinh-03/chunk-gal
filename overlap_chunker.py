import os
import re
import json
import uuid

def process_overlap_chunking(text, doc_title, min_size=500, max_size=2000, expected_size=1000, overlap=200):
    """
    Level 4: Fallback chunker that attempts to preserve semantic meaning 
    by splitting at structural boundaries (paragraphs, lists) while 
    maintaining a sliding window with overlap.
    
    Sizes are in characters (roughly approximating tokens for this implementation).
    """
    if not text:
        return []
        
    # 1. Pre-process text into "semantic atoms" (paragraphs, lists, etc.)
    # This is inspired by the structural_chunker.py strategy
    lines = text.split('\n')
    atoms = []
    current_atom = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped:
            if current_atom:
                atoms.append('\n'.join(current_atom))
                current_atom = []
            i += 1
            continue
            
        # Detect list start or code block start
        is_list = re.match(r'^[-*+]\s|^\d+\.\s', stripped)
        is_code = stripped.startswith('```')
        
        if is_list or is_code:
            # If we were building a paragraph, finish it
            if current_atom:
                atoms.append('\n'.join(current_atom))
                current_atom = []
                
            if is_list:
                list_block = [line]
                j = i + 1
                while j < len(lines) and (re.match(r'^[-*+]\s|^\d+\.\s', lines[j].strip()) or not lines[j].strip()):
                    list_block.append(lines[j])
                    j += 1
                atoms.append('\n'.join(list_block))
                i = j
            else: # is_code
                code_block = [line]
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith('```'):
                    code_block.append(lines[j])
                    j += 1
                if j < len(lines):
                    code_block.append(lines[j])
                    j += 1
                atoms.append('\n'.join(code_block))
                i = j
            continue
            
        current_atom.append(line)
        i += 1
        
    if current_atom:
        atoms.append('\n'.join(current_atom))

    # 2. Group atoms into chunks with overlap
    chunks = []
    current_chunk_atoms = []
    current_chunk_size = 0
    
    atom_idx = 0
    while atom_idx < len(atoms):
        atom = atoms[atom_idx]
        atom_size = len(atom)
        
        # If a single atom is larger than max_size, we must split it by characters
        if atom_size > max_size:
            # First, if we have a pending chunk, save it
            if current_chunk_atoms:
                content = '\n\n'.join(current_chunk_atoms)
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "content": content,
                    "metadata": {
                        "doc_title": doc_title,
                        "type": "overlap_structural",
                        "size": len(content)
                    }
                })
                current_chunk_atoms = []
                current_chunk_size = 0

            # Split the giant atom
            start = 0
            while start < atom_size:
                end = start + expected_size
                if end > atom_size:
                    end = atom_size
                else:
                    # Try to find a space near the end
                    last_space = atom.rfind(' ', end - 100, end)
                    if last_space != -1 and last_space > start:
                        end = last_space + 1
                
                chunk_text = atom[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": chunk_text,
                        "metadata": {
                            "doc_title": doc_title,
                            "type": "overlap_forced",
                            "size": len(chunk_text)
                        }
                    })
                start = end - overlap
                if start < 0: start = 0
                if end >= atom_size: break
            
            atom_idx += 1
            continue

        # Normal grouping logic
        if current_chunk_size + atom_size > expected_size and current_chunk_atoms:
            # We reached expected size, save chunk
            content = '\n\n'.join(current_chunk_atoms)
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": content,
                "metadata": {
                    "doc_title": doc_title,
                    "type": "overlap_structural",
                    "size": len(content)
                }
            })
            
            # For overlap, we need to backtrack atom_idx to include some previous text
            # Or simpler: keep some atoms that sum up to ~overlap
            overlap_size = 0
            new_chunk_atoms = []
            backtrack_idx = atom_idx - 1
            while backtrack_idx >= 0 and overlap_size < overlap:
                prev_atom = atoms[backtrack_idx]
                new_chunk_atoms.insert(0, prev_atom)
                overlap_size += len(prev_atom) + 2 # +2 for \n\n
                backtrack_idx -= 1
            
            current_chunk_atoms = new_chunk_atoms
            current_chunk_size = overlap_size

        current_chunk_atoms.append(atom)
        current_chunk_size += atom_size + (2 if current_chunk_atoms else 0)
        atom_idx += 1

    # Final chunk
    if current_chunk_atoms:
        content = '\n\n'.join(current_chunk_atoms)
        chunks.append({
            "id": str(uuid.uuid4()),
            "content": content,
            "metadata": {
                "doc_title": doc_title,
                "type": "overlap_structural",
                "size": len(content)
            }
        })
            
    return chunks

