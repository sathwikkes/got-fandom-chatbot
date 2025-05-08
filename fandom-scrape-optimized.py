import requests
import os
import json
import re
import time
import argparse
from bs4 import BeautifulSoup, Tag
from urllib.parse import quote
import concurrent.futures
from typing import Dict, List, Optional, Any, Set, Tuple
import pymongo
from datetime import datetime

# Import MongoDB connection class
from mongodb_connect import GOTMongoConnection

API = "https://gameofthrones.fandom.com/api.php"
BASE_URL = "https://gameofthrones.fandom.com/wiki/"
OUTPUT_DIR = "assets/data"
EXCLUDED_CATEGORIES = ["File:", "Template:", "Category:", "Special:", "Help:", "Portal:"]
MONGODB_IMPORT_FILE = os.path.join(OUTPUT_DIR, "mongodb_import.json")

def sanitize_filename(title):
    """Create a safe filename from a title"""
    # Replace problematic characters with underscore
    safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().replace(' ', '_')
    return safe_title

def deduplicate_text(text: str) -> str:
    """Remove duplicate lines and sections that may have been extracted twice"""
    lines = text.split('\n')
    seen_lines: Set[str] = set()
    unique_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        # Skip empty lines or lines we've seen
        if not line_stripped or line_stripped in seen_lines:
            continue
            
        # Add the original line with its spacing
        unique_lines.append(line)
        seen_lines.add(line_stripped)
    
    return '\n'.join(unique_lines)

def get_all_pages(limit=None, batch_size=50):
    """Get all wiki pages excluding special namespaces"""
    all_titles = []
    params = {
        "action": "query",
        "format": "json",
        "list": "allpages",
        "aplimit": batch_size,
        "apnamespace": 0  # Main namespace only
    }
    
    continuation = None
    page_count = 0
    
    print("Fetching all wiki pages...")
    
    while True:
        if continuation:
            params["apcontinue"] = continuation
            
        resp = requests.get(API, params=params).json()
        
        # Extract titles
        if "query" in resp and "allpages" in resp["query"]:
            batch_titles = [p["title"] for p in resp["query"]["allpages"] 
                          if not any(p["title"].startswith(prefix) for prefix in EXCLUDED_CATEGORIES)]
            all_titles.extend(batch_titles)
            page_count += len(batch_titles)
            
            print(f"Found {page_count} pages so far...")
            
            # Check if we have enough pages or if there are more
            if "continue" in resp and "apcontinue" in resp["continue"] and (limit is None or page_count < limit):
                continuation = resp["continue"]["apcontinue"]
            else:
                break
                
            # Be nice to the API
            time.sleep(0.5)
    
    print(f"Total pages found: {len(all_titles)}")
    return all_titles

def extract_infobox(soup: BeautifulSoup) -> Tuple[str, Dict[str, str]]:
    """Extract information from the infobox"""
    infobox_text = ""
    infobox_data = {}
    
    # Find the portable infobox
    infobox = soup.select_one('.portable-infobox')
    if not infobox:
        return infobox_text, infobox_data
    
    # Extract infobox title
    title_elem = infobox.select_one('.pi-title')
    if title_elem:
        title_text = title_elem.get_text().strip()
        infobox_text += f"{title_text}\n"
        infobox_data["title"] = title_text
    
    # Extract section headers
    for header in infobox.select('.pi-header'):
        header_text = header.get_text().strip()
        if header_text:
            infobox_text += f"\n== {header_text} ==\n\n"
            infobox_data[f"header_{header_text.lower().replace(' ', '_')}"] = header_text
    
    # Extract data items (label-value pairs)
    for item in infobox.select('.pi-item.pi-data'):
        label = item.select_one('.pi-data-label')
        value = item.select_one('.pi-data-value')
        
        if label and value:
            label_text = label.get_text().strip()
            value_text = value.get_text().strip()
            
            if label_text and value_text:
                infobox_text += f"{label_text}: {value_text}\n"
                infobox_data[label_text.lower().replace(' ', '_')] = value_text
    
    # Add a separator after the infobox
    infobox_text += "\n"
    
    return infobox_text, infobox_data

def extract_text_from_element(element: Tag) -> str:
    """Extract text from an HTML element, handling special cases"""
    if element.name in ['p', 'span', 'div', 'li']:
        return element.get_text().strip()
    elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        level = int(element.name[1])
        text = element.get_text().strip()
        # Create section headers with appropriate formatting
        return f"\n{'='*level} {text} {'='*level}\n"
    elif element.name == 'table':
        # Extract table data
        rows = []
        for row in element.select('tr'):
            cells = [cell.get_text().strip() for cell in row.find_all(['th', 'td'])]
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)
    elif element.name == 'ul' or element.name == 'ol':
        # Extract list items
        items = []
        for li in element.find_all('li', recursive=False):
            text = li.get_text().strip()
            if text:
                items.append(f"- {text}")
        return "\n".join(items)
    else:
        return ""

def get_page_content(title: str) -> Optional[str]:
    """Get the full content of a page including infobox and main text"""
    # URL encode the title
    encoded_title = quote(title.replace(' ', '_'))
    url = f"{BASE_URL}{encoded_title}"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch {title} (Status code: {response.status_code})")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check if this is a redirect page
        redirect_msg = soup.select_one('.redirectMsg')
        if redirect_msg:
            redirect_link = redirect_msg.select_one('a')
            if redirect_link:
                redirect_target = redirect_link.get('title')
                if redirect_target:
                    print(f"Following redirect from {title} to {redirect_target}")
                    return get_page_content(redirect_target)
        
        # Get the page content
        content_parts = []
        
        # 1. Start with the page title
        content_parts.append(f"{title}\n")
        
        # 2. Extract infobox content
        infobox_text, infobox_data = extract_infobox(soup)
        if infobox_text:
            content_parts.append(infobox_text)
        
        # 3. Get the main content
        content_div = soup.select_one('.mw-parser-output')
        if not content_div:
            print(f"Failed to find content for {title}")
            return None
        
        # Remove unwanted elements before processing
        for element in content_div.select('.reference, .mw-editsection, script, style, .navbox, .toc, .noprint, .error, .mw-empty-elt'):
            if element:
                element.decompose()
        
        # Extract text from main content elements we care about
        for element in content_div.find_all(['p', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'table']):
            # Skip elements already in the infobox
            if element.find_parent('.portable-infobox'):
                continue
                
            # Skip empty elements and certain sections
            if not element.get_text().strip():
                continue
                
            # Skip references and external links sections
            if element.name.startswith('h') and element.get_text().strip().lower() in ['references', 'notes', 'external links', 'see also']:
                break
            
            text = extract_text_from_element(element)
            if text:
                content_parts.append(text)
        
        # Clean up the text
        full_content = "\n".join(content_parts)
        
        # Remove reference numbers [1], [2], etc.
        full_content = re.sub(r'\[\d+\]', '', full_content)
        
        # Remove any HTML tags that might remain
        full_content = re.sub(r'<.*?>', '', full_content)
        
        # Normalize spacing
        full_content = re.sub(r'\n{3,}', '\n\n', full_content)
        
        # Deduplicate content
        full_content = deduplicate_text(full_content)
        
        return full_content
    
    except Exception as e:
        print(f"Error fetching {title}: {str(e)}")
        return None

def save_page_content(title: str, content: str) -> str:
    """Save a page's content to a file"""
    # Create a safe filename from the title
    safe_title = sanitize_filename(title)
    filename = os.path.join(OUTPUT_DIR, f"{safe_title}.txt")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Title: {title}\n\n")
        f.write(content)
    
    return filename

def append_to_mongodb_import(title: str, content: str) -> None:
    """Append a document to the MongoDB import file"""
    safe_title = sanitize_filename(title)
    
    # Create a document structure
    document = {
        "title": title,
        "content": content,
        "filename": f"{safe_title}.txt",
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "Game of Thrones Wiki",
        "url": f"{BASE_URL}{quote(title.replace(' ', '_'))}"
    }
    
    # Append to file
    with open(MONGODB_IMPORT_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(document) + "\n")

def create_json_metadata(titles, successful_titles):
    """Create a JSON file with metadata about all scraped pages"""
    metadata = {
        "total_attempted": len(titles),
        "total_successful": len(successful_titles),
        "pages": [{"title": title, "filename": f"{sanitize_filename(title)}.txt"} for title in successful_titles],
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    with open(os.path.join(OUTPUT_DIR, "metadata.json"), 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

def get_popular_character_titles():
    """Get a list of important character pages"""
    main_characters = [
        "Jon Snow", "Daenerys Targaryen", "Tyrion Lannister", 
        "Cersei Lannister", "Jaime Lannister", "Arya Stark",
        "Sansa Stark", "Bran Stark", "Eddard Stark", "Robb Stark",
        "Catelyn Stark", "Theon Greyjoy", "Joffrey Baratheon",
        "Robert Baratheon", "Stannis Baratheon", "Tywin Lannister",
        "Brienne of Tarth", "Petyr Baelish", "Samwell Tarly",
        "Davos Seaworth", "Sandor Clegane", "Gregor Clegane",
        "Tormund", "Gendry", "Melisandre", "Varys",
        "Grey Worm", "Missandei", "Bronn", "Podrick Payne",
        "Margaery Tyrell", "Olenna Tyrell", "Loras Tyrell",
        "Tommen Baratheon", "Myrcella Baratheon", "Ellaria Sand",
        "Oberyn Martell", "Ramsay Bolton", "Roose Bolton",
        "Lyanna Mormont", "Jorah Mormont", "Jeor Mormont",
        "Hodor", "Khal Drogo", "Viserys Targaryen", "Rickon Stark",
        "Osha", "Meera Reed", "Jojen Reed", "Walder Frey"
    ]
    return main_characters

def get_important_house_titles():
    """Get a list of important house pages"""
    main_houses = [
        "House Stark", "House Lannister", "House Targaryen",
        "House Baratheon", "House Greyjoy", "House Tully",
        "House Arryn", "House Tyrell", "House Martell",
        "House Bolton", "House Frey", "House Mormont",
        "House Umber", "House Karstark", "House Reed",
        "House Glover", "House Clegane", "House Tarly"
    ]
    return main_houses

def get_important_location_titles():
    """Get a list of important location pages"""
    main_locations = [
        "Westeros", "Essos", "King's Landing", "Winterfell", 
        "Dragonstone", "Casterly Rock", "Highgarden", "Dorne",
        "The Wall", "Castle Black", "The Eyrie", "Riverrun",
        "Iron Islands", "Braavos", "Meereen", "Valyria",
        "The North", "The Reach", "The Westerlands", "The Stormlands",
        "The Riverlands", "The Vale", "The Crownlands", "Harrenhal"
    ]
    return main_locations

def scrape_pages(titles, max_pages=None, batch_size=5, delay=0.5):
    """Scrape content from multiple pages with rate limiting"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Create or clear the MongoDB import file
    with open(MONGODB_IMPORT_FILE, 'w', encoding='utf-8') as f:
        pass  # Just create an empty file
    
    # Limit the number of pages if specified
    if max_pages and max_pages < len(titles):
        titles_to_process = titles[:max_pages]
        print(f"Processing {max_pages} pages out of {len(titles)} total pages")
    else:
        titles_to_process = titles
        print(f"Processing all {len(titles)} pages")
    
    successful_titles = []
    
    # Process titles in batches to avoid overwhelming the server
    total_batches = (len(titles_to_process) + batch_size - 1) // batch_size
    for i in range(0, len(titles_to_process), batch_size):
        batch = titles_to_process[i:i+batch_size]
        current_batch = i // batch_size + 1
        print(f"Processing batch {current_batch}/{total_batches} ({len(batch)} pages)...")
        
        for title in batch:
            print(f"Fetching content for {title}...")
            content = get_page_content(title)
            
            if content and len(content) > 100:  # Ensure we have substantial content
                filename = save_page_content(title, content)
                print(f"Saved {title} to {filename}")
                successful_titles.append(title)
                
                # Append to MongoDB import file
                append_to_mongodb_import(title, content)
            else:
                print(f"Insufficient content found for {title}")
            
            # Be nice to the server
            time.sleep(delay)
        
        # Create/update metadata after each batch
        create_json_metadata(titles_to_process, successful_titles)
        
        # Print progress
        success_rate = (len(successful_titles) / (current_batch * batch_size)) * 100 if current_batch * batch_size <= len(titles_to_process) else (len(successful_titles) / len(titles_to_process)) * 100
        print(f"Progress: {len(successful_titles)}/{len(titles_to_process)} pages processed ({success_rate:.1f}% success rate)")
    
    print(f"Successfully saved {len(successful_titles)} pages to {OUTPUT_DIR}/")
    return successful_titles

def create_mongodb_readme():
    """Create a README file with MongoDB import instructions"""
    readme = """# Game of Thrones Wiki Data for MongoDB

This directory contains scraped data from the Game of Thrones Wiki, ready for import into MongoDB.

## Files
- `mongodb_import.json`: JSON file in MongoDB import format (one document per line)
- Text files: Individual wiki pages in text format
- `metadata.json`: Information about the scraped data

## Importing to MongoDB

### Method 1: Using mongoimport (Command Line)
```bash
# Basic import
mongoimport --db gotChatbot --collection wikiPages --file assets/data/mongodb_import.json

# With options (drop existing collection, import as JSON)
mongoimport --db gotChatbot --collection wikiPages --drop --file assets/data/mongodb_import.json
```

### Method 2: Using PyMongo (Python)
```python
import pymongo
import json

# Connect to MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["gotChatbot"]
collection = db["wikiPages"]

# Drop existing collection if needed
collection.drop()

# Import data
with open('assets/data/mongodb_import.json', 'r') as f:
    for line in f:
        document = json.loads(line)
        collection.insert_one(document)

print(f"Imported {collection.count_documents({})} documents")

# Create indexes for better search performance
collection.create_index([("content", pymongo.TEXT), ("title", pymongo.TEXT)])
collection.create_index("title")
```

## Using the MongoDB Utils

The provided `mongo_utils.py` file contains a class to help interact with the Game of Thrones data:

```python
from mongo_utils import GOTChatbotDB

# Connect to the database
db = GOTChatbotDB()

# Search for documents
results = db.text_search("Stark family")
for doc in results:
    print(doc["title"])

# Get context for chatbot
context = db.create_chatbot_context("Who killed Joffrey?")
print(context)
```

## Chatbot Integration

The `chatbot.py` file provides a simple interface to query the database and generate responses.
In a real implementation, you would integrate with an LLM API to generate responses based on the context.
"""
    
    with open(os.path.join(OUTPUT_DIR, "MONGODB_README.md"), 'w', encoding='utf-8') as f:
        f.write(readme)

def load_existing_mongodb_titles():
    """Load titles already in MongoDB to avoid duplicates"""
    try:
        # Connect to MongoDB
        mongo = GOTMongoConnection()
        cursor = mongo.collection.find({}, {"title": 1})
        existing_titles = {doc["title"] for doc in cursor if "title" in doc}
        print(f"Found {len(existing_titles)} existing titles in MongoDB")
        mongo.close()
        return existing_titles
    except Exception as e:
        print(f"Error fetching existing titles from MongoDB: {str(e)}")
        print("Will use metadata.json instead")
        
        # Fall back to metadata.json
        metadata_path = os.path.join(OUTPUT_DIR, "metadata.json")
        existing_titles = set()
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    if "pages" in metadata:
                        for page in metadata["pages"]:
                            if "title" in page:
                                existing_titles.add(page["title"])
                print(f"Loaded {len(existing_titles)} existing titles from metadata.json")
            except Exception as e:
                print(f"Error loading metadata.json: {str(e)}")
        
        return existing_titles

def save_to_mongodb(title: str, content: str):
    """Save a page directly to MongoDB"""
    try:
        mongo = GOTMongoConnection()
        safe_title = sanitize_filename(title)
        
        # Create document
        document = {
            "title": title,
            "content": content,
            "filename": f"{safe_title}.txt",
            "scraped_at": datetime.utcnow(),
            "source": "Game of Thrones Wiki",
            "url": f"{BASE_URL}{quote(title.replace(' ', '_'))}"
        }
        
        # Insert or update in MongoDB
        result = mongo.collection.update_one(
            {"title": title}, 
            {"$set": document},
            upsert=True
        )
        
        if result.modified_count > 0:
            print(f"Updated {title} in MongoDB")
        elif result.upserted_id:
            print(f"Inserted {title} into MongoDB")
        else:
            print(f"No changes made for {title}")
            
        mongo.close()
        return True
        
    except Exception as e:
        print(f"Error saving to MongoDB: {str(e)}")
        return False

def scrape_with_mongodb_check(titles, max_pages=None, batch_size=5, delay=1.0):
    """Scrape pages while checking for existing entries in MongoDB"""
    # Load existing MongoDB titles
    existing_titles = load_existing_mongodb_titles()
    
    # Filter to only new titles
    new_titles = [t for t in titles if t not in existing_titles]
    print(f"Found {len(new_titles)} new titles to scrape")
    
    # Limit the number to scrape if specified
    if max_pages and max_pages < len(new_titles):
        titles_to_scrape = new_titles[:max_pages]
        print(f"Will scrape {len(titles_to_scrape)} of them")
    else:
        titles_to_scrape = new_titles
        
    # Scrape and save to both MongoDB and files
    successful_titles = []
    
    # Process titles in batches
    total_batches = (len(titles_to_scrape) + batch_size - 1) // batch_size
    for i in range(0, len(titles_to_scrape), batch_size):
        batch = titles_to_scrape[i:i+batch_size]
        current_batch = i // batch_size + 1
        print(f"Processing batch {current_batch}/{total_batches} ({len(batch)} pages)...")
        
        for title in batch:
            print(f"Fetching content for {title}...")
            content = get_page_content(title)
            
            if content and len(content) > 100:  # Ensure we have substantial content
                # Save to file
                filename = save_page_content(title, content)
                print(f"Saved {title} to {filename}")
                
                # Save to MongoDB
                saved_to_db = save_to_mongodb(title, content)
                if saved_to_db:
                    print(f"Saved {title} to MongoDB")
                
                # Append to MongoDB import file
                append_to_mongodb_import(title, content)
                
                successful_titles.append(title)
            else:
                print(f"Insufficient content found for {title}")
            
            # Be nice to the server
            time.sleep(delay)
        
        # Create/update metadata after each batch
        create_json_metadata(titles_to_scrape, successful_titles)
    
    return successful_titles

def main():
    parser = argparse.ArgumentParser(description="Game of Thrones Wiki Scraper with MongoDB Integration")
    parser.add_argument(
        "--max-pages", 
        type=int, 
        default=20, 
        help="Maximum number of new pages to scrape (default: 20)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=5, 
        help="Number of pages to process in a batch (default: 5)"
    )
    parser.add_argument(
        "--delay", 
        type=float, 
        default=1.0, 
        help="Delay between page requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--no-limit", 
        action="store_true", 
        help="Remove the page limit and scrape as many new pages as possible"
    )
    parser.add_argument(
        "--important-only", 
        action="store_true", 
        help="Only scrape important character/house/location pages"
    )
    
    args = parser.parse_args()
    
    print("Game of Thrones Wiki Scraper with MongoDB Integration")
    print("---------------------------------------------------")
    
    # Ensure directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # First, try to scrape important pages that we know are valuable
    important_titles = []
    important_titles.extend(get_popular_character_titles())
    important_titles.extend(get_important_house_titles())
    important_titles.extend(get_important_location_titles())
    
    print(f"Collected {len(important_titles)} important page titles")
    
    # Determine max pages
    max_pages = None if args.no_limit else args.max_pages
    
    # Scrape important titles
    print(f"Scraping important pages (max: {max_pages if max_pages else 'unlimited'})...")
    successful_important = scrape_with_mongodb_check(
        important_titles, 
        max_pages=max_pages,
        batch_size=args.batch_size,
        delay=args.delay
    )
    
    # If we're not limited to important pages and there are still pages to scrape
    successful_general = []
    if not args.important_only and (max_pages is None or len(successful_important) < max_pages):
        # Calculate remaining pages to scrape
        remaining_pages = None if max_pages is None else max_pages - len(successful_important)
        
        if remaining_pages is None or remaining_pages > 0:
            # Get additional pages
            print("\nFetching general wiki pages...")
            all_titles = get_all_pages(limit=1000)  # Limit to 1000 for efficiency
            
            # Scrape general pages
            print(f"Scraping general pages (max: {remaining_pages if remaining_pages else 'unlimited'})...")
            successful_general = scrape_with_mongodb_check(
                all_titles,
                max_pages=remaining_pages,
                batch_size=args.batch_size,
                delay=args.delay
            )
    
    # Combine successful titles
    all_successful = successful_important + successful_general
    
    print("\nSummary:")
    print(f"- Successfully scraped {len(all_successful)} pages total")
    print(f"- {len(successful_important)} important pages")
    print(f"- {len(successful_general)} general pages")
    
    print("\nData is now stored in:")
    print(f"1. MongoDB database 'gotChatbot', collection 'wikiPages'")
    print(f"2. Text files in {OUTPUT_DIR}")
    print(f"3. MongoDB import file: {MONGODB_IMPORT_FILE}")

if __name__ == "__main__":
    main()