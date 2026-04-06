#!python3
import os
import time
import requests
import csv

def main():
   API_URL = "https://www.huduser.gov/hudapi/public/usps"
   hudToken = os.getenv('HUD_TOKEN')
   if not hudToken:
      print("Please set the HUD_TOKEN environment variable.")
      exit(1)

   reqHeaders = {
      "Authorization": f"Bearer {hudToken}"
   }
   zipToState = []
   zipsFile = open("dmv.txt", "r")
   apiCallCnt = 0
   for zipCode in zipsFile:
      zipCode = zipCode.strip()
      print(f"Processing zip code: {zipCode}")
      try:
         response = requests.get(f"{API_URL}?type=2&query={zipCode}", headers=reqHeaders)
         apiCallCnt += 1
         response.raise_for_status()
      except requests.exceptions.HTTPError as e:
         if response.status_code == 404:
            zipToState.append({"Zip Code": zipCode, "State": "Unknown/invalid", "City": "Unknown/invalid"})
            continue
         print("HTTP error calling HUD API: {}".format(e))
         exit(1)
      except requests.exceptions.RequestException as e:
         print("Error calling HUD API: {}".format(e))
         exit(1)
      data = response.json()
      state = data['data']['results'][0]['state'] if data['data']['results'] else "Unknown"
      city = data['data']['results'][0]['city'] if data['data']['results'] else "Unknown"
      zipToState.append({"Zip Code": zipCode, "State": state, "City": city})
      if apiCallCnt == 50:
         apiCallCnt = 0
         print("Sleeping for 90 seconds to avoid hitting API rate limits ...")
         time.sleep(90)  # Sleep for 90 seconds to avoid hitting API rate limits

   zipsFile.close()
   with open("zip2state.csv", mode='w', newline='') as csvFile:
      writer = csv.DictWriter(csvFile, fieldnames=["Zip Code", "State", "City"])
      writer.writeheader()  # Write header row
      writer.writerows(zipToState)  # Write data rows
   
if __name__ == "__main__":
   main()   