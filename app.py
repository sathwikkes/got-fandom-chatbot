#!/usr/bin/env python3
"""
Game of Thrones Chatbot Web Application
- Flask web interface for GOT chatbot
- Includes MongoDB database connection
- Integrates with LLMs for enhanced responses
"""

import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from chatbot_llm import GOTChatbotLLM

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
chatbot = None

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """API endpoint for chatbot interaction"""
    global chatbot
    
    # Initialize chatbot if not already done
    if chatbot is None:
        chatbot = GOTChatbotLLM()
    
    # Get question from request
    data = request.get_json()
    question = data.get('question', '')
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    # Process question and get response
    try:
        response = chatbot.process_question(question)
        return jsonify({
            'response': response,
            'question': question
        })
    except Exception as e:
        return jsonify({
            'error': f"An error occurred: {str(e)}",
            'question': question
        }), 500

@app.route('/api/info', methods=['GET'])
def info():
    """Get information about the chatbot's database"""
    global chatbot
    
    # Initialize chatbot if not already done
    if chatbot is None:
        chatbot = GOTChatbotLLM()
    
    # Get database information
    try:
        db_stats = {
            'total_documents': chatbot.mongo.collection.count_documents({}),
            'characters': len(chatbot.character_names),
            'houses': len(chatbot.houses),
            'locations': len(chatbot.locations),
            'llm_provider': chatbot.llm.llm_provider if chatbot.llm.api_key else 'None',
            'llm_model': chatbot.llm.model if chatbot.llm.api_key else 'None'
        }
        
        # Get sample character names (up to 10)
        sample_characters = chatbot.character_names[:10] if chatbot.character_names else []
        
        return jsonify({
            'stats': db_stats,
            'sample_characters': sample_characters
        })
    except Exception as e:
        return jsonify({
            'error': f"An error occurred: {str(e)}"
        }), 500

@app.route('/api/characters', methods=['GET'])
def characters():
    """Get a list of all characters in the database"""
    global chatbot
    
    # Initialize chatbot if not already done
    if chatbot is None:
        chatbot = GOTChatbotLLM()
    
    # Get characters
    try:
        return jsonify({
            'characters': chatbot.character_names
        })
    except Exception as e:
        return jsonify({
            'error': f"An error occurred: {str(e)}"
        }), 500

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Ensure templates and static directories exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Create chatbot instance
    chatbot = GOTChatbotLLM()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=port)