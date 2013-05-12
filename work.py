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
from boto import connect_s3, connect_cloudwatch
import logging
import lib

if __name__ == '__main__':
    lib.http_auth = environ['GITHUB_USERNAME'], environ['GITHUB_PASSWORD']
    lib.org_name = environ['GITHUB_ORGANIZATION']
    
    failures = []
    
    while True:
        out = StringIO()
        print >> out, '#', datetime.now()
        
        passed, failed = 0, 0
    
        for repo in lib.generate_repos():
            if not lib.is_current_repo(repo):
                continue
        
            is_compliant, readme_sha = lib.is_compliant_repo(repo)
            
            if is_compliant:
                print >> out, 'pass', repo['full_name'], readme_sha
                passed += 1
    
            else:
                print >> out, 'fail', repo['full_name'], readme_sha
                failed += 1

        key = connect_s3().get_bucket('github-observer').new_key('observations.txt')
        kwargs = dict(headers={'Content-Type': 'text/plain'}, policy='public-read')
        key.set_contents_from_string(out.getvalue(), **kwargs)
        
        failures = (failures + [failed])[-20:]
        change = failures[-1] - failures[0]

        cloudwatch = connect_cloudwatch()
        cloudwatch.put_metric_data('Github Observer', 'Passed', passed, unit='Count')
        cloudwatch.put_metric_data('Github Observer', 'Failed', failed, unit='Count')
        cloudwatch.put_metric_data('Github Observer', 'Change', change, unit='Count')
        
        sleep(3 * 60)
