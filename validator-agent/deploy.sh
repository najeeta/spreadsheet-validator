#!/usr/bin/env bash
# deploy.sh — Deploy SpreadsheetValidator to Cloud Run with Vertex AI services.
#
# Prerequisites:
#   - gcloud CLI authenticated (`gcloud auth login`)
#   - Docker configured for GCR (`gcloud auth configure-docker`)
#   - A GCP project with billing enabled
#
# Usage:
#   ./deploy.sh
#
# Required env vars (or set in .env):
#   GOOGLE_CLOUD_PROJECT   — GCP project ID
#   GOOGLE_CLOUD_LOCATION  — Region (default: us-central1)
#   GCS_ARTIFACT_BUCKET    — GCS bucket name for artifacts
#   AGENT_ENGINE_ID        — Reasoning Engine resource name
#
# Optional:
#   SERVICE_NAME           — Cloud Run service name (default: spreadsheet-validator)
#   CORS_ORIGINS           — Allowed CORS origins (default: *)

set -euo pipefail

# ---------- Configuration ----------
PROJECT="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
BUCKET="${GCS_ARTIFACT_BUCKET:?Set GCS_ARTIFACT_BUCKET}"
AGENT_ENGINE_ID="${AGENT_ENGINE_ID:?Set AGENT_ENGINE_ID (from gcloud ai reasoning-engines list)}"
SERVICE="${SERVICE_NAME:-spreadsheet-validator}"
CORS="${CORS_ORIGINS:-*}"
IMAGE="gcr.io/${PROJECT}/${SERVICE}"

echo "==> Project:         ${PROJECT}"
echo "==> Location:        ${LOCATION}"
echo "==> Bucket:          ${BUCKET}"
echo "==> Agent Engine ID: ${AGENT_ENGINE_ID}"
echo "==> Service:         ${SERVICE}"
echo ""

# ---------- 1. Enable required APIs ----------
echo "==> Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  --project="${PROJECT}" --quiet

# ---------- 2. Create GCS bucket if needed ----------
echo "==> Ensuring GCS bucket gs://${BUCKET} exists..."
if ! gsutil ls -b "gs://${BUCKET}" &>/dev/null; then
  gsutil mb -p "${PROJECT}" -l "${LOCATION}" "gs://${BUCKET}"
  echo "    Created gs://${BUCKET}"
else
  echo "    Bucket already exists."
fi

# ---------- 3. Grant IAM permissions to default compute SA ----------
echo "==> Granting IAM permissions..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT}" --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${SA}" \
  --role="roles/aiplatform.user" \
  --quiet >/dev/null

gsutil iam ch "serviceAccount:${SA}:roles/storage.objectAdmin" \
  "gs://${BUCKET}" 2>/dev/null
echo "    Granted aiplatform.user and storage.objectAdmin to ${SA}"

# ---------- 4. Build and push container ----------
echo "==> Building and pushing container image..."
docker build --platform linux/amd64 -t "${IMAGE}" .
docker push "${IMAGE}"

# ---------- 5. Deploy to Cloud Run ----------
echo "==> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}" \
  --region="${LOCATION}" \
  --project="${PROJECT}" \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="ENVIRONMENT=production,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${LOCATION},AGENT_ENGINE_ID=${AGENT_ENGINE_ID},GCS_ARTIFACT_BUCKET=${BUCKET},CORS_ORIGINS=${CORS}" \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --quiet

# ---------- 6. Output service URL ----------
SERVICE_URL=$(gcloud run services describe "${SERVICE}" \
  --region="${LOCATION}" \
  --project="${PROJECT}" \
  --format="value(status.url)")

echo ""
echo "==> Deployment complete!"
echo "    Service URL: ${SERVICE_URL}"
echo "    Health check: curl ${SERVICE_URL}/health"
