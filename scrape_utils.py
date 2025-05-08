import os
import json
import re
import time
from typing import List, Dict, Set, Any, Optional
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

# Constants
API = "https://gameofthrones.fandom.com/api.php"
BASE_URL = "https://gameofthrones.fandom.com/wiki/"
OUTPUT_DIR = "assets/data"
EXCLUDED_CATEGORIES = ["File:", "Template:", "Category:", "Special:", "Help:", "Portal:"]
MONGODB_IMPORT_FILE = os.path.join(OUTPUT_DIR, "mongodb_import.json")

def sanitize_filename(title: str) -> str:
    """Create a safe filename from a title"""
    # Replace problematic characters with underscore
    safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().replace(' ', '_')
    return safe_title

def load_existing_titles() -> Set[str]:
    """Load already scraped titles from metadata.json"""
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

def get_all_pages(limit=None, batch_size=50) -> List[str]:
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

def get_popular_character_titles() -> List[str]:
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

def get_important_house_titles() -> List[str]:
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

def get_important_location_titles() -> List[str]:
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

def get_important_event_titles() -> List[str]:
    """Get a list of important event pages"""
    main_events = [
        "Robert's Rebellion", "War of the Five Kings", "Battle of the Blackwater",
        "Red Wedding", "Purple Wedding", "Battle of Castle Black",
        "Hardhome", "Battle of the Bastards", "Great War",
        "Long Night", "Battle of Winterfell", "Greyjoy Rebellion",
        "Massacre at Hardhome", "Destruction of the Great Sept of Baelor"
    ]
    return main_events

def extract_infobox(soup: BeautifulSoup) -> str:
    """Extract information from the infobox"""
    infobox_data = {}
    
    # Find the portable infobox
    infobox = soup.select_one('.portable-infobox')
    if not infobox:
        return ""
    
    # Extract infobox title
    title_elem = infobox.select_one('.pi-title')
    if title_elem:
        infobox_data["infobox_title"] = title_elem.get_text().strip()
    
    # Extract data groups
    for group in infobox.select('.pi-item'):
        # Handle data items with label/value pairs
        label = group.select_one('.pi-data-label')
        value = group.select_one('.pi-data-value')
        
        if label and value:
            label_text = label.get_text().strip()
            value_text = value.get_text().strip()
            infobox_data[label_text] = value_text
        
        # Handle header items
        header = group.select_one('.pi-header')
        if header:
            header_text = header.get_text().strip()
            infobox_data[f"Header: {header_text}"] = ""
    
    # Format as text
    formatted_infobox = []
    for k, v in infobox_data.items():
        if k == "infobox_title":
            formatted_infobox.append(f"{v}")
        elif k.startswith("Header:"):
            formatted_infobox.append(f"\n== {k.replace('Header: ', '')} ==\n")
        else:
            formatted_infobox.append(f"{k}: {v}")
    
    return "\n".join(formatted_infobox)

def deduplicate_text(text: str) -> str:
    """Remove duplicate lines and sections that may have been extracted twice"""
    lines = text.split('\n')
    seen_lines = set()
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
        infobox_text = extract_infobox(soup)
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
            
            # Extract text based on element type
            if element.name in ['p', 'span', 'div', 'li']:
                text = element.get_text().strip()
                if text:
                    content_parts.append(text)
            elif element.name.startswith('h'):
                level = int(element.name[1])
                text = element.get_text().strip()
                if text:
                    content_parts.append(f"\n{'='*level} {text} {'='*level}\n")
            elif element.name == 'table':
                # Extract table data
                table_text = []
                for row in element.select('tr'):
                    cells = [cell.get_text().strip() for cell in row.find_all(['th', 'td'])]
                    if cells:
                        table_text.append(" | ".join(cells))
                if table_text:
                    content_parts.append("\n".join(table_text))
            elif element.name in ['ul', 'ol']:
                # Extract list items
                items = []
                for li in element.find_all('li', recursive=False):
                    text = li.get_text().strip()
                    if text:
                        items.append(f"- {text}")
                if items:
                    content_parts.append("\n".join(items))
        
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

def scrape_additional_pages(max_pages=10, batch_size=5, delay=1.0):
    """Scrape additional pages without duplicating existing content"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load existing titles
    existing_titles = load_existing_titles()
    print(f"Found {len(existing_titles)} existing scraped titles")
    
    # Ensure MongoDB import file exists
    if not os.path.exists(MONGODB_IMPORT_FILE):
        with open(MONGODB_IMPORT_FILE, 'w', encoding='utf-8') as f:
            pass  # Create empty file
    
    # Get important titles that we want to prioritize
    important_titles = []
    important_titles.extend(get_popular_character_titles())
    important_titles.extend(get_important_house_titles())
    important_titles.extend(get_important_location_titles())
    important_titles.extend(get_important_event_titles())
    print(f"Collected {len(important_titles)} important titles to check")
    
    # Filter out titles we already have
    new_important_titles = [t for t in important_titles if t not in existing_titles]
    print(f"Found {len(new_important_titles)} new important titles to scrape")
    
    # Scrape important titles that we don't have yet
    successful_titles = []
    
    if new_important_titles:
        # Limit to max_pages if specified
        titles_to_process = new_important_titles[:max_pages] if max_pages else new_important_titles
        print(f"Will scrape {len(titles_to_process)} new important titles")
        
        # Process titles in batches
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
                    
                    # Update existing titles set to avoid duplicates in future runs
                    existing_titles.add(title)
                else:
                    print(f"Insufficient content found for {title}")
                
                # Be nice to the server
                time.sleep(delay)
    else:
        print("No new important titles to scrape.")
    
    # If we haven't reached max_pages yet, get more general pages
    if max_pages and len(successful_titles) < max_pages:
        remaining_pages = max_pages - len(successful_titles)
        print(f"Scraping {remaining_pages} additional general pages...")
        
        # Get all wiki pages
        all_titles = get_all_pages(limit=1000)  # Limit to 1000 for efficiency
        
        # Filter out titles we already have
        new_titles = [t for t in all_titles if t not in existing_titles]
        print(f"Found {len(new_titles)} new general titles")
        
        # Process remaining titles up to max_pages
        titles_to_process = new_titles[:remaining_pages]
        
        # Process titles in batches
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
                    
                    # Update existing titles set to avoid duplicates in future runs
                    existing_titles.add(title)
                else:
                    print(f"Insufficient content found for {title}")
                
                # Be nice to the server
                time.sleep(delay)
    
    # Update metadata to include all titles
    all_titles = list(existing_titles)
    create_json_metadata(all_titles, all_titles)
    
    print(f"\nSummary:")
    print(f"- Successfully scraped {len(successful_titles)} new pages")
    print(f"- Total pages in database: {len(existing_titles)}")
    
    return successful_titles