import os
import json
import pymongo
import datetime
from typing import List, Dict, Any, Optional

# Try to import langchain modules, but make them optional
try:
    from langchain.vectorstores import MongoDBAtlasVectorSearch
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.document_loaders import TextLoader
    from langchain.text_splitter import CharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("LangChain not installed. Vector search capabilities will be limited.")

class GOTMongoConnection:
    """Class to manage MongoDB connection for Game of Thrones data"""
    
    def __init__(self, 
                mongo_uri: str = "mongodb://localhost:27017/", 
                db_name: str = "gotChatbot",
                collection_name: str = "wikiPages",
                vector_collection_name: str = "vectorIndex"):
        """Initialize connection to MongoDB with vector search capabilities"""
        try:
            # Connect to MongoDB
            self.client = pymongo.MongoClient(mongo_uri)
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]
            self.vector_collection = self.db[vector_collection_name]
            
            # Set up embeddings model - requires OpenAI API key and LangChain
            self.embeddings = None
            if LANGCHAIN_AVAILABLE and "OPENAI_API_KEY" in os.environ:
                try:
                    self.embeddings = OpenAIEmbeddings()
                    print("OpenAI embeddings initialized.")
                except Exception as e:
                    print(f"Warning: Could not initialize OpenAI embeddings: {str(e)}")
            elif not LANGCHAIN_AVAILABLE:
                print("LangChain not installed. Vector search capabilities disabled.")
            else:
                print("Warning: OPENAI_API_KEY not found in environment variables. Vector search won't be available.")
                
            # Create indexes if they don't exist
            self._ensure_indexes()
            
            print(f"Connected to MongoDB. Database: {db_name}")
            print(f"Collections: {', '.join(self.db.list_collection_names())}")
            print(f"Wiki pages: {self.collection.count_documents({})}")
            
        except Exception as e:
            print(f"Error connecting to MongoDB: {str(e)}")
            self.client = None
            self.db = None
            self.collection = None
            self.vector_collection = None
    
    def _ensure_indexes(self):
        """Ensure required indexes exist for efficient queries"""
        # Text search index
        self.collection.create_index([("content", pymongo.TEXT), ("title", pymongo.TEXT)])
        
        # Regular index on title and creation date
        self.collection.create_index("title")
        
        # Index on vector field if using vector search
        if self.vector_collection.count_documents({}) > 0:
            if "embedding" in self.vector_collection.find_one({}):
                self.vector_collection.create_index([("embedding", pymongo.HASHED)])
    
    def import_from_directory(self, dir_path: str) -> int:
        """Import all text files from a directory"""
        if not os.path.exists(dir_path):
            print(f"Directory {dir_path} does not exist")
            return 0
            
        count = 0
        
        for filename in os.listdir(dir_path):
            if filename.endswith(".txt"):
                try:
                    filepath = os.path.join(dir_path, filename)
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
                            "imported_from": filepath,
                            "imported_at": datetime.datetime.utcnow()
                        }
                        
                        # Insert or update
                        self.collection.update_one(
                            {"title": title},
                            {"$set": document},
                            upsert=True
                        )
                        count += 1
                        
                except Exception as e:
                    print(f"Error importing {filename}: {str(e)}")
        
        print(f"Successfully imported {count} files into MongoDB")
        return count
    
    def import_from_jsonl(self, filepath: str) -> int:
        """Import data from a JSONL file (one JSON object per line)"""
        if not os.path.exists(filepath):
            print(f"File {filepath} does not exist")
            return 0
            
        count = 0
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    document = json.loads(line)
                    
                    # Use upsert to avoid duplicates
                    self.collection.update_one(
                        {"title": document["title"]},
                        {"$set": document},
                        upsert=True
                    )
                    count += 1
                    
                except Exception as e:
                    print(f"Error importing line: {str(e)}")
        
        print(f"Successfully imported {count} documents from {filepath}")
        return count
    
    def create_vector_index(self):
        """Create vector embeddings for improved semantic search"""
        if self.embeddings is None:
            print("OpenAI embeddings not available. Please set OPENAI_API_KEY.")
            return False
            
        try:
            # Get all documents
            documents = list(self.collection.find({}))
            print(f"Creating vector embeddings for {len(documents)} documents...")
            
            # Process each document
            for i, doc in enumerate(documents):
                try:
                    title = doc["title"]
                    content = doc["content"]
                    
                    # Generate embedding
                    text_to_embed = f"Title: {title}\n\n{content[:8000]}"  # Limit content length
                    embedding = self.embeddings.embed_query(text_to_embed)
                    
                    # Create vector document
                    vector_doc = {
                        "title": title,
                        "content": content[:10000],  # Limit content length
                        "embedding": embedding,
                        "original_id": doc["_id"]
                    }
                    
                    # Insert or update vector document
                    self.vector_collection.update_one(
                        {"title": title},
                        {"$set": vector_doc},
                        upsert=True
                    )
                    
                    if (i + 1) % 10 == 0:
                        print(f"Processed {i + 1}/{len(documents)} documents")
                        
                except Exception as e:
                    print(f"Error processing document {doc.get('title', 'Unknown')}: {str(e)}")
            
            print(f"Successfully created vector embeddings for {len(documents)} documents")
            return True
            
        except Exception as e:
            print(f"Error creating vector index: {str(e)}")
            return False
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for documents using text search"""
        try:
            results = self.collection.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            
            return list(results)
        except Exception as e:
            print(f"Error searching: {str(e)}")
            return []
    
    def vector_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for documents using vector similarity"""
        if self.embeddings is None:
            print("Vector search not available. Using text search instead.")
            return self.search(query, limit)
            
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Perform vector search
            results = self.vector_collection.aggregate([
                {
                    "$search": {
                        "index": "vector_index",
                        "knnBeta": {
                            "vector": query_embedding,
                            "path": "embedding",
                            "k": limit
                        }
                    }
                },
                {
                    "$limit": limit
                }
            ])
            
            return list(results)
        except Exception as e:
            print(f"Error with vector search: {str(e)}")
            print("Falling back to text search.")
            return self.search(query, limit)
    
    def find_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Find exact document by title"""
        return self.collection.find_one({"title": title})
    
    def get_similar_titles(self, title_fragment: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find documents with similar titles"""
        regex = {"$regex": title_fragment, "$options": "i"}
        results = self.collection.find({"title": regex}).limit(limit)
        return list(results)
    
    def get_excerpt(self, doc: Dict[str, Any], search_term: str, context_chars: int = 150) -> str:
        """Extract an excerpt from content around the search term"""
        content = doc.get("content", "")
        
        # Find position of search term
        pos = content.lower().find(search_term.lower())
        
        if pos >= 0:
            # Calculate excerpt boundaries
            start = max(0, pos - context_chars)
            end = min(len(content), pos + len(search_term) + context_chars)
            
            # Try to find paragraph boundaries
            paragraph_start = content.rfind("\n\n", 0, pos)
            if paragraph_start > 0 and paragraph_start > pos - 500:
                start = paragraph_start + 2
                
            paragraph_end = content.find("\n\n", pos)
            if paragraph_end > 0 and paragraph_end < pos + 500:
                end = paragraph_end
                
            # Extract excerpt
            excerpt = content[start:end].strip()
            
            # Add ellipsis if needed
            if start > 0:
                excerpt = "..." + excerpt
            if end < len(content):
                excerpt = excerpt + "..."
                
            return excerpt
            
        # If search term not found, return beginning of content
        return content[:300].strip() + "..."
    
    def create_context(self, query: str, max_docs: int = 3, max_chars: int = 4000) -> str:
        """Create context for a chatbot from relevant documents"""
        # Try vector search first, fall back to text search
        if self.embeddings is not None and self.vector_collection.count_documents({}) > 0:
            results = self.vector_search(query, max_docs)
        else:
            results = self.search(query, max_docs)
            
        context_parts = []
        total_chars = 0
        
        for doc in results:
            title = doc.get("title", "Unknown")
            excerpt = self.get_excerpt(doc, query)
            
            if total_chars + len(excerpt) + len(title) + 10 <= max_chars:
                context_parts.append(f"--- {title} ---\n{excerpt}")
                total_chars += len(excerpt) + len(title) + 10
                
        return "\n\n".join(context_parts)

    def get_all_character_names(self) -> List[str]:
        """Get a list of all character names in the database"""
        # This is a simple implementation. You might want to refine with regex patterns
        # to identify actual character names more precisely
        pipeline = [
            {"$match": {"content": {"$regex": "character|lord|lady|ser|king|queen", "$options": "i"}}},
            {"$project": {"title": 1}}
        ]
        
        results = self.collection.aggregate(pipeline)
        return [doc.get("title", "") for doc in results if doc.get("title")]
    
    def get_random_documents(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get random documents from the database"""
        pipeline = [{"$sample": {"size": count}}]
        results = self.collection.aggregate(pipeline)
        return list(results)
    
    def close(self):
        """Close the MongoDB connection"""
        if self.client:
            self.client.close()
            print("MongoDB connection closed")


if __name__ == "__main__":
    # Example usage
    mongo = GOTMongoConnection()
    
    # Import data from directory
    data_dir = "assets/data"
    if os.path.exists(data_dir):
        mongo.import_from_directory(data_dir)
    
    # Import data from JSONL if it exists
    jsonl_file = os.path.join(data_dir, "mongodb_import.json")
    if os.path.exists(jsonl_file):
        mongo.import_from_jsonl(jsonl_file)
    
    # Test search functionality
    query = "Stark family"
    results = mongo.search(query, 3)
    print(f"\nSearch results for '{query}':")
    for doc in results:
        print(f"- {doc.get('title')}")
        excerpt = mongo.get_excerpt(doc, "Stark")
        print(f"  Excerpt: {excerpt[:100]}...")
    
    # Create context for chatbot
    context = mongo.create_context(query)
    print(f"\nContext for chatbot query '{query}':")
    print(context[:500] + "..." if len(context) > 500 else context)
    
    # Close connection
    mongo.close()