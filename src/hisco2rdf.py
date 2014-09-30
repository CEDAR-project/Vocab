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
import logging

ROOT      = "http://historyofwork.iisg.nl/"
MAJOR_URL = "major.php"
SKOS      = Namespace("http://www.w3.org/2004/02/skos/core#")
HISCO     = Namespace("http://example.org#")
LANG_MAP  = {'French':'fr',
             'German':'de',
             'Dutch':'nl',
             'Swedish':'sv',
             'Portugese':'pt',
             'English':'en'}

log = logging.getLogger("HISCO2RDF")
logging.basicConfig(format = '%(asctime)s [%(name)s:%(levelname)s] %(message)s')
log.setLevel(logging.INFO)

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
        log.info("Parse %s" % url)
        
        # Look for the minor groups
        minor_groups = self._parse_records_table(url, 2)
        
        # Add the groups to the graph
        for group in minor_groups:
            minor_group_uri = HISCO['scheme-%s' % group['code']]
            self.graph.add((minor_group_uri, RDF.type, SKOS['ConceptScheme']))
            self.graph.add((minor_group_uri, DCTERMS.title, Literal(group['title'])))
            self.graph.add((minor_group_uri, DCTERMS.description, Literal(group['description'])))

        # Parse the sub links
        for group in minor_groups:
            for link in group['links']:
                self.parse_rubri(link)
        
    def parse_rubri(self, url):
        '''
        Parse a page with rubri groups
        '''
        log.info("Parse %s" % url)
        
        # Look for the minor groups
        groups = self._parse_records_table(url, 3)
        
        # Add the groups to the graph
        for group in groups:
            group_uri = HISCO['scheme-%s' % group['code']]
            self.graph.add((group_uri, RDF.type, SKOS['ConceptScheme']))
            self.graph.add((group_uri, DCTERMS.title, Literal(group['title'])))
            self.graph.add((group_uri, DCTERMS.description, Literal(group['description'])))
    
        # Parse the sub links
        for group in groups:
            for link in group['links']:
                self.parse_micro(link)
                
    def parse_micro(self, url):
        '''
        Parse a page with micro groups
        '''
        log.info("Parse %s" % url)
        
        # Look for the minor groups
        groups = self._parse_records_table(url, 5)
        
        # Add the groups to the graph
        for group in groups:
            group_uri = HISCO['scheme-%s' % group['code']]
            self.graph.add((group_uri, RDF.type, SKOS['ConceptScheme']))
            self.graph.add((group_uri, DCTERMS.title, Literal(group['title'])))
            self.graph.add((group_uri, DCTERMS.description, Literal(group['description'])))
    
    def _parse_records_table(self, url, size):
        '''
        Minor, Rubri and Micro have the same structure except an additional
        column for Micro with links to the titles
        '''
        # Load the page
        doc = BeautifulSoup(requests.get(ROOT + url).content)
        
        # Find the right table
        table = doc.find('table', attrs={'cellspacing':'8', 'cellpadding':'0'})
        
        # Look for the minor groups
        groups = []
        group = None
        columns = table.find_all('td')
        for index in range(0,len(columns)):
            # New group
            if re.match("[0-9]{%d}" % size, columns[index].text):
                if group != None:
                    groups.append(group)
                group = {}
                group['code'] = columns[index].text
                group['title'] = columns[index+1].text
                link = columns[index+1].find_all('a')[0]['href']
                group.setdefault('links',[])
                group['links'].append(link)
                group['description'] = columns[index+2].text
                if columns[index+3].text == "Display Titles":
                    link = columns[index+3].find_all('a')[0]['href']
                    group['titles_link'] = link
                    print link
        groups.append(group)
        
        log.info("Found %d group(s)" % len(groups))
        return groups
    
    def parse_titles_table(self, url):
        next_page = url
        
        while next_page != None:
            # Load the page
            doc = BeautifulSoup(requests.get(ROOT + next_page).content)
                
            # Find the right table
            table = doc.find('table', attrs={'cellspacing':'0', 'cellpadding':'2'})
    
            # Look for all the titles 
            for row in table.find_all('tr')[1:]: # Skip the header
                cols = row.find_all('td') 
                occupation_title = cols[1].text
                language = LANG_MAP[cols[2].text]
                hisco_code = cols[3].text.replace('*','')
                
                # Add the collection to the graph
                resource = self._get_hisco_code_uri(hisco_code)
                self.graph.add((resource, RDF.type, SKOS['Collection']))
                self.graph.add((resource, SKOS.altLabel, Literal(occupation_title, lang=language)))
                
                # Get more information about the title and add it as a member of the collection
                member_concept = self.parse_details_page(cols[1].find_all('a')[0]['href'])
                self.graph.add((resource, SKOS.member, member_concept))
                
            # Look for the "next" link
            table = doc.find('table', class_='nextprev')
            next_page = None
            for link in table.find_all('a'):
                if 'Next' in link.text:
                    next_page = link['href']
                    print next_page
            
    def _get_hisco_code_uri(self, code):
        return HISCO['occupation-%s' % code]
    
    def _get_occupation_title_uri(self, code):
        return HISCO['occupationtitle-%s' % code]
    
    def parse_details_page(self, url):
        # Extract the code of this occupation from the url
        code = None TODO
        resource = self._get_occupation_title_uri(code)
                
        # Load the page
        doc = BeautifulSoup(requests.get(ROOT + url).content)

        # Find the right table
        table = doc.find('table', attrs={'cellspacing':'8', 'cellpadding':'0'})
        
        # Get all the key-value pairs
        keyvalues = {}
        for row in table.find_all('tr'):
            cols = row.find_all('td')
            keyvalues[cols[0].text.strip()] = cols[-1].text.strip()

        #if 'Provenance' in keyvalues:
            
        return resource
            
    def get_output(self):
        self.graph.serialize(destination=sys.stdout, format='n3')
        
if __name__ == '__main__':
    hisco2rdf = Hisco2RDF()
    #hisco2rdf.parse_major()
    #hisco2rdf.parse_minor("list_minor.php?text01=7&&text01_qt=strict")
    #hisco2rdf.parse_rubri('list_rubri.php?keywords=11&keywords_qt=lstrict&orderby=keywords')
    #hisco2rdf.parse_micro('list_micro.php?keywords=110&keywords_qt=lstrict')
    hisco2rdf.parse_titles_table('list_hiswi.php?text02=11010&&text02_qt=lstrict&orderby=text02')
    #hisco2rdf.parse_details_page('detail_hiswi.php?know_id=10401&lang=')   
    #hisco2rdf.get_output()

