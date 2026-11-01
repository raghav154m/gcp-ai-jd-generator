#!/usr/bin/env bash
# Deploy the full stack to an existing GCP project with billing enabled.
# Usage: PROJECT_ID=my-project ./scripts/deploy.sh
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

gcloud config set project "$PROJECT_ID"
gcloud services enable aiplatform.googleapis.com firestore.googleapis.com \
  cloudfunctions.googleapis.com cloudbuild.googleapis.com run.googleapis.com

gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 \
  || gcloud firestore databases create --location="$REGION"

# Runtime service account with least privilege
SA="jd-generator@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 \
  || gcloud iam service-accounts create jd-generator --display-name="JD generator"
for role in roles/aiplatform.user roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA" --role="$role" --condition=None >/dev/null
done

PROJECT_ID="$PROJECT_ID" python3 "$ROOT/scripts/seed_firestore.py"

deploy() {  # name entry-point memory
  gcloud functions deploy "$1" --gen2 --runtime=python312 --region="$REGION" \
    --source="$ROOT/functions" --entry-point="$2" --trigger-http \
    --allow-unauthenticated --memory="$3" --timeout=120s \
    --service-account="$SA" \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,FUNCTION_REGION=$REGION"
}
deploy generate-job-description generate_job_description_http 512Mi
deploy validate-compliance validate_compliance 256Mi

for fn in generate-job-description validate-compliance; do
  echo "$fn: $(gcloud functions describe "$fn" --gen2 --region="$REGION" \
    --format='value(serviceConfig.uri)')"
done
