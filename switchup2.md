
1. X / Twitter (API-free)
Nitter (primary)
What it is
Privacy-focused alternative Twitter frontend
No auth, no API keys
Many public instances
Data you can extract
Bios (often contain emails)
Tweets
Links
Follower counts
Media
Replies
Endpoints
https://nitter.net/username
https://nitter.net/search?q=music+booking

Typical pipeline usage
Bio email extraction
Curator discovery via keyword search
Reply graph construction
⚠️ Use rotating instances:
nitter.net
nitter.snopyta.org
nitter.unixfox.eu

TwitRSS / RSSHub
What it is
RSS feeds generated from Twitter without API
Why it’s useful
Passive monitoring
No scraping JS
Example
https://nitter.net/username/rss


Common Crawl (Twitter pages)
What it is
Massive public crawl archive
Use case
Historical bios & tweets
No rate limits
Good for
Bulk discovery
Long-tail curator mapping

2. Instagram (API-free)
Imginn / Picuki / Dumpor
What they are
Public Instagram profile viewers
No login required
Data you can extract
Bio text
Website links
Captions
Comments
Tagged users
Examples
https://imginn.com/username/
https://picuki.com/profile/username

Why useful
Emails often in bios
Captions often contain management contacts

Bibliogram (self-hosted)
What it is
Open-source Instagram frontend (now archived, still forked)
Why useful
Full HTML access
Works well with headless scraping

Link-in-Bio Pages
(Not an API, but critical)
Extract emails from:
Linktree
Beacons
Campsite
Carrd
Bio.fm
These often expose:
Booking emails
Manager links
PR firm domains

3. YouTube (No official API)
Invidious
What it is
Privacy-friendly YouTube frontend
Data you can extract
Channel About pages
Video descriptions
External links
Subscriber counts
Endpoints
https://invidious.io/channel/CHANNEL_ID
https://invidious.io/watch?v=VIDEO_ID

Why useful
Artist managers often list emails in About pages
No quota limits

yt-dlp (metadata mode)
What it is
CLI downloader with metadata extraction
Extract
Description
Uploader
Tags
Channel links
No API keys required.

4. Reddit (API-free)
Libreddit
What it is
Alternative Reddit frontend
Extract
Submissions
Comments
User bios
Moderator lists
Example
https://libreddit.kavin.rocks/r/WeAreTheMusicMakers


Pushshift (historical)
What it is
Public Reddit data archive
Use case
Historical discovery of curators, labels, booking agents
Identify repeated submission emails

5. TikTok (API-free)
ProxiTok
What it is
TikTok frontend mirror
Extract
Bios
External links
Captions
Example
https://proxitok.pabloferreiro.es/@username


Urlebird / Snaptik mirrors
Why useful
Public pages
Often expose raw bio HTML

6. SoundCloud / Bandcamp
SoundCloud
No API required for:
Track pages
Profile pages
Comments
“Contact” links
Emails frequently appear in:
Track descriptions
Profile bios

Bandcamp
Extremely scrape-friendly:
Artist pages
Label pages
Contact pages
Footer legal emails
Goldmine for
Booking
Licensing
Label A&R contacts

7. Domain & Infrastructure-Level Sources
WHOIS / RDAP
Why
PR firms & labels hide emails on sites but forget domain WHOIS
Data
Registrant email
Admin email

SSL Certificates (crt.sh)
Extract
Organization names
Domains linked to same entity
Helps cluster:
Artist websites
PR microsites
Campaign domains

DNS & MX Records
Why
Identify email providers
Match multiple artists using same management email domain

8. Documents & File Metadata
Google Drive / Docs (public)
PDFs
Slides
Press kits
Festival decks
Metadata often contains:
Author email
Company email

SlideShare / SpeakerDeck
Often used by:
Music conferences
Booking agencies
Festival organizers

9. Event & Venue Data (API-free)
Songkick / Bandsintown
Scrape:
Event organizers
Venue pages
Promoter links
Emails often hidden in:
Venue contact pages
Footer legal notices

Resident Advisor
Electronic music goldmine:
Promoters
Labels
Event organizers

10. General Search Layer (Critical)
Search Engine Scraping
Use:
DuckDuckGo HTML
Brave Search
SearxNG instances
Queries like:
"booking@" "artist name"
"submissions@" "label"
"press@" "music"


Common Crawl
Underrated but powerful:
Entire web snapshots
Extract historical contact pages

11. Anti-Fragile Strategy (Best Practice)
Instead of relying on one source:
Artist
 ├─ Instagram mirror
 │   └─ Linktree
 │       └─ Management site
 │           └─ WHOIS email
 ├─ Nitter bio
 ├─ YouTube Invidious About page
 └─ Bandcamp contact

Score emails higher if they appear across multiple independent sources.
##
##
1️⃣ Nitter Scraper (Twitter/X alternative)
Extracts
Bio text
Emails
External links
Display name
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.snopyta.org",
    "https://nitter.unixfox.eu"
]

def scrape_nitter(username):
    base = random.choice(NITTER_INSTANCES)
    url = f"{base}/{username}"
    html = fetch(url)

    soup = BeautifulSoup(html, "html.parser")
    bio = soup.select_one(".profile-bio")

    text = bio.get_text(" ", strip=True) if bio else ""
    emails = extract_emails(text)

    links = [a["href"] for a in soup.select(".profile-bio a[href]")]

    return {
        "platform": "twitter",
        "username": username,
        "bio": text,
        "emails": emails,
        "links": links,
        "source": url
    }


2️⃣ Invidious Scraper (YouTube alternative)
Extracts
Channel About text
Business email
External links
INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://vid.puffyan.us",
    "https://invidious.io"
]

def scrape_invidious_channel(channel_id):
    base = random.choice(INVIDIOUS_INSTANCES)
    url = f"{base}/channel/{channel_id}/about"
    html = fetch(url)

    soup = BeautifulSoup(html, "html.parser")
    about = soup.select_one(".channel-about")

    text = about.get_text(" ", strip=True) if about else ""
    emails = extract_emails(text)

    links = [a["href"] for a in soup.select("a[href^='http']")]

    return {
        "platform": "youtube",
        "channel_id": channel_id,
        "about": text,
        "emails": emails,
        "links": links,
        "source": url
    }


3️⃣ Imginn Scraper (Instagram mirror)
Extracts
Bio
Emails
External links
def scrape_imginn(username):
    url = f"https://imginn.com/{username}/"
    html = fetch(url)

    soup = BeautifulSoup(html, "html.parser")
    bio = soup.select_one(".bio")

    text = bio.get_text(" ", strip=True) if bio else ""
    emails = extract_emails(text)

    links = [a["href"] for a in soup.select("a[href^='http']")]

    return {
        "platform": "instagram",
        "username": username,
        "bio": text,
        "emails": emails,
        "links": links,
        "source": url
    }


4️⃣ Libreddit Scraper (Reddit alternative)
Extracts
Post content
Emails from threads
Useful for “submissions open” discovery
LIBREDDIT_INSTANCES = [
    "https://libreddit.kavin.rocks",
    "https://lr.riverside.rocks"
]

def scrape_libreddit_subreddit(subreddit, limit=5):
    base = random.choice(LIBREDDIT_INSTANCES)
    url = f"{base}/r/{subreddit}"
    html = fetch(url)

    soup = BeautifulSoup(html, "html.parser")
    posts = soup.select("div.post")[:limit]

    results = []
    for post in posts:
        text = post.get_text(" ", strip=True)
        emails = extract_emails(text)
        if emails:
            results.append({
                "text": text[:300],
                "emails": emails,
                "source": url
            })

    return {
        "platform": "reddit",
        "subreddit": subreddit,
        "matches": results
    }


5️⃣ ProxiTok Scraper (TikTok mirror)
Extracts
Bio
External links
Emails
def scrape_proxitok(username):
    url = f"https://proxitok.pabloferreiro.es/@{username}"
    html = fetch(url)

    soup = BeautifulSoup(html, "html.parser")
    bio = soup.select_one(".bio")

    text = bio.get_text(" ", strip=True) if bio else ""
    emails = extract_emails(text)

    links = [a["href"] for a in soup.select("a[href^='http']")]

    return {
        "platform": "tiktok",
        "username": username,
        "bio": text,
        "emails": emails,
        "links": links,
        "source": url
    }


6️⃣ Unified Orchestrator (Plug-and-Play)
def scrape_all(handles):
    results = []

    if "twitter" in handles:
        results.append(scrape_nitter(handles["twitter"]))

    if "youtube" in handles:
        results.append(scrape_invidious_channel(handles["youtube"]))

    if "instagram" in handles:
        results.append(scrape_imginn(handles["instagram"]))

    if "tiktok" in handles:
        results.append(scrape_proxitok(handles["tiktok"]))

    if "reddit" in handles:
        results.append(scrape_libreddit_subreddit(handles["reddit"]))

    return results


Example Usage
handles = {
    "twitter": "artistname",
    "instagram": "artistname",
    "youtube": "UCxxxxxxxx",
    "tiktok": "artistname",
    "reddit": "WeAreTheMusicMakers"
}

data = scrape_all(handles)

for d in data:
    print(d)


##
 focus on infrastructure glue, enrichment layers, orchestration, verification, deduplication, reputation safety, and scale mechanics — the stuff that turns scripts into a real system.

1) Evidence Ledger (Why we trust this email)
Instead of just a score, store machine-auditable evidence.
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Evidence:
    email: str
    source: str
    signal: str
    url: str
    timestamp: str

def log_evidence(email, source, signal, url):
    return Evidence(
        email=email,
        source=source,
        signal=signal,
        url=url,
        timestamp=datetime.utcnow().isoformat()
    )

This enables:
audit trails
re-scoring
legal defensibility
explainable automation

2) Cross-Source Email Canonicalization
Normalize aliases like press@, booking@, mgmt@.
def canonicalize_email(email):
    local, domain = email.lower().split("@")
    aliases = ["press", "booking", "mgmt", "management"]
    if local in aliases:
        local = "official"
    return f"{local}@{domain}"

Used before:
clustering
deduplication
sending limits

3) Domain-Level Reputation Gate
Avoid burning domains by limiting per-manager sends.
from collections import defaultdict
from time import time

SEND_LIMITS = defaultdict(list)

def can_send(domain, max_per_day=3):
    now = time()
    SEND_LIMITS[domain] = [t for t in SEND_LIMITS[domain] if now - t < 86400]
    return len(SEND_LIMITS[domain]) < max_per_day

def log_send(domain):
    SEND_LIMITS[domain].append(time())


4) MX + Role Account Detection (No SMTP yet)
Lightweight verification without sending mail.
import dns.resolver

ROLE_PREFIXES = {"info", "contact", "hello", "admin"}

def check_email_domain(email):
    local, domain = email.split("@")
    try:
        dns.resolver.resolve(domain, "MX")
        has_mx = True
    except:
        has_mx = False

    return {
        "has_mx": has_mx,
        "role_account": local in ROLE_PREFIXES
    }


5) Link-in-Bio Recursive Resolver
Crawl one hop deeper only if useful.
def resolve_link_tree(url, depth=1):
    if depth == 0:
        return []

    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    emails = extract_emails(html)
    links = [a["href"] for a in soup.select("a[href^='http']")]

    return {
        "emails": emails,
        "links": links,
        "children": [
            resolve_link_tree(l, depth-1)
            for l in links if "linktr.ee" in l or "beacons.ai" in l
        ]
    }


6) Temporal Signal Strength (Freshness Bias)
Recent evidence > old evidence.
from datetime import datetime, timedelta

def freshness_weight(timestamp):
    age = datetime.utcnow() - datetime.fromisoformat(timestamp)
    if age < timedelta(days=30):
        return 1.0
    if age < timedelta(days=180):
        return 0.7
    return 0.4

Used during scoring aggregation.

7) Artist → Manager Resolution Confidence
Not all clusters are equally certain.
def manager_resolution_confidence(cluster):
    signals = 0
    signals += len(cluster["emails"]) * 2
    signals += len(cluster["domains"]) * 3
    signals += len(cluster["artists"])
    return min(100, signals * 5)


8) Contact Surface Area Metric
How exposed / reachable is this manager?
def contact_surface(cluster):
    return {
        "email_count": len(cluster["emails"]),
        "domain_count": len(cluster["domains"]),
        "platform_count": cluster.get("platform_count", 1),
        "surface_score": (
            len(cluster["emails"]) +
            2 * len(cluster["domains"]) +
            cluster.get("platform_count", 1)
        )
    }

Useful for prioritization.

9) Outreach Cooldown Scheduler
Prevent accidental double sends.
LAST_CONTACT = {}

def can_contact(email, cooldown_days=14):
    last = LAST_CONTACT.get(email)
    if not last:
        return True
    return (datetime.utcnow() - last).days >= cooldown_days

def mark_contacted(email):
    LAST_CONTACT[email] = datetime.utcnow()


10) Platform Confidence Aggregator
Blend multiple weak signals into one strong one.
def aggregate_platform_confidence(signals):
    weights = {
        "official_site": 3,
        "social_bio": 2,
        "third_party_mirror": 1,
        "whois": 2
    }
    return sum(weights.get(s, 0) for s in signals)


11) Graph Drift Detection (Manager Changes)
Detect when artists switch management.
def detect_manager_change(old_cluster, new_cluster):
    old_domains = set(old_cluster["domains"])
    new_domains = set(new_cluster["domains"])
    return old_domains != new_domains

Trigger:
re-outreach
update CRM
historical tracking

12) Low-Risk Warmup Mode
New sending domain protection.
def warmup_allowed(confidence, domain_age_days):
    if domain_age_days < 30:
        return confidence >= 85
    if domain_age_days < 90:
        return confidence >= 70
    return confidence >= 50


13) Pipeline Orchestrator (State Machine)
PIPELINE_STATES = [
    "scraped",
    "normalized",
    "clustered",
    "scored",
    "verified",
    "ready_to_send",
    "contacted"
]

def advance_state(record, new_state):
    assert new_state in PIPELINE_STATES
    record["state"] = new_state


14) Manager Archetype Classifier (Rule-Based)
def classify_manager(cluster):
    if len(cluster["artists"]) >= 10:
        return "AGENCY"
    if len(cluster["artists"]) >= 3:
        return "BOUTIQUE_MANAGER"
    return "SOLO_MANAGER"

Used to:
choose template
adjust tone
control cadence

15) Failure-Resilient Task Queue (Minimal)
from queue import Queue

task_queue = Queue()

def enqueue(task):
    task_queue.put(task)

def worker():
    while not task_queue.empty():
        task = task_queue.get()
        try:
            task()
        except Exception as e:
            print("Task failed:", e)
        task_queue.task_done()


###
16) Async Scraping + Enrichment Executor (Concurrency-Safe)
Moves you off sequential scraping.
import asyncio
import aiohttp

SEM = asyncio.Semaphore(5)

async def fetch_async(session, url):
    async with SEM:
        async with session.get(url, timeout=10) as r:
            r.raise_for_status()
            return await r.text()

async def run_tasks(tasks):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        coros = [task(session) for task in tasks]
        return await asyncio.gather(*coros, return_exceptions=True)

Used for:
mirrors
link-in-bio hops
document downloads
enrichment APIs

17) Postgres-Ready Data Model (Normalized, Minimal)
This avoids NoSQL chaos later.
CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE,
    domain TEXT,
    confidence INT,
    tier TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP
);

CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    type TEXT, -- artist | manager | curator
    name TEXT
);

CREATE TABLE evidence (
    id SERIAL PRIMARY KEY,
    contact_id INT REFERENCES contacts(id),
    signal TEXT,
    source TEXT,
    url TEXT,
    timestamp TIMESTAMP
);

CREATE TABLE relationships (
    from_entity INT,
    to_entity INT,
    type TEXT -- manages | represents | books
);

This schema maps cleanly to your graph logic.

18) Incremental Re-Crawl Scheduler (Change Detection)
Don’t rescrape everything.
def should_recrawl(last_seen, interval_days=14):
    return (datetime.utcnow() - last_seen).days >= interval_days

Used per:
artist
manager
platform

19) Text Embedding Similarity for Manager Matching
Catches:
“XYZ Management” vs “XYZ Mgmt LLC”
from sklearn.metrics.pairwise import cosine_similarity

def is_same_manager(vec1, vec2, threshold=0.85):
    return cosine_similarity([vec1], [vec2])[0][0] > threshold

You embed:
bio text
about pages
company descriptions
(Any embedding model works.)

20) Evidence-Weighted Entity Merge
Prevents over-merging.
def merge_entities(e1, e2, confidence):
    if confidence < 70:
        return None
    return {
        "merged": True,
        "source": e1["id"],
        "target": e2["id"],
        "confidence": confidence
    }


21) Search Index (Fast Lookup for Outreach Ops)
Local, no Elasticsearch required.
from collections import defaultdict

SEARCH_INDEX = defaultdict(set)

def index_contact(email, artist, manager):
    SEARCH_INDEX[email].add((artist, manager))

def search_email(email):
    return SEARCH_INDEX.get(email, [])


22) Webhook Ingestion (External Signals)
Lets you plug in:
Google Alerts
RSS
Zapier
Manual tips
from flask import Flask, request

app = Flask(__name__)

@app.route("/ingest", methods=["POST"])
def ingest():
    payload = request.json
    enqueue(lambda: process_payload(payload))
    return {"status": "ok"}


23) Confidence Decay Over Time
Old data becomes weaker.
def decay_confidence(score, last_seen):
    days = (datetime.utcnow() - last_seen).days
    return max(0, score - days // 30 * 5)


24) Per-Manager Outreach Throttle
Not per email — per entity.
MANAGER_TOUCHES = {}

def manager_can_receive(manager_id, max_per_month=2):
    touches = MANAGER_TOUCHES.get(manager_id, [])
    recent = [t for t in touches if (datetime.utcnow()-t).days < 30]
    return len(recent) < max_per_month


25) Automatic “Wrong Contact” Detection
If they reply “not me”, learn.
def downgrade_contact(email):
    contact = CONTACTS[email]
    contact["confidence"] = max(0, contact["confidence"] - 40)
    contact["tier"] = "DO_NOT_CONTACT"


26) Artist ↔ Manager Drift Timeline
Historical tracking.
def record_relationship(entity_a, entity_b, start):
    return {
        "from": entity_a,
        "to": entity_b,
        "start": start,
        "end": None
    }


27) Observability: Pipeline Health Metrics
You want to know when things break.
METRICS = {
    "scrape_failures": 0,
    "emails_found": 0,
    "clusters_formed": 0
}

def metric(name, inc=1):
    METRICS[name] += inc


28) Source Trust Calibration
Some sources lie more than others.
SOURCE_TRUST = {
    "official_site": 1.0,
    "social_bio": 0.8,
    "mirror": 0.6,
    "forum": 0.4
}

def weighted_signal(source):
    return SOURCE_TRUST.get(source, 0.3)


29) Cold-Start Safe Mode
When system confidence is low.
def safe_mode(cluster):
    return (
        cluster["resolution_confidence"] < 60 or
        max(c["confidence"] for c in cluster["scored_emails"]) < 70
    )


30) End-to-End “Send Readiness” Gate
Final arbiter before outreach.
def ready_to_send(cluster):
    top = cluster["scored_emails"][0]
    return (
        top["confidence"] >= 70 and
        manager_can_receive(cluster["manager_id"]) and
        not safe_mode(cluster)
    )


What You’ve Now Built (Objectively)
You now have code for:
async crawling
entity persistence
similarity resolution
ingestion from outside world
trust calibration
temporal decay
outreach safety
observability
historical relationship tracking
fail-safe controls
This is well beyond a scraper — this is a contact intelligence + outreach orchestration platform.


