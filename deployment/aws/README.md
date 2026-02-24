# CinematchAI — AWS Deployment Guide

## Architecture Overview

```
User → CloudFront (Amplify) → React App
                ↓ API calls
         API Gateway (HTTP API)
                ↓
         AWS Lambda (FastAPI + Mangum)
          ↓              ↓
     Qdrant Cloud    Supabase PostgreSQL
     (vector search)  (users / auth)
          ↓
       Groq API        Voyage AI API
       (LLM)           (embeddings)
```

## Services & Free Tiers

| Service | Free Limit | Notes |
|---------|-----------|-------|
| AWS Amplify | 1000 build min/mo, 15GB transfer | Frontend |
| AWS Lambda | 1M req/mo, 400K GB-sec | Backend |
| AWS API Gateway | 1M HTTP calls/mo (12 months) | API routing |
| AWS ECR | 500MB storage (12 months) | Container registry |
| Qdrant Cloud | 1GB, 1 node, forever free | Vector DB |
| Supabase | 500MB DB, forever free | User/auth DB |
| Voyage AI | 50M tokens for new users | Embeddings |
| Groq | Free tier | LLM |

---

## Step-by-Step Setup

### 1. Prerequisites
```bash
# Install AWS CLI and configure
brew install awscli
aws configure   # enter Access Key, Secret, region (e.g. us-east-1)

# Install Docker Desktop (for building Lambda container)
```

### 2. Sign up for free services
- **Qdrant Cloud**: https://cloud.qdrant.io → Create free cluster → copy URL + API key
- **Supabase**: https://supabase.com → New project → Settings → Database → copy connection string
- **Voyage AI**: https://www.voyageai.com → Get API key (50M free tokens)
- **Groq**: https://console.groq.com → API keys (already have this)

### 3. Re-index movies with Voyage AI (run once locally)
```bash
pip install voyageai qdrant-client pandas pyarrow tqdm

export VOYAGE_API_KEY=your_key
export QDRANT_URL=https://xxxx.qdrant.io:6333
export QDRANT_API_KEY=your_key

python scripts/reindex_voyageai.py
# Takes ~10 min for 62K movies, uses ~620K tokens (well within 50M free)
```

### 4. Create Lambda function (AWS Console or CLI)
```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export LAMBDA_FUNCTION_NAME=cinematch-api

# Build + push + deploy
./deployment/aws/deploy.sh

# After first push, create the function in AWS Console:
# Lambda → Create function → Container image → select ECR image
# Settings:
#   Memory: 1024 MB (or 2048 MB for better performance)
#   Ephemeral storage: 1024 MB (/tmp)
#   Timeout: 60 seconds
#   Architecture: arm64
```

### 5. Set Lambda environment variables
In AWS Lambda → Configuration → Environment variables, add all vars from `.env.aws.example`.

### 6. Create API Gateway
```
API Gateway → Create API → HTTP API
→ Add integration: Lambda → select cinematch-api
→ Routes: $default (catches all paths)
→ Deploy → copy the Invoke URL
```

### 7. Deploy frontend to AWS Amplify
```
Amplify → New app → Host web app → GitHub
→ Select repo + branch (feat/aws-deployment)
→ amplify.yml is auto-detected
→ Environment variables:
    VITE_API_URL = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
    VITE_GOOGLE_CLIENT_ID = your_google_client_id
→ Deploy
```

### 8. Keep Lambda warm (optional, prevents cold starts)
```
EventBridge → Create rule → Schedule: rate(5 minutes)
→ Target: Lambda → cinematch-api
→ Input: {"path": "/api/v1/health/", "httpMethod": "GET", ...}
```

---

## Redeployment
After any code changes:
```bash
./deployment/aws/deploy.sh
```
Frontend auto-deploys on push to `feat/aws-deployment` branch via Amplify.

---

## Reverting to HuggingFace
```bash
git checkout main   # back to HF version, untouched
```
