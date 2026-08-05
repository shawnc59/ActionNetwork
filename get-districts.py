#!python3
import os
import requests
from datetime import datetime, date
# from tabulate import tabulate
import argparse
import csv
import logging

def main():
   logger: logging.Logger = logging.getLogger(__name__)
   logging.basicConfig(
      format='%(levelname)s: %(message)s', 
      level=os.getenv('LOG_LEVEL', 'INFO').upper()
   )

   parser = argparse.ArgumentParser(
      description ='Create CSV with state legislative districts',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter
   )
   parser.add_argument(
      '-a', "--antoken",
      dest = 'anApiToken', 
      action = 'store', 
      required = False,
      default = None,
      help = 'Action Network API token (also can be set in the AN_API_TOKEN environment variable).'
   )
   parser.add_argument(
      '-c', "--ctoken",
      dest = 'cApiToken', 
      action = 'store', 
      required = False,
      default = None,
      help = 'Census geocoding API token (also can be set in the CENSUS_API_TOKEN environment variable).'
   )
   parser.add_argument(
      '-u', "--update",
      dest = 'applyUpdates', 
      action = 'store_true', 
      required = False,
      default = False,
      help = 'Apply updates to directly to Action Network; otherwise, we create a CSV file for AN bulk upload.'
   )
   parser.add_argument(
      '-t', "--test",
      dest = 'testRun', 
      action = 'store_true', 
      required = False,
      default = False,
      help = 'Run in test mode without applying updates to Action Network.'
   )
   args = parser.parse_args()
   if args.anApiToken:
      anApiToken = args.anApiToken
   else:
      anApiToken = os.getenv('AN_API_TOKEN')
      if not anApiToken:
         logger.warning("Please set the AN_API_TOKEN environment variable or pass it with the -t option.")
         exit(1)
   if args.cApiToken:
      cApiToken = args.cApiToken
   else:
      cApiToken = os.getenv('CENSUS_API_TOKEN')
      if not cApiToken:
         logger.warning("Please set the CENSUS_API_TOKEN environment variable or pass it with the -c option.")
         exit(1)
   applyUpdates: bool = args.applyUpdates
   testRun: bool = args.testRun

   AN_REQUIRED_HDRS = {
      "OSDI-API-Token": anApiToken
   }
   AN_API_BASE_URI = "https://actionnetwork.org/api/v2"
   CENSUS_API_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
   FIELDS = [
      "Email", 
      "TA-State-District-Lower", 
      "TA-State-District-Upper"
   ]
   BLANK_GPS_VALUES = [None, 0, 0.0]

   # First, get all the tags for this group to avoid per-activist API calls later.
   uri: str = "/tags"
   moreData: bool = True
   tags: dict[str, str] = {} # Tag ID and name pairs.
   while moreData:
      try:
         response = requests.get(f"{AN_API_BASE_URI}/{uri}", headers=AN_REQUIRED_HDRS)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         logger.error("Error calling Action Network API endpoint '/tags': {}".format(e))
         exit(1)
      data = response.json()
      if "osdi:tags" in data['_embedded']:
         for tag in data['_embedded']['osdi:tags']:
            tags[tag['identifiers'][0].removeprefix("action_network:")] = tag['name']

      if data['page'] >= data['total_pages']:
         moreData = False
      else:
         uri = f"/tags?page={data['page'] + 1}"
 
   # Loop through all the people entries and find those which are subscribed.
   uri = "/people"
   moreData = True
   subscribedCnt = addrExistsSkippedCnt = badLocSkippedCnt = districtsAddedCnt = districtsUpdatedCnt = locHitCnt = 0
   activists = []
   locations: dict[str, dict] = {} # Values from identical coordinate pairs.
   while moreData:
      try:
         response = requests.get(f"{AN_API_BASE_URI}{uri}", headers=AN_REQUIRED_HDRS)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         logger.error("Error calling Action Network API: {}".format(e))
         exit(1)
      data = response.json()

      for person in data['_embedded']['osdi:people']:
         # Get the "self" URL to this PEOPLE record so we can update it later if needed.
         selfURL: str = ''
         if '_links' in person and 'self' in person['_links'] and 'href' in person['_links']['self']:
            selfURL = person['_links']['self']['href']
         else:
            logger.warning(f"Skipping '{email}' - no self URL found for this record in case of update.")
            continue
         # Skip any people who don't have email addresses or aren't subscribed
         if "email_addresses" in person and len(person['email_addresses']) > 0 and person['email_addresses'][0]['status'] == 'subscribed':
            subscribedCnt += 1
            if subscribedCnt % 25 == 0:
               logger.info(f"Processed {subscribedCnt} subscribed activists so far ...")

            email = person['email_addresses'][0]['address']
            # Now get any postal addresses if they exist
            longitude = latitude = 0
            locKey = state = derivedStateDistrictLower = derivedStateDistrictUpper = ''

            if "postal_addresses" in person and len(person['postal_addresses']) > 0:
               postalAddress = person['postal_addresses'][0]
               # If the activist has a street address, then AN will provide the state districts.
               if 'address_lines' in postalAddress and len(postalAddress['address_lines']) > 0:
                  logger.debug(f"Skipping activist with email {email} due to presence of street address.")
                  addrExistsSkippedCnt += 1
                  continue

               # Check if this activist already has the district info in their record.
               districtsMissing = False
               currentStateDistrictLower = currentStateDistrictUpper = ''
               if 'custom_fields' in person:
                  currentStateDistrictLower = person['custom_fields']['TA-State-District-Lower'] \
                     if 'TA-State-District-Lower' in person['custom_fields'] else ''
                  currentStateDistrictUpper = person['custom_fields']['TA-State-District-Upper'] \
                     if 'TA-State-District-Upper' in person['custom_fields'] else ''
                  if currentStateDistrictLower == '' or currentStateDistrictUpper == '':
                     districtsMissing = True

               if 'location' in postalAddress:
                  longitude = postalAddress['location']['longitude'] if 'longitude' in postalAddress['location'] else 0
                  latitude = postalAddress['location']['latitude'] if 'latitude' in postalAddress['location'] else 0
            # Make sure we don't have "blank" values.
            if longitude in BLANK_GPS_VALUES or latitude in BLANK_GPS_VALUES:
               badLocSkippedCnt += 1
               # See if the activist is missing a Zip Code.
               if 'postal_code' not in postalAddress or postalAddress['postal_code'] == '':
                  logger.warning(f"Skipping activist with email {email} due to blank/missing longitude/latitude values and missing postal code.")
               else:
                  logger.warning(f"Skipping activist with email {email} due to blank/missing longitude/latitude values.")
               continue
            # If we've already seen this coordinate pair, use the cached values. 
            # Otherwise, call the Census geocoding API to get the district info.
            locKey = f"{longitude}/{latitude}"
            if locKey in locations:
               locHitCnt += 1
               derivedStateDistrictLower = locations[locKey]['stateLowerDist']
               derivedStateDistrictUpper = locations[locKey]['stateUpperDist']
            else:
               try:
                  response = requests.get(
                     CENSUS_API_URL, 
                     params={
                        "x": longitude, 
                        "y": latitude, 
                        "benchmark": "Public_AR_Current", 
                        "vintage": "Current_Current", 
                        "format": "json", 
                        "key": cApiToken
                     }
                  )
                  response.raise_for_status()
               except requests.exceptions.RequestException as e:
                  logger.error("Error calling Census geocoding API: {}".format(e))
                  exit(1)
               censusData = response.json()
               if 'result' in censusData and 'geographies' in censusData['result']:
                  state: str = censusData['result']['geographies']['States'][0]['NAME'] \
                     if 'States' in censusData['result']['geographies'] and len(censusData['result']['geographies']['States']) > 0 else ''
                  # Find the keys in the geographies dict for legislative districts. 
                  stateLowerKey = next((k for k in (censusData['result']['geographies']).keys() \
                                       if "State Legislative Districts - Lower" in k), None)
                  stateUpperKey = next((k for k in (censusData['result']['geographies']).keys() \
                                       if "State Legislative Districts - Upper" in k), None)

                  derivedStateDistrictLower = \
                     f"US - {state} {censusData['result']['geographies'][stateLowerKey][0]['NAME']}" if stateLowerKey else ''
                  derivedStateDistrictUpper = \
                     f"US - {state} {censusData['result']['geographies'][stateUpperKey][0]['NAME']}" if stateUpperKey else ''
                  locations[locKey] = {
                     "stateLowerDist": derivedStateDistrictLower,
                     "stateUpperDist": derivedStateDistrictUpper 
                  }

            # Now that we have the district info, check whether this user already has these values so we don't unnecessarily update it. 
            if districtsMissing or currentStateDistrictLower != derivedStateDistrictLower or currentStateDistrictUpper != derivedStateDistrictUpper:
               if districtsMissing:
                   districtsAddedCnt += 1
               else:
                   districtsUpdatedCnt += 1

               # Update the Action Network record if the user specified the --update option.
               action: str = "Would have updated" if testRun else "Updated"
               if applyUpdates:
                  if not testRun:
                     updatePayload = {
                        "custom_fields": {
                           "TA-State-District-Lower": derivedStateDistrictLower,
                           "TA-State-District-Upper": derivedStateDistrictUpper
                        }
                     }
                     try:
                        response = requests.put(selfURL, headers=AN_REQUIRED_HDRS, json=updatePayload)
                        response.raise_for_status()
                     except requests.exceptions.RequestException as e:
                        logger.error(f"Error updating Action Network record for {email}: {e}")
                        continue
                  logger.info(f"{action} '{email}' - Lower: '{derivedStateDistrictLower}' (old: '{currentStateDistrictLower}'), Upper: '{derivedStateDistrictUpper}' (old: '{currentStateDistrictUpper}')")
               else:
                  # If we're not doing direct updates to Action Network, then just add this activist to the CSV file.
                  activists.append({
                     "Email": email,
                     "TA-State-District-Lower": derivedStateDistrictLower,
                     "TA-State-District-Upper": derivedStateDistrictUpper
                  })
         # if "email_addresses" ...
      # for person ...
      if 'next' not in data['_links'] or 'href' not in data['_links']['next']:
         moreData = False
      else:
         uri = data['_links']['next']['href'].removeprefix(AN_API_BASE_URI) # API_BASE_URI is prepended in the API call.
   if not applyUpdates:
      with open("districts.csv", mode='w', newline='') as csvFile:
         writer = csv.DictWriter(csvFile, fieldnames=FIELDS)
         writer.writeheader()  # Write header row
         writer.writerows(activists)  # Write data rows
   logger.info(f"Activist counts - total subscribed: {subscribedCnt}; custom fields to add: {districtsAddedCnt}, custom fields to update: {districtsUpdatedCnt} (reused coordinates: {locHitCnt} times); w/ address (skipped): {addrExistsSkippedCnt} (no location data: {badLocSkippedCnt})")

if __name__ == "__main__":
   main()   