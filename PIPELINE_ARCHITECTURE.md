# 🎤 Artist Promotion Backend - Enhanced Pipeline

This repository contains a production-ready Python backend for automating music promotion outreach with n8n integration, enhanced with a modern pipeline architecture for scalability and reliability.

## 🚀 New Pipeline Architecture

The system now implements a multi-stage pipeline architecture with the following components:

### 📦 Pipeline Layers Overview

```
API/CLI Layer
   │
   ├─ app/api/main.py       # REST endpoints
   └─ cli.py               # CLI triggers
           │ enqueue_job()
           ▼
Queue Layer
   ├─ Redis queues
   │    ├─ queue:scrape
   │    ├─ queue:normalize
   │    ├─ queue:enrich
   │    ├─ queue:graph
   │    └─ queue:outreach
           │
Worker Layer
   ├─ Scrape Worker
   │    └─ app/scrapers/* (stateless)
   │         ▼ produces
   │      scraper_raw_signals (Postgres)
   │
   ├─ Signal Normalizer Worker
   │    └─ reads scraper_raw_signals
   │         ▼ produces
   │      staging_contacts
   │
   ├─ Entity Resolver / Enrichment Worker
   │    └─ reads staging_contacts
   │         ▼ produces
   │      resolved_entities
   │
   ├─ Graph Builder & Cluster Worker
   │    └─ reads resolved_entities + edges
   │         ▼ produces
   │      graph_nodes / graph_edges / cluster_runs
   │
   └─ Outreach Worker
        └─ reads resolved_entities + cluster info
             ▼ triggers
             email / DM / intro via app/integrations/
```

### 🗄️ Database Layer

The system now uses staging and canonical tables:

| Table | Purpose |
|-------|---------|
| `scraper_raw_signals` | Raw scraper output; each job produces one or more rows |
| `staging_contacts` | Normalized candidates with confidence scores, emails, handles |
| `resolved_entities` | Deduplicated, merged canonical entities; maps to app.models.Contact |
| `graph_nodes` | Nodes in the manager/artist/curator graph |
| `graph_edges` | Edges between nodes with type + weight (represents, follows) |
| `cluster_runs` | Stores clusters, cluster_ids, influence scores, provenance |
| `app.models.Contact` | Existing canonical contacts; optionally updated via adapter |

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Redis
- PostgreSQL (or SQLite for development)

### Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure your settings
4. Run database migrations:
   ```bash
   python cli.py migrate
   ```

### Running with Docker Compose

```bash
# Start the full pipeline
docker-compose up -d

# Start individual workers
docker-compose run scrape-worker
docker-compose run normalize-worker
docker-compose run enrich-worker
docker-compose run graph-worker
docker-compose run outreach-worker
```

### Running Individual Components

```bash
# Start the API server
uvicorn app.api.main:app --reload

# Start a specific worker
python cli.py start-worker scrape --concurrency 2

# Run a scraper directly
python cli.py scrape-spotify --genre "hip-hop" --min-followers 1000
```

## 📊 API Endpoints

### Scraping Endpoints (Now Async)
- `POST /scrape/spotify` → Enqueues Spotify scraping job
- `POST /scrape/youtube` → Enqueues YouTube scraping job  
- `POST /scrape/instagram` → Enqueues Instagram scraping job
- `POST /scrape/web` → Enqueues web scraping job

### Job Management Endpoints
- `GET /jobs/status/{job_id}` → Get status of a background job
- `GET /jobs/queues` → Get status of all queues

### Traditional Endpoints (Still Available)
- `GET /contacts` → Query contacts with filters
- `POST /contacts/verify` → Verify email address
- `POST /contacts/score` → Recalculate priority scores
- `POST /export/csv` → Export contacts to CSV
- `POST /webhook/n8n/scrape` → Trigger scraping from n8n
- `POST /webhook/n8n/export` → Export data for n8n workflow

## 🏗️ Pipeline Flow

1. **API/CLI** receives request → calls `enqueue_job(job_type, params)`
2. Job pushed to Redis queue → picked up by appropriate worker
3. **Scrape Worker** executes → writes to `scraper_raw_signals` → pushes to normalize queue
4. **Signal Normalizer Worker** reads raw signals → normalizes → writes to `staging_contacts`
5. **Entity Resolver + Enrichment Worker** reads staging → deduplicates → enriches → writes to `resolved_entities`
6. **Graph Builder Worker** reads resolved entities → builds graph → writes to `graph_nodes`/`graph_edges`
7. **Cluster Worker** runs community detection → writes to `cluster_runs`
8. **Outreach Worker** reads clusters → makes decisions → sends emails/DMs

## 🛠️ Worker Types

- **Scrape Worker**: Stateless, rate-limited, async scraping
- **Signal Normalizer Worker**: Normalizes raw signals, parses emails/handles/timestamps
- **Entity Resolver + Enrichment Worker**: Deduplication, enrichment, confidence scoring
- **Graph Builder Worker**: Builds relationship graphs with weighted edges
- **Cluster Worker**: Runs community detection and influence propagation
- **Outreach Worker**: Multi-channel outreach with LLM personalization

## 📈 Monitoring & Observability

- Queue depth per type (Redis LLEN)
- Job success/failure metrics per worker
- Latency from enqueue → final cluster
- Scraper rate limits/failures
- Outreach response rates per channel

All metrics integrate with existing Sentry + Prometheus hooks.

## 🔄 Backwards Compatibility

All existing API endpoints continue to work. The new pipeline operates alongside the existing synchronous path, allowing for gradual migration.

## 🤖 n8n Integration

The system includes a workflow template for n8n integration that can trigger scraping jobs and receive results.

## 🛡️ Security Features

- Environment variable configuration (no hardcoded secrets)
- Rate limiting in scrapers
- User-agent rotation
- SQL injection prevention
- CORS configuration
- JWT authentication with refresh tokens
- Role-based access control

## 📊 Expected Results

After implementing the pipeline:
- Scalable scraping with horizontal worker scaling
- Deduplicated and enriched contact data
- Graph-based relationship analysis
- Community detection for manager clusters
- Automated, personalized outreach
- Improved reliability and error handling

## 🎯 Next Steps

1. Configure your API keys in `.env`
2. Set up Redis and PostgreSQL
3. Start the API server and workers
4. Connect to n8n using the included workflow template
5. Monitor queue performance and adjust worker counts
6. Iterate based on outreach response rates

---

Built for independent hip-hop artists who want to take control of their promotion 🎤🔥