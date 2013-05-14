#!/usr/bin/env python
''' Checks all repositories from a Github organization for compliant READMEs.

Runs in a long-running loop, results are posted to an S3 page.

Amazon S3 connection parameters will be looked for in boto's standard config
locations: /etc/boto.cfg, ~/.boto  or environment variables AWS_ACCESS_KEY_ID
and AWS_SECRET_ACCESS_KEY (http://code.google.com/p/boto/wiki/BotoConfig).
'''
from os import environ
from time import sleep
from os.path import dirname
from optparse import OptionParser
from datetime import datetime
from boto import connect_s3, connect_cloudwatch
from jinja2 import Environment, FileSystemLoader
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
        #
        # List all current repositories.
        #
        passed, failed = 0, 0
        repos = filter(lib.is_current_repo, lib.generate_repos())
        
        for repo in repos:
            is_compliant, commit_sha, reasons = lib.is_compliant_repo(repo)
            repo.update(dict(passed=is_compliant, sha=commit_sha, reasons=reasons))
            
            if is_compliant:
                passed += 1
    
            else:
                failed += 1
        
        repos.sort(key=lambda repo: (int(repo['passed']), repo['name'].lower()))

        #
        # Prepare destination and template for output HTML.
        #
        key = connect_s3().get_bucket(opts.bucket).new_key('observations.html')
        env = Environment(loader=FileSystemLoader(dirname(__file__)))
        tpl = env.get_template('observations.html')
        
        #
        # Render and upload output HTML to S3.
        #
        html = tpl.render(repos=repos, timestamp=str(datetime.now()))
        kwargs = dict(headers={'Content-Type': 'text/html'}, policy='public-read')
        key.set_contents_from_string(html, **kwargs)
        
        #
        # Save pass/fail metrics to Cloudwatch.
        # Use a linear convolution kernel over past hour of failure counts.
        #
        k = 15
        failures = (failures + [failed])[-k:]
        kernel = [n * 1./(k - 1) - .5 for n in range(k)]
        change = sum([n * f for (n, f) in zip(kernel, failures)])

        cloudwatch = connect_cloudwatch()
        cloudwatch.put_metric_data(opts.namespace, 'Passed', passed, unit='Count')
        cloudwatch.put_metric_data(opts.namespace, 'Failed', failed, unit='Count')
        cloudwatch.put_metric_data(opts.namespace, 'Change', change, unit='Count')
        
        sleep(60 * 60/k)
