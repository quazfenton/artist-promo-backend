# 🎤 Hip-Hop Artist Promotion Backend

A comprehensive, serverless-ready Python backend for automating music promotion outreach. Integrates with n8n for workflow automation.

## 🚀 Features

### **Scraping Modules**
1. **Spotify Playlist Curator Scraper** - Find playlist owners, follower counts, and curator profiles
2. **YouTube Channel Email Extractor** - Extract business emails from About pages
3. **Instagram Contact Harvester** - Scrape business profiles for contact buttons/emails
4. **Web Contact Scraper** - Extract emails from team pages, press kits, and contact pages
5. **Venue Website Scraper** - Get booking contacts from venue sites

### **Contact Management**
- Advanced email validation (DNS, deliverability, role-based detection)
- Email enrichment via Hunter.io and NeverBounce
- Priority scoring algorithm (follower count, recency, engagement, LLM quality)
- Genre/style matching for relevance
- De-duplication and verification tracking

### **Export & Integration**
- CSV export with custom filters
- n8n webhook endpoints
- RESTful API for external integrations
- Background task processing

## 📦 Installation

### Prerequisites
- Python 3.9+
- PostgreSQL or SQLite
- Redis (optional, for background tasks)

### Setup

```bash
# Clone the repository
git clone <your-repo>
cd artist-promo-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### Environment Variables

Get API keys from:
- **Spotify**: https://developer.spotify.com/dashboard
- **YouTube**: https://console.cloud.google.com/apis/credentials
- **Hunter.io**: https://hunter.io/api
- **NeverBounce**: https://neverbounce.com/

## 🎯 Usage

### Run the API Server

```bash
# Development
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

# Production (with Gunicorn)
gunicorn app.api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### API Endpoints

#### Scraping Endpoints

**Scrape Spotify Playlists**
```bash
POST /scrape/spotify
{
  "scraper_type": "spotify",
  "genre": "hip-hop",
  "min_followers": 500,
  "max_results": 50
}
```

**Scrape YouTube Channels**
```bash
POST /scrape/youtube
{
  "scraper_type": "youtube",
  "query": "hip hop playlist curator",
  "max_results": 50
}
```

**Scrape Instagram Profiles**
```bash
POST /scrape/instagram
{
  "scraper_type": "instagram",
  "url": "https://instagram.com/username"
}
```

**Scrape Website**
```bash
POST /scrape/web
{
  "scraper_type": "web",
  "url": "https://example.com/contact"
}
```

#### Contact Endpoints

**Get Contacts**
```bash
GET /contacts?contact_type=playlist_curator&min_score=50&limit=100
```

**Verify Email**
```bash
POST /contacts/verify?email=curator@example.com
```

**Recalculate Scores**
```bash
POST /contacts/score
```

**Export to CSV**
```bash
POST /export/csv
{
  "contact_type": "playlist_curator",
  "min_score": 60,
  "limit": 500
}
```

### n8n Integration

#### Webhook Endpoints

**n8n Scrape Trigger**
```bash
POST /webhook/n8n/scrape
{
  "action": "scrape_spotify",
  "params": {
    "genre": "hip-hop",
    "min_followers": 1000
  }
}
```

**n8n Export Trigger**
```bash
POST /webhook/n8n/export
{
  "contact_type": "playlist_curator",
  "min_score": 70,
  "limit": 100
}
```

### n8n Workflow Setup

1. **Create HTTP Request Node**
   - Method: POST
   - URL: `http://your-api:8000/webhook/n8n/scrape`
   - Body: JSON with action and params

2. **Add Schedule Trigger** (optional)
   - Run daily/weekly to refresh contacts

3. **Add Data Processing Node**
   - Filter results, format emails

4. **Add Email/CRM Integration**
   - Send to Gmail, SendGrid, HubSpot, etc.

## 📊 Database Schema

### Contacts Table
- `id` - Primary key
- `full_name` - Contact name
- `email` - Email address
- `contact_type` - playlist_curator, publicist, manager, ar_rep, etc.
- `follower_count` - Social media followers
- `priority_score` - Calculated priority (0-100)
- `verified` - Email verification status
- `source_platform` - Where contact was found
- `genres` - JSON array of genres

### Playlists Table
- `id` - Primary key
- `platform_id` - Spotify/Apple Music ID
- `name` - Playlist name
- `follower_count` - Number of followers
- `owner_username` - Curator username
- `relevance_score` - Match score for artist

### Venues Table
- `id` - Primary key
- `name` - Venue name
- `city` - Location
- `booking_email` - Booking contact
- `capacity` - Venue size
- `venue_score` - Priority score

## 🧮 Scoring Algorithm

**Priority Score Formula:**
```
Score = 0.4*(Followers normalized) + 
        0.3*(Recency factor) + 
        0.2*(Engagement rate) +
        0.1*(LLM Quality)
```

**Normalization:**
- Followers use log scale (1K→30, 10K→40, 100K→60, 1M→100)
- Recency: last 7 days=100, 30 days=80, 60 days=60, etc.
- Type multipliers: A&R=1.2x, Manager=1.15x, Publicist=1.1x

## 🔧 Advanced Features

### Custom Scraper Example

```python
from app.scrapers.base_scraper import BaseScraper

class CustomScraper(BaseScraper):
    def __init__(self):
        super().__init__("custom_scraper")
    
    def scrape(self, url):
        response = self.fetch_page(url)
        soup = self.parse_html(response.text)
        
        # Your scraping logic
        emails = self.extract_emails(soup.get_text())
        
        result = {
            "url": url,
            "emails": emails
        }
        
        self.save_result(result)
        return self.get_results()
```

### Email Validation Example

```python
from app.utils.email_validator import EmailValidator

validator = EmailValidator()

# Basic validation
is_valid = validator.basic_validate("test@example.com")

# Advanced validation with DNS check
result = validator.advanced_validate("test@example.com")
# Returns: { valid, deliverable, mx_records, disposable, role_based }

# Enrichment
enriched = validator.enrich_with_hunter("test@example.com")
```

### Scoring Example

```python
from app.utils.scoring import ContactScorer

scorer = ContactScorer()

score = scorer.calculate_priority_score(
    follower_count=50000,
    last_active=datetime.now(),
    engagement_rate=0.05,
    llm_quality_score=85,
    contact_type="ar_rep"
)
```

## 🚢 Deployment

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app.api.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/artist_promo
    depends_on:
      - db
  
  db:
    image: postgres:14
    environment:
      POSTGRES_PASSWORD: yourpassword
      POSTGRES_DB: artist_promo
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Serverless Deployment (AWS Lambda)

Use **Mangum** adapter:

```python
from mangum import Mangum
from app.api.main import app

handler = Mangum(app)
```

Deploy with:
```bash
pip install mangum
serverless deploy
```

### Railway / Render / Fly.io

1. Connect GitHub repo
2. Set environment variables
3. Deploy automatically from main branch

## 📈 Monitoring & Logs

Logs are handled via **Loguru**. Configure in code:

```python
from loguru import logger

logger.add("logs/scraper_{time}.log", rotation="1 day", retention="7 days")
```

Optional: Integrate with **Sentry** for error tracking (set `SENTRY_DSN` in `.env`).

## 🔒 Security Best Practices

1. **Never commit `.env` file** - Use `.env.example` as template
2. **Rate limiting** - Respect API limits (built into scrapers)
3. **Email validation** - Always validate before sending
4. **GDPR compliance** - Add opt-out mechanisms
5. **API authentication** - Add OAuth2/JWT in production

## 📝 CSV Export Template

Generated CSV format:

| ID | Name | Email | Type | Priority Score | Followers | Instagram | Twitter | Company | Genres | Verified | Source URL |
|----|------|-------|------|----------------|-----------|-----------|---------|---------|--------|----------|------------|
| 1 | John Doe | john@example.com | playlist_curator | 85.5 | 50000 | @johndoe | @johndoe | IndieLabel | hip-hop,rap | Yes | https://... |

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📜 License

MIT License - See LICENSE file for details

## 💡 Tips & Tricks

### Best Practices

1. **Run scrapers during off-peak hours** to avoid rate limits
2. **Verify emails before bulk outreach** to maintain sender reputation
3. **Use scoring to prioritize** - Focus on contacts with 70+ scores
4. **Update data weekly** - Scrape again to refresh follower counts
5. **Combine multiple sources** - Cross-reference Spotify, Instagram, and web data

### Optimizing for Hip-Hop

**Targeted Keywords:**
- "hip hop playlist"
- "rap curator"
- "underground hip hop"
- "new rap music"
- "trap music"
- "boom bap"

**Curator Profile Signals:**
- Playlist followers > 1,000
- Updated in last 30 days
- Bio mentions "submissions" or "dm for playlist"
- Business account on Instagram

### Avoiding Spam Filters

1. Personalize each email (use LLM for custom intros)
2. Don't send more than 50 emails/day from new domain
3. Use SPF, DKIM, DMARC records
4. Include unsubscribe link
5. Monitor bounce rates

## 🔗 Resources

- [Spotify Web API Docs](https://developer.spotify.com/documentation/web-api/)
- [YouTube Data API Docs](https://developers.google.com/youtube/v3)
- [n8n Documentation](https://docs.n8n.io/)
- [Hunter.io API Docs](https://hunter.io/api-documentation)

## 📞 Support

For issues or questions:
- Open a GitHub issue
- Email: support@example.com
- Discord: [Your Discord Server]

---

**Built with ❤️ for independent hip-hop artists**
