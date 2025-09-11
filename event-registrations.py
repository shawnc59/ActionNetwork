#!python3
import os
import requests
from datetime import datetime, date
from tabulate import tabulate
import argparse

def main():
   parser = argparse.ArgumentParser(description ='Generate event registrant report')
   parser.add_argument(
      '-t', "--token",
      dest = 'anApiToken', 
      action = 'store', 
      required = False,
      default = None,
      help = 'Action Network API token'
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
   baseUrl = "https://actionnetwork.org/api/v2"

   # Loop through all the events and get the number of RSVPs
   uri = "/events"
   moreData = True
   eventCnt = 0
   print(f"-- Event registrations as of {date.today()}")
   eventInfo = []
   while moreData:
      try:
         response = requests.get(f"{baseUrl}{uri}", headers=headers)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         print("Error calling Action Network API: {}".format(e))
         exit(1)
      data = response.json()

      for event in data['_embedded']['osdi:events']:
         if event['status'] != 'cancelled':
            eventStartDate = datetime.strptime(event['start_date'], '%Y-%m-%dT%H:%M:%SZ')
            if eventStartDate > datetime.now():
               eventStatus = "Event starts in {} day(s).".format((eventStartDate - datetime.now()).days)
            if 'end_date' in event and event['end_date']:
               eventEndDate = datetime.strptime(event['end_date'], '%Y-%m-%dT%H:%M:%SZ')
               if eventEndDate < datetime.now():
                  eventStatus = "Event end date has passed."

            hiddenAlert = "(Note: event is hidden)" if event['action_network:hidden'] else ""
            eventCnt += 1
            title = event['title']
            numRegistrants = event['total_accepted'] - 1 # Subtract 1 to exclude the host (automatically accepted)
   #         print(f"Event title: '{title}'; # of registrants: {numRegistrants}; {eventStatus} {hiddenAlert}")  
            eventInfo.append((title, numRegistrants, eventStatus, hiddenAlert))

      if data['page'] >= data['total_pages']:
         moreData = False
      else:
         uri = f"/events?page={data['page'] + 1}"
   print(tabulate(eventInfo, headers=["Event Title", "# Registrants", "Status", ""]))
   print("-- Total events:", eventCnt)

if __name__ == "__main__":
   main()   