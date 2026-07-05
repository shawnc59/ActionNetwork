#!python3
from bs4 import BeautifulSoup as bs
import os
import argparse

def main():

   parser = argparse.ArgumentParser(
      description ='Clean Action Network newsletter HTML',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter
   )
   parser.add_argument(
      '-i', "--input",
      dest = 'htmlFile', 
      action = 'store', 
      required = False,
      default = 'newsletter.html',
      help = 'Path to the HTML file to clean.'
   )
   args = parser.parse_args()
   if args.htmlFile != 'newsletter.html':
      htmlFile = args.htmlFile

   pwd = os.path.dirname(os.path.abspath(__file__))
   htmlFile = f'{pwd}/{htmlFile}'

   with open(htmlFile, 'r') as f:
      soup = bs(f, 'html.parser')
      # Find all the paragraph tags, then loop through them looking for the Action Network clip references.
      paragraphs = soup.find_all('p')
      for element in paragraphs:
         if element.string == "Dear {{ FirstName | default: 'Friend' }}, ":
            element.string = "Dear Friend,"
            print("Swapped name")
         if element.string is not None and element.string.find("{{ GroupName }}") != -1:
            element.string = element.string.replace("{{ GroupName }}", "Third Act Wisconsin")
            print("Swapped group name")
      # The 2nd instance of {{ GroupName }} is in a bold tag, so repeat the process.
      bolds = soup.find_all('strong')
      for element in bolds:
         if element.string is not None and element.string.find("{{ GroupName }}") != -1:
            element.string = element.string.replace("{{ GroupName }}", "Third Act Wisconsin")
            print("Swapped group name")
   f.close()
   with open(htmlFile, 'wb') as f:
      f.write(soup.prettify("utf-8"))

if __name__ == "__main__":
   main()