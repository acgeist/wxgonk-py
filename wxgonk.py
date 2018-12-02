#!/usr/bin/env python3
# wxgonk.py

# TODO:
# -turn all print statements into a debug string, then generate html
#  using yattag.  Html debugging page should include links to metars,
#  tafs, fields, and a google map, and should have a whole report of
#  all testing that has been done.  In the end this should be used
#  to present the data (i.e. build the display table).

import coord_man

import random
import re 
import sys
import urllib.request
import webbrowser
from typing import List
# reference http://www.diveintopython3.net/your-first-python-program.html
try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree

FILING_MINS = {'vis': 1.5, 'ceiling': 500}
TEST_FIELDS = []
ALT_REQ = {'vis': 3.0, 'ceiling': 2000}
ALT_MINS = {'vis': 2.0, 'ceiling': 1000}
NO_CEIL_VAL = 9999
timeRegex = ''

def makeUrl(dataType:str, stationList:List[str], country:str = 'us') -> str:
    '''Make the URL for each dataset'''
    if not isinstance(dataType, str):
        raise InvalidFunctionInput("Data type must be a string")
    if not dataType.upper() in ['TAFS', 'TAF', 'METAR', 'METARS', 'FIELD', 'FIELDS',
            'COUNTRY']:
        raise InvalidFunctionInput("Data type must be 'TAFS', 'TAF', " 
        + "'METAR', 'METARS', 'FIELD', 'FIELDS', or COUNTRY")
    possible_country_codes =  ' af ax al dz as ad ao ai aq ag ar am aw au at az'
    possible_country_codes += ' bs bh bd bb by be bz bj bm bt bo bq ba bw bv br'
    possible_country_codes += ' io vg bn bg bf bi kh cm ca cv ky cf td cl cn cx'
    possible_country_codes += ' cc co km ck cr hr cu cw cy cz cd dk dj dm do tl'
    possible_country_codes += ' ec eg sv gq er ee et fk fo fj fi fr gf pf tf ga'
    possible_country_codes += ' gm ge de gh gi gr gl gd gp gu gt gg gn gw gy ht'
    possible_country_codes += ' hm hn hk hu is in id ir iq ie im il it ci jm jp'
    possible_country_codes += ' je jo kz ke ki xk kw kg la lv lb ls lr ly li lt'
    possible_country_codes += ' lu mo mk mg mw my mv ml mt mh mq mr mu yt mx fm'
    possible_country_codes += ' md mc mn me ms ma mz mm na nr np nl an nc nz ni'
    possible_country_codes += ' ne ng nu nf kp mp no om pk pw ps pa pg py pe ph'
    possible_country_codes += ' pn pl pt pr qa cg re ro ru rw bl sh kn lc mf pm'
    possible_country_codes += ' vc ws sm st sa sn rs cs sc sl sg sx sk si sb so'
    possible_country_codes += ' za gs kr ss es lk sd sr sj sz se ch sy tw tj tz'
    possible_country_codes += ' th tg tk to tt tn tr tm tc tv vi ug ua ae gb us'
    possible_country_codes += ' um uy uz vu va ve vn wf eh ye zm zw'
    if not country.lower() in possible_country_codes.split():
        raise InvalidFunctionInput("Function makeUrl was passed " + country +
                ", which was not recognized as a valid 2-letter identifier." +
                " reference https://laendercode.net/en/2-letter-list.html.")
    if not re.search('[a-z]{2}', country):
        raise InvalidFunctionInput("country must be a 2-letter abbreviation " + 
                "in accordance with ISO-3166-1 ALPHA-2. Reference " + 
                "https://laendercode.net/en/2-letter-list.html")
    url = 'https://www.aviationweather.gov/adds/dataserver_current/httpparam?'
    url += 'requestType=retrieve'
    url += '&format=xml'
    if dataType.upper() in ['TAFS', 'TAF']:
        url += '&dataSource=tafs'
        url += '&hoursBeforeNow=24'
        url += '&mostRecentForEachStation=true'
    elif dataType.upper() in ['METAR', 'METARS']:
        url += '&dataSource=metars'
        # Don't use METAR if unable to get one newer than 3 hours
        url += '&hoursBeforeNow=3'
        url += '&mostRecentForEachStation=true'
    elif dataType.upper() in ['FIELDS', 'FIELD']:
        url += '&dataSource=stations'
    elif dataType.upper() in ['COUNTRY']:
        url += '&dataSource=stations'
        url += '&stationString=~' + country
        return url
    else:
        return 'https://www.aviationweather.gov/adds/dataserver_current'
    url += '&stationString='
    url += '%20'.join(stationList)
    return url

class InvalidFunctionInput(Exception):
    pass
class InvalidDataType(Exception):
    pass

def getRoot(url:str):
    return etree.fromstring(urllib.request.urlopen(url).read())
    
def can_file_metar(metar_node, field:str) -> bool:
    '''Return filing legality based on current conditions'''
    vis_at_dest = float(metar_node.findall('.//*[station_id="' + DEST_ID 
        + '"]/visibility_statute_mi')[0].text)
    print('In function "can_file_metar" the visibility at ' + DEST_ID + ' is ' 
            + '{:.1f}'.format(vis_at_dest) + 'sm, which is ', end='')
    if vis_at_dest >= FILING_MINS['vis']:
        print('greater than or equal to ', end='')
    else:
        print('less than ', end='')
    # Reference: https://mkaz.blog/code/python-string-format-cookbook/
    print('FILING_MINS["vis"] (' + '{:.1f}'.format(FILING_MINS['vis']) + 'sm)')
    return vis_at_dest > FILING_MINS['vis'] 

def has_ceiling(node) -> bool:
    '''Return whether or not node contains a BKN/OVC/OVX line'''
    layers = list(filter(lambda layer: 
        layer.get('sky_cover') in ['BKN', 'OVC', 'OVX'], node)) 
    return False if len(layers) == 0 else True

def get_ceiling(node) -> int:
    '''Return the ceiling in feet AGL, or 9999 if no ceiling exists'''
    if not has_ceiling(node):
        return NO_CEIL_VAL
    else:
        layers = list(filter(lambda layer: 
            layer.get('sky_cover') in ['BKN', 'OVC', 'OVX'], node)) 
        layers = list(map(lambda layer: 
            int(layer.get('cloud_base_ft_agl')), layers))
        return min(layers)

def get_vis(node) -> str:
    return node.find('visibility_statute_mi').text

def req_alt(node) -> bool:
    '''Return whether or not an alternate is required'''
    vis_at_dest = float(node.findall('.//*[station_id="' + DEST_ID 
        + '"]/visibility_statute_mi')[0].text)
    print('In function "req_alt" the visibility at ' + DEST_ID + ' is ' 
            + '{:.1f}'.format(vis_at_dest) + 'sm, which is ', end='')
    if vis_at_dest >= ALT_REQ['vis'] :
        print('greater than or equal to ', end='')
    else:
        print('less than ', end='')
    print('ALT_REQ["vis"] (' + '{:.1f}'.format(ALT_REQ['vis']) + 'sm)')
    ceil_at_dest = get_ceiling(node)
    print('In function "req_alt" the ceiling at ' + DEST_ID + ' is '
            + '{:.0f}'.format(ceil_at_dest) + 'ft agl, which is ', end='')
    if ceil_at_dest >= ALT_REQ['ceiling']:
        print('greater than or equal to ', end='')
    else:
        print('less than ', end='')
    print('ALT_REQ["ceiling"] (' + '{:.0f}'.format(ALT_REQ['ceiling']) + 'ft)')
    return vis_at_dest >= ALT_REQ['ceiling'] and ceil_at_dest >= ALT_REQ['ceiling']

def print_raw_metar(field:str) -> None:
    '''Print the raw metar for a given 4-letter identifier'''
    if not isinstance(field, str) or re.match(r'\b[a-zA-Z]{4}\b', field) == None:
        raise InvalidFunctionInput("Invalid input at print_raw_metar: " + field)
    if field in TEST_FIELDS:
        print(metar_root.findall('.//*[station_id="' + field.upper()
            + '"]/raw_text')[0].text)
    else:
        temp_url = makeUrl('METAR', field.split())
        temp_root = getRoot(temp_url)
        print(
                temp_root.findall('.//raw_text')[0].text if 
                int(temp_root.find('data').attrib['num_results']) > 0 else
                'METAR for ' + field + ' not found.')

def print_node(node, indent:int = 0):
    '''Print an XML tree'''
    # TODO: include attributes
    print(indent * '\t', end='')
    print(node.tag if node.text == None else node.tag + ': ' + node.text)
    if len(node.findall('*')) > 0:
        for child in node:
            print_node(child, indent + 1)

def genBadFieldList() -> List[str]:
    country_string = 'ar br bg ca cl cn dk eg ee fr de in ie il it jp nl nz kp '
    country_string += 'no ph ru sg za kr tr ua ae gb us ve vn'
    country_list = country_string.split()
    is_valid_choice = False
    while not is_valid_choice:
        country_choice = random.choice(country_list)
        print('country_choice is ' + country_choice + ' - num_results = ', end='')
        bad_field_url = makeUrl('country', [], country_choice)
        bad_field_root = getRoot(bad_field_url)
        bad_fields_list = [] 
        print(bad_field_root.find('data').attrib['num_results'])
        if bad_field_root.find('data').attrib['num_results'] == 0:
            country_list.remove(country_choice)
            continue
        for field in bad_field_root.findall('.//Station'):
            bad_fields_list.append(field.find('station_id').text)
        rand_field_list = []
        # http requests start to break with >1000 fields
        for i in range(0, min(1000, len(bad_fields_list))):
            rand_field_list.append(random.choice(bad_fields_list))
        bad_metar_url = makeUrl('METAR', rand_field_list)
        bad_metar_root = getRoot(bad_metar_url)
        bad_metars = bad_metar_root.findall('.//METAR')
        bad_metars = list(filter(lambda metar:
            not re.search('\d+', metar.find('station_id').text) and
            metar.find('visibility_statute_mi') is not None and
            float(metar.find('visibility_statute_mi').text) < ALT_REQ['vis'],
            bad_metars))
        if len(bad_metars) > 2:
            is_valid_choice = True
        else:
            print('No fields in ' + country_choice + ' currently have visibility',
                '< ' + str(ALT_REQ['vis']) + '. Picking another country.')
    print(str(len(bad_metars)) + ' fields have visibility < ' + 
            str(ALT_REQ['vis']))
    if len(bad_metars) > 10:
        del bad_metars[10:]
    bad_field_ids = []
    for metar in bad_metars:
        bad_field_ids.append(metar.find('station_id').text)
    return bad_field_ids

def test():
    print('TEST_FIELDS = ' + ' '.join(TEST_FIELDS))
    print('Home station/destination = ' + DEST_ID, end=' ')
    home_lat = float(field_root.findall('.//*.[station_id="' + DEST_ID 
            + '"]/latitude')[0].text) 
    home_lon = float(field_root.findall('.//*.[station_id="' + DEST_ID 
            + '"]/longitude')[0].text) 
    print('('
        + field_root.findall('.//*.[station_id="' + DEST_ID 
            + '"]/site')[0].text + '), located at lat/long: ' 
        + str(home_lat) + ', '+ str(home_lon))
    for root in roots:
        print('Received ' + root.find('data').attrib['num_results']
                + ' ' +  root.find('data_source').attrib['name'] + ': ', 
                end='')
        for id in root.findall('.//station_id'):
            print(id.text, end=' ')
        print()
    for field in field_root.findall('.//Station'):
        if not field.find('station_id').text in DEST_ID:
            print(field.find('station_id').text + '('
                    + field_root.findall('.//*.[station_id="' 
                        + field.find('station_id').text
                        + '"]/site')[0].text + ') is ' 
                    + str(round(coord_man.dist_between_coords(home_lat, home_lon,
                        field.find('latitude').text, 
                        field.find('longitude').text)))
                    + ' statute miles from ' 
                    + DEST_ID)

    # https://docs.python.org/2/library.xml.etree.elementtree.html#elementtree-xpath
    metars = metar_root.findall('.//METAR')

    for metar in metars:
        print(metar.find('raw_text').text)

    print('Can I legally file to ' + DEST_ID + '?')
    print_raw_metar(DEST_ID)
    print('can_file_metar: ' + str(can_file_metar(metar_root, DEST_ID)))
    print('has_ceiling: ' + str(has_ceiling(metar_root.findall('.//*[station_id="' 
        + DEST_ID + '"]/sky_condition'))))
    print('ceiling: ' + str(get_ceiling(metar_root.findall('.//*[station_id="'
        + DEST_ID + '"]/sky_condition'))))
    print('visibility: ' + get_vis(metar_root.find('.//*[station_id="'
        + DEST_ID + '"]')))
    if can_file_metar(metar_root, DEST_ID):
        print('Do I require an alternate to file to ' + DEST_ID + '?')
        print('req_alt: ' + str(req_alt(metar_root)))


    timeRegex = re.compile(r'''       # Strings are of form YYYY-MM-DDTHH:MM:SSZ
        ^                   # start of string
        (?P<yr>20\d{2})-    # grab 4-digit year (as long as it is in the range
                            # 2000-2099) and put it in named group "yr"
        (?P<mon>\d{2})-     # grab 2-digit month and put it in named group "mon"
        (?P<day>\d{2})T     # grab 2-digit day/date and put in named group "day"
        (?P<hr>\d{2}):      # grab 2-digit hour and put in named group "hr"
        (?P<min>\d{2}):     # grab 2-digit minute and put in named group "min"
        \d{2}Z$             # no need to put seconds in a group
        ''', re.VERBOSE|re.IGNORECASE)
    test_time = metar_root.findall('.//METAR/observation_time')[0].text
    result = re.search(timeRegex, test_time).group()
    print('Result: ', result)

if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
        if re.match(r'\b[a-zA-Z]{4}\b', arg) == None:
            print('The command line argument "' + arg + '" did not match '
                    + 'the pattern for a valid ICAO identifier.')
            break
        else:
            TEST_FIELDS.append(arg.upper())
else:
    TEST_FIELDS = genBadFieldList()
DEST_ID = TEST_FIELDS[0]

taf_url = makeUrl('tafs', TEST_FIELDS)    
metar_url = makeUrl('metars', TEST_FIELDS)    
field_url = makeUrl('fields', TEST_FIELDS)    
url_file = open("/var/www/html/urls.html", "w")
file_contents_string = '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
file_contents_string += '<meta charset="utf-8">\n<title>WxGonk Troubleshooting'
file_contents_string += '</title>\n</head>\n<body>\n<h1>Most recent URLs:</h1>'
file_contents_string += '\n<a href=' + metar_url + '>METARs</a>'
file_contents_string += '\n<a href=' + taf_url + '>TAFs</a>'
file_contents_string += '\n<a href=' + field_url + '>FIELDs</a>\n'
file_contents_string += '</body>\n</html>'
url_file.write(file_contents_string)
url_file.close()
urls = [taf_url, metar_url, field_url]
    
taf_root = getRoot(taf_url)
metar_root = getRoot(metar_url)
field_root = getRoot(field_url)
roots = [taf_root, metar_root, field_root]

# reference https://stackoverflow.com/a/419185
if __name__ == '__main__':
    pass
