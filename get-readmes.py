#!/usr/bin/env python
''' Checks all repositories from a Github organization for compliant READMEs.
'''
from optparse import OptionParser
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

    for repo in lib.generate_repos():
        if not lib.is_current_repo(repo):
            continue
    
        is_compliant, readme_sha, reasons = lib.is_compliant_repo(repo)
        
        if is_compliant:
            print 'pass', repo['full_name'], readme_sha, reasons

        else:
            print 'fail', repo['full_name'], readme_sha, reasons
