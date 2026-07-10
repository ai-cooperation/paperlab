#!/usr/bin/env bash
# Deploy newarch to ac-2012. ⚠️ rsync alone is NOT a deploy: the paper-job-service
# daemon holds imported modules in memory, so website-submitted jobs keep running
# OLD code until restart (2026-07-10: four fix deployments were rsync-only; the
# first fresh E2E job burned its review budget on a leak-gate false positive that
# had been fixed on disk for hours). CLI batches mask this because each spawn
# loads fresh code. Deploy = rsync + RESTART + health check, always.
set -euo pipefail
cd "$(dirname "$0")"
rsync -rlptD \
  --exclude='jobs/' --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='*.pyc' --exclude='_phase_logs/' --exclude='.pytest_cache/' \
  ./ ac-2012:paper-job-service/newarch/
ssh ac-2012 "systemctl --user restart paper-job-service && sleep 3 \
  && curl -sf http://localhost:8765/health \
  && systemctl --user show paper-job-service -p ActiveEnterTimestamp"
echo ""
echo "DEPLOYED + RESTARTED + HEALTH OK"
