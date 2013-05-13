#!/usr/bin/env python
''' Checks all repositories from a Github organization for compliant READMEs.
'''
from os.path import dirname
from optparse import OptionParser
from jinja2 import Environment, FileSystemLoader
import logging
import lib

parser = OptionParser(usage='python %prog\n\n' + __doc__.strip())

defaults = dict(username=None, password=None, organization=None, loglevel=logging.INFO)

parser.set_defaults(**defaults)

parser.add_option('-u', '--username', dest='username', help='Github username, default %s.' % repr(defaults['username']))
parser.add_option('-p', '--password', dest='password', help='Github password, default %s.' % repr(defaults['password']))
parser.add_option('-o', '--organization', dest='organization', help='Github organization, default %s.' % repr(defaults['organization']))

parser.add_option('-v', '--verbose', dest='loglevel', action='store_const', const=logging.DEBUG)
parser.add_option('-q', '--quiet', dest='loglevel', action='store_const', const=logging.WARNING)

if __name__ == '__main__':

    opts, args = parser.parse_args()
    
    logging.basicConfig(level=opts.loglevel, format='%(levelname)s - %(message)s')
    lib.http_auth = (opts.username, opts.password)
    lib.org_name = opts.organization
    
    repos = filter(lib.is_current_repo, lib.generate_repos())
    
    for repo in repos:
        is_compliant, commit_sha, reasons = lib.is_compliant_repo(repo)
        repo.update(dict(passed=is_compliant, sha=commit_sha, reasons=reasons))
    
    repos.sort(key=lambda repo: (repo['passed'], repo['name'].lower()))
    
    env = Environment(loader=FileSystemLoader(dirname(__file__)))
    tpl = env.get_template('observations.html')
    
    print tpl.render(repos=repos)
