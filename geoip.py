#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys,os
import urllib2
import time
import math
import random
import argparse
import xml.etree.ElementTree as ET
from urlparse import urlparse
from dns.resolver import Resolver

# To use this script, please enter your own Google Place API key here
API_KEY = ''

"""
Steps:
1. search nearby
https://maps.googleapis.com/maps/api/place/nearbysearch/xml?type=business&location=31.2304,121.4737&radius=10000&key=
2. search based on id
https://maps.googleapis.com/maps/api/place/details/xml?placeid=ChIJSfp2vkFwsjURxuR6sUVe-jM&key=
3. get website
4. get web server info: nslookup, whois, etc
"""


def get_zip_code(loc):
    url = "https://maps.googleapis.com/maps/api/geocode/xml?&latlng=%s&key=%s" % (loc, API_KEY)
    req = urllib2.urlopen(url)
    tree = ET.parse(req)
    root = tree.getroot()

    status = find_element(root, 'status')
    if status != "OK":
        if status is "OVER_QUERY_LIMIT":
            sys.exit(1)
        print ">>>>>>> Bad request", url
        print status

    result = root.find('result')
    if result is None:
        print ">>>>>>> No result", url
        return None

    # Verify zip code
    if result.find("address_component") is None:
        print ">>>>>>> No address component exists", url
        return None

    zip_code = None
    for address_component in result.findall("address_component"):
        if find_element(address_component, "type") == "postal_code":
            zip_code = find_element(address_component, "long_name")

    return zip_code


def get_place_info(place_id):

    url = "https://maps.googleapis.com/maps/api/place/details/xml?" \
          "placeid=%s" \
          "&key=%s" % (place_id, API_KEY)
    # print url
    req = urllib2.urlopen(url)
    tree = ET.parse(req)

    root = tree.getroot()

    status = find_element(root, 'status')
    if status != "OK":
        if status is "OVER_QUERY_LIMIT":
            sys.exit(1)
        print ">>>>>>> Bad request", url
        print status
        return None, None, None

    result = root.find('result')
    if result is None:
        print ">>>>>>> No result", url
        return None, None, None

    # Verify zip code
    if result.find("address_component") is None:
        print ">>>>>>> No address component exists", url
        return None, None, None

    my_zip_code = None
    for address_component in result.findall("address_component"):
        if find_element(address_component, "type") == "postal_code":
            my_zip_code = find_element(address_component, "long_name")

    website = find_element(result, "website")
    lat = find_element(result.find("geometry").find("location"), "lat")
    lng = find_element(result.find("geometry").find("location"), "lng")

    """
    if my_zip_code is None:
        print ">>>>>>> Can't find zipcode", url

    if website is None:
        print ">>>>>>>> No website", url
    """

    return website, my_zip_code, (float(lat), float(lng))


def find_element(node, attr):
    try:
        return node.find(attr).text
    except:
        return None


def make_url_with_coordinate(loc):
    # TBD: hardcode 10km radius
    url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/xml?location=%s&radius=10000&type=business&key=%s' % (loc,API_KEY)
    return url


def search_nearby(loc):
    url = make_url_with_coordinate(loc)
    # print url
    ids = []

    req = urllib2.urlopen(url)
    # print "req",req
    tree = ET.parse(req)
    # print "tree",tree
    root = tree.getroot()
    # print "root",root
    status = find_element(root, 'status')
    # print "status",status
    while status == 'OK':
        if root.find('result') is None:
            break

        for result in root.findall('result'):
            # _name = result.find('name').text
            # _id = result.find('id').text
            # ids.append((_name, _id))
            # print result
            place_id = result.find('place_id').text
            if place_id is not None:
                ids.append(place_id)

        pagetoken = root.find('next_page_token')
        if pagetoken is None:
            break
        # print "pagetoken",pagetoken.text
        time.sleep(2)
        req = urllib2.urlopen(url+"&pagetoken="+pagetoken.text)
        # print url+"&pagetoken="+pagetoken.text
        tree = ET.parse(req)
        # print tree
        root = tree.getroot()
        # print root
        status = find_element(root, 'status')
        # print 'status',status
        if status == "OVER_QUERY_LIMIT":
            print 'key expires'
            sys.exit(1)

    return ids


def is_latitude(lat):
    if -90 < lat < 90:
        return True
    return False


def is_longitude(lng):
    if -180 < lng < 180:
        return True
    return False


def is_loc(loc):
    (lat,lng) = loc.split(',')
    try:
        lat,lng = float(lat),float(lng)
        if not is_latitude(lat) or not is_longitude(lng):
            return False
    except:
        return False
    return True


def is_same_zip_prefix(zip1, zip2):
    if zip2 is None or zip1 is None:
        return True
    for i in range(4):
        if zip1[i] != zip2[i]:
            return False
    return True


def get_random_loc(loc):
    location = None
    lat,lng = loc.split(',')
    lat = float(lat)
    lng = float(lng)
    r = RADIUS
    u = random.random()
    v = random.random()
    w = r*math.sqrt(u)
    t = 2*math.pi*v
    delta_lng = w*math.cos(t)/math.cos(lng/math.pi)
    delta_lat = w*math.sin(t)
    lat = round(lat + delta_lat, 6)
    lng = round(lng + delta_lng, 6)
    location = str(lat)+','+str(lng)
    return location


def find_servers_nearby(loc):
    resolver = Resolver()

    assert type(loc) == type(''), loc+' must be a string'
    # test loc is a real location
    assert is_loc(loc), loc+" is not a location coordinate, " \
                            "please enter a location coordinate in the format of latitude,longitude, " \
                            "e.g., 31.2304,121.4737"

    ids = search_nearby(loc)
    # print ids
    # print len(ids)

    loc_zip_code = get_zip_code(loc)
    print 'ZIP CODE:',loc_zip_code
    # assert loc_zip_code is not None, "Can not resolve the zip code of coordinate %c" % loc

    total = 0
    zip_code_not_match = 0
    no_website = 0
    no_ip = 0

    for place_id in ids:
        # print
        # print
        website, zip_code, loc_coordinate = get_place_info(place_id)
        if zip_code is None:
            continue

        # this is a real location
        total += 1

        if not is_same_zip_prefix(zip_code, loc_zip_code):
            # not belong to the same zip code, so rule it out
            zip_code_not_match += 1
            continue

        if website is None:
            no_website += 1
            continue

        url = urlparse(website)
        # presumably this is a domain name, maybe not
        domain = url.netloc
        ips = []

        try:
            answer = resolver.query(domain)

            for a in answer:
                ips.append(a.to_text())

            if len(ips) == 0:
                no_ip += 1
                continue
        except:
            ips.append(None)

        # print len(ips)

        # random select an IP address
        ip = random.choice(ips)

        # print place_id+"|"+website+"|"+zip_code+"|"+str(loc_coordinate)+"|"+ip
    try:
        print place_id , website , zip_code , loc_coordinate[0], loc_coordinate[1], ip
    except:
        print 'Some field does not exist'

    print 'Stat:', total, zip_code_not_match, no_website, no_ip


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def main():
    parser = argparse.ArgumentParser(description='Reproduce landmark discovery in the paper of NSDI 2012')
    # The list of remote servers
    parser.add_argument('-c', '--city', default="shanghai", type=str,
                        help='The city to scan')
    parser.add_argument('-f', '--file', default='city/shanghai', type=str,
                        help='The config file')
    args = parser.parse_args()

    assert args.file.endswith(args.city)

    city = args.city
    config_file = args.file

    os.system('mkdir -p result/'+city)

    fin = open(config_file, 'r')
    center_loc = fin.read()
    fin.close()

    original = sys.stdout
    for i in range(SAMPLE):
        loc = get_random_loc(center_loc)
        start = time.time()
        print 'Search:',loc,'at',start
        sys.stdout = open('result/'+city+'/'+loc, 'w')
        find_servers_nearby(loc)
        sys.stdout = original
        print 'Done:',time.time() - start
        time.sleep(60)


if __name__ == "__main__":
    main()


