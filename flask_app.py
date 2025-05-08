import os
from flask import Flask, render_template, request, jsonify
from chatbot_llm import GOTChatbotLLM

app = Flask(__name__)
chatbot = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
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
    response = chatbot.process_question(question)
    
    return jsonify({
        'response': response,
        'question': question
    })

if __name__ == '__main__':
    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)
    
    # Create chatbot instance
    chatbot = GOTChatbotLLM()
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)