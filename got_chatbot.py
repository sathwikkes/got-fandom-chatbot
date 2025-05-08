import os
import sys
import json
import random
import readline
from typing import List, Dict, Any, Optional
from mongodb_connect import GOTMongoConnection

class GOTChatbot:
    """
    Game of Thrones Chatbot using MongoDB data with LLM integration
    """
    
    def __init__(self, mongodb_uri: str = "mongodb://localhost:27017/"):
        """Initialize chatbot with database connection"""
        self.mongo = GOTMongoConnection(mongodb_uri)
        self.conversation_history = []
        self.max_context_chars = 4000
        self.character_names = []
        self.houses = []
        self.locations = []
        
        # Check if database is populated
        doc_count = self.mongo.collection.count_documents({})
        if doc_count == 0:
            print("WARNING: The database is empty. Please run the scraper first.")
            print("You can use: python fandom-scrape-optimized.py")
            self._check_local_files()
        else:
            print(f"Connected to database with {doc_count} Game of Thrones wiki pages")
            
        # Load character names, houses, and locations for better responses
        self._load_entity_lists()
        
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
            
            # Get location names - this is a simplified approach
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
    
    def generate_response(self, query: str, context: str) -> str:
        """
        Generate a response based on context and query
        
        This is where you would integrate with an LLM API like OpenAI's GPT,
        Claude, or another LLM. For now, we'll implement a simpler approach.
        """
        if not context:
            return self._get_no_info_response()
        
        # For now, we provide a simple response using the context
        # In a full implementation, you would send the context to an LLM API
        
        # Extract the first mentioned entity from the context
        first_section = context.split("---")[0] if "---" in context else context
        first_title = context.split("---")[1].strip() if len(context.split("---")) > 1 else "unknown"
        
        # Construct a simple response
        if "who" in query.lower() or "what is" in query.lower():
            return self._format_response_about(first_title, context)
        elif "where" in query.lower():
            return self._format_location_response(query, context)
        elif "when" in query.lower():
            return self._format_time_response(query, context)
        elif "why" in query.lower():
            return self._format_reason_response(query, context)
        elif "how" in query.lower():
            return self._format_process_response(query, context)
        else:
            return self._format_general_response(query, context)
    
    def _format_response_about(self, entity: str, context: str) -> str:
        """Format a response about a character, house, or location"""
        # Extract a relevant snippet from the context
        paragraphs = context.split("\n\n")
        relevant_info = next((p for p in paragraphs if len(p) > 100), paragraphs[0])
        
        return f"Based on the Game of Thrones lore about {entity}, {relevant_info}"
    
    def _format_location_response(self, query: str, context: str) -> str:
        """Format a response about a location"""
        for location in self.locations:
            if location.lower() in context.lower():
                # Find a paragraph mentioning the location
                paragraphs = context.split("\n\n")
                location_para = next((p for p in paragraphs if location.lower() in p.lower()), 
                                     "is mentioned in the Game of Thrones universe")
                return f"{location} {location_para}"
        
        return "Based on the Game of Thrones lore, " + context.split("\n\n")[0]
    
    def _format_time_response(self, query: str, context: str) -> str:
        """Format a response about timing or events"""
        # Look for dates or time references
        time_indicators = ["during", "after", "before", "when", "at the time", 
                           "following", "AC", "BC", "age", "year"]
        
        for indicator in time_indicators:
            index = context.lower().find(indicator.lower())
            if index >= 0:
                # Extract the sentence containing the time reference
                start = max(0, context.rfind(".", 0, index) + 1)
                end = context.find(".", index)
                if end < 0:
                    end = len(context)
                
                time_sentence = context[start:end].strip()
                return f"According to Game of Thrones history, {time_sentence}."
        
        return "Based on Game of Thrones chronology, " + context.split("\n\n")[0]
    
    def _format_reason_response(self, query: str, context: str) -> str:
        """Format a response explaining reasons or motivations"""
        reason_indicators = ["because", "due to", "as a result", "reason", 
                             "motivated by", "intended to"]
        
        for indicator in reason_indicators:
            index = context.lower().find(indicator.lower())
            if index >= 0:
                # Extract the sentence containing the reason
                start = max(0, context.rfind(".", 0, index) + 1)
                end = context.find(".", index)
                if end < 0:
                    end = len(context)
                
                reason_sentence = context[start:end].strip()
                return f"In the Game of Thrones world, {reason_sentence}."
        
        return "According to Game of Thrones lore, " + context.split("\n\n")[0]
    
    def _format_process_response(self, query: str, context: str) -> str:
        """Format a response explaining how something happened"""
        # Simple paragraph extraction for "how" questions
        paragraphs = context.split("\n\n")
        relevant_paragraph = next((p for p in paragraphs if len(p) > 150), paragraphs[0])
        
        return f"Here's how it happened in Game of Thrones: {relevant_paragraph}"
    
    def _format_general_response(self, query: str, context: str) -> str:
        """Format a general response using the context"""
        # Extract the most relevant paragraph
        paragraphs = context.split("\n\n")
        
        # Try to find paragraphs containing words from the query
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        
        for paragraph in paragraphs:
            for word in query_words:
                if word in paragraph.lower():
                    return f"In Game of Thrones: {paragraph}"
        
        # Default to first substantial paragraph
        relevant_paragraph = next((p for p in paragraphs if len(p) > 100), paragraphs[0])
        return f"According to Game of Thrones lore: {relevant_paragraph}"
    
    def _get_no_info_response(self) -> str:
        """Generate a response when no context information is available"""
        responses = [
            "I don't have enough information about that in my Game of Thrones knowledge.",
            "That doesn't appear in my records of Westeros and Essos.",
            "The maesters haven't recorded that information in my archives.",
            "I don't know about that aspect of Game of Thrones. Would you like to ask about one of the main characters or houses instead?",
            "My knowledge of the Seven Kingdoms doesn't include that information.",
            "Even the Spider's little birds haven't whispered that to me yet."
        ]
        return random.choice(responses)
    
    def process_question(self, question: str) -> str:
        """Process a user question and return a response"""
        # Get relevant context from database
        context = self.get_context_for_query(question)
        
        # Generate response
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
        print("\n" + "=" * 60)
        print("Welcome to the Game of Thrones Chatbot!")
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
                print(f"\nChatbot: {response}")
                
            except KeyboardInterrupt:
                print("\nFarewell! The night is dark and full of terrors...")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")

def create_llm_integration():
    """
    Instructions for LLM API integration
    
    To integrate with an actual LLM API (like OpenAI's GPT, Claude, etc.):
    
    1. Replace the generate_response method with API calls to your LLM of choice
    2. Format your prompt using the context and query
    3. Handle the response from the API
    
    Example with OpenAI (requires openai package):
    ```python
    import openai
    
    # Set up OpenAI client
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    def generate_response(self, query: str, context: str) -> str:
        # Create a prompt with the context and query
        prompt = f'''
        You are a Game of Thrones expert chatbot. Use the following information from 
        the Game of Thrones wiki to answer the user's question.
        
        Game of Thrones Wiki Information:
        {context}
        
        User Question: {query}
        
        Answer based only on the information provided. If the information to answer
        the question is not contained in the provided context, say that you don't have
        enough information.
        '''
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4",  # or "gpt-3.5-turbo" for a less expensive option
            messages=[
                {"role": "system", "content": "You are a Game of Thrones expert chatbot."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    ```
    
    Example with Anthropic Claude:
    ```python
    import anthropic
    
    # Set up Anthropic client
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    def generate_response(self, query: str, context: str) -> str:
        # Create a prompt with the context and query
        prompt = f'''
        Human: You are a Game of Thrones expert chatbot. Use the following information from 
        the Game of Thrones wiki to answer the user's question.
        
        Game of Thrones Wiki Information:
        {context}
        
        User Question: {query}
        
        Answer based only on the information provided. If the information to answer
        the question is not contained in the provided context, say that you don't have
        enough information.
        
        Assistant:
        '''
        
        # Call Anthropic API
        response = client.completions.create(
            model="claude-2",
            prompt=prompt,
            max_tokens_to_sample=500,
            temperature=0.7,
        )
        
        return response.completion
    ```
    """
    pass

if __name__ == "__main__":
    chatbot = GOTChatbot()
    chatbot.run_cli()