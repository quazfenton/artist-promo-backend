# ✅ Getting Started Checklist

Follow this checklist to go from zero to scraping in under 30 minutes!

---

## 📋 Pre-Setup (5 minutes)

- [ ] **Sign up for API keys:**
  - [ ] [Spotify Developer Account](https://developer.spotify.com/dashboard) → Create App → Get Client ID & Secret
  - [ ] [YouTube Data API](https://console.cloud.google.com/apis/credentials) → Create API Key (optional but recommended)
  - [ ] [Hunter.io](https://hunter.io/users/sign_up) → Free tier (optional, for email verification)

- [ ] **Install prerequisites:**
  - [ ] Python 3.9+ installed (`python3 --version`)
  - [ ] pip installed (`pip --version`)
  - [ ] Git installed (optional, for version control)

---

## 🚀 Installation (5 minutes)

- [ ] **Navigate to project directory:**
  ```bash
  cd artist-promo-backend
  ```

- [ ] **Run automated setup:**
  ```bash
  ./setup.sh
  ```
  
  Or manually:
  ```bash
  python3 -m venv venv
  source venv/bin/activate  # Windows: venv\Scripts\activate
  pip install -r requirements.txt
  ```

- [ ] **Create configuration file:**
  ```bash
  cp .env.example .env
  ```

- [ ] **Edit `.env` file with your API keys:**
  ```bash
  nano .env  # or use any text editor
  ```
  
  **Minimum required:**
  ```
  SPOTIFY_CLIENT_ID=your_spotify_id_here
  SPOTIFY_CLIENT_SECRET=your_spotify_secret_here
  DATABASE_URL=sqlite:///./artist_promo.db
  ```

---

## 🧪 First Test (5 minutes)

- [ ] **Test API server:**
  ```bash
  uvicorn app.api.main:app --reload
  ```
  
  Visit: http://localhost:8000
  
  Should see: `{"app": "Artist Promotion API", "version": "1.0.0", "status": "running"}`

- [ ] **Open API documentation:**
  
  Visit: http://localhost:8000/docs
  
  You should see interactive API docs (Swagger UI)

- [ ] **Test CLI tool:**
  ```bash
  ./cli.py --help
  ```
  
  Should see list of available commands

---

## 🎯 First Scrape (5 minutes)

Choose ONE method:

### **Method A: Using CLI**

- [ ] **Scrape Spotify playlists:**
  ```bash
  ./cli.py scrape-spotify --genre hip-hop --min-followers 1000 --limit 10
  ```

- [ ] **Check database stats:**
  ```bash
  ./cli.py stats
  ```

- [ ] **Export to CSV:**
  ```bash
  ./cli.py export-csv --min-score 0 --output exports/my_first_export.csv
  ```

- [ ] **View the CSV:**
  ```bash
  cat exports/my_first_export.csv
  ```

### **Method B: Using API**

- [ ] **Start API server (if not running):**
  ```bash
  uvicorn app.api.main:app --reload
  ```

- [ ] **Trigger scrape via curl:**
  ```bash
  curl -X POST http://localhost:8000/scrape/spotify \
    -H "Content-Type: application/json" \
    -d '{"genre": "hip-hop", "min_followers": 1000, "max_results": 10}'
  ```

- [ ] **Get contacts:**
  ```bash
  curl "http://localhost:8000/contacts?limit=10"
  ```

- [ ] **Export CSV:**
  ```bash
  curl -X POST http://localhost:8000/export/csv \
    -H "Content-Type: application/json" \
    -d '{"min_score": 0}' \
    -o exports/api_export.csv
  ```

---

## 📊 Verify Results (2 minutes)

- [ ] **Check that data was saved:**
  ```bash
  ls -lh artist_promo.db  # Should see database file
  ls -lh exports/         # Should see CSV files
  ```

- [ ] **View database stats:**
  ```bash
  ./cli.py stats
  ```
  
  Should see something like:
  ```
  📊 Database Statistics
  
  Total Contacts: 10
  Verified Contacts: 0
  Total Playlists: 10
  Total Venues: 0
  ```

- [ ] **Open CSV in Excel/Google Sheets:**
  - Should see columns: ID, Name, Email, Type, Score, Followers, etc.
  - Should have 10 rows of data

---

## 🔗 Connect to n8n (10 minutes)

- [ ] **Install n8n (if not already):**
  ```bash
  npm install -g n8n
  # Or use Docker: docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n
  ```

- [ ] **Start n8n:**
  ```bash
  n8n start
  ```
  
  Visit: http://localhost:5678

- [ ] **Create new workflow:**
  - Import `n8n_workflow_template.json`
  - Or create manually:
    1. Add HTTP Request node
    2. Method: POST
    3. URL: `http://localhost:8000/webhook/n8n/scrape`
    4. Body: `{"action": "scrape_spotify", "params": {"genre": "hip-hop"}}`

- [ ] **Test n8n workflow:**
  - Click "Execute Workflow"
  - Check that contacts appear in database

- [ ] **Set up schedule (optional):**
  - Add Schedule Trigger node
  - Set to run weekly (e.g., Monday 9 AM)

---

## 🎓 Learn More (5 minutes)

- [ ] **Read documentation:**
  - [ ] `README.md` - Full overview
  - [ ] `TACTICS_GUIDE.md` - Advanced tactics
  - [ ] `VERIFIED_SOURCES.md` - Contact sources

- [ ] **Try other scrapers:**
  - [ ] YouTube: `./cli.py scrape-youtube --query "hip hop playlist"`
  - [ ] Web: `./cli.py scrape-web https://example.com/contact`

- [ ] **Explore API docs:**
  - Visit http://localhost:8000/docs
  - Try different endpoints interactively

---

## 🚀 Next Steps (Your Choice)

### **Option 1: Expand Data Collection**
- [ ] Scrape more platforms (Instagram, YouTube, etc.)
- [ ] Increase scraping limits
- [ ] Set up automated daily/weekly scrapes
- [ ] Add custom sources to scrapers

### **Option 2: Improve Data Quality**
- [ ] Set up email verification (Hunter.io or NeverBounce)
- [ ] Adjust scoring weights in `.env`
- [ ] Add LLM integration for quality scoring
- [ ] Verify top contacts manually

### **Option 3: Automate Outreach**
- [ ] Connect to email service (Gmail, SendGrid)
- [ ] Create personalized email templates
- [ ] Set up n8n workflow for automated pitching
- [ ] Add LLM for email personalization (OpenAI, Anthropic)
- [ ] Track response rates

### **Option 4: Deploy to Production**
- [ ] Set up PostgreSQL database
- [ ] Deploy with Docker
- [ ] Deploy to cloud (Railway, Render, AWS)
- [ ] Set up monitoring (Sentry)
- [ ] Configure HTTPS/SSL

---

## ❓ Troubleshooting

### **"Import Error" when running scripts**
- Make sure virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### **"Authentication Error" with Spotify**
- Check `.env` file has correct credentials
- Verify Spotify app is created and active
- Try regenerating Client Secret

### **"No results found"**
- Try different search terms (e.g., "rap" instead of "hip-hop")
- Increase `--limit` parameter
- Check API quotas (Spotify, YouTube)

### **"Database locked" error**
- Close any other processes using the database
- Use PostgreSQL instead of SQLite for production

### **"n8n can't connect to API"**
- Make sure API is running: `uvicorn app.api.main:app`
- Use `http://host.docker.internal:8000` if n8n is in Docker
- Check firewall settings

---

## 🎯 Success Criteria

You've successfully set up the system when:

- ✅ API server runs without errors
- ✅ First scrape completes and saves data
- ✅ CSV export contains valid contacts
- ✅ Database shows statistics with `./cli.py stats`
- ✅ n8n can trigger scrapes via webhook
- ✅ You understand how to customize and extend

---

## 📞 Need Help?

- **Check logs:** `tail -f logs/*.log`
- **View API errors:** Check terminal where `uvicorn` is running
- **Database issues:** Try deleting `artist_promo.db` and starting fresh
- **API documentation:** http://localhost:8000/docs

---

## 🎉 Congratulations!

You now have a fully functional artist promotion system!

**What you can do now:**
- 🎯 Build database of 1,000+ verified contacts
- 📊 Score and prioritize outreach targets
- 🤖 Automate discovery with n8n workflows
- 📧 Export data for email campaigns
- 🚀 Scale to multiple artists/campaigns

**Keep going!**
- Add more scrapers
- Improve scoring algorithms
- Build outreach templates
- Track campaign results
- Share your success story!

---

**Ready to promote your music? Let's go! 🎤🔥**
