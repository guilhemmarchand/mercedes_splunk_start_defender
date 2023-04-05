#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

__author__ = "Guilhem Marchand for Mercedes"

import os
import sys
import splunk
import splunk.entity
import requests
from requests.structures import CaseInsensitiveDict
import re
import json
import random
import time
import datetime
import logging
import uuid
from urllib.parse import urlencode
import urllib.parse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']

sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'splunk_start_defender', 'lib'))

import splunklib.client as client
import splunklib.results as results

# import ucclibs
from splunktaucclib.alert_actions_base import ModularAlertBase
from splunklib.modularinput.event import Event, ET
from splunklib.modularinput.event_writer import EventWriter

# logging:
# To avoid overriding logging destination of callers, the libs will not set on purpose any logging definition
# and rely on callers themselves

import requests
from requests.structures import CaseInsensitiveDict


# get system wide conf with least privilege approach
def splunk_start_defender_get_conf(session_key, splunkd_uri):
    """
    Retrieve settings.
    """

    # Ensure splunkd_uri starts with "https://"
    if not splunkd_uri.startswith("https://"):
        splunkd_uri = f"https://{splunkd_uri}"

    # Build header and target URL
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"Splunk {session_key}"
    target_url = f"{splunkd_uri}/services/splunk_start_defender/manager/splunk_start_defender_conf"

    # Create a requests session for better performance
    session = requests.Session()
    session.headers.update(headers)

    try:
        # Use a context manager to handle the request
        with session.get(target_url, verify=False) as response:
            if response.status_code == 200:
                logging.debug(f"Success retrieving conf, data=\"{response}\"")
                response_json = response.json()
                return response_json
            else:
                error_message = f"Failed to retrieve conf, status_code={response.status_code}, response_text=\"{response.text}\""
                logging.error(error_message)
                raise Exception(error_message)

    except Exception as e:
        error_message = f"Failed to retrieve conf, exception=\"{str(e)}\""
        logging.error(error_message)
        raise Exception(error_message)


# get account creds with least privilege approach
def splunk_start_defender_get_account(session_key, splunkd_uri, account):
    """
    Retrieve account creds.
    """

    # Ensure splunkd_uri starts with "https://"
    if not splunkd_uri.startswith("https://"):
        splunkd_uri = f"https://{splunkd_uri}"

    # Build header and target URL
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"Splunk {session_key}"
    target_url = f"{splunkd_uri}/services/splunk_start_defender/manager/get_account"

    # Create a requests session for better performance
    session = requests.Session()
    session.headers.update(headers)

    try:
        # Use a context manager to handle the request
        with session.post(target_url, data=json.dumps({'account': account}), verify=False) as response:
            if response.status_code == 200:
                logging.debug(f"Success retrieving account, data=\"{response}\"")
                response_json = response.json()
                return response_json
            else:
                error_message = f"Failed to retrieve account, status_code={response.status_code}, response_text=\"{response.text}\""
                logging.error(error_message)
                raise Exception(error_message)

    except Exception as e:
        error_message = f"Failed to retrieve account, exception=\"{str(e)}\""
        logging.error(error_message)
        raise Exception(error_message)


# Get status (executed by the relay)
def circ_get_status(circ_token, computername, circ_url):
    headers = CaseInsensitiveDict()
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36"
    headers["Authorization"] = f"Bearer {circ_token}"
    params = {'computername': computername}

    session = requests.Session()
    session.headers.update(headers)

    try:
        with session.post(circ_url, params=params, verify=False) as response:
            if response.ok:
                return response.json()
            else:
                error_message = f"Failed to get status, HTTP status code: {response.status_code}, HTTP response: {response.text}"
                logging.error(error_message)
                raise Exception(error_message)
    except Exception as e:
        logging.error(f"Failed to get status, exception=\"{str(e)}\"")
        raise Exception(f"Failed to get status, exception=\"{str(e)}\"")


# Get status (relay, executed in Splunk Cloud and delegated to the relay)
def circ_relay_get_status(account, relay_token, computername, relay_url):
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"Bearer {relay_token}"

    session = requests.Session()
    session.headers.update(headers)

    # set the url
    relay_url = relay_url + '/services/splunk_start_defender/manager/relay_circ_get_status'

    try:
        with session.post(relay_url, data=json.dumps({'account': account, 'computername': computername}), verify=False) as response:
            if response.ok:
                return response.json()
            else:
                error_message = f"Failed to get status, HTTP status code: {response.status_code}, HTTP response: {response.text}"
                logging.error(error_message)
                raise Exception(error_message)
    except Exception as e:
        logging.error(f"Failed to get status, exception=\"{str(e)}\"")
        raise Exception(f"Failed to get status, exception=\"{str(e)}\"")

# Start scan
def circ_start_scan(circ_token, computername, circ_url, fullscan=False):
    headers = CaseInsensitiveDict()
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36"
    headers["Authorization"] = f"Bearer {circ_token}"
    params = {'computername': computername, 'fullscan': fullscan}

    session = requests.Session()
    session.headers.update(headers)

    try:
        with session.post(circ_url, params=params, verify=False) as response:
            if response.ok:
                return response.json()
            else:
                error_message = f"Failed to get status, HTTP status code: {response.status_code}, HTTP response: {response.text}"
                logging.error(error_message)
                raise Exception(error_message)
    except Exception as e:
        logging.error(f"Failed to start scan, exception=\"{str(e)}\"")
        raise Exception(f"Failed to start scan, exception=\"{str(e)}\"")

# Start scan (relay)
def circ_relay_start_scan(account, relay_token, computername, relay_url, fullscan=False):
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"Bearer {relay_token}"

    session = requests.Session()
    session.headers.update(headers)

    # set the url
    relay_url = relay_url + '/services/splunk_start_defender/manager/relay_circ_start_scan'

    try:
        with session.post(relay_url, data=json.dumps({'account': account, 'computername': computername, 'fullscan': fullscan}), verify=False) as response:
            if response.ok:
                return response.json()
            else:
                error_message = f"Failed to get status, HTTP status code: {response.status_code}, HTTP response: {response.text}"
                logging.error(error_message)
                raise Exception(error_message)
    except Exception as e:
        logging.error(f"Failed to start scan, exception=\"{str(e)}\"")
        raise Exception(f"Failed to start scan, exception=\"{str(e)}\"")

