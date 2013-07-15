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

def get_hist_data(dest):

    hist = dict(watch=[], cont=[], star=[], labels=[])
    data = {}
    if dest.startswith('s3://'):
        conn = connect_s3()
        bucket_name, key_name = dest[5:].split('/', 1)

        bucket = conn.get_bucket(bucket_name)
        key = bucket.get_key(key_name)
        if key:
            data = json.loads(key.get_contents_as_string())
        else:
            key = bucket.new_key(key_name)
            print 'Missing file on S3, pleas run again.'
    else:
        with open(dest, 'r') as f:
            data = f.read()
            if data:
                data = json.loads(data)
            else:
                pass

    if 'watch' in data and 'cont' in data and 'star' in data:
        hist = data
    return hist


def get_list_totals(config_file):
    ''' Get total statistics from a whole list of repos
    '''
    with open(opts.config, 'r') as f:
        config = json.loads(f.read())
        repo_list = config['repos']
    total_closed = 0
    total_forks = 0

    for arepo in repo_list:
        if 'name' in arepo and 'owner' in arepo:
            total_closed = total_closed + len(lib.get_issues(arepo['name'], arepo['owner'], 'closed'))
            total_forks = total_forks + len(lib.get_forks(arepo['name'], arepo['owner']))
        else: logging.debug("Config file is invalid.")


    return {"total_closed": total_closed, "total_forks": total_forks}


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

def fill_data(repo_hist):
    end_dt = datetime.now()
    end_label = end_dt.strftime('%Y-%m-%d')
    start_label = repo_hist['labels'][-1]
    days_ago = 1
    watch = []
    star = []
    cont = []
    labels = []

    while end_label != start_label:
        end_label = (end_dt - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        labels.insert(0, end_label)
        watch.insert(0, 0)
        star.insert(0, 0)
        cont.insert(0, 0)
        days_ago += 1

    repo_hist['watch'].extend(watch)
    repo_hist['star'].extend(star)
    repo_hist['cont'].extend(cont)
    repo_hist['labels'].extend(labels)
    for group in repo_hist.iterkeys():
        while len(repo_hist[group]) >= 365:
            repo_hist[group] = repo_hist[group][1:]


    return repo_hist

def weekly_change(repo_hist):
    ''' Given a filled repository history, including today
        Computes the change in each stat over the last 7 days
    '''
    last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    if last_week in repo_hist['labels']:
        ind = repo_hist['labels'].index(last_week)
    else:
        ind = 0
    return dict(watch= repo_hist['watch'][-1] - repo_hist['watch'][ind],
        star= repo_hist['star'][-1] - repo_hist['star'][ind],
        cont= repo_hist['cont'][-1] - repo_hist['cont'][ind],
        )


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

            # Send time series data of each repo to destination
            for arepo in repo_data:

                # Daily count reports
                watch_info = arepo['watch_count']
                star_info = arepo['star_count']
                cont_info = arepo['contributor_count']
                label = end_dt.strftime('%Y-%m-%d')


                # Daily count destinations
                repo_info_dest = opts.fetch_dest + arepo['name'] + '.json'

                repo_hist = get_hist_data(repo_info_dest)
                repo_watch_hist = repo_hist['watch']
                repo_star_hist = repo_hist['star']
                repo_cont_hist = repo_hist['cont']
                label_hist = repo_hist['labels']

                # Keep points collected once per day, fill missing days
                if label in label_hist:
                    continue
                repo_hist = fill_data(repo_hist)


                repo_star_hist.append(star_info)
                repo_watch_hist.append(watch_info)
                repo_cont_hist.append(cont_info)
                label_hist.append(label)

                repo_hist = dict(watch=repo_watch_hist, star=repo_star_hist,
                    cont=repo_cont_hist, labels=label_hist)
                changes = weekly_change(repo_hist)
                repo_hist.update(dif_cont=changes['cont'], dif_star = changes['star'],
                    dif_watch = changes['watch'])

                # Save today's report with the rest
                output_data(json.dumps(repo_hist), repo_info_dest, 'json')

            totals = get_list_totals(opts.config)
            total_info_dest = opts.fetch_dest + "totals.json"
            output_data(json.dumps(totals), total_info_dest, 'json')

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

