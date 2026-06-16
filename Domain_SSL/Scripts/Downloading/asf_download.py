## This script requires that the asf-search python module is installed
## to install, run the following in a terminal
## `pip install asf-search`
## Then from the correct folder in your terminal run:
## `python asf-search-script-2025-08-22_09-14-42.py`
## 
## For more information, see the official documentation
## https://docs.asf.alaska.edu/asf_search/basics/
import asf_search as asf
import pprint

opts=asf.ASFSearchOptions(**{
    "maxResults": 250,
    "beamSwath": [
        "IW"
    ],
    "intersectsWith": "POLYGON ((18.3188999999999993 -34.6287999999999982, 26.3880000000000017 -34.4896000000000029, 31.4130000000000003 -30.4924999999999997, 31.8973000000000013 -30.0917999999999992, 32.2100999999999971 -29.6893999999999991, 31.3991000000000007 -29.3188999999999993, 18.2786000000000008 -33.5718999999999994, 17.8219999999999992 -33.7430000000000021, 17.1056999999999988 -34.0947000000000031, 17.9026999999999994 -34.6225999999999985, 18.3188999999999993 -34.6287999999999982))",
    "platform": [
        "SA",
        "SB",
        "SC"
    ],
    "processingLevel": [
        "SLC"
    ],
    "start": "2018-12-31T22:00:00Z",
    "end": "2025-08-21T21:59:59Z",
    "dataset": [
        "SENTINEL-1"
    ]
})

## if the search requires authentication, uncomment
## the lines below, and enter your EDL credentials when prompted
## (use `session.auth_with_token(getpass('EDL Token'))` instead if a CMR bearer token is required)
# from get_pass import get_pass
# session=asf.ASFSession()
# session.auth_with_creds(input('EDL Username'), getpass('EDL Password'))
# opts.session = session

results=asf.search(opts=opts)
pprint.pp(results.geojson())

