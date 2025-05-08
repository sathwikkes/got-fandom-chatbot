import pymongo
import json
import os
from typing import List, Dict, Any, Optional

class GOTChatbotDB:
    """Game of Thrones chatbot database utilities"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/", db_name: str = "gotChatbot"):
        """Initialize database connection"""
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.wiki_pages = self.db["wikiPages"]
        
        # Ensure text indexes for search
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Ensure required indexes exist"""
        # Text index for full-text search
        self.wiki_pages.create_index([("content", pymongo.TEXT), ("title", pymongo.TEXT)])
        
        # Regular index on title for exact matches
        self.wiki_pages.create_index("title")
    
    def import_from_jsonl(self, filepath: str) -> int:
        """Import data from JSONL file (one JSON object per line)"""
        count = 0
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                document = json.loads(line)
                # Use upsert to avoid duplicates
                self.wiki_pages.update_one(
                    {"title": document["title"]}, 
                    {"$set": document}, 
                    upsert=True
                )
                count += 1
        return count
    
    def import_from_directory(self, directory: str) -> int:
        """Import all text files from a directory"""
        count = 0
        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                filepath = os.path.join(directory, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Split title from content
                    parts = content.split("\n\n", 1)
                    if len(parts) == 2 and parts[0].startswith("Title: "):
                        title = parts[0].replace("Title: ", "")
                        content_text = parts[1]
                        
                        document = {
                            "title": title,
                            "content": content_text,
                            "filename": filename,
                            "imported_from": filepath
                        }
                        
                        # Use upsert to avoid duplicates
                        self.wiki_pages.update_one(
                            {"title": document["title"]}, 
                            {"$set": document}, 
                            upsert=True
                        )
                        count += 1
        return count
    
    def count_documents(self) -> int:
        """Count total documents in collection"""
        return self.wiki_pages.count_documents({})
    
    def text_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform text search across all content"""
        results = self.wiki_pages.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        return list(results)
    
    def find_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Find document by exact title"""
        return self.wiki_pages.find_one({"title": title})
    
    def find_title_contains(self, text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find documents with titles containing the given text"""
        regex = {"$regex": text, "$options": "i"}
        results = self.wiki_pages.find({"title": regex}).limit(limit)
        return list(results)
    
    def search_content(self, text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search content with regex"""
        regex = {"$regex": text, "$options": "i"}
        results = self.wiki_pages.find({"content": regex}).limit(limit)
        return list(results)
    
    def get_content_excerpt(self, doc: Dict[str, Any], search_term: str, context_chars: int = 100) -> str:
        """Extract context around first match of search term"""
        content = doc.get("content", "")
        pos = content.lower().find(search_term.lower())
        
        if pos >= 0:
            start = max(0, pos - context_chars)
            end = min(len(content), pos + len(search_term) + context_chars)
            
            # Find paragraph boundaries if possible
            if start > 0:
                paragraph_start = content.rfind("\n\n", 0, start)
                if paragraph_start > 0:
                    start = paragraph_start + 2
            
            if end < len(content):
                paragraph_end = content.find("\n\n", end)
                if paragraph_end > 0:
                    end = paragraph_end
            
            return content[start:end].strip()
        
        # If term not found, return beginning of content
        return content[:200].strip() + "..."
    
    def get_random_documents(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get random documents from the collection"""
        return list(self.wiki_pages.aggregate([{"$sample": {"size": count}}]))
    
    def create_chatbot_context(self, query: str, max_documents: int = 3, 
                               max_chars: int = 2000) -> str:
        """Create context for chatbot from relevant documents"""
        results = self.text_search(query, limit=max_documents)
        
        context_parts = []
        total_chars = 0
        
        for doc in results:
            excerpt = self.get_content_excerpt(doc, query)
            if total_chars + len(excerpt) + 20 <= max_chars:
                context_parts.append(f"--- {doc['title']} ---\n{excerpt}")
                total_chars += len(excerpt) + 20
        
        return "\n\n".join(context_parts)


# Example usage
if __name__ == "__main__":
    # Create database connection
    db = GOTChatbotDB()
    
    # Import data
    data_dir = "assets/data"
    jsonl_file = os.path.join(data_dir, "mongodb_import.json")
    
    if os.path.exists(jsonl_file):
        print(f"Importing from {jsonl_file}...")
        count = db.import_from_jsonl(jsonl_file)
        print(f"Imported {count} documents from JSON")
    else:
        print(f"Importing from directory {data_dir}...")
        count = db.import_from_directory(data_dir)
        print(f"Imported {count} documents from directory")
    
    # Show database stats
    total_docs = db.count_documents()
    print(f"Total documents in database: {total_docs}")
    
    # Example search
    print("\nExample search: 'Jon Snow'")
    results = db.text_search("Jon Snow", limit=2)
    for doc in results:
        print(f"- {doc['title']}")
        excerpt = db.get_content_excerpt(doc, "Jon")
        print(f"  Excerpt: {excerpt[:150]}...")
    
    # Example context generation
    print("\nExample context for query: 'Stark family'")
    context = db.create_chatbot_context("Stark family")
    print(context[:500] + "...")