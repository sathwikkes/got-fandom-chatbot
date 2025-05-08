# Game of Thrones Chatbot

A conversational AI chatbot that answers questions about the Game of Thrones universe, based on data scraped from the Game of Thrones Wiki. This project combines web scraping, MongoDB for data storage, and Language Model (LLM) integration for intelligent responses.

## Features

- **Web Scraping**: Scrapes character, house, and location information from the Game of Thrones Wiki
- **MongoDB Integration**: Stores and indexes the data for efficient semantic and text-based searching
- **LLM Integration**: Supports OpenAI and Anthropic Claude for natural language responses
- **Web Interface**: Flask-based web application with a responsive UI
- **CLI Interface**: Command-line interface for quick testing
- **Fallback Mode**: Rule-based responses when LLM integration is not configured

## Getting Started

### Prerequisites

- Python 3.8+
- MongoDB (local or remote)
- OpenAI API key or Anthropic API key (optional but recommended)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd got-fandom-chatbot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your environment variables:
   - Create a `.env` file in the project root
   - Add your API keys (see `.env.example`)
   - Alternatively, create an `api_keys.json` file with your API keys

4. Run the scraper to gather data:
   ```bash
   python fandom-scrape-optimized.py --max-pages 50
   ```

5. Launch the web interface:
   ```bash
   python flask_app.py
   ```

   Or use the CLI:
   ```bash
   python chatbot_llm.py
   ```

### Environment Variables

Create a `.env` file with the following:

```
# LLM Provider Configuration
# Uncomment and fill in the appropriate section

# For OpenAI:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your_api_key_here
# OPENAI_MODEL=gpt-4

# For Anthropic Claude:
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your_api_key_here
# ANTHROPIC_MODEL=claude-3-opus-20240229
```

Alternatively, you can create an `api_keys.json` file with this structure:

```json
{
    "openai": {
        "api_key": "your_openai_api_key_here",
        "model": "gpt-4o"
    },
    "anthropic": {
        "api_key": "your_anthropic_api_key_here",
        "model": "claude-3-opus-20240229"
    }
}
```

## Project Structure

### Core Components

| Script | Description |
|--------|-------------|
| `app.py` | Main entry point for the web application |
| `flask_app.py` | Flask web application that serves the chatbot interface |
| `chatbot.py` | Basic chatbot implementation without LLM integration |
| `chatbot_llm.py` | Enhanced chatbot with LLM integration (OpenAI/Claude) |
| `got_chatbot.py` | Original Game of Thrones chatbot implementation |
| `llm_integration.py` | Integration layer for different LLM providers |

### Data Management

| Script | Description |
|--------|-------------|
| `mongodb_connect.py` | MongoDB connection manager with vector search capabilities |
| `mongo_utils.py` | Utility functions for MongoDB operations |
| `fandom-scrape-optimized.py` | Optimized scraper for Game of Thrones Wiki |
| `scrape_utils.py` | Utility functions for web scraping |
| `export_for_vectors.py` | Tool to export data for vector embeddings |

### Directories

- `templates/` - HTML templates for the web interface
- `static/` - Static assets for the web interface
- `assets/data/` - Scraped text files and MongoDB import files

## Usage

### Web Scraping

```bash
# Scrape a specified number of pages
python fandom-scrape-optimized.py --max-pages 50

# Scrape with a slower rate limit
python fandom-scrape-optimized.py --max-pages 100 --delay 2.0

# Scrape without limit (will take a long time)
python fandom-scrape-optimized.py --no-limit
```

### Web Interface

1. Start the Flask application:
   ```bash
   python flask_app.py
   ```

2. Open your browser to `http://localhost:5000`

### CLI Interface

```bash
# Run the LLM-integrated chatbot
python chatbot_llm.py

# Run the basic chatbot (no LLM)
python chatbot.py
```

## Advanced Features

- **Vector Search**: MongoDB Atlas vector search integration for semantic similarity
- **Hallucination Detection**: Filter potential hallucinations from LLM responses
- **Context-Aware Responses**: Uses relevant wiki excerpts to ground responses in facts
- **Multi-Provider Support**: Swap between different LLM providers (OpenAI/Claude)

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue.

## License

[MIT License](LICENSE)

## Acknowledgements

- Game of Thrones Wiki for the source data
- OpenAI and Anthropic for the language model APIs
- Flask and MongoDB for the infrastructure