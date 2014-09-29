'''
Created on 25 sep. 2014

@author: cgueret
'''
from bs4 import BeautifulSoup
from rdflib import Namespace
import requests
import re
from rdflib.graph import ConjunctiveGraph
from rdflib.namespace import RDF, DCTERMS
import sys
from rdflib.term import Literal

ROOT      = "http://historyofwork.iisg.nl/"
MAJOR_URL = "major.php"
SKOS      = Namespace("http://www.w3.org/2004/02/skos/core#")
HISCO     = Namespace("http://example.org#")

class Hisco2RDF():
    '''
    Scrapes the HISCO Web site
    The hierarchy goes as "master > minor > rubri > micro"
    '''
    def __init__(self):
        self.graph = ConjunctiveGraph()
        self.graph.namespace_manager.bind('skos', SKOS)
        self.graph.namespace_manager.bind('hisco', HISCO)
        self.graph.namespace_manager.bind('dcterms', DCTERMS)
    
    def parse_major(self):
        '''
        Parse the page with the major groups
        '''
        # Load the page
        doc = BeautifulSoup(requests.get(ROOT + MAJOR_URL).content)
        
        # Find the major groups
        major_groups = []
        major_group = None
        for table in doc.find_all('table', attrs={'border':'0'}):
            for row in table.find_all('tr'):
                for col in row.find_all('td'):
                    # Skip empty rows
                    if len(col.text) == 1:
                        continue
                    # We are starting a new group
                    if col.text.startswith('Majorgroup'):
                        # Save the one we were building if any
                        if major_group != None:
                            major_groups.append(major_group)
                        m = re.search("Majorgroup ([^ ]*) ", col.text)
                        major_group = {}
                        major_group['title'] = col.text
                        major_group['code'] = m.group(1).replace('/','-')
                    # We have a description
                    if col.text.startswith('Workers'):
                        major_group['description'] = col.text
                    # We have links to minor
                    if col.text.startswith('List Minor'):
                        link = col.find_all('a')[0]['href']
                        major_group.setdefault('links',[])
                        major_group['links'].append(link)
        # Add the last group in the making
        if major_group != None:
            major_groups.append(major_group)

        # Add the groups to the graph
        for group in major_groups:
            major_group_uri = HISCO['scheme-%s' % group['code']]
            self.graph.add((major_group_uri, RDF.type, SKOS['ConceptScheme']))
            self.graph.add((major_group_uri, DCTERMS.title, Literal(group['title'])))
            self.graph.add((major_group_uri, DCTERMS.description, Literal(group['description'])))
            
        # Process the the minor links
        for group in major_groups:
            for link in group['links']:
                self.parse_minor(link)
            
    def parse_minor(self, url):
        '''
        Parse a page with minor groups
        '''
        # Load the page
        doc = BeautifulSoup(requests.get(ROOT + url).content)
        
        # Find the right table
        table = doc.find('table', attrs={'cellspacing':'8', 'cellpadding':'0'})
        
        # Look for the minor groups
        minor_groups = []
        minor_group = None
        columns = table.find_all('td')
        for index in range(0,len(columns)):
            col = columns[index]
            # New group
            if re.match('[0-9]{2}', col.text):
                if minor_group != None:
                    minor_groups.append(minor_group)
                minor_group = {}
                minor_group['code'] = col.text
                minor_group['title'] = columns[index+1].text
                link = columns[index+1].find_all('a')[0]['href']
                minor_group.setdefault('links',[])
                minor_group['links'].append(link)
                minor_group['description'] = columns[index+2].text
        
        # Add the groups to the graph
        for group in minor_groups:
            minor_group_uri = HISCO['scheme-%s' % group['code']]
            self.graph.add((minor_group_uri, RDF.type, SKOS['ConceptScheme']))
            self.graph.add((minor_group_uri, DCTERMS.title, Literal(group['title'])))
            self.graph.add((minor_group_uri, DCTERMS.description, Literal(group['description'])))
    
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
    
    def _compact_string(self, string):
        return string.replace('\n', '').replace('\r','').replace(' ', '')
    
    def get_output(self):
        self.graph.serialize(destination=sys.stdout, format='n3')
        
if __name__ == '__main__':
    hisco2rdf = Hisco2RDF()
    hisco2rdf.parse_major()
    #hisco2rdf.parse_minor("list_minor.php?text01=7&&text01_qt=strict")    
    hisco2rdf.get_output()

