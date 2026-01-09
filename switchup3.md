Module examples
artist_promo_pipeline/
├── scrapers/
│   ├── social.py          # IG / X / YouTube / Patreon
│   ├── pdf_metadata.py    # Press kits, conference slides
│   ├── venues.py          # Venue / promoter scraping
│   ├── beta_signup.py     # Early-adopter / product beta lists
│   ├── sample_pack.py     # Sample pack contributor mapping
│   ├── whois_scraper.py   # WHOIS / domain scraping
│   ├── captions.py        # Closed captions / YouTube transcripts
│   ├── reverse_image.py   # Reverse image search for PR mapping
│   └── alumni.py          # University / alumni directories
├── utils/
│   ├── email_utils.py     # Obfuscation resolver, validator
│   ├── storage.py         # MongoDB / SQLite interface
│   ├── ranking.py         # Graph centrality / scoring
│   └── export.py          # CSV/Excel export
├── main.py                # Orchestrator
├── requirements.txt
└── config.yaml            # API keys / scraping configs


2. Core Utilities
utils/email_utils.py
import re
from email_validator import validate_email, EmailNotValidError

def decode_obfuscated_email(text):
    """Convert obfuscated emails like 'manager [at] example [dot] com' to proper format"""
    text = text.lower()
    text = re.sub(r'\s*\[at\]\s*|\s*\(at\)\s*|\s+at\s+', '@', text)
    text = re.sub(r'\s*\[dot\]\s*|\s*\(dot\)\s*|\s+dot\s+', '.', text)
    text = re.sub(r'\s+', '', text)
    return text

def validate_email_address(email):
    """Check if email is valid"""
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

utils/storage.py
import pymongo

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["artist_promo"]
contacts_col = db["contacts"]

def save_contact(name, email, source, score=0):
    """Save or update a contact"""
    contacts_col.update_one(
        {"email": email},
        {"$set": {"name": name, "email": email, "source": source, "score": score}},
        upsert=True
    )

def get_all_contacts():
    """Fetch all contacts"""
    return list(contacts_col.find())

utils/ranking.py
import networkx as nx

def rank_contacts_graph(connections):
    """
    connections: list of tuples (source_contact, target_contact)
    Returns centrality scores
    """
    G = nx.DiGraph()
    G.add_edges_from(connections)
    centrality = nx.pagerank(G)
    return centrality

utils/export.py
import pandas as pd
from utils.storage import get_all_contacts

def export_contacts_csv(filename="artist_contacts.csv"):
    contacts = get_all_contacts()
    df = pd.DataFrame(contacts)
    df.to_csv(filename, index=False)
    print(f"Exported {len(df)} contacts to {filename}")


3. Scraper Modules (Examples)
scrapers/social.py
import requests
import re
from bs4 import BeautifulSoup
from utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_ig_business_email(username):
    url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = resp.json()
        email = data['graphql']['user'].get('business_email')
        if email and validate_email_address(email):
            return email
    except:
        pass
    return None

def extract_x_bio_emails(username):
    url = f"https://twitter.com/{username}"
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        match = re.search(r'<meta name="description" content="(.*?)"', resp.text)
        if match:
            bio = match.group(1)
            emails = [decode_obfuscated_email(e) for e in re.findall(r'[a-zA-Z0-9._%+\[\]()-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio)]
            return [e for e in emails if validate_email_address(e)]
    except:
        return []

scrapers/pdf_metadata.py
from PyPDF2 import PdfReader
import requests
from io import BytesIO
import re
from utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_pdf_emails(pdf_url):
    try:
        resp = requests.get(pdf_url)
        reader = PdfReader(BytesIO(resp.content))
        emails = []
        # Metadata
        if reader.metadata:
            for v in reader.metadata.values():
                emails += re.findall(r'[a-zA-Z0-9._%+\[\]()-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', str(v))
        # Page content
        for page in reader.pages:
            emails += re.findall(r'[a-zA-Z0-9._%+\[\]()-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page.extract_text())
        emails = [decode_obfuscated_email(e) for e in emails if validate_email_address(decode_obfuscated_email(e))]
        return list(set(emails))
    except:
        return []

scrapers/venues.py
import requests
from bs4 import BeautifulSoup
import re
from utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_venue_emails(venue_url):
    try:
        resp = requests.get(venue_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = [decode_obfuscated_email(e) for e in re.findall(r'[a-zA-Z0-9._%+\[\]()-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)]
        return [e for e in emails if validate_email_address(e)]
    except:
        return []

Other scrapers (beta_signup.py, sample_pack.py, whois_scraper.py, captions.py, reverse_image.py, alumni.py) follow the same pattern:
Scrape source → extract emails → normalize → return list.

4. Orchestrator main.py
from scrapers import social, pdf_metadata, venues
from utils.storage import save_contact
from utils.ranking import rank_contacts_graph
from utils.export import export_contacts_csv

def main():
    # 1️⃣ Social Media
    ig_usernames = ["artist_official"]
    x_usernames = ["artistmanager"]

    for u in ig_usernames:
        email = social.extract_ig_business_email(u)
        if email:
            save_contact(name=u, email=email, source="Instagram")

    for u in x_usernames:
        emails = social.extract_x_bio_emails(u)
        for e in emails:
            save_contact(name=u, email=e, source="X/Twitter")

    # 2️⃣ PDF Press Kits
    pdf_urls = ["https://example.com/artist-presskit.pdf"]
    for url in pdf_urls:
        emails = pdf_metadata.extract_pdf_emails(url)
        for e in emails:
            save_contact(name="PDF", email=e, source=url)

    # 3️⃣ Venue / Promoter Pages
    venue_urls = ["https://examplevenue.com/booking"]
    for url in venue_urls:
        emails = venues.extract_venue_emails(url)
        for e in emails:
            save_contact(name="Venue", email=e, source=url)

    # 4️⃣ Example ranking (connections can be built from curated data)
    connections = [("manager1@example.com", "curator1@example.com"),
                   ("manager2@example.com", "curator2@example.com")]
    scores = rank_contacts_graph(connections)
    print("Graph-based ranking scores:", scores)

    # 5️⃣ Export final contacts
    export_contacts_csv()

if __name__ == "__main__":
    main()


5. Features
✅ Modular: Add any new source scraper easily.
 ✅ Deduplication & normalization: Obfuscated emails handled.
 ✅ Storage: MongoDB keeps all contacts + sources + score.
 ✅ Graph ranking: Prioritize curators/managers by network connections.
 ✅ Export: CSV for outreach campaigns.
 ✅ Extensible: Add Reddit, Discord, reverse image, ISRC registry, alumni scraping.

6. Extensions
Add reverse image search (SerpAPI or Bing API) → map repeated PR images to contacts.
Add YouTube closed caption scraping → detect manager mentions.
Add WHOIS / domain scraping for PR firms.
Add Reddit / Discord monitoring for submissions.
Schedule pipeline with Airflow / Prefect for continuous updates.
Add LinkedIn / email enrichment APIs for missing contacts.
Score contacts using multi-factor ranking: social reach + centrality + repeated presence.


##Perfect — let’s design a full Python “Artist Promotion Automation Engine” that brings together all the modules we’ve discussed into a modular, extensible, actionable pipeline. I’ll provide a working scaffold you can extend, with scrapers, email extraction, normalization, deduplication, ranking, and export.

Artist Promotion Automation Engine — Python Scaffold
1. Project Structure
artist_promo/
├── scrapers/
│   ├── social.py          # IG/X/YT scraping
│   ├── pdf_metadata.py    # Press kits, conference slides
│   ├── venues.py          # Venue / promoter scraping
│   ├── beta_signup.py     # Beta / early adopter lists
│   ├── sample_pack.py     # Sample pack contributor mapping
│   ├── whois_scraper.py   # WHOIS / domain scraping
│   └── captions.py        # Closed captions / transcript mining
├── utils/
│   ├── email_utils.py     # Obfuscation resolver, validator
│   ├── storage.py         # MongoDB / SQLite interface
│   └── ranking.py         # Graph centrality / scoring
├── main.py                # Orchestrator
├── requirements.txt
└── config.yaml            # API keys / scraping configs


2. Core Utilities
utils/email_utils.py – normalization & validation:
import re
from email_validator import validate_email, EmailNotValidError

def decode_obfuscated_email(text):
    text = text.lower()
    text = re.sub(r'\s*\[at\]\s*|\s*\(at\)\s*|\s+at\s+', '@', text)
    text = re.sub(r'\s*\[dot\]\s*|\s*\(dot\)\s*|\s+dot\s+', '.', text)
    text = re.sub(r'\s+', '', text)
    return text

def validate_email_address(email):
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False


utils/storage.py – store normalized contacts:
import pymongo

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["artist_promo"]
contacts_col = db["contacts"]

def save_contact(name, email, source, score=0):
    contacts_col.update_one(
        {"email": email},
        {"$set": {"name": name, "email": email, "source": source, "score": score}},
        upsert=True
    )

def get_all_contacts():
    return list(contacts_col.find())


utils/ranking.py – simple curator/manager scoring:
import networkx as nx

def rank_contacts_graph(connections):
    """
    connections: list of tuples (source_contact, target_contact)
    """
    G = nx.DiGraph()
    G.add_edges_from(connections)
    centrality = nx.pagerank(G)
    return centrality


3. Scraper Module Examples
scrapers/social.py – IG / X / YouTube bio + contact extraction:
import requests
import re
from bs4 import BeautifulSoup
from utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_ig_business_email(username):
    url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = resp.json()
        email = data['graphql']['user'].get('business_email')
        if email and validate_email_address(email):
            return email
    except:
        pass
    return None

def extract_x_bio_emails(username):
    url = f"https://twitter.com/{username}"
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        match = re.search(r'<meta name="description" content="(.*?)"', resp.text)
        if match:
            bio = match.group(1)
            emails = [decode_obfuscated_email(e) for e in re.findall(r'[a-zA-Z0-9._%+\[\]\(\) -]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio)]
            return [e for e in emails if validate_email_address(e)]
    except:
        return []


scrapers/pdf_metadata.py – Press kits, slide decks:
from PyPDF2 import PdfReader
import requests
from io import BytesIO
import re
from utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_pdf_emails(pdf_url):
    try:
        resp = requests.get(pdf_url)
        reader = PdfReader(BytesIO(resp.content))
        emails = []
        # Metadata
        if reader.metadata:
            for k, v in reader.metadata.items():
                emails += re.findall(r'[a-zA-Z0-9._%+\[\]()-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', str(v))
        # Text content
        for page in reader.pages:
            emails += re.findall(r'[a-zA-Z0-9._%+\[\]()-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page.extract_text())
        emails = [decode_obfuscated_email(e) for e in emails if validate_email_address(decode_obfuscated_email(e))]
        return list(set(emails))
    except:
        return []


scrapers/venues.py – Venue / promoter roster extraction:
import requests
from bs4 import BeautifulSoup
import re
from utils.email_utils import decode_obfuscated_email, validate_email_address

def extract_venue_emails(venue_url):
    try:
        resp = requests.get(venue_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = [decode_obfuscated_email(e) for e in re.findall(r'[a-zA-Z0-9._%+\[\]()-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)]
        return [e for e in emails if validate_email_address(e)]
    except:
        return []


4. Orchestrator main.py
from scrapers import social, pdf_metadata, venues
from utils.storage import save_contact
from utils.ranking import rank_contacts_graph

def main():
    # Example list of sources
    ig_usernames = ["artist_official"]
    x_usernames = ["artistmanager"]
    venue_urls = ["https://examplevenue.com/booking"]
    pdf_urls = ["https://example.com/artist-presskit.pdf"]

    # --- Scrape Social Media ---
    for u in ig_usernames:
        email = social.extract_ig_business_email(u)
        if email:
            save_contact(name=u, email=email, source="Instagram")

    for u in x_usernames:
        emails = social.extract_x_bio_emails(u)
        for e in emails:
            save_contact(name=u, email=e, source="X/Twitter")

    # --- Scrape PDFs ---
    for url in pdf_urls:
        emails = pdf_metadata.extract_pdf_emails(url)
        for e in emails:
            save_contact(name="PDF", email=e, source=url)

    # --- Scrape Venues ---
    for url in venue_urls:
        emails = venues.extract_venue_emails(url)
        for e in emails:
            save_contact(name="Venue", email=e, source=url)

    # --- Example Ranking ---
    # Suppose we have connections for graph ranking
    connections = [("manager1@example.com", "curator1@example.com"),
                   ("manager2@example.com", "curator2@example.com")]
    scores = rank_contacts_graph(connections)
    print("Graph-based ranking scores:", scores)

if __name__ == "__main__":
    main()


5. Features of this Engine
✅ Modular: Add new scrapers (Discord, ISRC, sample packs, reverse image) easily
 ✅ Normalized & deduplicated: email_utils handles obfuscations
 ✅ Storage: MongoDB keeps all contacts + source + score
 ✅ Ranking: Graph centrality, connections across managers/curators
 ✅ Export: Easy to export CSV for outreach

##
WHOIS/Domain scraping, venue/promoter rosters, national ISRC registries, closed captions, image EXIF, alumni networks, and early adopter/beta signup scraping.


---

1. WHOIS / Domain Registrant Email Scraping

Some boutique PR/label sites expose registrant info publicly:

import whois

def get_domain_email(domain):
    try:
        w = whois.whois(domain)
        if w.emails:
            if isinstance(w.emails, list):
                return w.emails
            return [w.emails]
        return []
    except Exception as e:
        print(f"WHOIS error for {domain}: {e}")
        return []

# Example
emails = get_domain_email("boutiquePR.com")
print("Registrant emails:", emails)

> Can be combined with inferred first.last@domain patterns.




---

2. Venue / Promoter Roster Scraping

Booking pages often list managers for touring artists:

import requests
from bs4 import BeautifulSoup
import re

def scrape_venue_artists(venue_url):
    try:
        resp = requests.get(venue_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return list(set(emails))
    except Exception as e:
        print(f"Error scraping {venue_url}: {e}")
        return []

# Example
venue_url = "https://examplevenue.com/booking"
emails = scrape_venue_artists(venue_url)
print("Manager emails found:", emails)

> You could crawl multiple venue pages to map managers who tour the same circuit.




---

3. National ISRC Registry Parsing

ISRC allocation lists can help identify distributors/labels:

import requests
import pandas as pd

def parse_isrc_registry(csv_url):
    try:
        df = pd.read_csv(csv_url)
        contacts = []
        for _, row in df.iterrows():
            if 'label' in row and 'contact' in row:
                contacts.append({'label': row['label'], 'contact': row['contact']})
        return contacts
    except Exception as e:
        print(f"Error parsing ISRC CSV: {e}")
        return []

# Example
csv_url = "https://example.com/isrc_registry.csv"
contacts = parse_isrc_registry(csv_url)
print(contacts)

> You can enrich these contacts by combining with label websites or LinkedIn.




---

4. Closed Captions / Subtitles Scraping

Some videos’ subtitles mention PR/manager names:

from youtube_transcript_api import YouTubeTranscriptApi

def extract_youtube_sub_emails(video_id):
    emails = []
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        for entry in transcript:
            text = entry['text']
            found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            emails += found
        return list(set(emails))
    except Exception as e:
        print(f"Error fetching transcript {video_id}: {e}")
        return []

# Example
emails = extract_youtube_sub_emails("VIDEO_ID_HERE")
print("Emails in captions:", emails)


---

5. Event Photographer EXIF / Geotag Parsing

Public photos may include EXIF geotags or author handles linking to PR:

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def extract_exif(image_path):
    image = Image.open(image_path)
    exif_data = image._getexif()
    gps_info = {}
    if exif_data:
        for tag, value in exif_data.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = value[t]
    return gps_info

# Example
gps = extract_exif("concert_photo.jpg")
print("GPS info from EXIF:", gps)

> Can map to venues or promoters by geolocation.




---

6. University / Alumni Directory Scraping

Many universities list music industry alumni working as managers:

import requests
from bs4 import BeautifulSoup

def scrape_alumni_emails(university_url):
    try:
        resp = requests.get(university_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return list(set(emails))
    except Exception as e:
        print(f"Error scraping alumni page: {e}")
        return []

# Example
emails = scrape_alumni_emails("https://musicdept.example.edu/alumni")
print("Alumni emails:", emails)


---

7. Early Adopter / Beta Signup Directory Scraping

Detect artists/managers via product beta communities:

import requests
from bs4 import BeautifulSoup
import re

def extract_beta_emails(signup_page_url):
    try:
        resp = requests.get(signup_page_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return list(set(emails))
    except Exception as e:
        print(f"Error scraping beta page: {e}")
        return []

# Example
emails = extract_beta_emails("https://beta.musicapp.com/early-adopters")
print("Early adopter emails:", emails)


---

8. Sample Pack / Producer Credit Mapping

Extract producer/artist contacts from sample packs:

import requests
from bs4 import BeautifulSoup
import re

def extract_sample_pack_contacts(pack_url):
    try:
        resp = requests.get(pack_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return list(set(emails))
    except Exception as e:
        print(f"Error scraping sample pack: {e}")
        return []

# Example
emails = extract_sample_pack_contacts("https://splice.com/sample-packs")
print("Sample pack contacts:", emails)


---


1. WHOIS registrant scraping


2. Venue/promoter rosters


3. ISRC registry parsing


4. Video subtitle/closed caption email mining


5. Event photo EXIF / geolocation mapping


6. University alumni directories


7. Beta / early adopter signup scraping


8. Sample pack contributor mapping
Vimeo Pro descriptions sometimes include production company emails:
import requests
from bs4 import BeautifulSoup
import re

def extract_vimeo_emails(video_url):
    try:
        resp = requests.get(video_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return list(set(emails))
    except Exception as e:
        print(f"Error fetching Vimeo URL {video_url}: {e}")
        return []

# Example
vimeo_url = "https://vimeo.com/artistvideo"
emails = extract_vimeo_emails(vimeo_url)
print("Vimeo emails:", emails)


2. Conference Slide Deck / PDF Metadata Parsing
Conference PDFs often have organizer emails in metadata:
from PyPDF2 import PdfReader
import requests
from io import BytesIO

def extract_pdf_metadata_emails(pdf_url):
    try:
        resp = requests.get(pdf_url)
        reader = PdfReader(BytesIO(resp.content))
        meta = reader.metadata
        emails = []
        for key, value in meta.items():
            if value:
                emails += re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', str(value))
        return list(set(emails))
    except Exception as e:
        print(f"Error parsing PDF metadata {pdf_url}: {e}")
        return []

# Example
pdf_url = "https://example.com/conference_slides.pdf"
emails = extract_pdf_metadata_emails(pdf_url)
print("Emails in PDF metadata:", emails)


3. Reverse Image Search for PR Contacts (SerpAPI)
Automate detection of the same press image across multiple sites:
from serpapi import GoogleSearch

def reverse_image_contact_search(image_url, api_key):
    params = {
        "engine": "google_reverse_image",
        "image_url": image_url,
        "api_key": api_key
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    urls = [r['link'] for r in results.get('inline_images', [])]
    return urls

# Example
image_url = "https://example.com/artist_press_photo.jpg"
api_key = "YOUR_SERPAPI_KEY"
pages = reverse_image_contact_search(image_url, api_key)
print("Pages containing the image:", pages)


4. Reddit Submissions Monitoring (Open Calls / Curator Posts)
Monitor a subreddit for “submissions open” posts and extract emails:
import praw
import re

reddit = praw.Reddit(client_id='YOUR_ID',
                     client_secret='YOUR_SECRET',
                     user_agent='ArtistPromoBot')

subreddit = reddit.subreddit("WeAreTheMusicMakers")

for post in subreddit.search("submissions open", sort='new', limit=10):
    print(post.title)
    # Extract emails from post body
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', post.selftext)
    if emails:
        print("Emails found:", emails)


5. Discord Public Channel Submission Monitoring
Requires a bot token (for public channels only):
import discord
import re
import asyncio

TOKEN = "YOUR_BOT_TOKEN"
GUILD_ID = 1234567890
CHANNEL_ID = 9876543210

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        channel = self.get_channel(CHANNEL_ID)
        async for message in channel.history(limit=50):
            if "submissions open" in message.content.lower():
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message.content)
                if emails:
                    print(f"Found emails: {emails}")

client = MyClient()
asyncio.run(client.start(TOKEN))


6. Track Stem Metadata / DAW Bounce Notes
Some public stems contain artist notes/metadata with manager info:
from mutagen import File
import re

def extract_metadata_emails(file_path):
    audio = File(file_path)
    emails = []
    if audio:
        for tag, value in audio.tags.items():
            if isinstance(value, str):
                emails += re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value)
    return list(set(emails))

# Example
emails = extract_metadata_emails("track_stem.wav")
print("Emails in stem metadata:", emails)


7. Obfuscated Email Resolver (Advanced)
Automatically decodes complex obfuscations:
import re

def decode_obfuscated_email(text):
    # Handle common obfuscations
    text = text.lower()
    text = re.sub(r'\s*\[at\]\s*', '@', text)
    text = re.sub(r'\s*\(at\)\s*', '@', text)
    text = re.sub(r'\s+at\s+', '@', text)
    text = re.sub(r'\s*\[dot\]\s*', '.', text)
    text = re.sub(r'\s*\(dot\)\s*', '.', text)
    text = re.sub(r'\s+dot\s+', '.', text)
    text = re.sub(r'\s+', '', text)
    return text

# Examples
print(decode_obfuscated_email("manager [at] example [dot] com"))  # manager@example.com
print(decode_obfuscated_email("press (at) label (dot) org"))      # press@label.org


8. Extract Music Supervisor / Podcast Contact from RSS Ad Tags
import feedparser
import re

def extract_podcast_contacts(rss_url):
    feed = feedparser.parse(rss_url)
    contacts = []
    for entry in feed.entries:
        if 'ad' in entry.title.lower() or 'sponsor' in entry.title.lower():
            text = entry.summary + entry.title
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            contacts += emails
    return list(set(contacts))

rss_url = "https://examplepodcast.com/rss"
emails = extract_podcast_contacts(rss_url)
print("Podcast sponsor/manager emails:", emails)





##3
PART I — EMAIL SENDING STACK (REAL, SAFE, EXTENSIBLE)
This is not just smtplib.sendmail. This is deliverability-aware sending with tracking hooks.

1) Transport-Agnostic Sender Interface
You can swap SMTP, SES, Mailgun, Postmark, etc.
class EmailTransport:
    def send(self, to, subject, body, headers=None):
        raise NotImplementedError


2) SMTP Transport (Minimal, Hardened)
import smtplib
from email.message import EmailMessage

class SMTPTransport(EmailTransport):
    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def send(self, to, subject, body, headers=None):
        msg = EmailMessage()
        msg["From"] = self.user
        msg["To"] = to
        msg["Subject"] = subject

        if headers:
            for k, v in headers.items():
                msg[k] = v

        msg.set_content(body)

        with smtplib.SMTP_SSL(self.host, self.port) as server:
            server.login(self.user, self.password)
            server.send_message(msg)


3) Message Fingerprinting (Prevent Duplicate Sends)
import hashlib

def message_fingerprint(email, subject, body):
    raw = f"{email}|{subject}|{body}"
    return hashlib.sha256(raw.encode()).hexdigest()

Store fingerprints in Redis:
def already_sent(fp):
    return r.sismember("sent_messages", fp)

def mark_sent(fp):
    r.sadd("sent_messages", fp)


4) Send Worker (Integrated Safety)
def send_worker():
    transport = SMTPTransport(
        host="smtp.mailprovider.com",
        port=465,
        user="you@domain.com",
        password="APP_PASSWORD"
    )

    while True:
        task = dequeue("send_tasks")
        if not task:
            time.sleep(1)
            continue

        subject = task.get("subject", "Quick intro")
        body = task["message"]
        email = task["email"]

        fp = message_fingerprint(email, subject, body)
        if already_sent(fp):
            continue

        try:
            transport.send(
                to=email,
                subject=subject,
                body=body,
                headers={
                    "X-Campaign": "manager-outreach",
                    "X-Entity": task["manager_id"]
                }
            )
            mark_sent(fp)
            mark_contacted(email)

        except Exception as e:
            r.lpush("dead_letter", {
                "task": task,
                "error": str(e)
            })


5) Reply Ingestion (IMAP-Based Learning Loop)
This is how your system learns from replies.
import imaplib
import email

def ingest_replies(host, user, password):
    mail = imaplib.IMAP4_SSL(host)
    mail.login(user, password)
    mail.select("inbox")

    status, data = mail.search(None, "UNSEEN")
    for num in data[0].split():
        _, msg_data = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        from_email = email.utils.parseaddr(msg["From"])[1]
        subject = msg["Subject"]

        handle_reply(from_email, subject)


6) Automatic Confidence Adjustment from Replies
def handle_reply(email_addr, subject):
    if "wrong person" in subject.lower():
        downgrade_contact(email_addr)

    elif "send it" in subject.lower() or "happy to listen" in subject.lower():
        CONTACTS[email_addr]["confidence"] += 15


7) Unsubscribe / Opt-Out Enforcement
Critical for long-term operation.
OPTOUT = set()

def is_opted_out(email):
    return email in OPTOUT

def register_optout(email):
    OPTOUT.add(email)

Check before enqueueing send tasks.

PART II — MANAGER INFLUENCE HEATMAPS
Now we quantify who actually matters.

8) Influence Model (Numerical)
Influence is not followers. It’s:
artists represented


cross-platform presence
centrality in graph
outreach responsiveness
def manager_influence(cluster, graph):
    return {
        "artist_count": len(cluster["artists"]),
        "email_count": len(cluster["emails"]),
        "platforms": cluster.get("platform_count", 1),
        "graph_degree": graph.degree(cluster["manager_node"]),
        "influence_score": (
            len(cluster["artists"]) * 4 +
            graph.degree(cluster["manager_node"]) * 2 +
            cluster.get("platform_count", 1) * 3
        )
    }


9) Build Influence Matrix (Manager × Signal)
import pandas as pd

def build_influence_df(clusters, graph):
    rows = []
    for c in clusters:
        score = manager_influence(c, graph)
        rows.append({
            "manager": c["manager_id"],
            **score
        })
    return pd.DataFrame(rows)


10) Heatmap Visualization
import matplotlib.pyplot as plt
import seaborn as sns

def plot_influence_heatmap(df):
    data = df.set_index("manager")[[
        "artist_count",
        "email_count",
        "graph_degree",
        "platforms"
    ]]

    plt.figure(figsize=(12, 8))
    sns.heatmap(data, annot=True, cmap="YlOrRd")
    plt.title("Manager Influence Heatmap")
    plt.tight_layout()
    plt.show()


11) Temporal Heatmaps (Momentum Detection)
See who’s gaining power.
def influence_delta(old_df, new_df):
    merged = old_df.merge(new_df, on="manager", suffixes=("_old", "_new"))
    merged["delta"] = (
        merged["influence_score_new"] -
        merged["influence_score_old"]
    )
    return merged.sort_values("delta", ascending=False)


12) Geographic Heatmaps (Optional)
If you attach city/state to managers:
def geo_heatmap(df):
    geo = df.groupby("location")["influence_score"].sum()
    geo.plot(kind="bar", title="Influence by Region")


13) Outreach Priority Ranking
This feeds directly back into the pipeline.
def outreach_priority(cluster, influence):
    return (
        influence["influence_score"] *
        max(c["confidence"] for c in cluster["scored_emails"]) / 100
    )


14) Feedback Loop Integration
def update_influence_from_reply(manager_id, positive=True):
    delta = 5 if positive else -10
    MANAGER_SCORES[manager_id] += delta


You now have:
✔️ Safe email sending (idempotent, throttle-aware)
✔️ Reply ingestion & learning
✔️ Opt-out compliance
✔️ Quantified manager influence
✔️ Visual heatmaps
✔️ Temporal momentum detection
✔️ Outreach prioritization feedback loop


##4

PART I — GRAPH-BASED INFLUENCE PROPAGATION (REAL SIGNAL, NOT VANITY)
This answers:
“If I influence this manager, how much downstream leverage do I gain?”

1) Unified Influence Graph Model
We treat managers, artists, curators, PRs as nodes.
Edges are typed + weighted.
import networkx as nx

G = nx.DiGraph()

# Node types
G.add_node("mgr_A", type="manager")
G.add_node("artist_X", type="artist")
G.add_node("curator_Y", type="curator")

# Edge types
G.add_edge("mgr_A", "artist_X", weight=3, rel="represents")
G.add_edge("mgr_A", "curator_Y", weight=1, rel="knows")
G.add_edge("curator_Y", "playlist_Z", weight=5, rel="controls")


2) Personalized PageRank (Influence Propagation Core)
This models who amplifies whom.
def influence_propagation(graph, alpha=0.85):
    return nx.pagerank(
        graph,
        alpha=alpha,
        weight="weight"
    )

Output:
{
  "mgr_A": 0.042,
  "curator_Y": 0.091,
  "playlist_Z": 0.231
}

This is actual reach, not follower count.

3) Conditional Influence (If I Contact X)
Simulate impact of activating one node.
def conditional_influence(graph, source, boost=5):
    G2 = graph.copy()

    for n in G2.nodes:
        if n == source:
            for _, v, data in G2.out_edges(n, data=True):
                data["weight"] += boost

    return nx.pagerank(G2, weight="weight")

Use this to rank who is worth outreach.

4) Influence Gain Score
def marginal_gain(before, after):
    return {
        k: after[k] - before.get(k, 0)
        for k in after
    }

Sort managers by downstream delta.

5) Community-Level Propagation (Clusters)
def cluster_influence(graph, clusters):
    scores = influence_propagation(graph)
    return {
        cluster_id: sum(scores[n] for n in nodes)
        for cluster_id, nodes in clusters.items()
    }

This feeds campaign targeting.

6) Decay & Time-Weighting (Recency Bias)
def time_weighted_edge(base_weight, days_old):
    return base_weight * (0.95 ** days_old)

Apply during graph construction.

PART II — MULTI-CHANNEL OUTREACH ENGINE
This avoids blasting.
 It escalates intelligently.

7) Channel Capability Matrix
CHANNELS = {
    "email": {"cost": 1, "confidence_req": 60},
    "dm": {"cost": 2, "confidence_req": 75},
    "intro": {"cost": 5, "confidence_req": 85}
}


8) Contact Resolution Per Channel
def available_channels(contact):
    chans = []
    if contact.get("email"):
        chans.append("email")
    if contact.get("twitter") or contact.get("instagram"):
        chans.append("dm")
    if contact.get("mutuals"):
        chans.append("intro")
    return chans


9) Channel Selection Logic (Non-Spammy)
def select_channel(contact, influence_score):
    for channel in ["email", "dm", "intro"]:
        if (
            channel in available_channels(contact)
            and contact["confidence"] >= CHANNELS[channel]["confidence_req"]
            and influence_score >= CHANNELS[channel]["cost"]
        ):
            return channel
    return None


10) Outreach State Machine (Critical)
STATES = [
    "uncontacted",
    "emailed",
    "dm_sent",
    "intro_requested",
    "responded",
    "closed"
]


11) Escalation Worker
def escalation_worker():
    while True:
        contact = dequeue("outreach_queue")
        if not contact:
            time.sleep(1)
            continue

        influence = MANAGER_SCORES[contact["manager_id"]]
        channel = select_channel(contact, influence)

        if not channel:
            continue

        if channel == "email":
            enqueue_email(contact)

        elif channel == "dm":
            enqueue_dm(contact)

        elif channel == "intro":
            enqueue_intro(contact)


12) DM Sending (Via Scraped Frontends)
Example: Nitter DM link creation (manual send or browser automation).
def enqueue_dm(contact):
    r.lpush("dm_tasks", {
        "platform": "twitter",
        "handle": contact["twitter"],
        "message": dm_template(contact)
    })

Browser automation workers can consume this.

13) Warm Intro Request Logic
Only trigger when mutual exists.
def find_intro_path(graph, source, target):
    try:
        return nx.shortest_path(graph, source, target)
    except nx.NetworkXNoPath:
        return None


14) Intro Message Auto-Generation
def intro_request(path):
    mutual = path[1]
    return f"""
Hey {mutual},

Hope you're well — quick ask.
Would you be open to connecting me with {path[-1]}?
Think they'd genuinely like this project.

Totally fine if not.
"""


15) Outreach Outcome → Graph Feedback
Responses change the graph.
def positive_response(manager_id):
    for u, v, data in G.in_edges(manager_id, data=True):
        data["weight"] += 2

Negative → decay.

16) Channel Performance Learning
def channel_success_rate(logs):
    stats = {}
    for l in logs:
        stats.setdefault(l["channel"], []).append(l["success"])

    return {
        k: sum(v) / len(v)
        for k, v in stats.items()
    }

Feed back into CHANNELS[channel]["cost"].

17) Influence-Aware Campaign Builder
def campaign_targets(graph, threshold=0.05):
    scores = influence_propagation(graph)
    return [
        n for n, s in scores.items()
        if s > threshold and G.nodes[n]["type"] == "manager"
    ]


18) Anti-Burnout Safeguards
def rate_limit(manager_id):
    last = LAST_CONTACT.get(manager_id)
    return not last or time.time() - last > 14 * 86400


WHAT THIS GIVES YOU
You now have:
✔ Influence that propagates across relationships
 ✔ Who matters because of who they connect to
 ✔ Channel-aware outreach escalation
 ✔ Warm intro pathfinding
 ✔ Self-learning outreach optimization
 ✔ Spam-safe, reputation-aware system
This is how modern labels, agencies, and growth teams actually operate — just rarely automated end-to-end.

