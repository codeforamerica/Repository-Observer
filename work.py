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


def output_data(data, dest, ctype):        
    # Output collected data
    #
    content_types = {'html':'text/html', 'json':'application/json'}
    if dest.startswith('s3://'):
        bucket_name, key_name = dest[5:].split('/', 1)
        bucket = connect_s3().get_bucket(bucket_name)
        key = bucket.new_key(key_name)
        kwargs = dict(headers={'Content-Type': content_types[ctype]},
            policy='public-read')
        key.set_contents_from_string(data, **kwargs)
        
    else:
        with open(dest, 'w') as out:
            out.write(data)
        with open(dest.replace('html', 'json'), 'w') as out:
            out.write(json.dumps(repos))

def get_hist_data(dest):

    hist = dict(watch_count=[], cont_count=[], star_count=[])
    data = {}
    if dest.startswith('s3://'):
        conn = connect_s3()
        bucket_name, key_name = dest[5:].split('/', 1)

        # if bucket_name not in conn.get_all_buckets():
        #     logging.debug('Invalid bucket name: %s' % bucket_name)
        #     return list()

        bucket = conn.get_bucket(bucket_name)
        key = bucket.get_key(key_name)
        if key:
            data = json.loads(key.get_contents_as_string())
        else:
            key = bucket.new_key(key_name)
            print 'Missing file on S3, pleas run again.'
    else:
        with open(dest, 'r') as f:
            data = f.read
            if data:
                data = json.loads(data)
            else:
                pass

    if 'watch_count' in data and 'cont_count' in data and 'star_count' in data:
        hist = data
    return hist


def fetch_repo_info(config_file):
    ''' Fetch data about repo list
        Output data to s3 destination
    '''
    with open(opts.config, 'r') as f:
        config = json.loads(f.read())
        repo_list = config['repos']

    for arepo in repo_list:
        if 'name' in arepo and 'owner' in arepo:
            arepo.update(lib.get_repo_info(arepo['name'], arepo['owner']))
        else:
            logging.debug('Config file is invalid.')

    return repo_list


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
            repo_data = fetch_repo_info(opts.config)
            for arepo in repo_data:

                # Daily count reports
                watch_info = dict(watch_count=arepo['watch_count'],
                    time=end_dt.strftime('%Y-%m-%d'))
                star_info = dict(star_count=arepo['star_count'],
                    time=end_dt.strftime('%Y-%m-%d'))
                cont_info = dict(cont_count=arepo['contributor_count'],
                    time=end_dt.strftime('%Y-%m-%d'))


                # Daily count destinations
                repo_info_dest = opts.fetch_dest + arepo['name'] + '.json'

                repo_hist = get_hist_data(repo_info_dest)
                repo_watch_hist = repo_hist['watch_count']
                repo_star_hist = repo_hist['star_count']
                repo_cont_hist = repo_hist['cont_count']

                if len(repo_watch_hist) >= 365:
                    repo_watch_hist = repo_watch_hist[1:].append(watch_info)
                if len(repo_star_hist) >= 365:
                    repo_star_hist = repo_star_hist[1:].append(star_info)
                if len(repo_cont_hist) >= 365:
                    repo_cont_hist = repo_cont_hist[1:]

                repo_star_hist.append(star_info)
                repo_watch_hist.append(watch_info)
                repo_cont_hist.append(cont_info)

                repo_hist = dict(watch_count=repo_watch_hist, star_count=repo_star_hist,
                    cont_count=repo_cont_hist)

                # Save today's report with the rest
                output_data(json.dumps(repo_hist), repo_info_dest, 'json')

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
        output_data(html, destination, 'html')
        
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

