# IGV server
Dynamic IGV server linked to Airtable and S3

This app dynamically builds experiment and sample menus for IGV, using an
Airtable database. Clicking on a sample in the IGV server will load the BAM
directly from an S3 bucket (set as environment variable). 

## Getting started

### S3 configuration
This server requires an S3 bucket containing BAM files. Each BAM index must 
be the same path, but with the ".bai" appended to the path, as is standard 
practice.

Set the S3 bucket as an environment variable:
```
$ export S3_BUCKET=my-bucket
```

### Database configuration
The second requirement is a metadata database with experiments and samples,
which stores sample names and S3 URIs to the BAM files. The server is 
configured for the Airtable API, but it would be easy to adapt the code to any 
database with a good API.

The database must have an experiments table and a samples table (set
the exact table names as a constant in `app.py`). Samples are linked to 
experiments via the field "Experiment" by defualt, but this can also be 
set as a constant. Note that Airtable uses URL encoding for the table names.

```
EXPT_TABLE = 'Genomics%20Expt'
SAMPLE_TABLE = 'Genomics%20Sample'
SAMPLE_EXPT_FIELD = 'Experiment'
```

The code expects a few standard column names. Besides the "Name" field, which
is standard for Airtable, each table must have a "Description" text field, and 
each Sample recordmust have a "BAM" field containing the S3 url to the 
corresponding BAM file. 

That's it! Start the server with `python app.py`

## Acknowledgments
Thanks to @nkrumm for code (https://github.com/nkrumm/s3proxy) to stream S3 
objects in a format suitable to IGV. All I did here was to hook up the pieces.
