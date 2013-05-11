#!/usr/bin/env python
''' Checks all repositories from a Github organization for compliant READMEs.

Username and password will be found in environment variables
GITHUB_USERNAME and GITHUB_PASSWORD if not provided in options.
'''
from os import environ
from optparse import OptionParser

import logging

import lib

parser = OptionParser(usage='python %prog\n\n' + __doc__.strip())

defaults = dict(username=environ.get('GITHUB_USERNAME', None),
                password=environ.get('GITHUB_PASSWORD', None),
                organization='codeforamerica',
                loglevel=logging.INFO)

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

    for repo in lib.generate_repos():
        if not lib.is_current_repo(repo):
            continue
    
        elif lib.is_compliant_repo(repo):
            print 'pass', repo['full_name']

        else:
            print 'fail', repo['full_name']
