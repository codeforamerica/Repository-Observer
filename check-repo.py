#!/usr/bin/env python
''' Checks a repo or repos for compliant READMEs.

Amazon S3 connection parameters will be looked for in boto's standard config
locations: /etc/boto.cfg, ~/.boto  or environment variables AWS_ACCESS_KEY_ID
and AWS_SECRET_ACCESS_KEY (http://code.google.com/p/boto/wiki/BotoConfig).
'''
from os import environ
from optparse import OptionParser
import logging
import lib

parser = OptionParser(usage='python %prog <repo name(s)>\n\n' + __doc__.strip())

defaults = dict(username=environ.get('GITHUB_USERNAME', None),
                password=environ.get('GITHUB_PASSWORD', None),
                loglevel=logging.INFO)

parser.set_defaults(**defaults)

parser.add_option('-u', '--username', dest='username', help='Github username, defaults to GITHUB_USERNAME environment variable (%s).' % repr(defaults['username']))
parser.add_option('-p', '--password', dest='password', help='Github password, defaults to GITHUB_PASSWORD environment variable (%s).' % repr(defaults['password']))

if __name__ == '__main__':
    opts, repo_names = parser.parse_args()
    
    lib.http_auth = opts.username, opts.password
    
    for repo_name in repo_names:
        print repo_name, '...'
        
        passed, _, reasons = lib.is_compliant_repo(dict(full_name=repo_name))
        
        if not passed:
            print ', '.join(reasons)
