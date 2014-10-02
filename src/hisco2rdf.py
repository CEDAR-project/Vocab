'''
Created on 25 sep. 2014

Uses Python3 to avoid issues with UTF-8 encoding

@author: cgueret
'''
# coding: utf-8
import requests
import re
import sys
import logging
import sqlite3
from bs4 import BeautifulSoup
from rdflib import Namespace
from rdflib.graph import ConjunctiveGraph
from rdflib.namespace import RDF, DCTERMS, RDFS
from rdflib.term import Literal

ROOT = "http://historyofwork.iisg.nl/"
HISCO_TREE = "major.php"
OCCUPATIONAL_TITLES = "list_hiswi.php"
LANG_MAP = {'French':'fr', 'German':'de', 'Dutch':'nl', 'Swedish':'sv',
            'Portugese':'pt', 'English':'en', 'Norwegian':'no', 'Spanish':'es',
            'Catalan':'ct', 'Danish':'da', 'Greek': 'gr'}

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
HISCO = Namespace("http://example.org#")
SDMX_DIMENSION = Namespace("http://purl.org/linked-data/sdmx/2009/dimension#")
SDMX_CODE = Namespace("http://purl.org/linked-data/sdmx/2009/code#")

log = logging.getLogger("HISCO2RDF")
logging.basicConfig(format='%(asctime)s [%(name)s:%(levelname)s] %(message)s')
log.setLevel(logging.INFO)

class Hisco2RDF():
    '''
    Scrapes the HISCO Web site
    The hierarchy goes as "master > minor > rubri > micro"
    '''
    def __init__(self):
        # The graph to store the data
        self.graph = ConjunctiveGraph()
        self.graph.namespace_manager.bind('skos', SKOS)
        self.graph.namespace_manager.bind('hisco', HISCO)
        self.graph.namespace_manager.bind('dcterms', DCTERMS)
        self.graph.namespace_manager.bind('sdmx-dimension', SDMX_DIMENSION)
        self.graph.namespace_manager.bind('sdmx-code', SDMX_CODE)
        
        # SQLite DB for the cache
        self.cache = sqlite3.connect('cache.db')
        cursor = self.cache.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS  page (url text, html text)")
        self.cache.commit()
    
    def __del__(self):
        self.cache.close()
        
    def get_page(self, url):
        c = self.cache.cursor()
        c.execute("SELECT * FROM page WHERE url = ?", (url,))
        res = c.fetchone()
        doc = None
        if res == None:
            doc = requests.get(url).content
            c.execute("INSERT INTO page VALUES (?,?)", (url, doc))
            self.cache.commit()
        else:
            (_, doc) = res            
        return BeautifulSoup(doc)

    def get_output(self):
        # Print to the screen
        outfile = sys.stdout.buffer
        self.graph.serialize(destination=outfile, format='n3')
        
        # Save to the file
        outfile = open('../hisco.ttl', "wb")
        self.graph.serialize(destination=outfile, format='n3')
        outfile.close()
        
    def parse_hisco_tree(self):
        '''
        Parse the hisco tree
        '''
        # Load the page
        doc = self.get_page(ROOT + HISCO_TREE)
        
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
                        major_group['code'] = m.group(1).replace('/', '-')
                    # We have a description
                    if col.text.startswith('Workers'):
                        major_group['description'] = col.text
                    # We have links to minor
                    if col.text.startswith('List Minor'):
                        link = col.find_all('a')[0]['href']
                        major_group.setdefault('links', [])
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
            
        # Now move onto the minor groups following the links
        for major_group in major_groups:
            major_group_uri = HISCO['scheme-%s' % major_group['code']]
            for link in major_group['links']:
                log.info("Parse %s" % link)
        
                # Look for the minor groups
                minor_groups = self._parse_records_table(link, 2)
        
                # Add the groups to the graph
                for minor_group in minor_groups:
                    minor_group_uri = HISCO['scheme-%s' % minor_group['code']]
                    self.graph.add((minor_group_uri, RDF.type, SKOS['ConceptScheme']))
                    self.graph.add((minor_group_uri, DCTERMS.title, Literal(minor_group['title'])))
                    self.graph.add((minor_group_uri, DCTERMS.description, Literal(minor_group['description'])))
                    self.graph.add((major_group_uri, SKOS.related, minor_group_uri))

        # Now move onto the rubri groups following the links
        for minor_group in minor_groups:
            minor_group_uri = HISCO['scheme-%s' % minor_group['code']]
            for link in minor_group['links']:
                log.info("Parse %s" % link)
                
                # Look for the minor groups
                rubri_groups = self._parse_records_table(link, 3)
                
                # Add the groups to the graph
                for rubri_group in rubri_groups:
                    rubri_group_uri = HISCO['scheme-%s' % rubri_group['code']]
                    self.graph.add((rubri_group_uri, RDF.type, SKOS['ConceptScheme']))
                    self.graph.add((rubri_group_uri, DCTERMS.title, Literal(rubri_group['title'])))
                    self.graph.add((rubri_group_uri, DCTERMS.description, Literal(rubri_group['description'])))
                    self.graph.add((minor_group_uri, SKOS.related, rubri_group_uri))
    
        # Finally extract the micro, these are the actual HISCO codes
        for rubri_group in rubri_groups:
            rubri_group_uri = HISCO['scheme-%s' % rubri_group['code']]
            for link in rubri_group['links']:
                log.info("Parse %s" % link)
                
                # Look for the minor groups
                micro_groups = self._parse_records_table(link, 5)
                
                # Add the groups to the graph
                for micro_group in micro_groups:
                    hisco_uri = self._get_hisco_uri(micro_group['code'])
                    self.graph.add((hisco_uri, RDF.type, SKOS['Collection']))
                    self.graph.add((hisco_uri, DCTERMS.title, Literal(micro_group['title'])))
                    self.graph.add((hisco_uri, DCTERMS.description, Literal(micro_group['description'])))
                    self.graph.add((rubri_group_uri, SKOS.related, hisco_uri))
                
    def parse_occupational_titles(self):
        '''
        Scrape the section of the site about occupational titles
        Last page = http://historyofwork.iisg.nl/list_hiswi.php?step=1845&publish=Y&modus=ftsearch
        '''
        parsed_status_page = set()
        next_page = OCCUPATIONAL_TITLES
        
        while next_page != None:
            log.info("Parse %s" % next_page)
                
            # Load the page
            doc = self.get_page(ROOT + next_page)
                
            # Find the right table
            table = doc.find('table', attrs={'cellspacing':'0', 'cellpadding':'2', 'border':'0'})
    
            # Look for all the titles 
            for row in table.find_all('tr')[1:]:  # Skip the header
                cols = row.find_all('td')
                occupation_title = cols[1].text
                details_page_link = cols[1].find_all('a')[0]['href']
                language = LANG_MAP[cols[2].text]
                hisco_code = cols[3].text.replace('*', '')
                
                # TODO : replace the occupation_index by the DB id found in the URL
                # Get the DB index from details_page_link
                m = re.search('know_id=([^&]*)&', details_page_link)
                occupation_index = m.group(1)
                
                # Add the concept to the graph
                resource = self._get_occupation_title_uri(occupation_index)
                self.graph.add((resource, RDF.type, SKOS['Concept']))
                self.graph.add((resource, SKOS.prefLabel, Literal(occupation_title, lang=language)))
                self.graph.add((resource, SKOS.member, self._get_hisco_uri(hisco_code)))
                
                # Get more information about the title and add it as a member of the collection
                details_page = self.get_page(ROOT + details_page_link)
                details_table = details_page.find('table', attrs={'cellspacing':'8', 'cellpadding':'0'})
                keyvalues = {}
                for details_row in details_table.find_all('tr'):
                    details_cols = details_row.find_all('td')
                    keyvalues[details_cols[0].text.strip()] = details_cols[-1]

                # Do we know the gender ?
                if 'Gender' in keyvalues:
                    sex = SDMX_CODE['sex-U']
                    if keyvalues['Gender'].text.strip() == 'Male':
                        sex = SDMX_CODE['sex-M'] 
                    elif keyvalues['Gender'].text.strip() == 'Female':
                        sex = SDMX_CODE['sex-F']
                    self.graph.add((resource, SDMX_DIMENSION['sex'], sex))
                
                # Do we have a translation in English ?
                if 'Translation' in keyvalues:
                    trans = Literal(keyvalues['Translation'].text.strip().replace('´', "'"), lang='en')
                    self.graph.add((resource, SKOS.altLabel, trans))
                    
                # Do we know the status ?
                if 'Status' in keyvalues:
                    # Add the status
                    status = keyvalues['Status'].text.strip()
                    self.graph.add((resource, HISCO['status'], self._get_status_uri(status)))
                    # Parse the status page if necessary
                    status_page = keyvalues['Status'].find_all('a')[0]['href']
                    if status_page not in parsed_status_page:
                        self._parse_status_page(status_page)
                        parsed_status_page.add(status_page)
                    
                # TODO Deal with the provenance
                
            # Look for the "next" link
            next_table = doc.find('table', class_='nextprev')
            next_page = None
            for link in next_table.find_all('a'):
                if 'Next' in link.text:
                    next_page = link['href']
            
    def _parse_status_page(self, url):
        '''
        Parses a status page such as http://historyofwork.iisg.nl/status.php?int02=32
        '''
        log.info("Parse status %s" % url)
        
        # Load the page
        doc = self.get_page(ROOT + url)
        
        # Find the data about this status
        status_uri = None
        for line in doc.find('pre').text.split('\n'):
            if re.match("^[0-9]* [a-zA-Z]*", line):
                m = re.search("^([0-9]*) ([a-zA-Z]*)", line)
                status_uri = self._get_status_uri(m.group(1))
                self.graph.add((status_uri, RDF.type, HISCO['Status']))
                self.graph.add((status_uri, RDFS.label, Literal(m.group(2))))
                self.graph.add((status_uri, SKOS.prefLabel, Literal(m.group(2))))
                self.graph.add((status_uri, SKOS.notation, Literal(m.group(1))))
            if re.match("^[A-Z]{2}:\t[a-zA-Z]*", line):
                m = re.search("^([A-Z]{2}):\t([a-zA-Z]*)", line)
                lang_code = m.group(1).lower()
                label = Literal(m.group(2), lang = lang_code)
                self.graph.add((status_uri, SKOS.altLabel, label))
                
        # Describe the class
        status_class = HISCO['Status']
        descr = doc.find('table', attrs={'width':'600'}).text.strip().split('\r\n')
        self.graph.add((status_class, RDF.type, RDFS.Class))
        self.graph.add((status_class, RDFS.label, Literal(descr[0])))
        self.graph.add((status_class, DCTERMS.comment, Literal(descr[1])))
        
        # Describe the property
        status_property = HISCO['status']
        self.graph.add((status_property, RDF.type, RDF.Property))
        self.graph.add((status_property, RDFS.label, Literal("status associated to the occupation")))
        self.graph.add((status_property, RDFS.range, HISCO['Status']))
        self.graph.add((status_property, RDFS.domain, SKOS.Concept))
        
    def _parse_records_table(self, url, size):
        '''
        Minor, Rubri and Micro have the same structure except an additional
        column for Micro with links to the titles
        '''
        # Load the page
        doc = self.get_page(ROOT + url)
        
        # Find the right table
        table = doc.find('table', attrs={'cellspacing':'8', 'cellpadding':'0'})
        
        # Look for the minor groups
        groups = []
        group = None
        columns = table.find_all('td')
        for index in range(0, len(columns)):
            # New group
            if re.match("[0-9]{%d}" % size, columns[index].text):
                if group != None:
                    groups.append(group)
                group = {}
                group['code'] = columns[index].text
                group['title'] = columns[index + 1].text
                link = columns[index + 1].find_all('a')[0]['href']
                group.setdefault('links', [])
                group['links'].append(link)
                group['description'] = columns[index + 2].text
                if columns[index + 3].text == "Display Titles":
                    link = columns[index + 3].find_all('a')[0]['href']
                    group['titles_link'] = link
        groups.append(group)
        
        return groups
            
    def _get_hisco_uri(self, code):
        return HISCO['hisco-%s' % code]
    
    def _get_occupation_title_uri(self, code):
        return HISCO['occupation-%s' % code]
    
    def _get_status_uri(self, code):
        return HISCO['status-%s' % code]
            
if __name__ == '__main__':
    hisco2rdf = Hisco2RDF()
    # hisco2rdf.parse_hisco_tree()
    hisco2rdf.parse_occupational_titles()
    # TODO parse images
    # TODO parse encyclopedia
    hisco2rdf.get_output()

