import os
from flask import Flask
from flask import request
from flask import render_template
from flask import url_for
from flask import flash
from boto import connect_cloudwatch
from datetime import datetime, timedelta
from operator import itemgetter
import json


app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['REPO_KEY_SECRET']

def format_data(cloudwatch_data):
    return [dict(value=int(round(m['Average'])), 
        label=m['Timestamp'].strftime('%m/%d %I%p'))
        for m in sorted(cloudwatch_data, key=itemgetter('Timestamp'))]

def align_metrics(datasets):
    ''' Given a list of formatted datasets, align their labels
        returns sorted labels
    '''
    labels = set()
    for ind, dataset in enumerate(datasets):
        dlist = [{'value': int(round(m['Average'])), 
            'label': m['Timestamp'].strftime('%m/%d %I%p')}
            for m in sorted(dataset, key=itemgetter('Timestamp'))]
        datasets[ind] = dlist

        labels = labels | set([m['label'] for m in dlist])

    # Insert 0 point into dataset when a label is missing.
    for dataset in datasets:
        for ind, alabel in enumerate(labels):
            if alabel not in [m['label'] for m in dataset]:
                dataset.insert(ind, {'value': 0, 'label': alabel})

    for ind, dataset in enumerate(datasets):
        datasets[ind].sort(key=lambda k:k['label'])
        datasets[ind] = [m['value'] for m in datasets[ind]]

    labels = list(labels)
    labels.sort()
    return labels

@app.route("/chartData")
def get_chart_data():
    period = 60 * 60
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=14)
    repo = request.args.get('repo', '')

    cloudwatch = connect_cloudwatch()

    cont_hist = cloudwatch.get_metric_statistics(period, start_dt,
        end_dt, '%s_contributors' % repo, 'Github Observer', ['Average'])
    watcher_hist = cloudwatch.get_metric_statistics(period, start_dt,
        end_dt, '%s_watchers' % repo, 'Github Observer', ['Average'])
    star_hist = cloudwatch.get_metric_statistics(period, start_dt,
        end_dt, '%s_stars' % repo, 'Github Observer', ['Average'])

    cw_data = [cont_hist, watcher_hist, star_hist]
    labels = align_metrics(cw_data)

    metrics = {'cont': cw_data[0], 'watch': cw_data[1], 
        'star': cw_data[2], 'labels': labels, 'rname': repo}

    return json.dumps(metrics)

@app.route('/')
def show_graphs(): 

    with open('config.json', 'r') as f:
        config = json.loads(f.read())
        repo_list = config['repos']

    return render_template('graphs.html', repos=repo_list)


if __name__ == '__main__':
	app.run()