#!/usr/bin/env bash
# Remove deployed functions (Firestore data is left in place).
set -euo pipefail
REGION="${REGION:-us-central1}"
for fn in generate-job-description validate-compliance; do
  gcloud functions delete "$fn" --gen2 --region="$REGION" --quiet || true
done
echo "Functions removed. To delete everything: gcloud projects delete \$PROJECT_ID"
