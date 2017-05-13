"""IGV Server

This app dynamically builds experiment and sample menus for IGV, using an
Airtable database. Clicking on a sample in the IGV server will load the BAM
directly from an S3 bucket (set as environment variable). AWS credentials must
be set in a format that boto3 can recognize.

The Airtable database must have an experiments table and a samples table (set
the table names as a constant below), linked by a field in the samples table
(also set as a constant). Besides the standard "Name" field, each table must
have a "Description" text field, and each Sample record must have a "BAM" field
containing the S3 url to the corresponding BAM file. The BAM index must be the
same path, with the ".bai" appended to the path, as is standard practice.

Thanks to https://github.com/nkrumm/s3proxy for code to stream S3 objects in 
a format suitable to IGV.
"""
import os
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import boto3
import requests
from flask import Flask, Response, request, render_template, stream_with_context
from werkzeug.contrib.cache import SimpleCache
from werkzeug.datastructures import Headers

BUFFER_SIZE = 8192
URL_EXPIRATION = 24*60*60

S3_BUCKET = os.environ['S3_BUCKET']

# Airtable constants
AIRTABLE_API_KEY = os.environ.get('AIRTABLE_API_KEY')
API_ENDPOINT = os.environ.get('AIRTABLE_API_ENDPOINT')
EXPT_TABLE = 'Genomics%20Expt'
SAMPLE_TABLE = 'Genomics%20Sample'
SAMPLE_EXPT_FIELD = 'Experiment'
SAMPLE_DESCRIPTION_FIELD = 'Description'

cache = SimpleCache()
app = Flask(__name__)

# load AWS credentials and bucket
s3 = boto3.resource('s3')


def path_to_bucket_and_key(path):
    """Split an S3 url into bucket and key path"""
    (scheme, netloc, path, params, query, fragment) = urlparse(path)
    path_without_initial_slash = path[1:]
    return netloc, path_without_initial_slash


def get_key(path):
    """Get the S3 key or None if it doesn't exist"""
    key = s3.Object(S3_BUCKET, path)
    try:
        key.content_length
    except:
        return None
    return key


def _request(method, table, path, **kwargs):
    """Make a generic request with the Airtable API"""
    headers = {'Authorization': 'Bearer ' + AIRTABLE_API_KEY}
    url = API_ENDPOINT + table + path

    response = requests.request(method.upper(), url, headers=headers, **kwargs)
    response.raise_for_status()
    content = response.json()
    return content


def get_experiments():
    """Retrieve Experiment record by Name from Airtable API"""
    params = {'fields[]': ['Name', 'Description']}
    expts = _request('get', EXPT_TABLE, '/', params=params)['records']
    return [
        {
            'name': expt['fields']['Name'], 
            'description': expt['fields'].get('Description', '')
        }
        for expt in expts
    ]


def get_bams(expt_name):
    params = {
        'filterByFormula': '{Experiment} = "%s"' % expt_name,
        'fields[]': ['Name', 'Description', 'BAM']
    }
    records = _request('get', SAMPLE_TABLE, '/', params=params)['records']
    return [
        {
            'name': record['fields']['Name'],
            'description': record['fields'].get('Description', ''),
            'url': record['fields'].get('BAM', '')
        }
        for record in records
    ]


@app.route('/files/<path:url>', methods=["HEAD"])
def head_file(url):
    headers = Headers()
    key = get_key(url)
    try:
        size = key.content_length
    except:
        return Response(None, 404)
    headers.add("Content-Length", size)
    return Response(headers=headers, direct_passthrough=True)


@app.route('/files/<path:url>', methods=["GET"])
def get_file(url):
    range_header = request.headers.get('Range', None)
    return_headers = Headers()
    key = get_key(url)
    try:
        size = key.content_length
    except:
        return Response(None, 404)

    if range_header:
        print("{}: {} (size={})".format(url, range_header, size))
        start_range_str, end_range_str = range_header.split("=")[1].split("-")
        start_range = int(start_range_str)
        end_range = size - 1 if end_range_str == '' else int(end_range_str)
        get_range = "bytes={}-{}".format(start_range, end_range)

        return_headers.add('Accept-Ranges', 'bytes')
        return_headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(
            start_range, end_range, size))
        return_headers.add('Content-Length', end_range-start_range+1)
        #return_headers.add('Content-Type', 'application/x-gzip')
        
        return_code = 206
        response = key.get(Range=get_range)
    else:
        print("{}: all data (size={})".format(url, size))
        return_code = 200
        response = key.get()

    body = response['Body']

    def stream(key):
        while True:
            data = body.read(BUFFER_SIZE)
            if data:
                yield data
            else:
                raise StopIteration
    return Response(stream_with_context(stream(key)), return_code, 
                    headers=return_headers, direct_passthrough=True)


@app.route('/xml/<expt_name>')
def build_xml_menu(expt_name):
    menu = cache.get(expt_name + '_xml')
    if menu is None:
        bams = get_bams(expt_name)
        expts = get_experiments()
        expt = [e for e in expts if e.get('name','') == expt_name]
        if not expt:
            return 'Experiment {} not found'.format(expt_name)
        for bam in bams:
            bucket, key_path = path_to_bucket_and_key(bam['url'])
            bam['path'] = request.url_root + 'files/' + key_path
        sorted_bams = sorted(bams, key=lambda bam: bam['name'])
        menu = render_template('expt.xml', expt=expt[0], bams=sorted_bams)
        cache.set(expt_name + '_xml', menu, timeout=24*60*60)
    return menu


@app.route('/data_registry')
def data_registry():
    """Main entrypoint for IGV. 

    Returns a list of endpoints for XML resources per experiment. Add any 
    static paths (e.g. annotations) to the list of dynamic (xml) paths here.
    """
    expts = get_experiments()
    expt_names = [expt['name'] for expt in expts]
    xml_paths = [request.url_root + 'xml/' + name for name in expt_names]
    return '\n'.join(xml_paths)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
