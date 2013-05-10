from os import environ
from optparse import OptionParser
from datetime import datetime, timedelta
from urlparse import urljoin
from base64 import b64decode
from math import ceil

import logging

from requests import get as http_get
from dateutil.parser import parse as dateutil_parse
from dateutil.tz import tzutc

per_page = 25
http_headers = {'User-Agent': 'Python'}
http_auth = None

def url(path):
    ''' Join an absolute path to the Github API base.
    '''
    return urljoin('https://api.github.com', path)

def get_data(url):
    ''' Retrieve JSON data from a url.
    '''
    logging.debug('Loading %s' % url)
    
    resp = http_get(url, headers=http_headers, auth=http_auth)
    
    if resp.status_code not in range(200, 299):
        return None
    
    return resp.json()

def generate_repos():
    ''' Generate list of repo dictionaries.
    '''
    #
    # http://developer.github.com/v3/users/#get-a-single-user
    #
    user_info = get_data(url('/users/codeforamerica'))
    
    #
    # 1, 2, 3, etc. for each page of listed repos.
    #
    repo_count = user_info['public_repos']
    page_nums = range(1, 1 + int(ceil(repo_count / float(per_page))))

    for page in page_nums:
        #
        # http://developer.github.com/v3/repos/#list-user-repositories
        #
        page_url = url('/users/codeforamerica/repos?per_page=%d&page=%d' % (per_page, page))

        for repo in get_data(page_url):
            yield repo

def is_current_repo(repo):
    ''' Return True for a current repo, False otherwise.
    '''
    if repo['pushed_at'] is None:
        #
        # Never pushed means probably empty?
        #
        logging.debug('%(name)s has never been pushed' % repo)
        return False
    
    create_cutoff = datetime(2013, 5, 6, tzinfo=tzutc())
    push_cutoff = datetime.now(tzutc()) - timedelta(days=30)

    created_at = dateutil_parse(repo['created_at'])
    pushed_at = dateutil_parse(repo['pushed_at'])
    
    if created_at > create_cutoff:
        #
        # Repository created after May 2013, when we started looking.
        #
        logging.debug('%(name)s created recently enough: %(created_at)s' % repo)
        return True
    
    if pushed_at > push_cutoff:
        #
        # Repository pushed within the past 30 days.
        #
        logging.debug('%(name)s updated recently enough: %(pushed_at)s' % repo)
        return True
    
    logging.debug('%(name)s is too old: %(pushed_at)s' % repo)
    return False

def is_compliant_repo(repo):
    ''' Return True for a compliant repo, False otherwise.
    '''
    readme_url = url('/repos/codeforamerica/%(name)s/readme' % repo)
    readme = get_data(readme_url)
    
    #
    # Repository has a README file.
    #
    return bool(readme is not None)
    
    if readme is not None:
        print b64decode(readme['content'])

parser = OptionParser(usage='''python %prog

Username and password will be found in environment variables
GITHUB_USERNAME and GITHUB_PASSWORD if not provided in options.''')

defaults = dict(username=environ.get('GITHUB_USERNAME', None),
                password=environ.get('GITHUB_PASSWORD', None),
                loglevel=logging.INFO)

parser.set_defaults(**defaults)

parser.add_option('-u', '--username', dest='username', help='Github username, default %(username)s.' % defaults)
parser.add_option('-p', '--password', dest='password', help='Github password, default %(password)s.' % defaults)

parser.add_option('-v', '--verbose', dest='loglevel', action='store_const', const=logging.DEBUG)
parser.add_option('-q', '--quiet', dest='loglevel', action='store_const', const=logging.WARNING)

if __name__ == '__main__':

    opts, args = parser.parse_args()
    
    logging.basicConfig(level=opts.loglevel, format='%(levelname)s - %(message)s')
    http_auth = (opts.username, opts.password)

    for repo in generate_repos():
        if not is_current_repo(repo):
            continue
    
        elif is_compliant_repo(repo):
            print 'pass', repo['full_name']

        else:
            print 'fail', repo['full_name']
