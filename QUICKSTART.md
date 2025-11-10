# 🚀 Quick Start Guide

Get up and running in 5 minutes!

## 1. Install Dependencies

```bash
cd artist-promo-backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your API keys
```

**Minimum required:**
- `SPOTIFY_CLIENT_ID` - Get from [Spotify Dashboard](https://developer.spotify.com/dashboard)
- `SPOTIFY_CLIENT_SECRET`

## 3. Run the API

```bash
uvicorn app.api.main:app --reload
```

API will be available at: `http://localhost:8000`

## 4. Test Scraping (CLI)

```bash
# Make CLI executable
chmod +x cli.py

# Scrape Spotify playlists
./cli.py scrape-spotify --genre hip-hop --min-followers 1000 --limit 50

# Check stats
./cli.py stats

# Export to CSV
./cli.py export-csv --min-score 60 --output exports/curators.csv
```

## 5. Test API Endpoints

**Scrape Spotify:**
```bash
curl -X POST http://localhost:8000/scrape/spotify \
  -H "Content-Type: application/json" \
  -d '{"genre": "hip-hop", "min_followers": 1000, "max_results": 50}'
```

**Get Contacts:**
```bash
curl "http://localhost:8000/contacts?min_score=50&limit=10"
```

**Export CSV:**
```bash
curl -X POST http://localhost:8000/export/csv \
  -H "Content-Type: application/json" \
  -d '{"min_score": 60}' \
  -o curators.csv
```

## 6. Connect to n8n

1. In n8n, create a new workflow
2. Add **HTTP Request** node
3. Configure:
   - Method: `POST`
   - URL: `http://your-api:8000/webhook/n8n/scrape`
   - Body:
     ```json
     {
       "action": "scrape_spotify",
       "params": {
         "genre": "hip-hop",
         "min_followers": 1000
       }
     }
     ```
4. Add **Schedule Trigger** to run daily/weekly
5. Connect to email/CRM nodes for automated outreach

## 7. Docker Deployment (Optional)

```bash
docker-compose up -d
```

Access at: `http://localhost:8000`

---

## Next Steps

- 📖 Read [README.md](README.md) for full documentation
- 🔧 Customize scoring weights in `.env`
- 📊 Check `/health` endpoint for API status
- 🎯 Set up email verification with Hunter.io/NeverBounce
- 🤖 Create n8n workflows for automated outreach

## Need Help?

- View API docs: http://localhost:8000/docs
- Check logs: `logs/scraper_*.log`
- Run tests: `pytest tests/`

**Happy promoting! 🎤🔥**
