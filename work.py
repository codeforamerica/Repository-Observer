#!/usr/bin/env python
from time import sleep
from datetime import datetime

from boto import connect_s3

if __name__ == '__main__':

    while True:
        key = connect_s3().get_bucket('github-observer').new_key('hello.txt')
        kwargs = dict(headers={'Content-Type': 'text/plain'}, policy='public-read')
        key.set_contents_from_string(str(datetime.now()), **kwargs)
        
        sleep(10)