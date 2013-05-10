from json import loads as json_load
from operator import add as concat
from datetime import datetime, timedelta
from base64 import b64decode
from urlparse import urljoin
from urllib import urlopen
from pprint import pprint
from time import sleep
from math import ceil

import logging

from dateutil.parser import parse as dateutil_parse
from dateutil.tz import tzutc

per_page = 25

def url(path):
    return urljoin('https://api.github.com', path)

def get_data(url):
    return json_load(urlopen(url).read())

def pages(repo_count):
    return range(1, 1 + int(ceil(repo_count / float(per_page))))

def repos():
    '''
    '''
    #
    # http://developer.github.com/v3/users/#get-a-single-user
    #
    user_info = get_data(url('/users/codeforamerica'))

    for page in pages(user_info['public_repos']):
        #
        # http://developer.github.com/v3/repos/#list-user-repositories
        #
        page_url = url('/users/codeforamerica/repos?per_page=%d&page=%d' % (per_page, page))
        logging.debug('Loading %s' % page_url)
        
        for repo in get_data(page_url):
            yield repo

if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

    right_now = datetime.now(tzutc())
    cutoff_dt = right_now - timedelta(days=90)
    
    for repo in repos():
        readme_url = url('/repos/codeforamerica/%(name)s/readme' % repo)
        created_at = dateutil_parse(repo['created_at'])
        pushed_at = dateutil_parse(repo['pushed_at'])
        
        if pushed_at < cutoff_dt:
            continue
        
        print readme_url
    
        print 'full_name:', repo['full_name']
        print 'created_at:', repo['created_at'], (right_now - created_at)
        print 'pushed_at:', repo['pushed_at'], (right_now - pushed_at)
    
        sleep(1)
