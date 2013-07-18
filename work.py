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
                send_counts=False, loglevel=logging.INFO,
                fetch=False, config='./config.json', 
                fetch_dest='s3://data.codeforamerica.org/repos/')

parser.set_defaults(**defaults)

parser.add_option('-u', '--username', dest='username', help='Github username, defaults to GITHUB_USERNAME environment variable (%s).' % repr(defaults['username']))
parser.add_option('-p', '--password', dest='password', help='Github password, defaults to GITHUB_PASSWORD environment variable (%s).' % repr(defaults['password']))
parser.add_option('-o', '--organization', dest='organization', help='Github organization, default %s.' % repr(defaults['organization']))
parser.add_option('-n', '--namespace', dest='namespace', help='Cloudwatch namespace, default %s.' % repr(defaults['namespace']))
parser.add_option('-c', '--config', dest='config', help='JSON list of repos to fetch, default %s.' % repr(defaults['config']))
parser.add_option('-d', '--datadest', dest='fetch_dest', help='Directory to save JSON repo info to, default %s.' % repr(defaults['fetch_dest']))
parser.add_option('--fetch', dest='fetch', action='store_true', help='Fetch data from list of repos.')
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
        # Metric settings
        # 
        cloudwatch = connect_cloudwatch()

        period = 60 * 60
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)



        if opts.fetch:
            repo_data = lib.fetch_repolist_info(opts.config)
            lib.output_data(repo_data, opts.fetch_dest + 'raw.json', 'json')
            repo_hist = lib.get_graph_data(opts.fetch_dest + 'hist.json', 
                [repo['name'] for repo in repo_data])

            label = end_dt.strftime('%Y-%m-%d')
            # Send time series data of each repo to destination
            for arepo in repo_data:
                name = arepo['name']

                # Daily count reports
                fork_info = arepo['forks_count']
                star_info = arepo['stars_count']
                closed_issue_info = arepo['closed_issues_count']

                repo_fork_hist = repo_hist[name]['fork']
                repo_star_hist = repo_hist[name]['star']
                repo_closed_issue_hist = repo_hist[name]['closed_issue']
                label_hist = repo_hist[name]['labels']

                # Keep points collected once per day, fill missing days
                if label in label_hist:
                    continue
                repo_hist = lib.fill_data(repo_hist)


                repo_star_hist.append(star_info)
                repo_fork_hist.append(fork_info)
                repo_closed_issue_hist.append(closed_issue_info)
                label_hist.append(label)

                repo_hist[name] = dict(fork=repo_fork_hist, star=repo_star_hist,
                    closed_issue=repo_closed_issue_hist, labels=label_hist)


            # Save today's report with the rest
            lib.output_data(json.dumps(repo_hist), opts.fetch_dest + 'hist.json', 'json')

            totals = lib.get_list_totals(repo_data)
            total_info_dest = opts.fetch_dest + "totals.json"
            lib.output_data(json.dumps(totals), total_info_dest, 'json')

        #
        # List all current repositories.
        #
        passed, failed = 0, 0
        repos = filter(lib.is_current_repo, lib.generate_repos())
        
        for repo in repos:
            repo_name = repo['name']
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
        # Output HTML
        #
        lib.output_data(html, destination, 'html')
        
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

