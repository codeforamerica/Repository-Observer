from os import environ
from optparse import OptionParser
from json import loads as json_load
from operator import add as concat
from httplib import HTTPConnection, HTTPSConnection
from datetime import datetime, timedelta
from urlparse import urljoin, urlparse
from base64 import b64decode, b64encode
from pprint import pprint
from time import sleep
from math import ceil

import logging

from dateutil.parser import parse as dateutil_parse
from dateutil.tz import tzutc

per_page = 25
http_headers = {'User-Agent': 'Python'}

def url(path):
    return urljoin('https://api.github.com', path)

def get_data(url):
    ''' Retrieve JSON data from a url.
    '''
    logging.debug('Loading %s' % url)
    
    scheme, host, path, p, query, f = urlparse(url)
    connector = HTTPSConnection if scheme == 'https' else HTTPConnection

    conn = connector(host)
    conn.request('GET', path + '?' + query, headers=http_headers)

    resp = conn.getresponse()
    
    if resp.status not in range(200, 299):
        return None
    
    return json_load(resp.read())

def pages(repo_count):
    return range(1, 1 + int(ceil(repo_count / float(per_page))))

def repos():
    ''' Generate list of repo dictionaries.
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

        for repo in get_data(page_url):
            yield repo

parser = OptionParser(usage='''python %prog

Username and password will be found in environment variables
GITHUB_USERNAME and GITHUB_PASSWORD if not provided in options.''')

defaults = dict(username=environ.get('GITHUB_USERNAME', None),
                password=environ.get('GITHUB_PASSWORD', None))

parser.set_defaults(**defaults)

parser.add_option('-u', '--username', dest='username', help='Github username, default %(username)s.' % defaults)
parser.add_option('-p', '--password', dest='password', help='Github password, default %(password)s.' % defaults)

if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
    
    opts, args = parser.parse_args()
    
    http_headers['Authorization'] = 'Basic ' + b64encode('%s:%s' % (opts.username, opts.password))

    right_now = datetime.now(tzutc())
    cutoff_dt = right_now - timedelta(days=90)
    
    for repo in repos():
        if repo['pushed_at'] is None:
            continue
    
        readme_url = url('/repos/codeforamerica/%(name)s/readme' % repo)
        created_at = dateutil_parse(repo['created_at'])
        pushed_at = dateutil_parse(repo['pushed_at'])
        
        if pushed_at < cutoff_dt:
            continue
        
        print 'full_name:', repo['full_name']
        print 'created_at:', repo['created_at'], (right_now - created_at)
        print 'pushed_at:', repo['pushed_at'], (right_now - pushed_at)
        
        readme = get_data(readme_url)
        
        if readme is not None:
            print b64decode(readme['content'])
