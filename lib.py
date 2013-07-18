from datetime import datetime, timedelta
from urlparse import urljoin
from base64 import b64decode
from re import compile, I
from math import ceil
from boto import connect_s3

import logging

from requests import get as http_get
from dateutil.parser import parse as dateutil_parse
from BeautifulSoup import BeautifulSoup
from markdown2 import markdown
from dateutil.tz import tzutc
import json


logging.basicConfig(level=logging.DEBUG)
#
# Global configuration parameters, some overriden by command-line opts below.
#
per_page = 25
http_auth = None
org_name = None

any_pat = compile(r'.+')
head_pat = compile(r'^h[1234]$', I)
subhead_pat = compile(r'^h[23456]$', I)
body_tags = 'p', 'pre', 'ol', 'ul'

repos_without_installation_guides = set()

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

def get_star_count(repo_name, owner):
    ''' Get count of stargazers for a repo
    '''
    page_url = url('/repos/%s/%s/stargazers' % (owner, repo_name))
    data = get_data(page_url)
    if not data:
        return 0
    return len(data)

def get_watcher_count(repo_name, owner):
    ''' Get count of stargazers for a repo
    '''
    page_url = url('/repos/%s/%s' % (owner, repo_name))
    repo = get_data(page_url)
    if not repo:
        return 0
    return repo['watchers']

def get_contributor_count(repo_name, owner):
    ''' Get count of stargazers for a repo
    '''
    page_url = url('/repos/%s/%s/contributors' % (owner, repo_name))
    data = get_data(page_url)
    if not data:
        return 0
    return len(get_data(page_url))

def get_forks(repo_name, owner):
    ''' Get list of forks for a repo
    '''

    forks = []
    page_num = 1
    while True:
        page_url = url('/repos/%s/%s/forks?per_page=%d&page=%d' % 
            (owner, repo_name, per_page, page_num))
        data = get_data(page_url)

        if data is None:
            break
        if not data:
            break

        for fork in data:
            forks.append(dict(name=fork['full_name'], created_at=fork['created_at'],
            updated_at=fork['updated_at'], pushed_at=fork['pushed_at']))

        page_num += 1

    return forks

def get_pulls(repo_name, owner, state):
    ''' Get list of pull requests for a repo
        state can be "open" or "closed"
    '''
    # 
    # http://developer.github.com/v3/pulls/#list-pull-requests
    # 
    pulls = []
    page_num = 1
    while True:

        pulls_url = url('/repos/%s/%s/pulls?state=%s&per_page=%d&page=%d' % 
            (owner, repo_name, state, per_page, page_num))
        data = get_data(pulls_url)

        if data is None:
            break
        if not data:
            break

        for pull in data:
            pulls.append(dict(html_url=pull['html_url'], number=pull['number'], 
                title=pull['title'], body=pull['body'], 
                created_at=pull['created_at'], updated_at=pull['updated_at'], 
                closed_at=pull['closed_at'], state=pull['state'], 
                username=pull['user']['login'], avatar_url=pull['user']['avatar_url']))

        page_num += 1

    return pulls


def get_issues(repo_name, owner, state):
    ''' Get list of issues for a repo
        State can be open or closed
    '''
    # 
    # http://developer.github.com/v3/issues/#list-issues-for-a-repository
    # 
    issues = []
    page_num = 1
    # Get all issues of this state
    while True:
        issues_url = url('/repos/%s/%s/issues?state=%s&per_page=%d&page=%d' % 
            (owner, repo_name, state, per_page, page_num))
        data = get_data(issues_url)
        # If request failed
        if data is None:
            break

        # If request succeeded but was empty
        if not data:
            break

        for issue in data:
            issues.append(dict(html_url=issue['html_url'], number=issue['number'],
                title=issue['title'], body=issue['body'], comments=issue['comments'],
                created_at=issue['created_at'], updated_at=issue['updated_at'],
                closed_at=issue['closed_at'], state=issue['state'],
                username=issue['user']['login'], avatar_url=issue['user']['avatar_url']))
            
        page_num = page_num + 1

    return issues


def output_data(data, dest, ctype):        
    # Output collected data
    #
    content_types = {'html':'text/html', 'json':'application/json'}
    if dest.startswith('s3://'):
        bucket_name, key_name = dest[5:].split('/', 1)
        bucket = connect_s3().get_bucket(bucket_name)
        key = bucket.new_key(key_name)
        kwargs = dict(headers={'Content-Type': content_types[ctype]},
            policy='public-read')
        key.set_contents_from_string(data, **kwargs)
        
    else:
        with open(dest, 'w') as out:
            out.write(data)

def get_graph_data(dest, reponames):

    graph_data = {name: {'labels': [], 'closed_issue': [], 'star': [],
        'fork': []} for name in reponames}
    data = {}
    if dest.startswith('s3://'):
        conn = connect_s3()
        bucket_name, key_name = dest[5:].split('/', 1)

        bucket = conn.get_bucket(bucket_name)
        key = bucket.get_key(key_name)
        if key:
            data = json.loads(key.get_contents_as_string())
        else:
            key = bucket.new_key(key_name)
            print 'Missing file on S3, pleas run again.'
    else:
        with open(dest, 'r') as f:
            data = f.read()
            if data:
                data = json.loads(data)
            else:
                pass

    if data:
        graph_data = data
    return graph_data


def get_list_totals(repo_data):
    ''' Get total statistics from a whole list of repos
    '''
    total_closed_issues = 0
    total_open_issues = 0
    total_closed_pulls = 0
    total_open_pulls = 0
    total_stars = 0
    total_forks = 0

    for repo in repo_data:
        total_closed_issues = total_closed_issues + repo['closed_issues_count']
        total_open_issues = total_open_issues + repo['open_issues_count']
        total_closed_pulls =total_closed_pulls + repo['closed_pulls_count']
        total_open_pulls =total_open_pulls + repo['open_pulls_count']
        total_stars =total_stars + repo['stars_count']
        total_forks =total_forks + repo['forks_count']

    return {"total_closed_issues": total_closed_issues,
        "total_open_issues": total_open_issues,
        "total_closed_pulls": total_closed_pulls, 
        "total_open_pulls": total_open_pulls,
        "total_stars": total_stars, "total_forks": total_forks}


def fetch_repolist_info(config_file):
    ''' Fetch data about repo list
        Output data to s3 destination
    '''
    with open(config_file, 'r') as f:
        config = json.loads(f.read())
        repo_list = config['repos']

    for arepo in repo_list:
        if 'name' in arepo and 'owner' in arepo:
            arepo.update(get_repo_info(arepo['name'], arepo['owner']))
        else:
            logging.debug('Config file is invalid.')

    return repo_list

def fill_data(repo_hist):
    end_dt = datetime.now()

    for repo in repo_hist.iterkeys():
        stars = []
        closed_issues = []
        forks = []
        labels = []
        days_ago = 1
        end_label = (end_dt - timedelta(days=days_ago)).strftime('%Y-%m-%d')

        if repo_hist[repo]['labels']:
            start_label = repo_hist[repo]['labels'][-1]
        else:
            start_label = end_label


        while end_label > start_label:
            labels.insert(0, end_label)
            forks.insert(0, repo_hist[repo]['fork'][-1])
            stars.insert(0, repo_hist[repo]['star'][-1])
            closed_issues.insert(0, repo_hist[repo]['closed_issue'][-1])
            days_ago += 1
            end_label = (end_dt - timedelta(days=days_ago)).strftime('%Y-%m-%d')


        repo_hist[repo]['closed_issue'].extend(closed_issues)
        repo_hist[repo]['star'].extend(stars)
        repo_hist[repo]['fork'].extend(forks)
        repo_hist[repo]['labels'].extend(labels)
        for group in repo_hist[repo].iterkeys():
            while len(repo_hist[repo][group]) >= 365:
                repo_hist[repo][group] = repo_hist[repo][group][1:]

    return repo_hist

def get_repo_info(repo_name, owner):
    ''' Get a dictionary of all repo info.
    '''
    forks = get_forks(repo_name, owner)
    forks_count = len(forks)

    open_pulls = []
    open_pulls.extend(get_pulls(repo_name, owner, 'open'))
    open_pulls_count = len(open_pulls)

    closed_pulls = []
    closed_pulls.extend(get_pulls(repo_name, owner, 'closed'))
    closed_pulls_count = len(closed_pulls)

    open_issues = []
    open_issues.extend(get_issues(repo_name, owner, 'open'))
    open_issues_count = len(open_issues)

    closed_issues = []
    closed_issues.extend(get_issues(repo_name, owner,'closed'))
    closed_issues_count = len(closed_issues)


    stars_count = get_star_count(repo_name, owner)
    watch_count = get_watcher_count(repo_name, owner)
    cont_count = get_contributor_count(repo_name, owner)

    return dict(forks=forks, open_pulls=open_pulls, closed_pulls=closed_pulls,
        open_issues=open_issues, closed_issues=closed_issues, forks_count=forks_count,
        stars_count=stars_count, watch_count=watch_count, contributor_count=cont_count,
        open_pulls_count=open_pulls_count, closed_pulls_count=closed_pulls_count,
        open_issues_count=open_issues_count, closed_issues_count=closed_issues_count)

def generate_repos():
    ''' Generate list of repo dictionaries.
    '''
    #
    # http://developer.github.com/v3/orgs/#get-an-organization
    #
    user_info = get_data(url('/orgs/%s' % org_name))
    if user_info is None:
        print "Could not generate repo info, check organization name."
        exit(1)
    
    #
    # 1, 2, 3, etc. for each page of listed repos.
    #
    repo_count = user_info['public_repos']
    page_nums = range(1, 1 + int(ceil(repo_count / float(per_page))))

    for page in page_nums:
        #
        # http://developer.github.com/v3/repos/#list-organization-repositories
        #
        page_url = url('/orgs/%s/repos?per_page=%d&page=%d' % 
            (org_name, per_page, page))

        for repo in get_data(page_url):
            yield repo

def is_current_repo(repo):
    ''' Return True for a current repo, False otherwise.
    '''
    if repo is None:
        logging.debug('Failed to generate a repo.')
        return False
    if repo['pushed_at'] is None:
        #
        # Never pushed means probably empty?
        #
        logging.debug('%(name)s has never been pushed' % repo)
        return False

    if repo['size'] is 0:
        #
        # 0 size means probably empty?
        #
        logging.debug('%(name)s has a size of 0' % repo)
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
    commit_hash = None
    if commits:
        commit_hash = commits[0]['sha']
    else:
        logging.debug('Could not get commits for %(full_name)s' % repo)
    
    #
    # Repository has a README file.
    #
    if readme is None:
        return False, commit_hash, ['Missing README']
    
    text = b64decode(readme['content'])
    soup = BeautifulSoup(markdown(text))
    reasons = []
    
    if has_relocated_section(soup):
        return True, commit_hash, []
    
    if not has_installation_section(soup):
        if repo['full_name'] not in repos_without_installation_guides:
            reasons.append('No installation guide')
    
    #
    # Done.
    #
    if reasons:
        return False, commit_hash, reasons
    
    return True, commit_hash, []

def has_relocated_section(soup):
    ''' Return true if the tag soup has a relocation section.
    
        Looks for headers with words including 'repository has moved'
    '''
    texts = soup.findAll(text=compile(r'\bRepository has moved\b', I))
    found = filter(has_content, texts)
    
    return bool(found)

def has_installation_section(soup):
    ''' Return true if the tag soup has a populated installation section.
    
        Looks for headers with words like 'install', 'build', 'setup', or 'deploy'.
    '''
    texts = soup.findAll(text=compile(r'\bInstall(ation|ing)?\b|\bBuild(ing)?\b|\bSetup\b|\bDeploy(ing|ment)?\b', I))
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
