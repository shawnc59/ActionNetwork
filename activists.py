#!python3
import os
import requests
from datetime import datetime, date
# from tabulate import tabulate
import argparse
import csv

def main():
   parser = argparse.ArgumentParser(
      description ='Generate activist report',
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
   args = parser.parse_args()
   if args.anApiToken:
      anApiToken = args.anApiToken
   else:
      anApiToken = os.getenv('AN_API_TOKEN')
      if not anApiToken:
         print("Please set the AN_API_TOKEN environment variable or pass it with the -t option.")
         exit(1)
   if args.cApiToken:
      cApiToken = args.cApiToken
   else:
      cApiToken = os.getenv('CENSUS_API_TOKEN')
      if not cApiToken:
         print("Please set the CENSUS_API_TOKEN environment variable or pass it with the -c option.")
         exit(1)

   anReqHeaders = {
      "OSDI-API-Token": anApiToken
   }
   AN_API_BASE_URI = "https://actionnetwork.org/api/v2"
   CENSUS_API_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
   FIELDS = [
      "First Name", 
      "Last Name", 
      "Email", 
      "Phone", 
      "Street Address", 
      "City", 
      "State",
      "State (abbreviated)", 
      "Zip Code", 
      "Longitude/Latitude", 
      "County (census)", 
      "Congressional District (census)", 
      "State Lower District (census)", 
      "State Upper District (census)",
      "Tags"
   ]

   # First, get all the tags for this group to avoid per-activist API calls later.
   uri = "/tags"
   moreData = True
   tags: dict[str, str] = {} # Tag ID and name pairs.
   while moreData:
      try:
         response = requests.get(f"{AN_API_BASE_URI}/{uri}", headers=anReqHeaders)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         print("Error calling Action Network API endpoint '/tags': {}".format(e))
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
   personCnt = 0
   locHitCnt = 0
   activists = []
   locations: dict[str, dict] = {} # Values from identical coordinate pairs.
   print(f'-- Subscribed Activists as of {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
   while moreData:
      try:
         response = requests.get(f"{AN_API_BASE_URI}{uri}", headers=anReqHeaders)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         print("Error calling Action Network API: {}".format(e))
         exit(1)
      data = response.json()

      for person in data['_embedded']['osdi:people']:
         longitude = latitude = ''
         # Skip any people who don't have email addresses or aren't subscribed
         if "email_addresses" in person and len(person['email_addresses']) > 0 and person['email_addresses'][0]['status'] == 'subscribed':
            personCnt += 1
            firstName = person['given_name'] if 'given_name' in person else ''
            lastName = person['family_name'] if 'family_name' in person else ''
            email = person['email_addresses'][0]['address']
            # Get any phone numbers if they exist
            if "phone_numbers" in person and len(person['phone_numbers']) > 0:
               phone = person['phone_numbers'][0]['number'] if 'number' in person['phone_numbers'][0] else ''
            else:
               phone = ''
            # Now get any postal addresses if they exist
            streetAddr = city = stateAbbr = zipCode = ''
            if "postal_addresses" in person and len(person['postal_addresses']) > 0:
               postalAddress = person['postal_addresses'][0]
               if 'address_lines' in postalAddress and len(postalAddress['address_lines']) > 0:
                  for line in postalAddress['address_lines']:
                     streetAddr += line + ' '
                  streetAddr = streetAddr.strip()
               city = postalAddress['locality'] if 'locality' in postalAddress else ''
               stateAbbr = postalAddress['region'] if 'region' in postalAddress else ''
               zipCode = postalAddress['postal_code'] if 'postal_code' in postalAddress else ''
               longitude = latitude = locKey = ''
               if 'location' in postalAddress:
                  longitude = postalAddress['location']['longitude'] if 'longitude' in postalAddress['location'] else ''
                  latitude = postalAddress['location']['latitude'] if 'latitude' in postalAddress['location'] else ''

            # Find any tags for this person
            activistTags = []
            if "osdi:taggings" in person["_links"]:
               tagHREF = person["_links"]["osdi:taggings"]['href']
               try:
                  response = requests.get(tagHREF, headers=anReqHeaders)
                  response.raise_for_status()
               except requests.exceptions.RequestException as e:
                  print("Error calling Action Network API (taggings): {}".format(e))
                  exit(1)
               tagData = response.json()
               if "osdi:taggings" in tagData['_links']:
                  for tagging in tagData['_links']['osdi:taggings']:
                     if "href" in tagging:
                        # Format of the tag href is https://actionnetwork.org/api/v2/tags/{tag ID}/taggings/{taggings ID?}
                        # So we need the 6th element of the tokenized HREF string.
                        hrefTokens = tagging['href'].split('/')
                        if hrefTokens[6] in tags:
                           activistTags.append(tags[hrefTokens[6]])
            # If we have coordinates, use the Census geocoding API to get more activist info.
            county = congressDist = stateLowerDist = stateUpperDist = state = ''
            if longitude and latitude:
               locKey = f"{longitude}/{latitude}"
               if locKey in locations:
                  locHitCnt += 1
                  county = locations[locKey]['county']
                  state = locations[locKey]['state']
                  congressDist = locations[locKey]['congressDist']
                  stateLowerDist = locations[locKey]['stateLowerDist']
                  stateUpperDist = locations[locKey]['stateUpperDist']
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
                     print("Error calling Census geocoding API: {}".format(e))
                     exit(1)
                  censusData = response.json()
                  if 'result' in censusData and 'geographies' in censusData['result']:
                     if 'Counties' in censusData['result']['geographies'] and len(censusData['result']['geographies']['Counties']) > 0:
                        county = censusData['result']['geographies']['Counties'][0]['NAME']
                     if 'States' in censusData['result']['geographies'] and len(censusData['result']['geographies']['States']) > 0:
                        state = censusData['result']['geographies']['States'][0]['NAME']
                     # Find the keys in the geographies dict for legislative districts. 
                     congressKey = next((k for k in (censusData['result']['geographies']).keys() if "Congressional Districts" in k), None)
                     stateLowerKey = next((k for k in (censusData['result']['geographies']).keys() if "State Legislative Districts - Lower" in k), None)
                     stateUpperKey = next((k for k in (censusData['result']['geographies']).keys() if "State Legislative Districts - Upper" in k), None)

                     congressDist = f"US - {state} {censusData['result']['geographies'][congressKey][0]['NAME']}"if congressKey else ''
                     stateLowerDist = f"US - {state} {censusData['result']['geographies'][stateLowerKey][0]['NAME']}" if stateLowerKey else ''
                     stateUpperDist = f"US - {state} {censusData['result']['geographies'][stateUpperKey][0]['NAME']}" if stateUpperKey else ''
                     locations[locKey] = {
                        "county": county,
                        "state": state,
                        "congressDist": congressDist,
                        "stateLowerDist": stateLowerDist,
                        "stateUpperDist": stateUpperDist 
                     }
            # activists.append((firstName, lastName, email, phone, streetAddr, city, state, zipCode, ';'.join(activistTags), f"{longitude}/{latitude}", county, congressDist, stateLowerDist, stateUpperDist))
            activists.append({
               "First Name": firstName,
               "Last Name": lastName,
               "Email": email,
               "Phone": phone,
               "Street Address": streetAddr,
               "City": city,
               "State": state,
               "State (abbreviated)": stateAbbr,
               "Zip Code": zipCode,
               "Longitude/Latitude": locKey,
               "County (census)": county,
               "Congressional District (census)": congressDist,
               "State Lower District (census)": stateLowerDist,
               "State Upper District (census)": stateUpperDist,
               "Tags": ';'.join(activistTags)
            })
         if personCnt % 25 == 0:
            print(f"Processed {personCnt} subscribed activists so far ...")
      if 'next' not in data['_links'] or 'href' not in data['_links']['next']:
         moreData = False
      else:
         uri = data['_links']['next']['href'].removeprefix(AN_API_BASE_URI) # API_BASE_URI is prepended in the API call.
   with open("activists.csv", mode='w', newline='') as csvFile:
      writer = csv.DictWriter(csvFile, fieldnames=FIELDS)
      writer.writeheader()  # Write header row
      writer.writerows(activists)  # Write data rows
   # print(tabulate(activists, headers=["First Name", "Last Name", "Email", "Phone", "Street Address", "City", "State", "Zip Code", "Tags", "Longitude/Latitude", "County", "Congressional District", "State Lower District", "State Upper District"]))
   print(f"\n-- Total subscribed activists: {personCnt} (Location hits: {locHitCnt})")

if __name__ == "__main__":
   main()   