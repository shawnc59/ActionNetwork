#!/bin/bash
source .venv/bin/activate
AN_API_KEY="test"
if [ -n "$1" ]; then
  AN_API_KEY="$1"
fi

KEY_FILE="AN-API-${AN_API_KEY}.key"
AN_API_TOKEN=$(cat $KEY_FILE)
CENSUS_API_TOKEN=$(cat census-API.key)

python get-districts.py -a $AN_API_TOKEN -c $CENSUS_API_TOKEN