#!/bin/sh
# Write the API address into the board's runtime config (web/public/config.json).
set -e
api="$(azd env get-value SERVICE_API_URI)"
mkdir -p web/public
printf '{"apiUrl":"%s"}\n' "$api" > web/public/config.json
echo "board will talk to $api"
