#!/usr/bin/env python
''' Checks all repositories from a Github organization for compliant READMEs.

Runs in a long-running loop, results are sent to the destination argument,
which may be a local file name like 'observations.html' or a remote S3 path
like 's3://bucket-name/observations.html' (the 's3://' prefix is required).

Amazon S3 connection parameters will be looked for in boto's standard config
locations: /etc/boto.cfg, ~/.boto  or environment variables AWS_ACCESS_KEY_ID
and AWS_SECRET_ACCESS_KEY (http://code.google.com/p/boto/wiki/BotoConfig).
'''
from os import environ
from os.path import dirname
from time import sleep, time
from operator import itemgetter
from optparse import OptionParser
from datetime import datetime, timedelta
from boto import connect_s3, connect_cloudwatch
from jinja2 import Environment, FileSystemLoader
import logging
import json
import lib

parser = OptionParser(usage='python %prog <destination>\n\n' + __doc__.strip())

defaults = dict(username=environ.get('GITHUB_USERNAME', None),
                password=environ.get('GITHUB_PASSWORD', None),
                organization='codeforamerica', namespace='Github Observer',
                send_counts=False, loglevel=logging.INFO)

parser.set_defaults(**defaults)

parser.add_option('-u', '--username', dest='username', help='Github username, defaults to GITHUB_USERNAME environment variable (%s).' % repr(defaults['username']))
parser.add_option('-p', '--password', dest='password', help='Github password, defaults to GITHUB_PASSWORD environment variable (%s).' % repr(defaults['password']))
parser.add_option('-o', '--organization', dest='organization', help='Github organization, default %s.' % repr(defaults['organization']))
parser.add_option('-n', '--namespace', dest='namespace', help='Cloudwatch namespace, default %s.' % repr(defaults['namespace']))
parser.add_option('--send-counts', dest='send_counts', action='store_true', help='Turn on sending to Cloudwatch.')

#
# Exceptional repositories.
#
lib.repos_without_installation_guides.add('codeforamerica/cfa_coder_sounds')

if __name__ == '__main__':
    opts, (destination, ) = parser.parse_args()
    
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
        # Gather metrics.
        #
        cloudwatch = connect_cloudwatch()

        period = 60 * 60
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)
        
        pass_history = cloudwatch.get_metric_statistics(period, start_dt, end_dt, 'Passed', opts.namespace, ['Average'])
        fail_history = cloudwatch.get_metric_statistics(period, start_dt, end_dt, 'Failed', opts.namespace, ['Average'])

        pass_history = [int(round(m['Average'])) for m in sorted(pass_history, key=itemgetter('Timestamp'))]
        fail_history = [int(round(m['Average'])) for m in sorted(fail_history, key=itemgetter('Timestamp'))]
        
        history_json = json.dumps(dict(period=period, passed=pass_history, failed=fail_history))

        #
        # Prepare template for output HTML and render.
        #
        env = Environment(loader=FileSystemLoader(dirname(__file__)))
        tpl = env.get_template('observations.html')

        html = tpl.render(repos=repos, history=history_json, timestamp=int(time()), datetime=str(datetime.now())[:19])
        
        #
        # Output HTML.
        #
        if destination.startswith('s3://'):
            bucket_name, key_name = destination[5:].split('/', 1)
            key = connect_s3().get_bucket(bucket_name).new_key(key_name)
            kwargs = dict(headers={'Content-Type': 'text/html'}, policy='public-read')
            key.set_contents_from_string(html, **kwargs)
        
        else:
            with open(destination, 'w') as out:
                out.write(html)
        
        #
        # Save pass/fail metrics to Cloudwatch.
        #
        k = 15
        failures = (failures + [failed])[-k:]
        change = failures[-1] - failures[0]

        if opts.send_counts:
            cloudwatch.put_metric_data(opts.namespace, 'Passed', passed, unit='Count')
            cloudwatch.put_metric_data(opts.namespace, 'Failed', failed, unit='Count')
            cloudwatch.put_metric_data(opts.namespace, 'Change', change, unit='Count')
        
        sleep(60 * 60/k)
