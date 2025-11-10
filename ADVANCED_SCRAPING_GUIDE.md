# Advanced Contact Discovery & Scraping Strategies

## 🔒 OSS Platform Alternatives

### Privacy-Focused Scraping
Using open-source alternatives to avoid rate limits and privacy concerns:

- **Nitter** (Twitter/X): `nitter.net`, `nitter.it`, `nitter.unixfox.eu`
- **Proxigram** (Instagram): `proxigram.lunar.icu`, `proxigram.privacy.com.de`  
- **ProxiTok** (TikTok): `proxitok.pabloferreiro.es`, `tok.habedieeh.re`

```bash
POST /advanced-scrapers/oss-platforms
{
  "query": "hip hop curator booking press",
  "platforms": ["twitter", "instagram", "tiktok"],
  "max_per_platform": 25
}
```

## 🎯 Advanced Marketing Strategies

### 1. MusicBrainz/Discogs Manager Credits
Extract manager credits from release metadata:
```bash
POST /advanced-scrapers/advanced-marketing
{
  "artist_name": "Artist Name",
  "strategies": ["musicbrainz"]
}
```

### 2. LinkedIn Professional Search
Target music industry professionals:
- A&R Representatives
- Music Managers  
- Publicists
- Music Supervisors
- Booking Agents

### 3. YouTube About Page Extraction
Parse YouTube channel About pages for business emails with obfuscation handling.

### 4. Artist Team Page Scraping
Crawl official artist websites for team/management pages.

### 5. Press Kit PDF Mining
Search and parse press kit PDFs for contact information.

## 🎪 Niche Discovery Strategies

### Reddit/Discord Submissions
Monitor music subreddits for submission posts:
- `/r/hiphopheads`
- `/r/makinghiphop` 
- `/r/trapproduction`
- `/r/WeAreTheMusicMakers`

### Podcast Guest Credits
Scrape hip-hop podcast episodes for guest manager/publicist mentions.

### Venue Booking Pages
Extract manager contacts from venue booking rosters.

### Radio Station Contacts
Target college and local radio program directors.

### PR Firm Client Lists
Scrape PR firm case studies and client portfolios.

## 🚀 Predefined Presets

### Hip-Hop Comprehensive Discovery
```bash
POST /advanced-scrapers/run-preset/hip_hop_comprehensive
{
  "artist_name": "Your Artist",
  "city": "Los Angeles"
}
```

Complete contact discovery including:
- OSS platform bio scraping
- MusicBrainz manager credits
- LinkedIn professional search
- YouTube channel contacts
- Reddit submission posts
- Podcast mentions
- Venue bookings
- Radio contacts

### Playlist Curator Focus
```bash
POST /advanced-scrapers/run-preset/playlist_curator_focus
```

Targets specifically:
- Playlist curator Twitter bios
- Instagram business profiles
- YouTube playlist channels
- Reddit playlist submission posts

### Press & Media Contacts
```bash
POST /advanced-scrapers/run-preset/press_and_media
```

Focuses on:
- Music press Twitter accounts
- LinkedIn publicist search
- Press kit contacts
- Podcast industry mentions
- PR firm client lists

### Local Market Penetration
```bash
POST /advanced-scrapers/run-preset/local_market_penetration
{
  "city": "Nashville"
}
```

Targets local:
- Venue booking contacts
- Radio station directors
- Local podcast mentions

## 🔧 Advanced Techniques

### Cross-Platform Username Resolution
Resolve usernames across platforms to find business contacts:
```
Instagram @username → Twitter @username → Bandcamp profile → Business email
```

### Email Pattern Inference
Generate email patterns from company domains:
```
Company: "Indie Music Group"
Patterns: first.last@indiemusicgroup.com, firstname@img.com
```

### Bio Keyword Analysis
Search for specific terms in bios:
- "bookings"
- "press" 
- "manager"
- "submissions"
- "business inquiries"

### Contact Button Harvesting
Extract Instagram/Facebook business contact buttons via public APIs.

### Obfuscated Email Detection
Handle common email obfuscation:
- `contact[at]domain[dot]com`
- `contact @ domain . com`
- `contact (at) domain (dot) com`

## 📊 Success Metrics

### Quality Indicators
- **Business Email Ratio**: % of emails that are business vs personal
- **Contact Type Accuracy**: Correct classification of contact roles
- **Response Rate**: % of contacts that respond to outreach
- **Conversion Rate**: % that result in playlist adds/bookings

### Volume Metrics
- **Contacts per Hour**: Scraping efficiency
- **Unique Contacts**: Deduplicated contact count
- **Platform Coverage**: Number of platforms scraped
- **Geographic Spread**: Contact distribution by location

## 🛡️ Anti-Detection Measures

### Request Patterns
- Random delays between requests (0.5-2.0 seconds)
- User-agent rotation
- Proxy rotation
- Request fingerprinting prevention

### Rate Limiting
- Respect robots.txt
- Monitor response codes for rate limiting
- Exponential backoff on failures
- Distributed scraping across instances

### Content Parsing
- Handle JavaScript-rendered content
- Parse multiple content formats
- Extract from PDF metadata
- Handle CAPTCHA challenges

## 🔄 Automation Workflows

### Daily Discovery Pipeline
1. **Morning**: Run OSS platform scraping for trending hashtags
2. **Afternoon**: LinkedIn professional search for new contacts  
3. **Evening**: Process and deduplicate results
4. **Night**: Email validation and enrichment

### Weekly Deep Dive
1. **Monday**: MusicBrainz new release credits
2. **Wednesday**: Venue booking page updates
3. **Friday**: PR firm client list refresh
4. **Sunday**: Reddit/Discord submission monitoring

### Campaign-Triggered Discovery
1. **Pre-Release**: Team page and press kit scraping
2. **Release Week**: Playlist curator intensive search
3. **Post-Release**: Podcast and media contact discovery

## 📈 Optimization Tips

### High-Value Targets
1. **Verified Accounts**: Higher response rates
2. **Recent Activity**: Active within 30 days
3. **Follower Count**: 1K-100K sweet spot
4. **Bio Keywords**: Contains submission terms
5. **Business Profiles**: Instagram/Facebook business accounts

### Geographic Targeting
- **Local First**: Start with artist's home market
- **Genre Hubs**: Nashville (country), Atlanta (hip-hop), LA (pop)
- **College Towns**: University radio stations
- **Festival Cities**: SXSW (Austin), CMJ (NYC)

### Timing Optimization
- **Best Days**: Tuesday-Thursday
- **Best Times**: 10AM-2PM, 6PM-8PM local time
- **Avoid**: Mondays, Fridays after 3PM, weekends
- **Seasonal**: Avoid December holidays, summer vacation

## 🚨 Compliance & Ethics

### Data Privacy
- Respect GDPR/CCPA requirements
- Provide opt-out mechanisms
- Store minimal necessary data
- Regular data purging

### Platform Terms
- Respect robots.txt files
- Follow rate limiting guidelines
- Use official APIs when available
- Avoid scraping private content

### Email Compliance
- CAN-SPAM Act compliance
- Include unsubscribe links
- Accurate sender information
- No misleading subject lines

## 🔗 Integration Examples

### n8n Workflow
```json
{
  "nodes": [
    {
      "name": "Trigger Advanced Scraping",
      "type": "HTTP Request",
      "parameters": {
        "method": "POST",
        "url": "{{$env.API_URL}}/advanced-scrapers/run-preset/hip_hop_comprehensive",
        "body": {
          "artist_name": "{{$json.artist_name}}",
          "city": "{{$json.city}}"
        }
      }
    },
    {
      "name": "Wait for Completion",
      "type": "Wait",
      "parameters": {
        "amount": 10,
        "unit": "minutes"
      }
    },
    {
      "name": "Export Results",
      "type": "HTTP Request",
      "parameters": {
        "method": "POST",
        "url": "{{$env.API_URL}}/export/contacts",
        "body": {
          "format": "csv",
          "filters": {
            "created_at_gte": "{{$now}}"
          }
        }
      }
    }
  ]
}
```

### Zapier Integration
```javascript
// Trigger advanced scraping on new release
const response = await fetch(`${bundle.authData.api_url}/advanced-scrapers/run-preset/playlist_curator_focus`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${bundle.authData.jwt_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    artist_name: inputData.artist_name
  })
});
```

## 📞 Support & Resources

- **API Documentation**: `/docs` (Swagger UI)
- **Strategy Guide**: This document
- **Best Practices**: Contact team for consultation
- **Custom Strategies**: Available for enterprise clients
