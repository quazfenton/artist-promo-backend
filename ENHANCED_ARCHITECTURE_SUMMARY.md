# Enhanced Pipeline Architecture Summary

## Overview
The artist promotion backend has been significantly enhanced with a comprehensive pipeline architecture that includes:

## 1. Evidence Ledger System (`app/utils/evidence_ledger.py`)
- Machine-auditable evidence tracking for email validity
- Trust score calculation based on accumulated evidence
- Audit trails for legal defensibility
- Explainable automation through evidence logging

## 2. Email Canonicalization & Domain Reputation (`app/utils/email_canonicalization.py`)
- Normalization of email aliases (press@, booking@, mgmt@ → official@)
- Domain-level reputation tracking
- Send rate limiting to avoid domain burnout
- MX record and role account detection
- Business vs consumer email classification

## 3. Link-in-Bio Recursive Resolver (`app/utils/link_in_bio_resolver.py`)
- Recursive resolution of link-in-bio platforms (Linktree, Bio.fm, etc.)
- Email extraction from bio pages
- Social media link discovery
- Contact info aggregation from multiple sources
- Support for common link-in-bio platforms

## 4. Temporal Signal Strength & Freshness (`app/utils/temporal_scoring.py`)
- Freshness-weighted scoring based on signal recency
- Confidence decay over time
- Temporal consistency scoring
- Optimal refresh interval suggestions
- Signal recency categorization

## 5. Manager Resolution & Clustering (`app/utils/manager_resolution.py`)
- Manager resolution confidence calculation
- Contact surface area metrics
- Manager archetype classification (Agency, Boutique, Solo)
- Entity merge confidence scoring
- Manager change detection
- Cluster stability analysis
- Influence score calculation

## 6. Async Scraping & Enrichment Executor (`app/utils/async_scraping.py`)
- Concurrent scraping across multiple platforms
- Rate limiting and request throttling
- Platform-specific scrapers (Nitter, Invidious, Imginn, ProxiTok, Libreddit)
- Fallback URL handling
- Batch scraping with controlled concurrency
- Enrichment pipeline execution

## 7. Pipeline Orchestrator & State Machine (`app/utils/pipeline_orchestrator.py`)
- Multi-stage pipeline with state transitions
- Signal normalization
- Entity resolution and deduplication
- Cluster analysis
- Quality scoring
- Risk assessment
- State management for each stage

## 8. Search Index & Webhook Ingestion (`app/utils/search_and_ingestion.py`)
- Fast local search index for contacts
- Webhook ingestion system for external signals
- Outbound cooldown scheduling
- Pipeline health monitoring
- Duplicate detection
- Fuzzy search capabilities

## 9. Confidence Decay & Trust Calibration (`app/utils/confidence_calibration.py`)
- Temporal confidence decay management
- Source trust calibration based on reliability
- Wrong contact detection and handling
- Manager relationship drift tracking
- Cold start safety mechanisms
- Send readiness gates

## 10. API Endpoints Added
- `POST /ingest` - Webhook endpoint for external signal ingestion
- `POST /search/indexed` - Search contacts in local index

## 11. Enhanced Worker Architecture
- Scrape Worker - processes scraping jobs from queue
- Signal Normalizer Worker - normalizes raw signals to staging contacts
- Entity Resolver Worker - deduplicates and enriches contacts
- Graph Builder Worker - builds relationship graphs
- Outreach Worker - makes decisions and sends communications

## 12. Database Enhancements
- Staging tables for pipeline processing
- Evidence tracking tables
- Cluster analysis results
- Job tracking and monitoring

## 13. Quality Assurance Features
- Comprehensive integration tests
- Error handling and logging
- Performance monitoring
- Configuration validation
- Health checks for dependencies

## Benefits of the Enhanced Architecture

### Scalability
- Queue-based processing allows horizontal scaling
- Async operations maximize throughput
- Rate limiting prevents API abuse

### Reliability
- Evidence-based trust system
- Temporal decay prevents stale data usage
- Duplicate detection and prevention
- Error recovery and retry mechanisms

### Maintainability
- Modular architecture with clear separation of concerns
- Comprehensive logging and monitoring
- Configuration validation
- Test coverage for critical components

### Effectiveness
- Manager clustering identifies relationship patterns
- Confidence scoring prioritizes high-value contacts
- Domain reputation prevents spam trap hits
- Temporal awareness keeps data fresh

## Integration Points
- Backward compatible with existing API endpoints
- n8n integration maintained
- CLI tools updated for new functionality
- Database schema extended without breaking changes

This enhanced architecture transforms the system from a simple scraper into a comprehensive contact intelligence and outreach orchestration platform.