import os
import sys
from typing import List, Dict, Any
import json
import readline  # For better CLI input experience
from mongo_utils import GOTChatbotDB

class GOTChatbot:
    """Game of Thrones Chatbot using MongoDB data"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/"):
        """Initialize chatbot with database connection"""
        self.db = GOTChatbotDB(mongo_uri=mongo_uri)
        self.conversation_history = []
        self.max_context_chars = 4000
        
        # Check if database is populated
        doc_count = self.db.count_documents()
        if doc_count == 0:
            print("WARNING: The database is empty. Please run the scraper first.")
            print("You can use: python fandom-scrape-full.py")
            self._check_local_files()
        else:
            print(f"Connected to database with {doc_count} Game of Thrones wiki pages")
    
    def _check_local_files(self):
        """Check if there are local files to import"""
        data_dir = "assets/data"
        if os.path.exists(data_dir):
            txt_files = [f for f in os.listdir(data_dir) if f.endswith('.txt')]
            if txt_files:
                print(f"Found {len(txt_files)} text files in {data_dir}.")
                choice = input("Do you want to import these files to MongoDB? (y/n): ")
                if choice.lower() == 'y':
                    count = self.db.import_from_directory(data_dir)
                    print(f"Imported {count} documents to MongoDB.")
    
    def get_context_for_query(self, query: str) -> str:
        """Retrieve relevant context for a user query"""
        return self.db.create_chatbot_context(
            query=query,
            max_documents=5,
            max_chars=self.max_context_chars
        )
    
    def generate_response(self, query: str, context: str) -> str:
        """Generate a response based on context and query"""
        # This is a placeholder for actual LLM integration
        # In a real implementation, you would call an LLM API here
        
        # For now, we'll just provide a simple response based on available data
        if not context:
            return "I don't have enough information about that in my Game of Thrones knowledge. Could you ask something else about the series, characters, or lore?"
        
        # Very simple response - in a real implementation, you would use an LLM
        return f"Here's what I know about '{query}':\n\n{context}\n\nThis is where you would integrate with an LLM API to generate a proper response based on this context."
    
    def process_question(self, question: str) -> str:
        """Process a user question and return a response"""
        # Get relevant context from database
        context = self.get_context_for_query(question)
        
        # Generate response (with an LLM in a real implementation)
        response = self.generate_response(question, context)
        
        # Update conversation history
        self.conversation_history.append({
            "question": question,
            "response": response,
            "context_used": context[:100] + "..." if context else "None"
        })
        
        return response
    
    def run_cli(self):
        """Run an interactive CLI for the chatbot"""
        print("Welcome to the Game of Thrones Chatbot!")
        print("Ask me anything about Game of Thrones, or type 'exit' to quit.")
        print("-----------------------------------------------------")
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("Goodbye! The night is dark and full of terrors...")
                    break
                
                if not user_input:
                    continue
                
                print("\nThinking...")
                response = self.process_question(user_input)
                print(f"\nChatbot: {response}")
                
            except KeyboardInterrupt:
                print("\nGoodbye! The night is dark and full of terrors...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")

# Example implementation with LLM integration placeholder
def create_llm_integration():
    """
    Placeholder for LLM integration
    
    In a real implementation, you would:
    1. Connect to an LLM API (OpenAI, Claude, etc.)
    2. Format your prompt with context
    3. Handle the API response
    
    Example pseudocode:
    ```
    def generate_response(self, query: str, context: str) -> str:
        # Craft a prompt with context
        prompt = f'''
        You are a Game of Thrones expert chatbot. Use the following information to answer the question.
        If you don't know the answer, say so honestly.
        
        Game of Thrones Wiki Information:
        {context}
        
        Question: {query}
        
        Answer:
        '''
        
        # Call an LLM API
        response = openai.Completion.create(
            model="gpt-4",
            prompt=prompt,
            max_tokens=500,
            temperature=0.7,
        )
        
        return response.choices[0].text.strip()
    ```
    """
    pass

if __name__ == "__main__":
    chatbot = GOTChatbot()
    chatbot.run_cli()