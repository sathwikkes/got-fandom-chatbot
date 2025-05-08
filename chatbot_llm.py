#!/usr/bin/env python3
"""
Game of Thrones Chatbot with LLM Integration
- Uses MongoDB to retrieve context about Game of Thrones
- Integrates with LLMs (OpenAI or Anthropic) for advanced responses
- Falls back to rule-based responses if no LLM is configured
"""

import os
import sys
import readline
from typing import List, Dict, Any, Optional
from mongodb_connect import GOTMongoConnection
from llm_integration import LLMIntegration

class GOTChatbotLLM:
    """
    Game of Thrones Chatbot using MongoDB data with LLM integration
    """
    
    def __init__(self, mongodb_uri: str = "mongodb://localhost:27017/"):
        """Initialize chatbot with database connection and LLM"""
        self.mongo = GOTMongoConnection(mongodb_uri)
        self.llm = LLMIntegration()
        self.conversation_history = []
        self.max_context_chars = 4000
        
        # Load entity lists for better responses
        self.character_names = []
        self.houses = []
        self.locations = []
        
        # Check if database is populated
        doc_count = self.mongo.collection.count_documents({})
        if doc_count == 0:
            print("WARNING: The database is empty. Please run the scraper first.")
            print("You can use: python fandom_scraper.py")
            self._check_local_files()
        else:
            print(f"Connected to database with {doc_count} Game of Thrones wiki pages")
            
        # Load entity lists
        self._load_entity_lists()
        
        # Check if LLM is configured
        if self.llm.api_key:
            print(f"LLM Integration: {self.llm.llm_provider.capitalize()} model {self.llm.model}")
        else:
            print("No LLM configured. Using fallback responses.")
            print("Set up a .env file with your API keys to enable the LLM integration.")
    
    def _check_local_files(self):
        """Check if there are local files to import"""
        data_dir = "assets/data"
        if os.path.exists(data_dir):
            txt_files = [f for f in os.listdir(data_dir) if f.endswith('.txt')]
            if txt_files:
                print(f"Found {len(txt_files)} text files in {data_dir}.")
                choice = input("Do you want to import these files to MongoDB? (y/n): ")
                if choice.lower() == 'y':
                    count = self.mongo.import_from_directory(data_dir)
                    print(f"Imported {count} documents to MongoDB.")
                    # Also import JSONL if it exists
                    jsonl_path = os.path.join(data_dir, "mongodb_import.json")
                    if os.path.exists(jsonl_path):
                        self.mongo.import_from_jsonl(jsonl_path)
    
    def _load_entity_lists(self):
        """Load lists of characters, houses, and locations from database"""
        try:
            # Get character names - those ending with "Stark", "Lannister", etc.
            character_query = {"title": {"$regex": "^[A-Z][a-z]+ (Stark|Lannister|Targaryen|Baratheon|Greyjoy|Tully|Tyrell|Martell|Snow)$"}}
            character_docs = self.mongo.collection.find(character_query, {"title": 1})
            self.character_names = [doc["title"] for doc in character_docs]
            
            # Get house names
            house_query = {"title": {"$regex": "^House "}}
            house_docs = self.mongo.collection.find(house_query, {"title": 1})
            self.houses = [doc["title"] for doc in house_docs]
            
            # Get location names
            location_query = {"title": {"$in": [
                "Winterfell", "King's Landing", "The Wall", "Casterly Rock", "Dragonstone",
                "The North", "The Riverlands", "The Vale", "The Westerlands", "The Reach",
                "Dorne", "The Iron Islands", "The Stormlands", "Braavos", "Volantis",
                "Pentos", "Meereen", "Astapor", "Yunkai", "Qarth", "Valyria"
            ]}}
            location_docs = self.mongo.collection.find(location_query, {"title": 1})
            self.locations = [doc["title"] for doc in location_docs]
            
            print(f"Loaded {len(self.character_names)} characters, {len(self.houses)} houses, " + 
                  f"and {len(self.locations)} locations")
                  
        except Exception as e:
            print(f"Error loading entity lists: {str(e)}")
    
    def get_context_for_query(self, query: str) -> str:
        """Retrieve relevant context for a user query"""
        return self.mongo.create_context(
            query=query,
            max_docs=5,
            max_chars=self.max_context_chars
        )
    
    def process_question(self, question: str) -> str:
        """Process a user question and return a response"""
        # Get relevant context from database
        context = self.get_context_for_query(question)
        
        # Generate response using LLM
        if not context:
            response = "I don't have enough information about that in my Game of Thrones knowledge."
        else:
            response = self.llm.generate_response(question, context)
        
        # Update conversation history
        self.conversation_history.append({
            "question": question,
            "response": response,
            "context_used": context[:100] + "..." if context else "None"
        })
        
        return response
    
    def run_cli(self):
        """Run an interactive CLI for the chatbot"""
        print("\n" + "=" * 60)
        print("Welcome to the Game of Thrones Chatbot with LLM integration!")
        print("Ask me anything about Game of Thrones, or type 'exit' to quit.")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("\nFarewell! The night is dark and full of terrors...")
                    break
                
                if not user_input:
                    continue
                
                print("\nThinking...")
                response = self.process_question(user_input)
                print("\nChatbot:")
                print(response)
                
            except KeyboardInterrupt:
                print("\nFarewell! The night is dark and full of terrors...")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")
                
        # Close MongoDB connection on exit
        if self.mongo:
            self.mongo.close()


if __name__ == "__main__":
    chatbot = GOTChatbotLLM()
    chatbot.run_cli()