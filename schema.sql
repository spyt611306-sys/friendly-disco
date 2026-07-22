name: Collect and verify marine projects

on:
  workflow_dispatch:
  schedule:
    # 03:00, 09:00, 15:00, 21:00 KST
    - cron: "0 0,6,12,18 * * *"

concurrency:
  group: marine-project-collection
  cancel-in-progress: false

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    env:
      RENDER_BASE_URL: ${{ vars.RENDER_BASE_URL || 'https://friendly-disco-dstc.onrender.com' }}
      ADMIN_API_KEY: ${{ secrets.ADMIN_API_KEY }}
    steps:
      - name: Validate configuration
        run: |
          test -n "$ADMIN_API_KEY" || { echo "GitHub Actions secret ADMIN_API_KEY is required"; exit 1; }
          test -n "$RENDER_BASE_URL" || { echo "Repository variable RENDER_BASE_URL is required"; exit 1; }

      - name: Wake Render service
        run: curl --fail --show-error --silent --retry 5 --retry-delay 10 "$RENDER_BASE_URL/health" -o /dev/null || true

      - name: Start collection
        run: |
          curl --fail --show-error --silent --retry 3 --retry-delay 5 \
            -X POST \
            -H "X-Admin-Token: $ADMIN_API_KEY" \
            "$RENDER_BASE_URL/api/collect" > start.json
          jq '{jobId,status,message}' start.json

      - name: Wait for completion
        run: |
          for attempt in $(seq 1 60); do
            curl --fail --show-error --silent --retry 3 "$RENDER_BASE_URL/api/collect/status" > status.json
            running=$(jq -r '.running' status.json)
            status=$(jq -r '.status' status.json)
            progress=$(jq -r '.progress' status.json)
            echo "attempt=$attempt status=$status progress=$progress"
            if [ "$running" = "false" ]; then
              jq '{status,message,savedCount,rawCount,verifiedCount,errors}' status.json
              test "$status" = "SUCCESS" -o "$status" = "PARTIAL"
              exit $?
            fi
            sleep 20
          done
          echo "Collection did not finish within 20 minutes"
          exit 1

