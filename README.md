# Decision Maker Discovery Engine

## Product Overview

### Vision Statement
The Decision Maker Discovery Engine automates the discovery of business decision-makers across five social and business platforms: LinkedIn, Google Maps, Yelp, Facebook, and Instagram. Users upload CSV files containing Google Maps business listings; the system hunts down executives, founders, and key personnel using AI-powered analysis of public platform data.

### Product Type
SaaS web application with freemium subscription model. Users access through browser interface; no mobile apps in initial release.

### Target Market
B2B lead generation agencies, sales development representatives, recruiters, business development teams, and marketing agencies requiring contact enrichment at scale.

## Success Metrics

### Primary KPIs
- Decision-maker discovery rate: 70%+ of companies yield at least one verified decision-maker
- Average confidence score: 75+ out of 100
- Processing speed: 50 companies per hour per worker instance
- User retention: 60% monthly active user retention after month three
- Cost per lead: under $0.50 per discovered decision-maker

### Secondary KPIs
- Platform success distribution: LinkedIn 85%, Google Maps 45%, Yelp 30%, Facebook 25%, Instagram 20%
- Average decision-makers per company: 2.3
- Export completion rate: 80% of jobs result in downloaded export file
- API error rate: under 5%
- System uptime: 99.5%

## Tech Stack (Proposed)
- **Frontend**: React (Vite), Tailwind CSS
- **Backend**: Python (FastAPI)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **AI/Scraping**: Playwright/Selenium, OpenAI API (or similar) for analysis
