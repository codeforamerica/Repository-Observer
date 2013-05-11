#!/usr/bin/env python
''' Checks all repositories from a Github organization for compliant READMEs.

Username, password and organization name will be found in environment
variables GITHUB_USERNAME, GITHUB_PASSWORD and GITHUB_ORGANIZATION.
Amazon S3 connection parameters will be found in environment variables
AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.
'''
from os import environ
from time import sleep
from StringIO import StringIO
from datetime import datetime
from boto import connect_s3
import logging
import lib

if __name__ == '__main__':
    lib.http_auth = environ['GITHUB_USERNAME'], environ['GITHUB_PASSWORD']
    lib.org_name = environ['GITHUB_ORGANIZATION']
    
    while True:
        out = StringIO()
        print >> out, '#', datetime.now()
    
        for repo in lib.generate_repos():
            if not lib.is_current_repo(repo):
                continue
        
            elif lib.is_compliant_repo(repo):
                print >> out, 'pass', repo['full_name']
    
            else:
                print >> out, 'fail', repo['full_name']

        key = connect_s3().get_bucket('github-observer').new_key('observations.txt')
        kwargs = dict(headers={'Content-Type': 'text/plain'}, policy='public-read')
        key.set_contents_from_string(out.getvalue(), **kwargs)
        
        sleep(5 * 60)
