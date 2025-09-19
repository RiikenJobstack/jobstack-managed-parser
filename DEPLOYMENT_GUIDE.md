# 🚀 Google Cloud Run Deployment Guide
## Resume Parser API - Manual Deployment

This guide will help you deploy your production-ready Resume Parser API to Google Cloud Run using the web console (no CLI required).

---

## 📋 Prerequisites

### 1. Google Cloud Account Setup
- [ ] Google Cloud account with billing enabled
- [ ] Create a new project or use existing one
- [ ] Note your project ID (e.g., `resume-parser-prod-123`)

### 2. Required APIs (Enable in Google Cloud Console)
- [ ] **Cloud Run API**: `https://console.cloud.google.com/apis/library/run.googleapis.com`
- [ ] **Container Registry API**: `https://console.cloud.google.com/apis/library/containerregistry.googleapis.com`
- [ ] **Vertex AI API**: `https://console.cloud.google.com/apis/library/aiplatform.googleapis.com`
- [ ] **Document AI API**: `https://console.cloud.google.com/apis/library/documentai.googleapis.com`

### 3. Service Account Setup
1. Go to **IAM & Admin > Service Accounts**
2. Click **Create Service Account**
3. Name: `resume-parser-service`
4. Add these roles:
   - `Cloud Run Developer`
   - `Vertex AI User`
   - `Document AI API User`
   - `Storage Object Viewer` (if using GCS)
5. Download the JSON key file

---

## 🛠️ Pre-Deployment Setup

### 1. Prepare Your Environment Variables
Copy `.env.production` to `.env` and fill in your actual values:

```bash
# Required - Get from your providers
GEMINI_API_KEY=AIzaSyD...your_actual_key
AWS_ACCESS_KEY_ID=AKIA...your_actual_key
AWS_SECRET_ACCESS_KEY=your_actual_secret
JWT_SECRET_KEY=your_super_secure_secret_key

# Google Cloud (will be set automatically in Cloud Run)
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_DOCUMENTAI_PROCESSOR_ID=your_processor_id

# Optional - Customize if needed
ALLOWED_ORIGINS=https://yourdomain.com,https://staging.yourdomain.com
```

### 2. Test Locally (Optional)
```bash
cd managed_services
python app.py
# Test at http://localhost:8000/health
```

---

## 📦 Deployment Steps

### Step 1: Create Container Repository

1. **Go to Container Registry**
   - Navigate: `https://console.cloud.google.com/gcr`
   - Or search "Container Registry" in the console

2. **Enable Container Registry**
   - Click "Enable" if prompted
   - This creates a storage bucket for your images

### Step 2: Build and Push Container (Web-based)

You have two options for building:

#### Option A: Cloud Build (Recommended)
1. **Go to Cloud Build**
   - Navigate: `https://console.cloud.google.com/cloud-build`

2. **Create Trigger**
   - Click "Create Trigger"
   - Source: Connect your GitHub repo or upload ZIP
   - Configuration: Dockerfile
   - Dockerfile path: `managed_services/Dockerfile`
   - Build context: `managed_services/`

3. **Run Build**
   - Click "Run Trigger"
   - Wait for build to complete (~5-10 minutes)
   - Note the image URL: `gcr.io/[PROJECT-ID]/resume-parser:latest`

#### Option B: Local Build + Upload
If you have Docker installed locally:
```bash
cd managed_services
docker build -t gcr.io/[YOUR-PROJECT-ID]/resume-parser:latest .
docker push gcr.io/[YOUR-PROJECT-ID]/resume-parser:latest
```

### Step 3: Create Cloud Run Service

1. **Go to Cloud Run**
   - Navigate: `https://console.cloud.google.com/run`

2. **Create Service**
   - Click "Create Service"
   - Container image URL: `gcr.io/[YOUR-PROJECT-ID]/resume-parser:latest`
   - Service name: `resume-parser-api`
   - Region: Choose closest to your users (e.g., `us-central1`)

3. **Configure Service**

   **Container Tab:**
   - CPU allocation: `1 vCPU`
   - Memory: `2 GiB`
   - Port: `8000`
   - Startup timeout: `300 seconds`

   **Variables & Secrets Tab:**
   - Add all environment variables from your `.env` file
   - For Google credentials: Add as secret (see Step 4)

   **Connections Tab:**
   - CPU throttling: `No throttling`
   - Concurrency: `100`
   - Minimum instances: `1` (to reduce cold starts)
   - Maximum instances: `100`

4. **Authentication**
   - Select "Allow unauthenticated invocations" (your app handles auth internally)

5. **Click Create**

### Step 4: Add Google Cloud Credentials Secret

1. **Go to Secret Manager**
   - Navigate: `https://console.cloud.google.com/security/secret-manager`
   - Click "Create Secret"

2. **Create Credential Secret**
   - Name: `google-cloud-credentials`
   - Secret value: Upload your service account JSON file
   - Click "Create"

3. **Mount Secret in Cloud Run**
   - Go back to your Cloud Run service
   - Click "Edit & Deploy New Revision"
   - Go to "Variables & Secrets" tab
   - Click "Add Secret"
   - Select: `google-cloud-credentials`
   - Mount path: `/secrets/google-credentials/key.json`
   - Add environment variable:
     ```
     GOOGLE_APPLICATION_CREDENTIALS=/secrets/google-credentials/key.json
     ```

### Step 5: Final Configuration

1. **Update Environment Variables**
   ```
   USE_PROMPT_CACHING=true
   RESULT_CACHE_ENABLED=true
   RESULT_CACHE_TTL=14400
   NODE_ENV=production
   LOG_LEVEL=INFO
   ```

2. **Deploy Revision**
   - Click "Deploy"
   - Wait for deployment (~2-3 minutes)

---

## ✅ Post-Deployment Verification

### 1. Test Your Endpoints

**Health Check:**
```bash
curl https://[YOUR-SERVICE-URL]/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": 1695123456.789,
  "stats": {...},
  "cache": {...},
  "environment": {
    "gemini_configured": true,
    "aws_configured": true,
    "auth_configured": true,
    "prompt_caching_enabled": true
  }
}
```

**API Info:**
```bash
curl https://[YOUR-SERVICE-URL]/
```

### 2. Test Resume Parsing (Without Auth)
```bash
curl -X POST https://[YOUR-SERVICE-URL]/parse-resume-test \
  -F "file=@sample-resume.pdf"
```

### 3. Test with Authentication
```bash
curl -X POST https://[YOUR-SERVICE-URL]/parse-resume \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@sample-resume.pdf"
```

---

## 🔧 Configuration Guide

### Cost Optimization Settings

**Prompt Caching (89% cost reduction):**
```
USE_PROMPT_CACHING=true
```

**Result Caching (100% cost savings on duplicates):**
```
RESULT_CACHE_ENABLED=true
RESULT_CACHE_TTL=14400  # 4 hours
```

### Scaling Configuration

**For High Traffic:**
- CPU: 2 vCPU
- Memory: 4 GiB
- Max instances: 300
- Min instances: 5

**For Cost Optimization:**
- CPU: 1 vCPU
- Memory: 2 GiB
- Max instances: 50
- Min instances: 0

### CORS Configuration

**Option 1: Environment Variable**
```
ALLOWED_ORIGINS=https://yourdomain.com,https://staging.yourdomain.com
```

**Option 2: Automatic (uses managed origins)**
Leave `ALLOWED_ORIGINS` unset to use the built-in origins.

---

## 📊 Monitoring & Logs

### 1. View Logs
- Go to Cloud Run service
- Click "Logs" tab
- Filter by severity: Error, Warning, Info

### 2. Monitor Performance
- Click "Metrics" tab
- Monitor:
  - Request count
  - Request latency
  - Error rate
  - Memory utilization

### 3. Set Up Alerts
- Go to Cloud Monitoring
- Create alerting policies for:
  - High error rate (>5%)
  - High latency (>30s)
  - Memory usage (>80%)

---

## 🚨 Troubleshooting

### Common Issues

**1. Container fails to start**
- Check logs for import errors
- Verify all dependencies in `requirements.txt`
- Ensure environment variables are set

**2. 503 Service Unavailable**
- Increase startup timeout to 300s
- Check if service is scaling up
- Verify health check endpoint

**3. Authentication errors**
- Verify JWT_SECRET_KEY is set correctly
- Check CORS origins configuration
- Ensure proper Authorization header format

**4. Gemini API errors**
- Verify GEMINI_API_KEY is correct
- Check Google Cloud credentials mount
- Ensure Vertex AI API is enabled

**5. Out of memory errors**
- Increase memory allocation to 4 GiB
- Monitor memory usage in metrics
- Check for memory leaks in logs

### Performance Issues

**Slow response times:**
1. Enable prompt caching: `USE_PROMPT_CACHING=true`
2. Increase min instances to reduce cold starts
3. Use result caching for duplicate files

**High costs:**
1. Enable both caching mechanisms
2. Set appropriate result cache TTL
3. Monitor usage in billing dashboard

---

## 🔒 Security Best Practices

### 1. Environment Variables
- Never commit `.env` files to version control
- Use Cloud Run secrets for sensitive data
- Rotate API keys regularly

### 2. Service Account
- Use least-privilege principle
- Create dedicated service account
- Regular security audits

### 3. Network Security
- Configure CORS properly
- Use HTTPS only (automatic in Cloud Run)
- Implement rate limiting if needed

---

## 📈 Production Checklist

- [ ] All APIs enabled in Google Cloud
- [ ] Service account created with proper roles
- [ ] Environment variables configured
- [ ] Google credentials mounted as secret
- [ ] Health check passing
- [ ] CORS configured for your domains
- [ ] Monitoring and alerting set up
- [ ] Cost optimization enabled (caching)
- [ ] Security review completed
- [ ] Load testing performed
- [ ] Documentation updated

---

## 💰 Cost Estimation

**Monthly costs for 10,000 requests/month:**

**Base Cloud Run:**
- CPU-time: ~$15-30/month
- Memory: ~$5-10/month
- Requests: ~$1/month

**AI Processing:**
- Without caching: ~$200-400/month
- With prompt caching: ~$25-50/month
- With result caching: ~$10-25/month

**Total estimated cost: $50-100/month** (with optimizations)

---

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review Cloud Run logs for error messages
3. Verify all environment variables are set correctly
4. Test locally first to isolate deployment issues

Your Resume Parser API is now ready for production! 🎉