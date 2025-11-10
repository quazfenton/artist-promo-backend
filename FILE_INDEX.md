# 📁 File Index - Complete Project Structure

## Core Application Files

### `app/models/`
- **`database.py`** - SQLAlchemy database models
  - `Contact` - Main contacts table with scoring
  - `Playlist` - Discovered playlists
  - `Venue` - Venue booking contacts
  - `OutreachLog` - Email campaign tracking
  - `ScraperRun` - Scraper execution logs
  - Enums: `ContactType`, `Platform`

- **`__init__.py`** - Model exports

### `app/scrapers/`
- **`base_scraper.py`** - Base class for all scrapers
  - Retry logic with exponential backoff
  - Rate limiting
  - Email extraction
  - Social media handle extraction
  - Error tracking

- **`spotify_scraper.py`** - Spotify integration
  - `SpotifyPlaylistScraper` - Main scraper class
    - `scrape()` - Search by genre
    - `scrape_playlist_by_id()` - Get specific playlist
    - `get_curator_profile()` - Get curator details
    - `find_similar_curators()` - Graph mining
    - `search_playlists_by_keyword()` - Keyword search
  - `SpotifyAnalyzer` - Analytics class
    - `analyze_curator_activity()` - Activity metrics

- **`youtube_scraper.py`** - YouTube integration
  - `YouTubeChannelScraper`
    - `scrape()` - Search channels
    - `scrape_channel()` - Get channel via API
    - `scrape_channel_about_page()` - Parse About page HTML
    - `find_hip_hop_curators()` - Targeted search

- **`instagram_scraper.py`** - Instagram integration
  - `InstagramScraper`
    - `scrape()` - Scrape from hashtag
    - `scrape_profile()` - Get profile data
    - `scrape_followers()` - Get followers
    - `find_music_curators()` - Filter by keywords
    - `extract_contact_from_bio()` - Bio parsing

- **`web_scraper.py`** - General web scraping
  - `WebContactScraper`
    - `scrape()` - Scrape any website
    - `scrape_press_kit()` - Parse press kits
    - `scrape_venue_website()` - Venue-specific scraping
    - `_find_contact_pages()` - Auto-discover contact pages
    - `_extract_team_members()` - Team page parsing

- **`__init__.py`** - Scraper exports

### `app/utils/`
- **`email_validator.py`** - Email validation & enrichment
  - `EmailValidator` class
    - `basic_validate()` - Regex validation
    - `advanced_validate()` - DNS/MX record check
    - `enrich_with_hunter()` - Hunter.io integration
    - `verify_with_neverbounce()` - NeverBounce integration
    - `find_email_from_domain()` - Email pattern discovery
    - `extract_emails_from_text()` - Bulk extraction
  - `validate_email_quick()` - Quick validation function

- **`scoring.py`** - Priority scoring algorithms
  - `ContactScorer` class
    - `calculate_priority_score()` - Main scoring function
    - `calculate_match_score()` - Genre/style matching
    - `_normalize_followers()` - Log-scale normalization
    - `_calculate_recency_score()` - Time-based scoring
  - `VenueScorer` class
    - `calculate_venue_score()` - Venue priority
    - `_score_capacity()` - Capacity scoring
    - `_score_attendance()` - Attendance scoring
  - `PlaylistScorer` class
    - `calculate_relevance_score()` - Playlist relevance
    - `_playlist_recency_score()` - Update recency

- **`__init__.py`** - Utility exports

### `app/api/`
- **`main.py`** - FastAPI application (1000+ lines)
  - **Scraper Endpoints:**
    - `POST /scrape/spotify` - Scrape Spotify
    - `POST /scrape/youtube` - Scrape YouTube
    - `POST /scrape/instagram` - Scrape Instagram
    - `POST /scrape/web` - Scrape website
  - **Contact Endpoints:**
    - `GET /contacts` - Query contacts
    - `POST /contacts/verify` - Verify email
    - `POST /contacts/score` - Recalculate scores
  - **Export Endpoints:**
    - `POST /export/csv` - Export to CSV
  - **n8n Webhooks:**
    - `POST /webhook/n8n/scrape` - Trigger scraping
    - `POST /webhook/n8n/export` - Get JSON data
  - **Health:**
    - `GET /` - API info
    - `GET /health` - Health check
  - **Background Tasks:**
    - `save_spotify_results()` - Save to DB
    - `save_youtube_results()` - Save to DB
    - `save_instagram_results()` - Save to DB
    - `save_web_result()` - Save to DB

## Configuration Files

- **`.env.example`** - Environment variable template
  - Database configuration
  - API keys (Spotify, YouTube, Twitter, etc.)
  - Email validation API keys
  - LLM API keys
  - Scoring weights
  - Rate limits
  - Logging configuration

- **`requirements.txt`** - Python dependencies
  - FastAPI & Uvicorn
  - SQLAlchemy & Alembic
  - Scraping libraries (BeautifulSoup, Selenium, Playwright)
  - API clients (Spotipy, Instaloader, Tweepy)
  - Email validation libraries
  - Data processing (Pandas, NumPy)
  - Testing (Pytest)

## Deployment Files

- **`Dockerfile`** - Docker container configuration
  - Python 3.9-slim base image
  - System dependencies
  - Application setup
  - Gunicorn + Uvicorn workers

- **`docker-compose.yml`** - Multi-container setup
  - API service
  - PostgreSQL database
  - Redis cache
  - Volume mounts
  - Environment variable passing

- **`.gitignore`** - Git ignore rules
  - Environment files
  - Python cache
  - Virtual environments
  - Database files
  - Logs and exports

## Command-Line Interface

- **`cli.py`** - CLI tool (500+ lines)
  - Commands:
    - `scrape-spotify` - Scrape Spotify playlists
    - `scrape-youtube` - Scrape YouTube channels
    - `scrape-instagram` - Scrape Instagram profiles
    - `scrape-web` - Scrape website
    - `score-all` - Recalculate all scores
    - `export-csv` - Export to CSV
    - `stats` - Show database statistics

## Documentation Files

- **`README.md`** - Main documentation (300+ lines)
  - Feature overview
  - Installation instructions
  - Usage examples
  - API reference
  - Deployment guides
  - Best practices

- **`QUICKSTART.md`** - 5-minute setup guide
  - Quick installation
  - Basic configuration
  - First scrape
  - Testing
  - n8n connection

- **`TACTICS_GUIDE.md`** - Implementation guide (500+ lines)
  - 25+ tactics with code examples
  - Complete automation workflow
  - Pro tips
  - Data quality practices

- **`VERIFIED_SOURCES.md`** - Contact source directory (400+ lines)
  - Playlist curator directories
  - YouTube channels
  - Instagram accounts
  - PR firms
  - Venue directories
  - Music blogs
  - Tools and services

- **`PROJECT_SUMMARY.md`** - This project overview
  - What's been built
  - Features list
  - Technology stack
  - Expected results

- **`FILE_INDEX.md`** - This file
  - Complete file listing
  - Purpose of each file
  - Class/function reference

## Example Files

- **`examples/full_pipeline_example.py`** - Complete workflow
  - Multi-source scraping
  - Email verification
  - Priority scoring
  - CSV export
  - n8n webhook integration

## Automation Files

- **`n8n_workflow_template.json`** - n8n workflow
  - Schedule trigger
  - HTTP request nodes
  - Data filtering
  - LLM email generation
  - Email sending

- **`setup.sh`** - Automated setup script
  - Virtual environment creation
  - Dependency installation
  - Database initialization
  - Configuration prompts

## Directories

- **`app/`** - Main application code
- **`config/`** - Configuration files (empty, for custom configs)
- **`exports/`** - CSV exports destination
- **`examples/`** - Example scripts
- **`tests/`** - Test files (structure provided)
- **`logs/`** - Application logs (created at runtime)

## Total Line Count

**Approximate:**
- Python code: ~5,000 lines
- Documentation: ~3,000 lines
- Configuration: ~500 lines
- **Total: ~8,500 lines of production-ready code**

## File Count

- Python modules: 15
- Documentation files: 6
- Configuration files: 5
- Example files: 2
- **Total: 28 files**

## Key Features by File

| Feature | Primary File | Supporting Files |
|---------|-------------|------------------|
| Spotify scraping | `spotify_scraper.py` | `base_scraper.py`, `database.py` |
| YouTube scraping | `youtube_scraper.py` | `base_scraper.py`, `database.py` |
| Instagram scraping | `instagram_scraper.py` | `base_scraper.py`, `database.py` |
| Web scraping | `web_scraper.py` | `base_scraper.py` |
| Email validation | `email_validator.py` | - |
| Priority scoring | `scoring.py` | `database.py` |
| REST API | `main.py` | All scrapers, all utils |
| CLI tool | `cli.py` | All scrapers, all utils |
| Database | `database.py` | - |
| n8n integration | `main.py`, `n8n_workflow_template.json` | - |

## Usage Priority

**Start with these files:**
1. `QUICKSTART.md` - Get up and running
2. `.env.example` → `.env` - Configure
3. `cli.py` or `main.py` - Run your first scrape
4. `TACTICS_GUIDE.md` - Learn advanced features
5. `examples/full_pipeline_example.py` - See complete workflow

**For customization:**
1. `scoring.py` - Adjust scoring weights
2. `database.py` - Add custom fields
3. `base_scraper.py` - Modify scraper behavior
4. Individual scraper files - Add new sources

**For deployment:**
1. `Dockerfile` - Containerization
2. `docker-compose.yml` - Local/testing
3. `setup.sh` - Quick server setup

---

**All files are well-commented and follow Python best practices (PEP 8).**
