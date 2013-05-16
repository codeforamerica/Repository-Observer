from datetime import datetime, timedelta
from urlparse import urljoin
from base64 import b64decode
from re import compile, I
from math import ceil

import logging

from requests import get as http_get
from dateutil.parser import parse as dateutil_parse
from BeautifulSoup import BeautifulSoup
from markdown2 import markdown
from dateutil.tz import tzutc

#
# Global configuration parameters, some overriden by command-line opts below.
#
per_page = 25
http_auth = None
org_name = None

any_pat = compile(r'.+')
head_pat = compile(r'^h[123]$', I)
subhead_pat = compile(r'^h[23456]$', I)
body_tags = 'p', 'pre', 'ol', 'ul'

def url(path):
    ''' Join an absolute path to the Github API base.
    '''
    return urljoin('https://api.github.com', path)

def get_data(url):
    ''' Retrieve JSON data from a url.
    '''
    logging.debug('Loading %s' % url)
    
    resp = http_get(url, headers={'User-Agent': 'Python'}, auth=http_auth)
    
    if resp.status_code not in range(200, 299):
        return None
    
    return resp.json()

def generate_repos():
    ''' Generate list of repo dictionaries.
    '''
    #
    # http://developer.github.com/v3/orgs/#get-an-organization
    #
    user_info = get_data(url('/orgs/%s' % org_name))
    
    #
    # 1, 2, 3, etc. for each page of listed repos.
    #
    repo_count = user_info['public_repos']
    page_nums = range(1, 1 + int(ceil(repo_count / float(per_page))))

    for page in page_nums:
        #
        # http://developer.github.com/v3/repos/#list-organization-repositories
        #
        page_url = url('/orgs/%s/repos?per_page=%d&page=%d' % (org_name, per_page, page))

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
    ''' Return (boolean, string, list) tuple for a repository readme.
    
        First element will be True for a compliant repo, False otherwise.
        Second element will be a commit hash for the repository or None.
        Third element will be a list of strings with reasons for failure.
    '''
    readme_url = url('/repos/%(full_name)s/readme' % repo)
    readme = get_data(readme_url)
    
    commits_url = url('/repos/%(full_name)s/commits?per_page=1' % repo)
    commits = get_data(commits_url)
    commit_hash = commits[0]['sha']
    
    #
    # Repository has a README file.
    #
    if readme is None:
        return False, commit_hash, ['Missing README']
    
    text = b64decode(readme['content'])
    soup = BeautifulSoup(markdown(text))
    reasons = []
    
    if not has_installation_section(soup):
        reasons.append('No installation guide')
    
    #
    # Done.
    #
    if reasons:
        return False, commit_hash, reasons
    
    return True, commit_hash, []

def has_installation_section(soup):
    ''' Return true if the tag soup has a populated installation section.
    
        Looks for headers with words like 'install', 'build', or 'deploy'.
    '''
    texts = soup.findAll(text=compile(r'\bInstall(ation)?\b|\bBuild(ing)?\b|\bDeploy(ing|ment)?\b', I))
    found = filter(has_content, texts)
    
    return bool(found)

def has_content(text):
    ''' Return true if the text element looks like a head with some content under it.
    '''
    head = text.findParent(head_pat)
    
    if not head:
        # Not in a header
        return False
    
    sibling = head.findNextSibling(any_pat)
    
    if not hasattr(sibling, 'name'):
        # Found nothing
        return False
    
    if sibling.name in body_tags:
        # Found something
        return True
    
    if subhead_pat.match(sibling.name) and sibling.name > head.name:
        # Found sub-sections
        return True
    
    # Who knows
    return False
