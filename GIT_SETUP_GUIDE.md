# 📚 Git Repository Setup Guide
## Resume Parser API - Repository Creation & Deployment

This guide will help you create a separate repository for your Resume Parser API and set it up for Google Cloud Run deployment.

---

## 🎯 Step 1: Prepare Your Local Repository

### 1.1 Navigate to Your Project
```bash
cd /Users/riiken/Documents/svsfsfsfsfsf/managed_services
```

### 1.2 Verify Your Files
Make sure you have all the necessary files:
```bash
ls -la
```

**Expected files:**
- ✅ `app.py` - Main application
- ✅ `requirements.txt` - Dependencies
- ✅ `Dockerfile` - Container configuration
- ✅ `.env.production` - Environment template
- ✅ `.gitignore` - Git ignore rules
- ✅ `README.md` - Documentation
- ✅ `DEPLOYMENT_GUIDE.md` - Deployment instructions
- ✅ `src/` - Source code folder
- ✅ `credentials/` - Service account keys (will be ignored by git)

### 1.3 Initialize Git Repository
```bash
# Initialize git in the managed_services folder
git init

# Add all files (credentials will be ignored due to .gitignore)
git add .

# Check what will be committed
git status
```

**Important**: The `.gitignore` file will exclude:
- `.env` files (secrets)
- `credentials/` folder (API keys)
- `venv/` folder (virtual environment)
- Test files and logs

### 1.4 Create Initial Commit
```bash
git commit -m "Initial commit: Production-ready Resume Parser API

- FastAPI application with JWT authentication
- Multi-format resume parsing (PDF, DOC, DOCX, images)
- Google Gemini AI normalization with prompt caching (89% cost reduction)
- Result caching for duplicate files (100% cost savings)
- Origin validation and CORS configuration
- Production-ready Docker configuration
- Complete deployment documentation"
```

---

## 🌐 Step 2: Create GitHub Repository

### 2.1 Create New Repository on GitHub
1. **Go to GitHub**: https://github.com
2. **Click "New repository"** (green button)
3. **Repository details**:
   - **Name**: `resume-parser-api` (or your preferred name)
   - **Description**: `Production-ready Resume Parser API with AI normalization and caching`
   - **Visibility**:
     - ✅ **Private** (recommended for production APIs)
     - ❌ Public (only if you want it open source)
   - **Initialize**:
     - ❌ Don't check "Add a README file" (we have one)
     - ❌ Don't add .gitignore (we have one)
     - ❌ Don't choose a license (add later if needed)

4. **Click "Create repository"**

### 2.2 Connect Local Repository to GitHub
After creating the repository, GitHub will show you commands. Use these:

```bash
# Add GitHub as remote origin
git remote add origin https://github.com/YOUR_USERNAME/resume-parser-api.git

# Verify remote was added
git remote -v

# Push to GitHub
git branch -M main
git push -u origin main
```

**Replace `YOUR_USERNAME`** with your actual GitHub username.

---

## 🔧 Step 3: Set Up Environment Configuration

### 3.1 Create Production Environment File
```bash
# Copy the template to create your actual .env
cp .env.production .env
```

### 3.2 Fill in Your API Keys
Edit the `.env` file with your actual values:

```bash
# Edit the file (use your preferred editor)
nano .env
# OR
code .env
# OR
vim .env
```

**Required values to update:**
```bash
# Replace with your actual keys
GEMINI_API_KEY=AIzaSyD...your_actual_gemini_key
AWS_ACCESS_KEY_ID=AKIA...your_actual_aws_key
AWS_SECRET_ACCESS_KEY=your_actual_aws_secret
JWT_SECRET_KEY=your_super_secure_secret_minimum_32_characters

# Update with your actual Google Cloud project
GOOGLE_PROJECT_ID=your-actual-project-id
GOOGLE_DOCUMENTAI_PROCESSOR_ID=your_actual_processor_id

# Optional: Add your custom domains
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### 3.3 Verify Environment Setup
```bash
# Test locally (optional)
python app.py

# Check health endpoint
curl http://localhost:8000/health
```

**Note**: The `.env` file is already in `.gitignore`, so it won't be committed to GitHub.

---

## 🚀 Step 4: Deploy to Google Cloud Run

### 4.1 Connect GitHub to Google Cloud Build

1. **Go to Google Cloud Console**: https://console.cloud.google.com
2. **Navigate to Cloud Build Triggers**:
   - Search "Cloud Build" → Click "Triggers"
3. **Connect Repository**:
   - Click "Connect Repository"
   - Choose "GitHub (Cloud Build GitHub App)"
   - Authenticate with GitHub
   - Select your `resume-parser-api` repository
   - Click "Connect"

### 4.2 Create Build Trigger

1. **Create Trigger**:
   - Name: `resume-parser-deploy`
   - Event: `Push to a branch`
   - Branch: `^main$` (triggers on main branch)
   - Configuration: `Dockerfile`
   - Dockerfile location: `Dockerfile`
   - Dockerfile directory: `/` (root of repo)

2. **Build Configuration**:
   ```yaml
   # This will be auto-generated, but you can customize if needed
   steps:
   - name: 'gcr.io/cloud-builders/docker'
     args: ['build', '-t', 'gcr.io/$PROJECT_ID/resume-parser:$SHORT_SHA', '.']
   - name: 'gcr.io/cloud-builders/docker'
     args: ['push', 'gcr.io/$PROJECT_ID/resume-parser:$SHORT_SHA']
   ```

3. **Click "Create"**

### 4.3 Deploy to Cloud Run

1. **Go to Cloud Run**: https://console.cloud.google.com/run
2. **Create Service**:
   - Service name: `resume-parser-api`
   - Region: Your preferred region (e.g., `us-central1`)
   - Container image: `gcr.io/YOUR_PROJECT_ID/resume-parser:latest`

3. **Configure Service** (follow DEPLOYMENT_GUIDE.md for detailed settings):
   - CPU: 1 vCPU
   - Memory: 2 GiB
   - Port: 8000
   - Max instances: 100
   - Min instances: 1

### 4.4 Set Environment Variables

In Cloud Run service configuration, add these environment variables:
```bash
USE_PROMPT_CACHING=true
RESULT_CACHE_ENABLED=true
RESULT_CACHE_TTL=14400
NODE_ENV=production
LOG_LEVEL=INFO

# Add your API keys (get them from your local .env file)
GEMINI_API_KEY=your_actual_key
AWS_ACCESS_KEY_ID=your_actual_key
AWS_SECRET_ACCESS_KEY=your_actual_secret
JWT_SECRET_KEY=your_actual_secret
```

### 4.5 Add Google Cloud Credentials

1. **Secret Manager**:
   - Go to Secret Manager in Google Cloud Console
   - Create secret: `google-cloud-credentials`
   - Upload your service account JSON file

2. **Mount in Cloud Run**:
   - In service configuration → Variables & Secrets
   - Add secret as volume mount: `/secrets/google-credentials/key.json`
   - Add environment variable: `GOOGLE_APPLICATION_CREDENTIALS=/secrets/google-credentials/key.json`

---

## 🔄 Step 5: Continuous Deployment Workflow

### 5.1 Development Workflow
```bash
# Make changes to your code
git add .
git commit -m "Add new feature: XYZ"
git push origin main
```

### 5.2 Automatic Deployment
- Push to `main` branch triggers Cloud Build
- Cloud Build creates new container image
- Manually deploy new revision in Cloud Run (or set up automatic deployment)

### 5.3 Manual Deployment Trigger
If you want to trigger deployment manually:
1. Go to Cloud Build → Triggers
2. Find your trigger → Click "Run"
3. Or push a new commit to trigger automatically

---

## 📁 Repository Structure

Your GitHub repository will look like this:

```
resume-parser-api/
├── .gitignore              # Git ignore rules
├── README.md               # Project documentation
├── DEPLOYMENT_GUIDE.md     # Deployment instructions
├── GIT_SETUP_GUIDE.md      # This guide
├── app.py                  # Main FastAPI application
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container configuration
├── .env.production         # Environment template (committed)
├── .env                    # Actual secrets (NOT committed)
└── src/
    ├── auth/              # Authentication modules
    │   ├── auth_middleware.py
    │   └── token_service.py
    └── parsers/           # Core parsing logic
        ├── resume_processor.py
        ├── text_extractor.py
        ├── gemini_normalizer.py
        ├── gemini_cached_normalizer.py
        ├── result_cache.py
        ├── prompt_cache.py
        └── token_utils.py
```

**Files NOT in repository** (excluded by .gitignore):
- `.env` (contains your actual API keys)
- `credentials/` (service account files)
- `venv/` (virtual environment)
- `__pycache__/` (Python cache)
- Test files and logs

---

## 🔒 Security Checklist

### ✅ Repository Security
- [ ] Repository is private
- [ ] `.env` files are in `.gitignore`
- [ ] No API keys in committed code
- [ ] Service account files excluded

### ✅ Environment Security
- [ ] Strong JWT secret key (32+ characters)
- [ ] All API keys are valid and active
- [ ] Google Cloud credentials properly configured
- [ ] CORS origins properly set

### ✅ Deployment Security
- [ ] Cloud Run service uses secrets management
- [ ] Service account has minimal required permissions
- [ ] Environment variables set in Cloud Run (not in code)
- [ ] HTTPS enabled (automatic in Cloud Run)

---

## 🚨 Troubleshooting

### Common Issues

**1. Git push fails**
```bash
# If repository already exists, force push (CAREFUL!)
git push -f origin main

# Or create new branch
git checkout -b production
git push origin production
```

**2. Cloud Build fails**
- Check Dockerfile syntax
- Verify all required files are committed
- Check Cloud Build logs for specific errors

**3. Deployment fails**
- Verify environment variables are set
- Check that secrets are properly mounted
- Review Cloud Run logs for startup errors

**4. Authentication errors**
- Verify JWT_SECRET_KEY is the same in local and Cloud Run
- Check that Google Cloud credentials are properly mounted

---

## 🎯 Next Steps

After completing this setup:

1. **Test your deployment**: Follow the verification steps in `DEPLOYMENT_GUIDE.md`
2. **Set up monitoring**: Configure alerts and logging
3. **Configure custom domain**: If you have one
4. **Set up CI/CD**: Automate testing and deployment
5. **Performance testing**: Load test your API

---

## 📞 Quick Commands Summary

```bash
# Setup repository
cd managed_services
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/resume-parser-api.git
git push -u origin main

# Update environment
cp .env.production .env
# Edit .env with your API keys

# Test locally
python app.py
curl http://localhost:8000/health

# Deploy changes
git add .
git commit -m "Update: description of changes"
git push origin main
```

Your Resume Parser API is now ready for professional deployment! 🚀