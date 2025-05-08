import os
import json
import argparse
from tqdm import tqdm
from typing import List, Dict, Any

def read_got_files(data_dir: str) -> List[Dict[str, Any]]:
    """Read GOT text files and convert to document format"""
    documents = []
    
    # List all .txt files
    txt_files = [f for f in os.listdir(data_dir) if f.endswith('.txt')]
    print(f"Found {len(txt_files)} text files")
    
    # Process each file
    for filename in tqdm(txt_files, desc="Reading files"):
        try:
            filepath = os.path.join(data_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split title from content
            parts = content.split("\n\n", 1)
            if len(parts) == 2 and parts[0].startswith("Title: "):
                title = parts[0].replace("Title: ", "").strip()
                content_text = parts[1].strip()
                
                # Create document
                document = {
                    "title": title,
                    "content": content_text,
                    "filename": filename,
                    "source": "Game of Thrones Wiki"
                }
                
                documents.append(document)
                
        except Exception as e:
            print(f"Error reading {filename}: {str(e)}")
    
    return documents

def split_into_chunks(documents: List[Dict[str, Any]], 
                     chunk_size: int = 1000, 
                     overlap: int = 200) -> List[Dict[str, Any]]:
    """Split documents into smaller chunks for better vector search"""
    chunks = []
    
    for doc in tqdm(documents, desc="Splitting documents"):
        title = doc["title"]
        content = doc["content"]
        
        # Skip documents that are too short
        if len(content) < 100:
            continue
        
        # Split content into chunks
        if len(content) <= chunk_size:
            # Document is already small enough
            chunk = {
                "title": title,
                "content": content,
                "chunk_id": f"{title.replace(' ', '_')}_0",
                "source": doc["source"]
            }
            chunks.append(chunk)
        else:
            # Split document into overlapping chunks
            current_pos = 0
            chunk_id = 0
            
            while current_pos < len(content):
                # Calculate chunk boundaries
                chunk_end = min(current_pos + chunk_size, len(content))
                
                # If this is not the last chunk, try to end at a sentence boundary
                if chunk_end < len(content):
                    # Look for a period, question mark, or exclamation mark followed by space
                    for end_marker in ['. ', '? ', '! ', '.\n', '?\n', '!\n']:
                        pos = content.rfind(end_marker, current_pos, chunk_end)
                        if pos > current_pos:
                            chunk_end = pos + 1
                            break
                
                # Extract chunk content
                chunk_content = content[current_pos:chunk_end].strip()
                
                # Create chunk document
                chunk = {
                    "title": f"{title} (Part {chunk_id + 1})",
                    "content": chunk_content,
                    "parent_title": title,
                    "chunk_id": f"{title.replace(' ', '_')}_{chunk_id}",
                    "source": doc["source"]
                }
                
                chunks.append(chunk)
                
                # Move position for next chunk, accounting for overlap
                current_pos = chunk_end - overlap if chunk_end < len(content) else len(content)
                chunk_id += 1
    
    return chunks

def export_to_jsonl(documents: List[Dict[str, Any]], output_file: str):
    """Export documents to JSONL format"""
    with open(output_file, 'w', encoding='utf-8') as f:
        for doc in documents:
            f.write(json.dumps(doc) + '\n')
    
    print(f"Exported {len(documents)} documents to {output_file}")

def export_to_langchain_format(documents: List[Dict[str, Any]], output_dir: str):
    """Export documents to LangChain format (one file per document)"""
    os.makedirs(output_dir, exist_ok=True)
    
    for i, doc in enumerate(tqdm(documents, desc="Exporting to LangChain format")):
        # Create a filename from the chunk_id or title
        filename = doc.get("chunk_id", "").replace("/", "_").replace("\\", "_")
        if not filename:
            filename = f"doc_{i}_{doc['title'].replace(' ', '_')}"
        
        filepath = os.path.join(output_dir, f"{filename}.txt")
        
        # Format content
        content = f"Title: {doc['title']}\n\n{doc['content']}"
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    print(f"Exported {len(documents)} documents to {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Export GOT data for vector databases")
    parser.add_argument("--data-dir", default="assets/data", help="Directory containing GOT text files")
    parser.add_argument("--output-file", default="assets/got_chunks.jsonl", help="Output file for JSONL export")
    parser.add_argument("--langchain-dir", default="assets/langchain", help="Output directory for LangChain format")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Size of text chunks")
    parser.add_argument("--overlap", type=int, default=200, help="Overlap between chunks")
    parser.add_argument("--format", choices=["jsonl", "langchain", "both"], default="both", 
                        help="Export format (jsonl, langchain, or both)")
    
    args = parser.parse_args()
    
    # Read GOT files
    documents = read_got_files(args.data_dir)
    print(f"Read {len(documents)} documents")
    
    # Split into chunks
    chunks = split_into_chunks(documents, args.chunk_size, args.overlap)
    print(f"Split into {len(chunks)} chunks")
    
    # Export in specified format
    if args.format in ["jsonl", "both"]:
        os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
        export_to_jsonl(chunks, args.output_file)
    
    if args.format in ["langchain", "both"]:
        export_to_langchain_format(chunks, args.langchain_dir)

if __name__ == "__main__":
    main()