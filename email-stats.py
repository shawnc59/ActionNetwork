#!python3
import os
import requests
from datetime import datetime, date
from tabulate import tabulate
import argparse

def main():
   parser = argparse.ArgumentParser(
      description ='Generate Email statistics report',
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
   parser.add_argument(
      '-a', "--abbreviate",
      dest = 'abbreviateTitle', 
      action = 'store_true', 
      required = False,
      default = False,
      help = 'Whether to abbreviate Title to 50 characters.'
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

   # Loop through all the messages and find those with a status of "sent"
   uri = "/messages"
   moreData = True
   messageCnt = 0
   print(f'-- Sent Email statistics as of {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
   messageStats = []
   while moreData:
      try:
         response = requests.get(f"{API_BASE_URI}{uri}", headers=headers)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         print("Error calling Action Network API: {}".format(e))
         exit(1)
      data = response.json()

      for message in data['_embedded']['osdi:messages']:
         if message['status'] == 'sent':
            messageCnt += 1
            messageSentDate = datetime.strptime(message['sent_start_date'], '%Y-%m-%dT%H:%M:%SZ')
            subject = message['subject'] if not args.abbreviateTitle else (message['subject'][:50] + ("..." if len(message['subject']) > 50 else ""))
            numTargets = message['total_targeted'] 
            statistics = message['statistics']
            verifiedOpens = statistics['verified_opens'] if 'verified_opens' in statistics else 0
            machineOpened = statistics['machine_opened'] if 'verified_opens' in statistics else 0
            clicks = statistics['clicked'] if 'clicked' in statistics else 0
            unsubscribed = statistics['unsubscribed'] if 'unsubscribed' in statistics else 0
            messageStats.append((subject, messageSentDate, numTargets, verifiedOpens + machineOpened, verifiedOpens, machineOpened, clicks, unsubscribed))

      if data['page'] >= data['total_pages']:
         moreData = False
      else:
         uri = f"/messages?page={data['page'] + 1}"
   print(tabulate(messageStats, headers=["Subject", "Date Sent", "# of Targets", "Total Opened", "Verified Opens", "Machine Opened", "Clicks", "Unsubscribed"]))
   print("\n-- Total sent messages: " + str(messageCnt))

if __name__ == "__main__":
   main()   