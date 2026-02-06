#!python3
import os
import requests
from datetime import datetime, date
from tabulate import tabulate
import argparse

CAMPAIGN_URI = "https://actionnetwork.org/api/v2/event_campaigns/"

def main():
   parser = argparse.ArgumentParser(
      description ='Get event campaign registrants',
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
      '-c', "--campaign",
      dest = 'anCampaignId', 
      action = 'store', 
      required = False,
      default = None,
      help = 'Campaign ID for targeted events(also can be set in the AN_CAMPAIGN_ID environment variable).'
   )
   parser.add_argument(
      '-p', "--passed",
      dest = 'showPassedEvents', 
      action = 'store_true', 
      required = False,
      default = False,
      help = 'Whether to show events whose end date has passed.'
   )

   args = parser.parse_args()
   if args.anApiToken:
      anApiToken = args.anApiToken
   else:
      anApiToken = os.getenv('AN_API_TOKEN')
      if not anApiToken:
         print("Please set the AN_API_TOKEN environment variable or pass it with the -t option.")
         exit(1)
   anCampaignId = None         
   if args.anCampaignId:
      anCampaignId = args.anCampaignId
   else:
      anCampaignId = os.getenv('AN_CAMPAIGN_ID')
      if not anCampaignId:
         print("Will not use campaign ID as events filter.")

   headers = {
      "OSDI-API-Token": anApiToken
   }
   API_BASE_URI = "https://actionnetwork.org/api/v2"

   # Loop through all the events for the target campaign
   eventsUri = "/events"
   eventsUriQuery = ""
   moreEvents = True
   eventAttendees = {}
   while moreEvents:
      try:
         response = requests.get(f"{API_BASE_URI}{eventsUri}{eventsUriQuery}", headers=headers)
         response.raise_for_status()
      except requests.exceptions.RequestException as e:
         print("Error calling Action Network API: {}".format(e))
         exit(1)
      eventData = response.json()

      for event in eventData['_embedded']['osdi:events']:
         if event['status'] != 'cancelled':
            # First ensure this is part of the target event campaign.
            if (anCampaignId and 
               'action_network:event_campaign' in event['_links'] and
               event['_links']['action_network:event_campaign']['href'] != f"{CAMPAIGN_URI}{anCampaignId}"
            ):
               continue
            
            # Get all the attendees for this event
            eventId = event['identifiers'][0]
            if not eventId:
               print(f"Event {event['title']} is missing an identifier, skipping")
               continue
            eventId = eventId.removeprefix('action_network:')
            print(f"Getting attendees for event \"{event['title']}\" (ID: {eventId})")
            moreAttendances = True
            attendancesUri = f"/events/{eventId}/attendances"
            attendancesUriQuery = ""
            while moreAttendances:
               try:
                  response = requests.get(f"{API_BASE_URI}{attendancesUri}{attendancesUriQuery}", headers=headers)
                  response.raise_for_status()
               except requests.exceptions.RequestException as e:
                  print(f"Error calling Action Network API (events/{eventId}/attendances): {e}")
                  break
                  # exit(1)
               attendencesData = response.json()
               if 'osdi:attendances' in attendencesData['_embedded']:
                  for attendance in attendencesData['_embedded']['osdi:attendances']:
                     personId = attendance['action_network:person_id']
                     # See if we've already seen this person ID before calling the API
                     if personId not in eventAttendees.keys():
                        # Now get the person record to get their info
                        try:
                           response = requests.get(f"{API_BASE_URI}/people/{personId}", headers=headers)
                           response.raise_for_status()
                        except requests.exceptions.RequestException as e:
                           print(f"Error calling Action Network API (people/{personId}): {e}")
                           exit(1)
                        personData = response.json()
                        if 'email_addresses' in personData and len(personData['email_addresses']) > 0:
                           email = personData['email_addresses'][0]['address']
                           eventAttendees[personId] = email
                           print(f"Added person {personId} with email {email}")
                        else:
                           print(f"Person {personId} has no email address, skipping")
                  # for attendance in attendencesData ...
               if attendencesData['page'] >= attendencesData['total_pages']:
                  moreAttendances = False
               else:
                  attendancesUriQuery = f"?page={attendencesData['page'] + 1}"
            # while moreAttendances
         # if event['status'] != 'cancelled' ...
      # for event in eventData ...
      if eventData['page'] >= eventData['total_pages']:
         moreEvents = False
      else:
         eventsUriQuery = f"?page={eventData['page'] + 1}"
   # while moreEvents
   print(f"Found {len(eventAttendees)} unique attendees across all events")
   for email in eventAttendees.values():
      print(email)

if __name__ == "__main__":
   main()   