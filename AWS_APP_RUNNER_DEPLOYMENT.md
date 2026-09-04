# AWS App Runner deployment guide for JobScout

This guide is tailored to this repository and the existing deployment workflow in [.github/workflows/deploy.yml](.github/workflows/deploy.yml).

## Current project readiness

The repository already includes:

- Docker build for the app in [DockerFile](DockerFile)
- migration-first startup in [docker-entrypoint.sh](docker-entrypoint.sh)
- environment configuration in [app/config.py](app/config.py)
- health endpoints in [app/main.py](app/main.py)
- GitHub Actions deployment flow in [.github/workflows/deploy.yml](.github/workflows/deploy.yml)

I also verified the local project state with:

- `pytest -q` → `10 passed in 0.06s`

That means the repo is stable enough to move into deployment prep.

---

## 1. Prerequisites

You need:

- an AWS account
- an ECR repository
- an App Runner service
- a GitHub repository connected to the project
- an IAM role for GitHub Actions OIDC
- a managed PostgreSQL database (recommended)

---

## 2. Create the AWS resources

### 2.1 Create the ECR repository

Example:

```bash
aws ecr create-repository --repository-name jobscout
```

Note the repository URI.

### 2.2 Create the App Runner service

Create an App Runner service with:

- Source: ECR image
- Image port: `8000`
- Runtime: container image

The repo workflow expects App Runner to update an existing service using:

```bash
aws apprunner update-service --service-arn "$APP_RUNNER_SERVICE_ARN" \
  --source-configuration "ImageRepository={ImageIdentifier=$IMAGE,ImageRepositoryType=ECR,ImageConfiguration={Port=8000}}"
```

So your App Runner service must expose port `8000`.

---

## 3. Create the IAM role for GitHub Actions

Create a role that can be assumed by GitHub OIDC. The deployment workflow uses:

```yaml
permissions:
  id-token: write
  contents: read
```

The role must allow:

- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:BatchGetImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`
- `ecr:PutImage`
- `apprunner:UpdateService`
- `sts:AssumeRole`

You will place the role ARN in the GitHub secret `AWS_ROLE_ARN`.

---

## 4. GitHub repository setup

Set the following repository variables:

- `AWS_REGION` — e.g. `us-east-1`
- `ECR_REPOSITORY` — the ECR repo name, not the full URI
- `APP_RUNNER_SERVICE_ARN` — the ARN of the App Runner service

Set the following repository secret:

- `AWS_ROLE_ARN` — the IAM role ARN created above

This matches the workflow in [.github/workflows/deploy.yml](.github/workflows/deploy.yml).

---

## 5. Required environment variables

The app expects these values from [app/config.py](app/config.py):

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<db>
API_KEY=gsk_your_groq_key
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=jobscout
SMTP_EMAIL=
SMTP_PASSWORD=
ALERT_EMAIL=
GOOGLE_SHEET_ID=
GOOGLE_CREDENTIALS_PATH=
DISCORD_WEBHOOK_URL=
SENTRY_DSN=
ENVIRONMENT=production
LOG_LEVEL=INFO
ATS_GREENHOUSE_BOARDS=gitlab,asana,discord
ATS_LEVER_COMPANIES=palantir
```

### Important note

The app is designed to tolerate missing optional integrations, but required values like `DATABASE_URL` and `API_KEY` should always be set.

---

## 6. Database setup

For production, do not rely on the local Docker Compose database. Use a managed database.

Recommended:

- Amazon RDS PostgreSQL
- or a managed Postgres service that gives you a connection URL

The service should expose a database URL compatible with SQLAlchemy async drivers.

Example value:

```env
DATABASE_URL=postgresql+asyncpg://username:password@host:5432/jobscout
```

---

## 7. Deployment trigger

The repo is already configured to deploy on pushes to `main` via [.github/workflows/deploy.yml](.github/workflows/deploy.yml).

Push to `main` after the AWS and GitHub config is complete:

```bash
git add .
git commit -m "Prepare App Runner deployment"
git push origin main
```

Then GitHub Actions will:

1. install dependencies
2. run lint
3. compile the project
4. run tests
5. authenticate to AWS
6. build the Docker image
7. push to ECR
8. update App Runner

---

## 8. Health verification after deploy

Once the service is live, verify the app at:

- `/health`
- `/db-health`

Example:

```bash
curl https://<your-app-runner-url>/health
curl https://<your-app-runner-url>/db-health
```

The endpoint definitions are in [app/main.py](app/main.py).

Expected success:

```json
{"status": "ok", "service": "jobscout"}
```

And:

```json
{"db": "ok"}
```

---

## 9. Real smoke test

After deployment, test the main product flow:

1. open the homepage
2. confirm the chat UI loads
3. call the AI agent or the matching route
4. verify the database is reachable
5. confirm a scrape or hunter run can execute

This is the evidence your portfolio project needs to feel real.

---

## 10. Resume-ready story

Use the project as a demonstration of:

- backend API engineering
- AI-assisted workflows
- data processing and job matching
- cloud deployment
- CI/CD and containerization
- operational configuration and health checks

A good project summary:

> Built and deployed a full-stack AI job discovery platform using FastAPI, PostgreSQL, Docker, and AWS App Runner. The system scrapes job listings, stores and matches them against resumes, and provides AI-assisted CV tailoring and conversational job discovery workflows.

---

## 11. Recommended next steps after deployment

- capture screenshots of the app UI
- record a short live demo video
- polish the README for GitHub
- add the live URL to your portfolio
- add the project to your resume

---

## 12. If you want the next step

The next practical move is to either:

1. set up the AWS resources in your account, or
2. prepare the exact GitHub variable and IAM role values for your environment

If you want, I can help with the exact AWS role policy and the GitHub config values next.
