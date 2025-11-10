# Artist Promo Backend - API Guide

## 🚀 Enhanced API Features

The API now includes comprehensive features for contact management, campaign automation, analytics, and integrations.

## 🔐 Authentication

All endpoints require JWT authentication (except auth endpoints).

```bash
# Login to get token
POST /auth/login
{
  "email": "user@example.com",
  "password": "password"
}

# Use token in subsequent requests
Authorization: Bearer <jwt_token>
```

## 📊 Advanced Search & Filtering

### Search Contacts
```bash
POST /search/contacts
{
  "query": "hip hop curator",
  "filters": {
    "contact_type": "playlist_curator",
    "min_score": 80,
    "min_followers": 1000,
    "verified_only": true,
    "genres": ["hip-hop", "rap"]
  },
  "sort_by": "priority_score",
  "sort_order": "desc",
  "limit": 100,
  "offset": 0
}
```

### Get Search Suggestions
```bash
GET /search/suggestions?q=hip
# Returns: {"names": ["Hip Hop Central", "Hip Hop Nation"], "companies": [...]}
```

## 📤 Enhanced Export System

### Export Contacts (Multiple Formats)
```bash
POST /export/contacts
{
  "format": "excel",  # csv, json, excel
  "filters": {
    "contact_type": "playlist_curator",
    "min_score": 70
  },
  "fields": ["full_name", "email", "priority_score", "follower_count"],
  "async_export": true  # For large datasets
}
```

### Get Export Templates
```bash
GET /export/templates
# Returns predefined export configurations
```

### Available Export Fields
```bash
GET /export/fields
# Returns all available fields with types and descriptions
```

## 📧 Campaign Management

### Create Email Campaign
```bash
POST /campaigns/
{
  "name": "Hip-Hop Curator Outreach Q4",
  "description": "Targeting high-priority playlist curators",
  "subject_template": "New Hip-Hop Release: {{artist_name}} - {{track_title}}",
  "body_template": "Hi {{contact_name}}, I hope this finds you well...",
  "target_filters": {
    "contact_type": "playlist_curator",
    "min_score": 80,
    "min_followers": 1000
  }
}
```

### Send Campaign
```bash
POST /campaigns/{campaign_id}/send
# Queues emails for background sending
```

### Campaign Analytics
```bash
GET /campaigns/{campaign_id}/analytics
# Returns detailed metrics: open rates, click rates, replies, etc.
```

## 📈 Analytics & Reporting

### Dashboard Statistics
```bash
GET /analytics/dashboard
# Returns: totals, breakdowns by platform/type, growth metrics
```

### Contact Growth Trends
```bash
GET /analytics/contacts/trends?days=30
# Returns daily addition trends and platform breakdown
```

### Data Quality Metrics
```bash
GET /analytics/quality
# Returns completeness rates, score distribution, verification stats
```

### Top Performers
```bash
GET /analytics/top-performers?limit=20&metric=priority_score
# Returns highest scoring contacts
```

## 🔄 Background Task Management

### Queue Scraping Task
```bash
POST /tasks/scrape
{
  "task_type": "spotify",
  "priority": "high",
  "params": {
    "genre": "hip-hop",
    "min_followers": 1000,
    "limit": 100
  }
}
```

### Check Task Status
```bash
GET /tasks/status/{task_id}
# Returns: status, progress, results
```

### Monitor Queue Health
```bash
GET /tasks/queue-status
# Returns: active workers, task counts, queue breakdown
```

## 🪝 Webhook Management

### Create Webhook
```bash
POST /webhooks/
{
  "name": "n8n Integration",
  "url": "https://n8n.example.com/webhook/artist-promo",
  "events": ["contact.created", "scraper.completed"],
  "secret": "webhook_secret_key"
}
```

### Test Webhook
```bash
POST /webhooks/{webhook_id}/test
# Sends test payload to verify webhook endpoint
```

### Webhook Delivery History
```bash
GET /webhooks/{webhook_id}/deliveries
# Returns delivery attempts, success/failure rates
```

### Available Events
```bash
GET /webhooks/events/available
# Returns all webhook events with payload examples
```

## 🎯 Advanced Contact Operations

### Bulk Score Update
```bash
POST /contacts/bulk-score-update
{
  "updates": [
    {"contact_id": 1, "priority_score": 85.5},
    {"contact_id": 2, "priority_score": 92.0}
  ]
}
```

### Contact Deduplication
```bash
POST /contacts/deduplicate
# Finds and merges duplicate contacts based on email
```

### Contact Audit Trail
```bash
GET /contacts/{contact_id}/audit
# Returns complete change history for contact
```

## 🔧 Integration Examples

### n8n Workflow Integration
```json
{
  "nodes": [
    {
      "name": "Trigger Scrape",
      "type": "HTTP Request",
      "parameters": {
        "method": "POST",
        "url": "{{$env.API_BASE_URL}}/tasks/scrape",
        "headers": {
          "Authorization": "Bearer {{$env.JWT_TOKEN}}"
        },
        "body": {
          "task_type": "spotify",
          "params": {
            "genre": "hip-hop",
            "min_followers": 1000
          }
        }
      }
    },
    {
      "name": "Check Status",
      "type": "Wait",
      "parameters": {
        "amount": 5,
        "unit": "minutes"
      }
    },
    {
      "name": "Export Results",
      "type": "HTTP Request",
      "parameters": {
        "method": "POST",
        "url": "{{$env.API_BASE_URL}}/export/contacts",
        "body": {
          "format": "csv",
          "filters": {
            "min_score": 80
          }
        }
      }
    }
  ]
}
```

### Zapier Integration
```javascript
// Zapier webhook trigger
const response = await fetch('https://api.artist-promo.com/webhooks/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${bundle.authData.jwt_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'Zapier Integration',
    url: bundle.targetUrl,
    events: ['contact.created', 'campaign.sent']
  })
});
```

## 📊 Response Formats

### Standard Success Response
```json
{
  "status": "success",
  "data": {...},
  "message": "Operation completed successfully"
}
```

### Error Response
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid input parameters",
  "details": {...}
}
```

### Paginated Response
```json
{
  "total": 1500,
  "page": 1,
  "per_page": 100,
  "pages": 15,
  "results": [...],
  "facets": {...}
}
```

## 🚀 Performance Tips

1. **Use Async Exports** for large datasets (>1000 records)
2. **Implement Pagination** for search results
3. **Cache Frequent Queries** using Redis
4. **Use Webhooks** instead of polling for real-time updates
5. **Batch Operations** for bulk updates

## 🔒 Security Best Practices

1. **Rotate JWT Tokens** regularly
2. **Use HTTPS** for all API calls
3. **Validate Webhook Signatures** for security
4. **Rate Limit** API calls to prevent abuse
5. **Monitor API Usage** through analytics

## 📝 Rate Limits

- **General API**: 100 requests/minute per user
- **Search API**: 50 requests/minute per user
- **Export API**: 10 requests/minute per user
- **Webhook Delivery**: 1000 requests/minute per webhook

## 🆘 Error Codes

- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid/expired token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

## 📞 Support

For API support and questions:
- Documentation: `/docs` (Swagger UI)
- Status Page: `/health`
- Support Email: api-support@artist-promo.com
