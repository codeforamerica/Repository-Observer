#!/usr/bin/env python
''' Checks a repo or repos for compliant READMEs.

Amazon S3 connection parameters will be looked for in boto's standard config
locations: /etc/boto.cfg, ~/.boto  or environment variables AWS_ACCESS_KEY_ID
and AWS_SECRET_ACCESS_KEY (http://code.google.com/p/boto/wiki/BotoConfig).
'''
from os import environ
from optparse import OptionParser
from base64 import b64decode
import logging
import lib

from BeautifulSoup import BeautifulSoup
from markdown2 import markdown

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

        readme = lib.get_data(lib.url('/repos/%s/readme' % repo_name))
        
        if readme is None:
            print 'Missing README'
            continue
        
        text = b64decode(readme['content'])
        soup = BeautifulSoup(markdown(text))
        reasons = []
        
        if lib.has_relocated_section(soup):
            print 'Has relocated'
            continue
    
        if not lib.has_installation_section(soup):
            print 'No installation guide'
