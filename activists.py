#!python3
import os
import requests
from datetime import datetime, date
from tabulate import tabulate
import argparse

def main():
   parser = argparse.ArgumentParser(
      description ='Generate activist report',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter
   )
   parser.add_argument(
      '-t', "--token",
      dest = 'anApiToken', 
      action = 'store', 
      required = False,
      default = None,
      help = 'Action Network API token (also can be set in the AN_API_TOKEN environment variable).'
   )
   args = parser.parse_args()
   if args.anApiToken:
      anApiToken = args.anApiToken
   else:
      anApiToken = os.getenv('AN_API_TOKEN')
      if not anApiToken:
         print("Please set the AN_API_TOKEN environment variable or pass it with the -t option.")
         exit(1)

   headers = {
      "OSDI-API-Token": anApiToken
   }
   API_BASE_URI = "https://actionnetwork.org/api/v2"

   # First, get all the tags for this group to avoid per-activist API calls later.
   uri = "/tags"
   moreData = True
   tags: dict[str, str] = {} # Tag ID and name pairs.
   while moreData:
      try:
         response = requests.get(f"{API_BASE_URI}/{uri}", headers=headers)
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
   activists = []
   print(f'-- Subscribed Activists as of {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
   while moreData:
      try:
         response = requests.get(f"{API_BASE_URI}{uri}", headers=headers)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         print("Error calling Action Network API: {}".format(e))
         exit(1)
      data = response.json()

      for person in data['_embedded']['osdi:people']:
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
            streetAddr = city = state = zipCode = ''
            if "postal_addresses" in person and len(person['postal_addresses']) > 0:
               postalAddress = person['postal_addresses'][0]
               if 'address_lines' in postalAddress and len(postalAddress['address_lines']) > 0:
                  for line in postalAddress['address_lines']:
                     streetAddr += line + ' '
                  streetAddr = streetAddr.strip()
               city = postalAddress['locality'] if 'locality' in postalAddress else ''
               state = postalAddress['region'] if 'region' in postalAddress else ''
               zipCode = postalAddress['postal_code'] if 'postal_code' in postalAddress else ''
            # Find any tags for this person
            activistTags = []
            if "osdi:taggings" in person["_links"]:
               tagHREF = person["_links"]["osdi:taggings"]['href']
               try:
                  response = requests.get(tagHREF, headers=headers)
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
            activists.append((firstName, lastName, email, phone, streetAddr, city, state, zipCode, ';'.join(activistTags)))

      if 'next' not in data['_links'] or 'href' not in data['_links']['next']:
         moreData = False
      else:
         uri = data['_links']['next']['href'].removeprefix(API_BASE_URI) # API_BASE_URI is prepended in the API call.
   print(tabulate(activists, headers=["First Name", "Last Name", "Email", "Phone", "Street Address", "City", "State", "Zip Code", "Tags"]))
   print("\n-- Total subscribed activists: " + str(personCnt))

if __name__ == "__main__":
   main()   