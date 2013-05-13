#!/usr/bin/env python
''' Checks all repositories from a Github organization for compliant READMEs.

Runs in a long-running loop, results are posted to an S3 page.

Amazon S3 connection parameters will be looked for in boto's standard config
locations: /etc/boto.cfg, ~/.boto  or environment variables AWS_ACCESS_KEY_ID
and AWS_SECRET_ACCESS_KEY (http://code.google.com/p/boto/wiki/BotoConfig).
'''
from os import environ
from time import sleep
from optparse import OptionParser
from StringIO import StringIO
from datetime import datetime
from boto import connect_s3, connect_cloudwatch
import logging
import lib

parser = OptionParser(usage='python %prog\n\n' + __doc__.strip())

defaults = dict(username=environ.get('GITHUB_USERNAME', None),
                password=environ.get('GITHUB_PASSWORD', None),
                organization='codeforamerica', bucket='github-observer',
                namespace='Github Observer', loglevel=logging.INFO)

parser.set_defaults(**defaults)

parser.add_option('-u', '--username', dest='username', help='Github username, defaults to GITHUB_USERNAME environment variable (%s).' % repr(defaults['username']))
parser.add_option('-p', '--password', dest='password', help='Github password, defaults to GITHUB_PASSWORD environment variable (%s).' % repr(defaults['password']))
parser.add_option('-o', '--organization', dest='organization', help='Github organization, default %s.' % repr(defaults['organization']))
parser.add_option('-n', '--namespace', dest='namespace', help='Cloudwatch namespace, default %s.' % repr(defaults['namespace']))
parser.add_option('-b', '--bucket', dest='bucket', help='S3 destination bucket, default %s.' % repr(defaults['bucket']))

if __name__ == '__main__':
    opts, args = parser.parse_args()
    
    lib.http_auth = opts.username, opts.password
    lib.org_name = opts.organization
    
    failures = []
    
    while True:
        out = StringIO()
        print >> out, '#', datetime.now()
        
        passed, failed = 0, 0
    
        for repo in lib.generate_repos():
            if not lib.is_current_repo(repo):
                continue
        
            is_compliant, readme_sha, reasons = lib.is_compliant_repo(repo)
            
            if is_compliant:
                print >> out, 'pass', repo['full_name'], readme_sha, reasons
                passed += 1
    
            else:
                print >> out, 'fail', repo['full_name'], readme_sha, reasons
                failed += 1

        key = connect_s3().get_bucket(opts.bucket).new_key('observations.txt')
        kwargs = dict(headers={'Content-Type': 'text/plain'}, policy='public-read')
        key.set_contents_from_string(out.getvalue(), **kwargs)
        
        failures = (failures + [failed])[-20:]
        change = failures[-1] - failures[0]

        cloudwatch = connect_cloudwatch()
        cloudwatch.put_metric_data(opts.namespace, 'Passed', passed, unit='Count')
        cloudwatch.put_metric_data(opts.namespace, 'Failed', failed, unit='Count')
        cloudwatch.put_metric_data(opts.namespace, 'Change', change, unit='Count')
        
        sleep(3 * 60)
