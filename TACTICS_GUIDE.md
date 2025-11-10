# 🎯 Advanced Tactics for Hip-Hop Promotion

Complete implementation guide for each tactic mentioned in your requirements.

## 1. 🎵 Spotify Playlist Owner Reverse Lookup

### **Tactic**
Pull Spotify playlist pages → extract "owner" link → get profile → find contact info

### **Implementation**
```python
from app.scrapers.spotify_scraper import SpotifyPlaylistScraper

scraper = SpotifyPlaylistScraper()

# Method 1: Search by genre
results = scraper.scrape(genre="hip-hop", min_followers=500, limit=100)

# Method 2: Get specific playlist
playlist = scraper.scrape_playlist_by_id("37i9dQZF1DXcBWIGoYBM5M")

# Method 3: Get curator profile
curator = scraper.get_curator_profile("spotify_username")
```

### **Data Extracted**
- Curator username & display name
- Profile URL
- Follower count
- All public playlists
- Total reach (sum of all playlist followers)

---

## 2. 📺 YouTube About Email Extractor

### **Tactic**
Parse YouTube channel "About" pages for business email (often hidden in HTML)

### **Implementation**
```python
from app.scrapers.youtube_scraper import YouTubeChannelScraper

scraper = YouTubeChannelScraper()

# Method 1: Search for channels
channels = scraper.scrape(query="hip hop playlist", max_results=50)

# Method 2: Scrape specific channel
channel = scraper.scrape_channel("UC_channel_id_here")

# Method 3: Scrape About page directly (bypasses API limits)
contact_info = scraper.scrape_channel_about_page("UC_channel_id_here")
```

### **Email Location Patterns**
1. **About page "View Email" button** → `mailto:` link
2. **Channel description** → Plain text email
3. **ytInitialData JSON** → Business email field
4. **Links to external website** → Scrape that too

---

## 3. 📷 Instagram Contact Button Harvester

### **Tactic**
For business profiles, Instagram exposes email/contact button via public HTML

### **Implementation**
```python
from app.scrapers.instagram_scraper import InstagramScraper

scraper = InstagramScraper()

# Method 1: Scrape from hashtag
profiles = scraper.scrape(hashtag="hiphopplaylist", max_posts=100)

# Method 2: Scrape specific profile
profile = scraper.scrape_profile("username")

# Method 3: Find music curators
curators = scraper.find_music_curators(keywords=["playlist", "curator", "submissions"])
```

### **Data Extracted**
- Business email (if public)
- External URL (often Linktree → more contacts)
- Bio emails
- Phone numbers
- Booking keywords

---

## 4. 🔍 Playlist Follower Signal Mining

### **Tactic**
Scrape top followers of target playlists → identify curators who also create playlists

### **Implementation**
```python
from app.scrapers.spotify_scraper import SpotifyPlaylistScraper

scraper = SpotifyPlaylistScraper()

# Find similar curators via playlist analysis
similar_curators = scraper.find_similar_curators(playlist_id="37i9dQZF1DXcBWIGoYBM5M")

# Get curator's other playlists
curator_data = scraper.get_curator_profile("username")
all_playlists = curator_data['playlists']

# Rank by centrality (followers of followers)
```

### **Advanced Graph Mining**
Use NetworkX to build curator network:
```python
import networkx as nx

G = nx.Graph()
# Add curators as nodes, shared followers as edges
# Find high-centrality nodes = influential curators
```

---

## 5. 📰 Press Byline Crawl for Publicist Credits

### **Tactic**
Search `site:complex.com "publicist" OR "press"` to harvest publicist names

### **Implementation**
```python
from app.scrapers.web_scraper import WebContactScraper
import requests

# Use Google Custom Search API or SerpAPI
query = 'site:complex.com "publicist" OR "press" hip-hop'

# Or manual scraping
scraper = WebContactScraper()
articles = [
    "https://www.complex.com/music/artist-interview",
    # ... more URLs
]

for url in articles:
    data = scraper.scrape_press_kit(url)
    publicist_contacts = data['publicist_contacts']
```

### **Target Sites**
- Complex.com
- HipHopDX.com
- Pitchfork.com
- XXL.com
- The Source
- AllHipHop.com

---

## 6. 🎤 Conference Speaker Contact Lists

### **Tactic**
Scrape SXSW/A3C/ESSENCE speaker pages for agency/publicist emails

### **Implementation**
```python
# Target URLs
conference_urls = [
    "https://schedule.sxsw.com/speakers",  # SXSW
    "https://a3cfestival.com/speakers",     # A3C
    # Add more...
]

scraper = WebContactScraper()
for url in conference_urls:
    result = scraper.scrape(url)
    emails = result['emails']
```

### **Conferences to Target**
- **SXSW** - March, Austin TX
- **A3C Festival** - October, Atlanta
- **ESSENCE Festival** - July, New Orleans
- **Rolling Loud** - Multiple cities
- **Breakout Music Festival**
- **ASCAP "I Create Music" Expo**

---

## 7. 🎬 Music Licensing Agency Scraping

### **Tactic**
Scrape sync agencies' team pages for A&R / Music Supervisor emails

### **Implementation**
```python
sync_agencies = [
    "https://www.audionetwork.com/about-us/team",
    "https://www.extrememusic.com/contact",
    "https://www.musicbed.com/about/team",
]

for url in sync_agencies:
    team_data = scraper.scrape(url)
    supervisors = [m for m in team_data['team_members'] if 'supervisor' in m.get('role', '').lower()]
```

### **Top Sync Agencies**
- Audio Network
- Extreme Music
- Musicbed
- Jingle Punks
- The Music Playground
- Position Music

---

## 8. 🎼 Manager Credits from Metadata

### **Tactic**
Use MusicBrainz/Discogs API to pull "manager" credits on releases

### **Implementation**
```python
import requests

# MusicBrainz API
artist_mbid = "artist-id-here"
response = requests.get(f"https://musicbrainz.org/ws/2/artist/{artist_mbid}?inc=relations&fmt=json")
data = response.json()

# Find "manager" relationships
relations = data.get('relations', [])
managers = [r for r in relations if r.get('type') == 'manager']
```

### **Data Sources**
- [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)
- [Discogs API](https://www.discogs.com/developers)
- AllMusic.com credits pages
- Genius.com song annotations

---

## 9. 💼 LinkedIn Recruiter Search (Scripted)

### **Tactic**
Target LinkedIn queries for titles (A&R, Manager, Publicist) + hip-hop

### **Implementation**
```bash
# Search queries to use:
- "A&R" + "Hip-Hop" + "Current company"
- "Music Publicist" + "Rap"
- "Artist Manager" + "Hip-Hop"
- "Booking Agent" + "Rap"
```

### **Tools**
- **Phantombuster** - Automated LinkedIn scraper
- **LinkedIn Sales Navigator** - Advanced search (paid)
- **Apollo.io** - LinkedIn data enrichment
- Manual: Copy names → enrich with Hunter.io

---

## 10. 🐦 Twitter/X Bio Email Scraping

### **Tactic**
Search bios for "bookings", "press", "manager" keywords → extract emails

### **Implementation**
```python
import tweepy

# Twitter API v2
client = tweepy.Client(bearer_token="your_token")

# Search for users
query = "bookings OR press OR manager hip-hop"
users = client.search_users(query=query, max_results=100)

for user in users:
    bio = user.description
    emails = extract_emails(bio)
```

### **Search Patterns**
- "bookings: email@domain.com"
- "press inquiries: ..."
- "management: ..."
- "📧 email@domain.com"

---

## 11. 🌐 Artist/Label Team Pages

### **Tactic**
Crawl artist official sites for "Team" pages listing manager/publicist contacts

### **Implementation**
```python
artist_sites = [
    "https://artistname.com/team",
    "https://artistname.com/about",
    "https://artistname.com/contact",
]

for url in artist_sites:
    team_data = scraper.scrape(url)
    team_members = team_data['team_members']
    # Filter for managers/publicists
```

---

## 12. 📄 Press Kit PDF Search

### **Tactic**
Search for "artist + press kit PDF" and parse metadata

### **Implementation**
```python
# Google search: "hip hop artist press kit filetype:pdf"
# Then parse PDFs:

from pdfminer.high_level import extract_text

def extract_contacts_from_pdf(pdf_path):
    text = extract_text(pdf_path)
    emails = extract_emails(text)
    return emails
```

---

## 13. 🎪 Venue Roster Scraping

### **Tactic**
Scrape venue booking pages → get manager emails of acts they book

### **Implementation**
```python
venue_url = "https://venue.com/calendar"
venue_data = scraper.scrape_venue_website(venue_url)

# Extract artist lineup
# Find artist websites
# Scrape artist manager contacts
```

---

## 🚀 Complete Automation Workflow

### **Full Pipeline Script**

```python
#!/usr/bin/env python3
"""
Complete automated contact discovery pipeline
"""

from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
from app.scrapers.youtube_scraper import YouTubeChannelScraper
from app.scrapers.instagram_scraper import InstagramScraper
from app.scrapers.web_scraper import WebContactScraper
from app.utils.email_validator import EmailValidator
from app.utils.scoring import ContactScorer

def full_discovery_pipeline():
    """Run all tactics and compile results"""
    
    all_contacts = []
    
    # 1. Spotify playlists
    spotify = SpotifyPlaylistScraper()
    spotify_results = spotify.scrape(genre="hip-hop", min_followers=1000)
    all_contacts.extend(spotify_results)
    
    # 2. YouTube channels
    youtube = YouTubeChannelScraper()
    youtube_results = youtube.find_hip_hop_curators(min_subscribers=10000)
    all_contacts.extend(youtube_results)
    
    # 3. Instagram curators
    instagram = InstagramScraper()
    insta_results = instagram.find_music_curators()
    all_contacts.extend(insta_results)
    
    # 4. Conference speakers
    conferences = [
        "https://schedule.sxsw.com/speakers",
        "https://a3cfestival.com/speakers"
    ]
    web_scraper = WebContactScraper()
    for url in conferences:
        result = web_scraper.scrape(url)
        if result:
            all_contacts.extend(result['emails'])
    
    # 5. Verify all emails
    validator = EmailValidator()
    verified_contacts = []
    
    for contact in all_contacts:
        email = contact.get('email')
        if email:
            validation = validator.advanced_validate(email)
            if validation['valid'] and validation['deliverable']:
                contact['verified'] = True
                verified_contacts.append(contact)
    
    # 6. Score contacts
    scorer = ContactScorer()
    for contact in verified_contacts:
        score = scorer.calculate_priority_score(
            follower_count=contact.get('follower_count', 0),
            contact_type=contact.get('type', 'playlist_curator')
        )
        contact['priority_score'] = score
    
    # 7. Sort by score
    verified_contacts.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
    
    # 8. Export top 500
    import csv
    with open('exports/all_contacts_verified.csv', 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'email', 'type', 'score', 'followers'])
        writer.writeheader()
        writer.writerows(verified_contacts[:500])
    
    print(f"✅ Discovered {len(verified_contacts)} verified contacts")
    print(f"📊 Top score: {verified_contacts[0].get('priority_score', 0):.1f}")
    print(f"💾 Exported to: exports/all_contacts_verified.csv")

if __name__ == "__main__":
    full_discovery_pipeline()
```

---

## 💡 Pro Tips

### **Maximize Hit Rate**
1. **Cross-reference**: Find same contact on multiple platforms
2. **Timing**: Contact curators right after they update playlists
3. **Relevance**: Only pitch to curators in your specific subgenre
4. **Personalization**: Mention specific playlist names

### **Avoid Spam Traps**
1. Always use double opt-in for new lists
2. Remove hard bounces immediately
3. Monitor engagement rates
4. Use reputable email service (SendGrid, Mailgun)
5. Keep daily send volume under 200 initially

### **Data Quality**
- Re-verify emails every 90 days
- Remove contacts inactive > 6 months
- Track response rates per source
- A/B test subject lines

---

**Ready to implement? Start with the Quick Start guide!**
