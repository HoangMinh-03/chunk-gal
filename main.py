import os
import json
import argparse
import re
from chunk.hierarchical import process_hierarchical_chunking, HIERARCHY_CONFIG
from chunk.structure import process_structure_chunking
from chunk.force import process_chunking as process_force_chunking
from chunk.overlap import process_overlap_chunking

def detect_level(content):
    """
    Detects the appropriate chunking level based on content characteristics.
    Level 1: Hierarchical (Chương, Mục, Điều)
    Level 2: Structural (Markdown headings, lists)
    Level 3: Force (No MD structure but has text markers)
    Level 4: Overlap (Fallback for everything else)
    """
    # Level 1 check: Look for strong hierarchical markers (Chương, Mục, Điều)
    # Using LEGAL_CONFIG patterns
    if any(level["pattern"].search(content) for level in HIERARCHY_CONFIG[:3]): # Exclude 'khoan' for level 1 detection to be sure
        return 1

    # Level 2 check: Look for Markdown headers (at least one # at start of line)
    if re.search(r'^#+ ', content, re.MULTILINE):
        return 2

    # Level 3 check: Look for text markers (flexible search for OCR bad cases)
    # We look for "Điều X." or "Chương X." or "Mục X." anywhere in the text
    force_markers = [r'Điều \d+', r'Chương [IVX\d]+', r'Mục \d+']
    if any(re.search(m, content, re.IGNORECASE) for m in force_markers):
        return 4

    # Level 4: Fallback
    return 4


def main():
    parser = argparse.ArgumentParser(description="Multi-level document chunking")
    parser.add_argument("input", help="Path to input markdown file")
    parser.add_argument("--output_dir", default="result", help="Directory to save results")
    parser.add_argument("--title", help="Document title")
    args = parser.parse_args()
    
    input_path = args.input
    output_dir = args.output_dir
    doc_title = args.title or os.path.basename(input_path).split('.')[0]
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    if not os.path.exists(input_path):
        print(f"Error: Input file {input_path} not found.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Normalize literal '\n' and '\r\n' if they exist in the text
    # This happens when the input MD file was not correctly unescaped
    if '\\n' in content:
        content = content.replace('\\r\\n', '\n').replace('\\n', '\n')
        
    level = detect_level(content)
    print(f"Detected Level: {level}")
    
    chunks = []
    method_used = ""
    
    if level == 1:
        print("Using Hierarchical Chunker...")
        chunks = process_hierarchical_chunking(content, doc_title, HIERARCHY_CONFIG)
        method_used = "hierarchical"
        # Check if we actually got meaningful chunks (more than just 1 big chunk)
        if len(chunks) <= 1:
            print("Hierarchical failed to find enough structure, falling back...")
            level = 2
            
    if level == 2:
        print("Using Structural Chunker...")
        chunks = process_structure_chunking(content, doc_title)
        method_used = "structural"
        if len(chunks) <= 1:
            print("Structural failed to find enough structure, falling back...")
            level = 3
            
    if level == 3:
        print("Using Force Chunker...")
        chunks = process_force_chunking(content, doc_title)
        method_used = "force"
        if len(chunks) <= 1:
            print("Force failed to find markers, falling back...")
            level = 4
            
    if level == 4:
        print("Using Overlap Chunker...")
        chunks = process_overlap_chunking(content, doc_title)
        method_used = "overlap"

    output_path = os.path.join(output_dir, f"{doc_title}_chunks.json")
    
    # Add metadata about method used
    result = {
        "metadata": {
            "doc_title": doc_title,
            "method_used": method_used,
            "chunk_count": len(chunks)
        },
        "chunks": chunks
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully processed {len(chunks)} chunks using {method_used} method.")
    print(f"Result saved to: {output_path}")

if __name__ == "__main__":
    main()
