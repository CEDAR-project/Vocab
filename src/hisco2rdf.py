'''
Created on 25 sep. 2014

@author: cgueret
'''
from bs4 import BeautifulSoup
import requests

ROOT = "http://historyofwork.iisg.nl/"
MAJOR_URL = "major.php"

class Hisco2RDF():
    '''
    Scrapes the HISCO Web site
    The hierarchy goes as "master > minor > rubri > micro"
    '''
    def __init__(self):
        pass
    
    def parse_major(self):
        '''
        Parse the page with the master groups
        '''
        # Load the page
        doc = BeautifulSoup(requests.get(ROOT + MAJOR_URL).content)
        
        # Keep a list of links to minor pages
        minor_links = []
        
        # Find the table
        
        
        # Look for the minor links
        for link in doc.find_all('a'):
            if "List Minor" in link.text:
                minor_links.append(link['href'])
        
        # Go one level deeper
        for minor_link in minor_links[:1]:
            self.parse_minor(minor_link)
            
    def parse_minor(self, url):
        '''
        Parse a page with minor groups
        '''
        print "Parse " + url
        # Load the page
        doc = BeautifulSoup(requests.get(ROOT + url).content)
        
        # Find the right table
        for table in doc.find('td', class_='bodyclass').find_all('table'):
            print '-----'
            print table
    
    def parse_rubri(self, url):
        '''
        Parse a page with rubri groups
        '''
        pass
    
    def parse_micro(self, url):
        '''
        Parse a page with micro groups
        '''
        pass
    
if __name__ == '__main__':
    hisco2rdf = Hisco2RDF()
    hisco2rdf.parse_major()
    
