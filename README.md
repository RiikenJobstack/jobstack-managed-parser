# 📄 Resume Parser API

Production-ready resume parsing service with AI normalization, caching, and authentication.

## 🚀 Features

- **Multi-format Support**: PDF, DOC, DOCX, PNG, JPG, JPEG
- **AI-Powered**: Google Gemini for intelligent text normalization
- **Cost Optimized**: 89% cost reduction with prompt caching + 100% savings on duplicates
- **Production Ready**: JWT authentication, CORS, monitoring, health checks
- **High Performance**: 15-second target response time, 100+ concurrent users
- **Smart Caching**: Result cache + Vertex AI prompt cache

## 📊 Performance Metrics

- **Response Time**: 15 seconds target (0.001s for cache hits)
- **Concurrency**: 100+ users
- **File Size Limit**: 10MB
- **Cost Reduction**: Up to 95% with dual caching
- **Uptime**: 99.9% (Google Cloud Run SLA)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │───▶│  Resume Parser  │───▶│   AI Services   │
│   (CORS)        │    │     API         │    │   (Cached)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Result Cache   │
                       │  (4 hour TTL)   │
                       └─────────────────┘
```

## 🔧 Quick Start

### 1. Local Development
```bash
# Clone and setup
cd managed_services
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.production .env
# Edit .env with your API keys

# Run
python app.py
```

### 2. Test Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Test parsing (no auth)
curl -X POST http://localhost:8000/parse-resume-test \
  -F "file=@sample-resume.pdf"

# Authenticated parsing
curl -X POST http://localhost:8000/parse-resume \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@sample-resume.pdf"
```

## 📚 API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | ❌ | API information |
| `/health` | GET | ❌ | Health check + stats |
| `/parse-resume` | POST | ✅ | Main parsing endpoint |
| `/parse-resume-test` | POST | ❌ | Test endpoint (dev only) |
| `/cache/stats` | GET | ❌ | Cache statistics |
| `/cache/clear` | POST | ❌ | Clear cache |
| `/secure/origin-test` | GET | ❌ | Origin validation test |

## 🔐 Authentication

Uses JWT Bearer tokens:
```bash
curl -X POST /parse-resume \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -F "file=@resume.pdf"
```

## 🎯 Response Format

```json
{
  "success": true,
  "data": {
    "content": {
      "personalInfo": {
        "fullName": "John Doe",
        "email": "john@example.com",
        "phone": "+1-555-0123",
        "location": "New York, NY",
        "linkedIn": "linkedin.com/in/johndoe"
      },
      "experience": [...],
      "education": [...],
      "skills": {...}
    },
    "parseMetadata": {
      "confidence": 0.95,
      "parseTime": 12.5,
      "processing_status": {
        "status": "success",
        "cached": false
      },
      "cost": {
        "total_cost_usd": 0.002,
        "total_cost_inr": 0.17
      }
    }
  },
  "metadata": {
    "filename": "resume.pdf",
    "processing_time_seconds": 12.5,
    "user_id": "user123",
    "origin": "https://yourdomain.com"
  }
}
```

## 💰 Cost Optimization

### Prompt Caching (89% reduction)
```bash
USE_PROMPT_CACHING=true
```
- First request: Full cost
- Subsequent requests: 89% discount
- Cache duration: 23 hours

### Result Caching (100% savings)
```bash
RESULT_CACHE_ENABLED=true
RESULT_CACHE_TTL=14400  # 4 hours
```
- Duplicate files: 0.001s response time
- 100% cost savings on cache hits

## 🌐 CORS Configuration

### Environment-based Origins
```bash
ALLOWED_ORIGINS=https://yourdomain.com,https://staging.yourdomain.com
```

### Managed Origins (default)
- `https://jobstackuidev-gwakgfdgbgh5emdw.canadacentral-01.azurewebsites.net/`
- `https://jobstackuiuat-cybnbdf8h6gkb7g3.canadacentral-01.azurewebsites.net/`
- `http://localhost:5173`

## 🔧 Configuration

### Required Environment Variables
```bash
# AI Services
GEMINI_API_KEY=your_gemini_key
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret

# Authentication
JWT_SECRET_KEY=your_jwt_secret

# Google Cloud (auto-set in Cloud Run)
GOOGLE_PROJECT_ID=your_project_id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

### Optional Settings
```bash
# Caching
USE_PROMPT_CACHING=true
RESULT_CACHE_ENABLED=true
RESULT_CACHE_TTL=14400

# Performance
LOG_LEVEL=INFO
NODE_ENV=production

# Budget
MONTHLY_BUDGET_INR=5000
```

## 📁 Project Structure

```
managed_services/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── .env.production       # Environment template
├── .gitignore           # Git ignore rules
├── README.md            # This file
├── DEPLOYMENT_GUIDE.md  # Deployment instructions
├── src/
│   ├── auth/           # Authentication middleware
│   │   ├── auth_middleware.py
│   │   └── token_service.py
│   └── parsers/        # Core parsing logic
│       ├── resume_processor.py
│       ├── text_extractor.py
│       ├── gemini_normalizer.py
│       ├── gemini_cached_normalizer.py
│       ├── result_cache.py
│       ├── prompt_cache.py
│       └── token_utils.py
└── credentials/        # Service account keys
    └── google-cloud-service-account.json
```

## 🚀 Deployment

See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for complete Google Cloud Run deployment instructions.

## 📊 Monitoring

### Health Check
```bash
curl https://your-service-url/health
```

### Cache Statistics
```bash
curl https://your-service-url/cache/stats
```

### Key Metrics
- Request count and success rate
- Average processing time
- Cache hit ratio
- Cost savings (USD/INR)
- Memory and CPU usage

## 🚨 Error Handling

### Structured Error Response
```json
{
  "success": false,
  "error": {
    "message": "File too large (max 10MB)",
    "filename": "large-resume.pdf",
    "processing_time_seconds": 0.1,
    "timestamp": 1695123456.789
  },
  "data": {
    "personalInfo": {...},  // Empty structure
    "parseMetadata": {
      "processing_status": {
        "status": "failed",
        "can_retry": true,
        "retry_suggestions": [...]
      }
    }
  }
}
```

### Retry Logic
- Failed results are NOT cached
- Use `?fresh=true` to bypass cache
- Clear retry suggestions in error response

## 🛠️ Development

### Setup
```bash
git clone <repository>
cd managed_services
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.production .env
# Edit .env with your keys
python app.py
```

### Testing
```bash
# Test with sample file
curl -X POST http://localhost:8000/parse-resume-test \
  -F "file=@test.pdf"

# Test caching
curl -X POST http://localhost:8000/parse-resume-test \
  -F "file=@test.pdf" \
  -F "fresh=false"
```

### Debug Mode
```bash
LOG_LEVEL=DEBUG python app.py
```

## 📜 License

Private project - All rights reserved.

## 🆘 Support

For deployment issues, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) troubleshooting section.