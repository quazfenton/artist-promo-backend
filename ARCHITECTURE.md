# 🏗️ Architecture Overview

Visual guide to the system architecture and data flow.

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                          │
├─────────────────────────────────────────────────────────────────┤
│  CLI Tool          │  REST API          │  n8n Webhooks         │
│  (cli.py)          │  (FastAPI)         │  (Automation)         │
└────────┬───────────┴─────────┬──────────┴──────────┬────────────┘
         │                     │                     │
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BUSINESS LOGIC LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Scrapers    │  │  Validators  │  │   Scorers    │         │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│  │ • Spotify    │  │ • Email      │  │ • Contact    │         │
│  │ • YouTube    │  │ • DNS Check  │  │ • Playlist   │         │
│  │ • Instagram  │  │ • Hunter.io  │  │ • Venue      │         │
│  │ • Web        │  │ • NeverBounce│  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│  SQLAlchemy ORM                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Contacts │  │Playlists │  │  Venues  │  │ Outreach │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL / SQLite Database                                    │
│  Redis Cache (Optional)                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow - Scraping Pipeline

```
┌─────────────┐
│   Trigger   │  (Manual CLI, API call, or n8n scheduled)
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  Scraper Selection  │  (Spotify, YouTube, Instagram, Web)
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Data Extraction    │
├─────────────────────┤
│ • Fetch page/API    │
│ • Parse HTML/JSON   │
│ • Extract contacts  │
│ • Extract metrics   │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Data Processing    │
├─────────────────────┤
│ • Normalize data    │
│ • Extract emails    │
│ • Validate format   │
│ • Deduplicate       │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Email Validation   │
├─────────────────────┤
│ • Regex check       │
│ • DNS/MX lookup     │
│ • Disposable check  │
│ • Hunter.io enrich  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Priority Scoring   │
├─────────────────────┤
│ • Follower weight   │
│ • Recency weight    │
│ • Engagement weight │
│ • Quality weight    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Database Storage   │
├─────────────────────┤
│ • Check duplicates  │
│ • Update if exists  │
│ • Insert new record │
│ • Index for search  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Response/Export    │
├─────────────────────┤
│ • JSON response     │
│ • CSV file          │
│ • n8n webhook       │
└─────────────────────┘
```

---

## 🗄️ Database Schema

```
┌──────────────────────────┐
│       contacts           │
├──────────────────────────┤
│ id (PK)                  │◄───┐
│ full_name                │    │
│ username                 │    │
│ email                    │    │
│ contact_type (ENUM)      │    │
│ follower_count           │    │
│ priority_score           │    │
│ verified                 │    │
│ source_platform          │    │
│ genres (JSON)            │    │
│ created_at               │    │
│ updated_at               │    │
└──────────────────────────┘    │
                                 │
┌──────────────────────────┐    │
│       playlists          │    │
├──────────────────────────┤    │
│ id (PK)                  │    │
│ platform_id (UNIQUE)     │    │
│ platform (ENUM)          │    │
│ name                     │    │
│ curator_id (FK) ─────────┼────┘
│ follower_count           │
│ relevance_score          │
│ last_updated             │
│ playlist_url             │
└──────────────────────────┘

┌──────────────────────────┐
│         venues           │
├──────────────────────────┤
│ id (PK)                  │
│ name                     │
│ city                     │
│ booking_email            │
│ capacity                 │
│ venue_score              │
│ genres (JSON)            │
└──────────────────────────┘

┌──────────────────────────┐      ┌──────────────────────────┐
│    outreach_logs         │      │     scraper_runs         │
├──────────────────────────┤      ├──────────────────────────┤
│ id (PK)                  │      │ id (PK)                  │
│ contact_id (FK)          │      │ scraper_name             │
│ campaign_name            │      │ status                   │
│ sent_at                  │      │ items_found              │
│ status                   │      │ items_saved              │
│ n8n_execution_id         │      │ started_at               │
└──────────────────────────┘      └──────────────────────────┘
```

---

## 🌐 API Endpoint Map

```
/
├── GET  /                       → API info
├── GET  /health                 → Health check
│
├── /scrape/
│   ├── POST /scrape/spotify     → Scrape Spotify playlists
│   ├── POST /scrape/youtube     → Scrape YouTube channels
│   ├── POST /scrape/instagram   → Scrape Instagram profiles
│   └── POST /scrape/web         → Scrape website
│
├── /contacts/
│   ├── GET  /contacts           → Query contacts (filters, pagination)
│   ├── POST /contacts/verify    → Verify email address
│   └── POST /contacts/score     → Recalculate priority scores
│
├── /export/
│   └── POST /export/csv         → Export contacts to CSV
│
└── /webhook/n8n/
    ├── POST /webhook/n8n/scrape → Trigger scraping from n8n
    └── POST /webhook/n8n/export → Export data for n8n workflow
```

---

## 🔀 Integration Flow - n8n

```
┌─────────────────┐
│  Schedule       │  Every Monday 9 AM
│  Trigger        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTP Request   │  POST /webhook/n8n/scrape
│  (Trigger)      │  {"action": "scrape_spotify", "params": {...}}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Python API     │  Executes scraper in background
│  Processes      │  Returns status
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTP Request   │  GET /contacts?min_score=70
│  (Get Results)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Filter Node    │  Filter contacts with valid emails
│  (JavaScript)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OpenAI Node    │  Generate personalized email
│  (LLM)          │  "Write a pitch for curator {name}..."
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Email Node     │  Send via Gmail/SendGrid
│  (Send)         │  Track in outreach_logs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Webhook        │  POST back to /webhook/n8n/log
│  (Log Result)   │  Update contact with status
└─────────────────┘
```

---

## 🧩 Module Dependencies

```
cli.py
  ├─── app.models.database
  ├─── app.scrapers.*
  ├─── app.utils.*
  └─── app.api.main (functions)

app.api.main
  ├─── app.models.database
  ├─── app.scrapers.*
  └─── app.utils.*

app.scrapers.spotify_scraper
  ├─── app.scrapers.base_scraper
  ├─── spotipy (external)
  └─── app.models.database

app.scrapers.youtube_scraper
  ├─── app.scrapers.base_scraper
  └─── google-api-python-client (external)

app.scrapers.instagram_scraper
  ├─── app.scrapers.base_scraper
  └─── instaloader (external)

app.scrapers.web_scraper
  ├─── app.scrapers.base_scraper
  └─── beautifulsoup4 (external)

app.utils.email_validator
  ├─── email-validator (external)
  └─── dnspython (external)

app.utils.scoring
  └─── app.models.database (enums)
```

---

## 📦 Deployment Architecture

### **Local Development**
```
┌──────────────────────┐
│   Developer Machine  │
├──────────────────────┤
│  Python venv         │
│  SQLite database     │
│  Uvicorn server      │
│  CLI tool            │
└──────────────────────┘
```

### **Docker Compose**
```
┌─────────────────────────────────────────┐
│          Docker Host                    │
├─────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐    │
│  │  API         │  │  PostgreSQL  │    │
│  │  Container   │◄─┤  Container   │    │
│  └──────┬───────┘  └──────────────┘    │
│         │                               │
│         │          ┌──────────────┐    │
│         └─────────►│  Redis       │    │
│                    │  Container   │    │
│                    └──────────────┘    │
└─────────────────────────────────────────┘
```

### **Production (Cloud)**
```
┌──────────────────────────────────────────────────┐
│              Load Balancer / CDN                  │
└────────────────┬─────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
┌─────────┐             ┌─────────┐
│  API    │             │  API    │  (Multiple instances)
│ Instance│             │ Instance│
└────┬────┘             └────┬────┘
     │                       │
     └───────────┬───────────┘
                 │
                 ▼
┌────────────────────────────┐
│  Managed PostgreSQL        │  (RDS, Cloud SQL, etc.)
│  (with replicas)           │
└────────────────────────────┘
         │
         │
┌────────────────────────────┐
│  Redis Cache               │  (ElastiCache, etc.)
└────────────────────────────┘
```

---

## 🔒 Security Layers

```
┌─────────────────────────────────────────┐
│  Network Layer                          │
│  • HTTPS/TLS                            │
│  • Firewall rules                       │
│  • Rate limiting                        │
└────────────────┬────────────────────────┘
                 │
┌─────────────────────────────────────────┐
│  Application Layer                      │
│  • Input validation                     │
│  • SQL injection prevention             │
│  • XSS protection                       │
│  • CORS configuration                   │
└────────────────┬────────────────────────┘
                 │
┌─────────────────────────────────────────┐
│  Data Layer                             │
│  • Encrypted credentials (.env)         │
│  • Database encryption at rest          │
│  • Secure API key storage               │
│  • PII data protection                  │
└─────────────────────────────────────────┘
```

---

## 🚀 Scaling Strategy

### **Horizontal Scaling**
```
Single Instance (0-1K contacts/day)
         ↓
Multiple API Instances (1K-10K contacts/day)
         ↓
+ Background Workers (10K-100K contacts/day)
         ↓
+ Distributed Queue (100K+ contacts/day)
```

### **Caching Strategy**
```
1. Memory Cache (Frequent queries)
2. Redis Cache (Session data, temp results)
3. Database Query Cache (Materialized views)
4. CDN Cache (Static exports)
```

---

## 📊 Monitoring & Logging

```
┌──────────────────────────────────────┐
│         Application                   │
└────────┬─────────────────────────────┘
         │
         ├─── Logs ──────► File System
         │                 (loguru)
         │
         ├─── Errors ────► Sentry
         │                 (error tracking)
         │
         ├─── Metrics ───► Prometheus
         │                 (performance)
         │
         └─── Analytics ─► Custom DB
                          (scraper stats)
```

---

**This architecture supports:**
- ✅ Rapid development and testing
- ✅ Easy deployment (local, Docker, cloud)
- ✅ Horizontal scaling
- ✅ Multiple integration points (CLI, API, webhooks)
- ✅ Production-grade reliability
- ✅ Extensibility (add new scrapers easily)
