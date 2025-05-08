import os
import json
import re
import string
from typing import Dict, Any, Optional, List, Set, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class LLMIntegration:
    """
    LLM Integration for the Game of Thrones Chatbot
    Supports multiple LLM providers: OpenAI, Anthropic Claude, etc.
    """
    
    def __init__(self, config_file: Optional[str] = "api_keys.json"):
        """Initialize the LLM integration with configuration"""
        self.config = {}
        self.llm_provider = None
        self.api_key = None
        self.model = None
        
        # Try loading from api_keys.json first
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
                
                # Check for OpenAI config
                if "openai" in self.config and "api_key" in self.config["openai"]:
                    self.llm_provider = "openai"
                    self.api_key = self.config["openai"]["api_key"]
                    self.model = self.config["openai"].get("model", "gpt-4")
                # Check for Anthropic config
                elif "anthropic" in self.config and "api_key" in self.config["anthropic"]:
                    self.llm_provider = "anthropic"
                    self.api_key = self.config["anthropic"]["api_key"]
                    self.model = self.config["anthropic"].get("model", "claude-3-opus-20240229")
                
                if self.api_key != "your_openai_api_key_here" and self.api_key != "your_anthropic_api_key_here":
                    print(f"Loaded API keys from {config_file}")
                else:
                    self.api_key = None
                    print(f"Please update {config_file} with your actual API keys")
            except Exception as e:
                print(f"Error loading from {config_file}: {str(e)}")
        
        # If API key not found in file, try environment variables
        if not self.api_key:
            self._load_from_env()
        
        # Initialize the provider client
        self._initialize_provider()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Get provider from env vars
        provider = os.getenv("LLM_PROVIDER", "").lower()
        if provider:
            self.llm_provider = provider
            
            # Set API key based on provider
            if provider == "openai":
                self.api_key = os.getenv("OPENAI_API_KEY")
                self.model = os.getenv("OPENAI_MODEL", "gpt-4")
            elif provider == "anthropic":
                self.api_key = os.getenv("ANTHROPIC_API_KEY")
                self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
            else:
                print(f"Warning: Unsupported LLM provider {provider}")
    
    def _initialize_provider(self):
        """Initialize the API client for the selected provider"""
        if not self.llm_provider or not self.api_key:
            print("Warning: No LLM provider configured. Using fallback responses.")
            return
            
        try:
            if self.llm_provider == "openai":
                # Import and initialize OpenAI client
                try:
                    import openai
                    self.client = openai.OpenAI(api_key=self.api_key)
                    print(f"Initialized OpenAI client with model {self.model}")
                except ImportError:
                    print("OpenAI package not installed. Run: pip install openai")
                    self.client = None
                    
            elif self.llm_provider == "anthropic":
                # Import and initialize Anthropic client
                try:
                    import anthropic
                    self.client = anthropic.Anthropic(api_key=self.api_key)
                    print(f"Initialized Anthropic Claude client with model {self.model}")
                except ImportError:
                    print("Anthropic package not installed. Run: pip install anthropic")
                    self.client = None
        except Exception as e:
            print(f"Error initializing LLM provider: {str(e)}")
            self.client = None
    
    def generate_response(self, query: str, context: str) -> str:
        """Generate a response using the configured LLM"""
        if not self.client:
            # Return a fallback response if client not initialized
            response = self._generate_fallback_response(query, context)
            return response + "\n\n(Using rule-based response system - No LLM configured)"
            
        try:
            if self.llm_provider == "openai":
                raw_response = self._generate_openai_response(query, context)
                # Apply hallucination filter
                filtered_response = self._filter_hallucinations(raw_response, context, query)
                return filtered_response + f"\n\n(Generated using OpenAI {self.model})"
                
            elif self.llm_provider == "anthropic":
                raw_response = self._generate_anthropic_response(query, context)
                # Apply hallucination filter
                filtered_response = self._filter_hallucinations(raw_response, context, query)
                return filtered_response + f"\n\n(Generated using Anthropic {self.model})"
                
            else:
                response = self._generate_fallback_response(query, context)
                return response + "\n\n(Using rule-based response system - No LLM configured)"
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}. Please try again."
            
    def _filter_hallucinations(self, response: str, context: str, query: str) -> str:
        """
        Filter potential hallucinations from LLM responses by comparing them to the provided context
        """
        # If there's no response, just return it
        if not response:
            return response
            
        # Extract key entities from context
        context_entities = self._extract_entities(context)
        
        # Extract key entities from response
        response_entities = self._extract_entities(response)
        
        # Find potential hallucinated entities (in response but not in context)
        potential_hallucinations = response_entities - context_entities
        
        # Filter out common words and stop words
        filtered_hallucinations = self._filter_common_words(potential_hallucinations)
        
        # If no hallucinations found, return the original response
        if not filtered_hallucinations:
            return response
            
        # Check if the response already contains uncertainty markers about these entities
        uncertain_response = self._contains_uncertainty_markers(response, filtered_hallucinations)
        if uncertain_response:
            return response
        
        # Otherwise, add a note about possible hallucinations
        disclaimer = self._create_hallucination_disclaimer(filtered_hallucinations, query)
        
        return f"{response}\n\n{disclaimer}"
    
    def _extract_entities(self, text: str) -> Set[str]:
        """Extract potential named entities and key terms from text"""
        # Normalize and clean the text
        text = text.lower()
        
        # Extract potential named entities (capitalized words)
        words = re.findall(r'\b[A-Z][a-z]+\b', text)
        
        # Also get bigrams and trigrams for multi-word entities
        tokens = [token.strip(string.punctuation) for token in text.split()]
        bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens)-1)]
        trigrams = [f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}" for i in range(len(tokens)-2)]
        
        # Combine all potential entities
        all_potential_entities = set(words) | set(bigrams) | set(trigrams)
        
        # Return normalized entities
        return {entity.lower() for entity in all_potential_entities if len(entity) > 3}
    
    def _filter_common_words(self, entities: Set[str]) -> Set[str]:
        """Filter out common words and stop words"""
        # List of common words to filter out
        common_words = {
            "this", "that", "these", "those", "there", "their", "they", "about", "which", 
            "would", "could", "should", "have", "based", "information", "because", "however",
            "while", "series", "character", "season", "episode", "show", "many", "more",
            "other", "another", "first", "second", "last", "next", "previous", "following",
            "before", "after", "during", "game", "thrones", "westeros", "essos"
        }
        
        # Remove common words
        return {entity for entity in entities if entity.lower() not in common_words}
    
    def _contains_uncertainty_markers(self, response: str, entities: Set[str]) -> bool:
        """Check if the response already expresses uncertainty about the potential hallucinations"""
        # List of phrases indicating uncertainty
        uncertainty_phrases = [
            "i don't have information", 
            "not mentioned in", 
            "isn't specified", 
            "not specified", 
            "isn't mentioned",
            "not provided", 
            "no information", 
            "don't know", 
            "isn't clear", 
            "not clear",
            "based on the information i have",
            "the provided context doesn't",
            "not detailed in",
            "can't determine",
            "cannot determine"
        ]
        
        # Check if any uncertainty phrase is present for each entity
        response_lower = response.lower()
        for entity in entities:
            entity_lower = entity.lower()
            for phrase in uncertainty_phrases:
                if f"{phrase}" in response_lower and entity_lower in response_lower:
                    return True
                    
        return False
    
    def _create_hallucination_disclaimer(self, hallucinations: Set[str], query: str) -> str:
        """Create a disclaimer about potential hallucinations"""
        if not hallucinations:
            return ""
            
        # Format the hallucinations list (limit to the top 3)
        hallucination_list = list(hallucinations)[:3]
        formatted_list = ", ".join([f'"{h}"' for h in hallucination_list])
        
        # Create a disclaimer note
        disclaimer = (
            "Note: Some details in this response might extend beyond the information provided in the context. "
            "The information about " + formatted_list + " is not explicitly mentioned in the provided dataset. "
            "Please consider this information with caution."
        )
        
        return disclaimer
    
    def _generate_openai_response(self, query: str, context: str) -> str:
        """Generate a response using OpenAI's API"""
        # Create a prompt with the context and query
        prompt = f"""
        You are a Game of Thrones expert chatbot with access to a specific dataset of Game of Thrones information.

        EXTREMELY IMPORTANT: You must ONLY use the information provided below. Do NOT use any external knowledge or make up details not explicitly mentioned in the provided context. If the information needed to answer the question is not in the provided context, clearly state that you don't have that specific information in your dataset.

        Game of Thrones Wiki Information:
        {context}

        User Question: {query}

        RESPONSE REQUIREMENTS:
        1. ONLY use information explicitly provided in the context above
        2. If the exact answer is not in the context, say: "Based on the information I have, I don't know [specific detail]." Do NOT guess or make up information.
        3. Use direct quotes or paraphrase directly from the context whenever possible
        4. Keep your tone friendly and conversational, like a fan discussing the show
        5. Use 2-3 concise paragraphs at most
        6. Focus exclusively on answering what was asked, using only the context provided
        7. Start your response by focusing on the most relevant information from the context
        """
        
        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a Game of Thrones expert chatbot."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    def _generate_anthropic_response(self, query: str, context: str) -> str:
        """Generate a response using Anthropic Claude API"""
        # Create a prompt with the context and query
        prompt = f"""
        Human: You are a Game of Thrones expert chatbot with access ONLY to a specific dataset of Game of Thrones information.

        EXTREMELY IMPORTANT: You must ONLY use the information provided below. Do NOT use ANY external knowledge or make up details not explicitly mentioned in the provided context. If the information needed to answer my question is not in the provided context, clearly state that you don't have that specific information in your dataset.

        Game of Thrones Wiki Information:
        {context}

        My Question: {query}

        RESPONSE REQUIREMENTS:
        1. ONLY use information explicitly provided in the context above
        2. If the exact answer is not in the context, say: "Based on the information I have, I don't know [specific detail]." Do NOT guess or make up information.
        3. Use direct quotes or paraphrase directly from the context whenever possible
        4. Keep your tone friendly and conversational, like a fan discussing the show
        5. Use 2-3 concise paragraphs at most
        6. Focus exclusively on answering what was asked, using only the context provided
        7. Start your response by focusing on the most relevant information from the context
        8. If asked about something not in the context, don't apologize - simply state what information you do and don't have

        Assistant:
        """
        
        # Call Anthropic API
        message = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=0.7,
            system="You are a Game of Thrones expert chatbot. You provide insightful and accurate information about the world of ice and fire.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
    
    def _generate_fallback_response(self, query: str, context: str) -> str:
        """Generate a rule-based response when LLM is not available"""
        if not context:
            return self._get_no_info_response()
            
        # Extract the first mentioned entity from the context
        first_section = context.split("---")[0] if "---" in context else context
        first_title = context.split("---")[1].strip() if len(context.split("---")) > 1 else "unknown"
        
        # Construct a response based on query type
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
    
    def _get_no_info_response(self) -> str:
        """Generate a response when no context information is available"""
        import random
        responses = [
            "I don't have enough information about that in my Game of Thrones knowledge.",
            "That doesn't appear in my records of Westeros and Essos.",
            "The maesters haven't recorded that information in my archives.",
            "I don't know about that aspect of Game of Thrones. Would you like to ask about one of the main characters or houses instead?",
            "My knowledge of the Seven Kingdoms doesn't include that information.",
            "Even the Spider's little birds haven't whispered that to me yet."
        ]
        return random.choice(responses)
    
    def _format_response_about(self, entity: str, context: str) -> str:
        """Format a response about a character, house, or location"""
        # Extract a relevant snippet from the context
        paragraphs = context.split("\n\n")
        relevant_info = next((p for p in paragraphs if len(p) > 100), paragraphs[0])
        
        return f"Based on the Game of Thrones lore about {entity}, {relevant_info}"
    
    def _format_location_response(self, query: str, context: str) -> str:
        """Format a response about a location"""
        # List of known locations in GOT
        locations = [
            "Winterfell", "King's Landing", "The Wall", "Casterly Rock", "Dragonstone",
            "The North", "The Riverlands", "The Vale", "The Westerlands", "The Reach",
            "Dorne", "The Iron Islands", "The Stormlands", "Braavos", "Volantis",
            "Pentos", "Meereen", "Astapor", "Yunkai", "Qarth", "Valyria"
        ]
        
        for location in locations:
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


# Example usage of the LLM integration
if __name__ == "__main__":
    # Test the LLM integration
    llm = LLMIntegration()
    
    # Check if LLM is configured
    if not llm.api_key:
        print("No API key found. Please set the appropriate environment variables.")
        print("For OpenAI: OPENAI_API_KEY and LLM_PROVIDER=openai")
        print("For Anthropic: ANTHROPIC_API_KEY and LLM_PROVIDER=anthropic")
        
        # Create .env template file if it doesn't exist
        if not os.path.exists(".env"):
            with open(".env", "w") as f:
                f.write("""# LLM Provider Configuration
# Uncomment and fill in the appropriate section

# For OpenAI:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your_api_key_here
# OPENAI_MODEL=gpt-4

# For Anthropic Claude:
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your_api_key_here
# ANTHROPIC_MODEL=claude-3-opus-20240229
""")
            print("Created .env template file. Please edit it with your API keys.")
    else:
        # Test response generation
        test_context = "--- Jon Snow ---\nJon Snow is a fictional character in the A Song of Ice and Fire series of fantasy novels by American author George R. R. Martin, and its television adaptation Game of Thrones, in which he is portrayed by English actor Kit Harington. In the novels, he is a prominent point of view character."
        test_query = "Who is Jon Snow?"
        
        print("\nTest query:", test_query)
        print("\nContext:", test_context)
        print("\nResponse:", llm.generate_response(test_query, test_context))