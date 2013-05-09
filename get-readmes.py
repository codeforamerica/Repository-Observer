from json import loads as json_load
from operator import add as concat
from urlparse import urljoin
from urllib import urlopen
from pprint import pprint
from math import ceil

import logging

per_page = 100

def url(path):
    return urljoin('https://api.github.com', path)

def pages(repo_count):
    return range(1, 1 + int(ceil(repo_count / float(per_page))))

if __name__ == '__main__':

    #
    # http://developer.github.com/v3/users/#get-a-single-user
    #
    user_info = json_load(urlopen(url('/users/codeforamerica')).read())
    
    repos = []
    
    for page in pages(user_info['public_repos']):
        #
        # http://developer.github.com/v3/repos/#list-user-repositories
        #
        page_url = url('/users/codeforamerica/repos?per_page=%d&page=%d' % (per_page, page))
        logging.debug('Loading %s' % page_url)
        repos += json_load(urlopen(page_url).read())
    
    print 'Found', len(repos), 'repos.'
