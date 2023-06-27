from __future__ import absolute_import, division, print_function, unicode_literals

__name__ = "splunk_start_manager_rest_handler.py"
__author__ = "Guilhem Marchand for Mercedes"

import logging
from logging.handlers import RotatingFileHandler
import os, sys
import json
import re
import time

splunkhome = os.environ['SPLUNK_HOME']

# set logging
logger = logging.getLogger(__name__)
filehandler = RotatingFileHandler('%s/var/log/splunk/splunk_start_manager_rest_api.log' % splunkhome, mode='a', maxBytes=10000000, backupCount=1)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(funcName)s %(lineno)d %(message)s')
logging.Formatter.converter = time.gmtime
filehandler.setFormatter(formatter)
log = logging.getLogger()
for hdlr in log.handlers[:]:
    if isinstance(hdlr,logging.FileHandler):
        log.removeHandler(hdlr)
log.addHandler(filehandler)
log.setLevel(logging.INFO)

sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'splunk_start_defender', 'lib'))

# import API handler
import rest_handler

# import additional libs
from lib_splunk_start_defender import circ_get_status, circ_start_scan

# import Splunk libs
import splunklib.client as client
import splunklib.results as results

class SplunkStartDefender_v1(rest_handler.RESTHandler):


    def __init__(self, command_line, command_arg):
        super(SplunkStartDefender_v1, self).__init__(command_line, command_arg, logger)


    def get_test_endpoint(self, request_info, **kwargs):

        response = {
            'resource_endpoint': 'test_endpoint',
            'resource_response': 'Welcome. Good to see you.', 
        }

        return {
            "payload": response,
            'status': 200
        }
    

    # get configuration items
    def get_splunk_start_defender_conf(self, request_info, **kwargs):

        describe = False

        # Retrieve from data
        try:
            resp_dict = json.loads(str(request_info.raw_args['payload']))
        except Exception as e:
            resp_dict = None

        if resp_dict is not None:
            try:
                describe = resp_dict['describe']
                if describe in ("true", "True"):
                    describe = True
            except Exception as e:
                describe = False
        else:
            # body is not required
            describe = False

        # if describe is requested, show the usage
        if describe:

            response = {
                'describe': 'This endpoint retrieves and provide system wide configuration, it requires a GET call with no optionss:',
                "resource_desc": "Retrieve system wide configuration",
            }
            return {
                "payload": response,
                'status': 200
            }

        # Get service
        service = client.connect(
            owner="nobody",
            app="splunk_start_defender",
            port=request_info.connection_listening_port,
            token=request_info.system_authtoken
        )

        # set and get conf
        conf_file = "splunk_start_defender_settings"
        confs = service.confs[str(conf_file)]

        # Initialize the splunk_start_defender dictionary
        splunk_start_defender = {}

        # Get conf
        for stanza in confs:
            logging.debug(f"get_conf, Processing stanza.name=\"{stanza.name}\"")
            # Create a sub-dictionary for the current stanza name if it doesn't exist
            if stanza.name not in splunk_start_defender:
                splunk_start_defender[stanza.name] = {}

            # Store key-value pairs from the stanza content in the corresponding sub-dictionary
            for stanzakey, stanzavalue in stanza.content.items():
                logging.debug(f"get_splunk_start_defender, Processing stanzakey=\"{stanzakey}\", stanzavalue=\"{stanzavalue}\"")
                splunk_start_defender[stanza.name][stanzakey] = stanzavalue

        logging.debug("get_splunk_start_defender, process result: {}".format(splunk_start_defender))

        return {
            "payload": splunk_start_defender,
            'status': 200
        }


    # get account details with least privileges approach
    def post_get_account(self, request_info, **kwargs):

        describe = False

        # Retrieve from data
        try:
            resp_dict = json.loads(str(request_info.raw_args['payload']))
        except Exception as e:
            resp_dict = None

        if resp_dict is not None:
            try:
                describe = resp_dict['describe']
                if describe in ("true", "True"):
                    describe = True
            except Exception as e:
                describe = False
                account = resp_dict['account']
        else:
            # body is required
            describe = True

        # if describe is requested, show the usage
        if describe:

            response = {
                'describe': 'This endpoint provides connectivity information, it requires a POST call with the following options:',
                "resource_desc": "Retrieve the account configuration",
                'options': [{
                    'account': 'The account configuration identifier',
                }]
            }
            return {
                "payload": response,
                'status': 200
            }

        # Get service
        service = client.connect(
            owner="nobody",
            app="splunk_start_defender",
            port=request_info.connection_listening_port,
            token=request_info.system_authtoken
        )

        # set loglevel
        loglevel = 'INFO'
        conf_file = "splunk_start_defender_settings"
        confs = service.confs[str(conf_file)]
        for stanza in confs:
            if stanza.name == 'logging':
                for stanzakey, stanzavalue in stanza.content.items():
                    if stanzakey == "loglevel":
                        loglevel = stanzavalue
        logginglevel = logging.getLevelName(loglevel)
        log.setLevel(logginglevel)

        # Splunk credentials store
        storage_passwords = service.storage_passwords

        # get instance role
        conf_file = "splunk_start_defender_settings"
        confs = service.confs[str(conf_file)]
        for stanza in confs:
            if stanza.name == 'role':
                for key, value in stanza.content.items():
                    if key == "instance_role":
                        instance_role = value

        # get all acounts
        accounts = []
        conf_file = "splunk_start_defender_account"
        confs = service.confs[str(conf_file)]
        for stanza in confs:
            # get all accounts
            for name in stanza.name:
                accounts.append(stanza.name)
                break

        # get account
        circ_url = None
        relay_url = None

        for stanza in confs:
            if stanza.name == str(account):
                for key, value in stanza.content.items():
                    if key == "circ_url":
                        circ_url = value
                    if key == "relay_url":
                        relay_url = value                              

        # end of get configuration

        # Stop here if we cannot find the submitted account
        if not account in accounts:
            return {
                "payload": {
                    'status': 'failure',
                    'message': 'The account could be found on this system, check the spelling and your configuration',
                    'account': account,
                },
                'status': 500
            }

        elif len(accounts) == 0:
            return {
                "payload": {
                    'status': 'failure',
                    'message': 'There are no account configured yet for this instance.',
                    'account': account,
                },
                'status': 500
            }

        else:

            # if instance_role is Splunk Relay
            if instance_role in ('splunk_relay'):

                # enforce https
                if not circ_url.startswith("https://"):
                    circ_url = "https://" + str(circ_url)

                # remote trailing slash in the URL, if any
                if circ_url.endswith('/'):
                    circ_url = circ_url[:-1]

                # get circ_token
                circ_token = None

                # realm
                credential_realm = '__REST_CREDENTIAL__#splunk_start_defender#configs/conf-splunk_start_defender_account'
                credential_name = str(credential_realm) + ":" + str(account) + "``"

                # extract as raw json
                bearer_token_rawvalue = ""

                for credential in storage_passwords:
                    if credential.content.get('realm') == str(credential_realm) and credential.name.startswith(credential_name):
                        bearer_token_rawvalue = bearer_token_rawvalue + str(credential.content.clear_password)

                # extract a clean json object
                bearer_token_rawvalue_match = re.search('\{\"circ_token\":\s*\"(.*)\"\}', bearer_token_rawvalue)
                if bearer_token_rawvalue_match:
                    circ_token = bearer_token_rawvalue_match.group(1)
                else:
                    circ_token = None

            # else if instance_role is Splunk Cloud
            elif instance_role in ('splunk_cloud'):

                # enforce https
                if not relay_url.startswith("https://"):
                    relay_url = "https://" + str(relay_url)

                # remote trailing slash in the URL, if any
                if relay_url.endswith('/'):
                    relay_url = relay_url[:-1]

                # get relay_token
                relay_token = None

                # realm
                credential_realm = '__REST_CREDENTIAL__#splunk_start_defender#configs/conf-splunk_start_defender_account'
                credential_name = str(credential_realm) + ":" + str(account) + "``"

                # extract as raw json
                bearer_token_rawvalue = ""

                for credential in storage_passwords:
                    if credential.content.get('realm') == str(credential_realm) and credential.name.startswith(credential_name):
                        bearer_token_rawvalue = bearer_token_rawvalue + str(credential.content.clear_password)

                # extract a clean json object
                bearer_token_rawvalue_match = re.search('\{\"relay_token\":\s*\"(.*)\"\}', bearer_token_rawvalue)
                if bearer_token_rawvalue_match:
                    relay_token = bearer_token_rawvalue_match.group(1)
                else:
                    relay_token = None

            #
            # verify and return the response
            #

            if instance_role in ("splunk_cloud") and not relay_token:

                msg = 'This instance is configured with role {} but the circ_token could not be retrieved, cannot continue.'.format(instance_role)
                logging.error(msg)

                return {
                    "payload": {
                        'status': 'failure',
                        'message': msg,
                        'account': account,
                    },
                    'status': 500
                }
            
            elif instance_role in ("splunk_relay") and not circ_token:
            
                msg = 'This instance is configured with role {} but the relay_token could not be retrieved, cannot continue.'.format(instance_role)
                logging.error(msg)

                return {
                    "payload": {
                        'status': 'failure',
                        'message': msg,
                        'account': account,
                    },
                    'status': 500
                }

            else:

                if instance_role in ("splunk_cloud"):

                    return {
                        "payload": {
                            'status': 'success',
                            'instance_role': instance_role,
                            'account': account,
                            'relay_url': relay_url,
                            'relay_token': relay_token,
                        },
                        'status': 200
                    }
            
                elif instance_role in ("splunk_relay"):

                    return {
                        "payload": {
                            'status': 'success',
                            'instance_role': instance_role,
                            'account': account,
                            'circ_url': circ_url,
                            'circ_token': circ_token,
                        },
                        'status': 200
                    }


    # Run the circ get status action
    def post_relay_circ_get_status(self, request_info, **kwargs):

        describe = False

        # Retrieve from data
        try:
            resp_dict = json.loads(str(request_info.raw_args['payload']))
        except Exception as e:
            resp_dict = None

        if resp_dict is not None:
            try:
                describe = resp_dict['describe']
                if describe in ("true", "True"):
                    describe = True
            except Exception as e:
                describe = False
                account = resp_dict['account']
                computername = resp_dict['computername']
        else:
            # body is required
            describe = True

        # if describe is requested, show the usage
        if describe:

            response = {
                'describe': 'This endpoint runs the action circ get status, it requires a POST call with the following options:',
                "resource_desc": "Run circ get status action",
                'options': [{
                    'account': 'The name of the account',
                    'computername': 'The computer name',
                }]
            }
            return {
                "payload": response,
                'status': 200
            }

        # Get service
        service = client.connect(
            owner="nobody",
            app="splunk_start_defender",
            port=request_info.connection_listening_port,
            token=request_info.system_authtoken
        )

        # set loglevel
        loglevel = 'INFO'
        conf_file = "splunk_start_defender_settings"
        confs = service.confs[str(conf_file)]
        for stanza in confs:
            if stanza.name == 'logging':
                for stanzakey, stanzavalue in stanza.content.items():
                    if stanzakey == "loglevel":
                        loglevel = stanzavalue
        logginglevel = logging.getLevelName(loglevel)
        log.setLevel(logginglevel)

        # first, retrieve the credentials for this account

        # Splunk credentials store
        storage_passwords = service.storage_passwords

        # get all acounts
        accounts = []
        conf_file = "splunk_start_defender_account"
        confs = service.confs[str(conf_file)]
        for stanza in confs:
            # get all accounts
            for name in stanza.name:
                accounts.append(stanza.name)
                break

        # get account
        circ_url = None
        relay_url = None

        for stanza in confs:
            if stanza.name == str(account):
                for key, value in stanza.content.items():
                    if key == "circ_url":
                        circ_url = value
                    if key == "relay_url":
                        relay_url = value                              

        # end of get configuration

        # Stop here if we cannot find the submitted account
        if not account in accounts:
            return {
                "payload": {
                    'status': 'failure',
                    'message': 'The account could be found on this system, check the spelling and your configuration',
                    'account': account,
                },
                'status': 500
            }

        elif len(accounts) == 0:
            return {
                "payload": {
                    'status': 'failure',
                    'message': 'There are no account configured yet for this instance.',
                    'account': account,
                },
                'status': 500
            }

        else:

            # enforce https
            if not circ_url.startswith("https://"):
                circ_url = "https://" + str(circ_url)

            # remote trailing slash in the URL, if any
            if circ_url.endswith('/'):
                circ_url = circ_url[:-1]

            # get circ_token
            circ_token = None

            # realm
            credential_realm = '__REST_CREDENTIAL__#splunk_start_defender#configs/conf-splunk_start_defender_account'
            credential_name = str(credential_realm) + ":" + str(account) + "``"

            # extract as raw json
            bearer_token_rawvalue = ""

            for credential in storage_passwords:
                if credential.content.get('realm') == str(credential_realm) and credential.name.startswith(credential_name):
                    bearer_token_rawvalue = bearer_token_rawvalue + str(credential.content.clear_password)

            # extract a clean json object
            bearer_token_rawvalue_match = re.search('\{\"circ_token\":\s*\"(.*)\"\}', bearer_token_rawvalue)
            if bearer_token_rawvalue_match:
                circ_token = bearer_token_rawvalue_match.group(1)
            else:
                circ_token = None

        # proceed
        try:
            response = circ_get_status(circ_token, computername, circ_url)
            return {
                "payload": response,
                'status': 200
            }

        except Exception as e:
            return {
                "payload": {
                    'action': 'failure',
                    'exception': str(e),
                },
                'status': 500
            }


    # Run the circ start scan action
    def post_relay_circ_start_scan(self, request_info, **kwargs):

        describe = False

        # Retrieve from data
        try:
            resp_dict = json.loads(str(request_info.raw_args['payload']))
        except Exception as e:
            resp_dict = None

        if resp_dict is not None:
            try:
                describe = resp_dict['describe']
                if describe in ("true", "True"):
                    describe = True
            except Exception as e:
                describe = False
                account = resp_dict['account']
                computername = resp_dict['computername']
                fullscan = resp_dict['fullscan']
        else:
            # body is not required in this endpoint, if not submitted do not describe the usage
            describe = True

        # if describe is requested, show the usage
        if describe:

            response = {
                'describe': 'This endpoint runs the action circ get status, it requires a POST call with the following options:',
                "resource_desc": "Run circ get status action",
                'options': [{
                    'account': 'The account',
                    'computername': 'The computer name',
                    'fullscan': 'Run fullscan (boolean)',
                }]
            }
            return {
                "payload": response,
                'status': 200
            }

        # Get service
        service = client.connect(
            owner="nobody",
            app="splunk_start_defender",
            port=request_info.connection_listening_port,
            token=request_info.system_authtoken
        )

        # set loglevel
        loglevel = 'INFO'
        conf_file = "splunk_start_defender_settings"
        confs = service.confs[str(conf_file)]
        for stanza in confs:
            if stanza.name == 'logging':
                for stanzakey, stanzavalue in stanza.content.items():
                    if stanzakey == "loglevel":
                        loglevel = stanzavalue
        logginglevel = logging.getLevelName(loglevel)
        log.setLevel(logginglevel)

        # first, retrieve the credentials for this account

        # Splunk credentials store
        storage_passwords = service.storage_passwords

        # get all acounts
        accounts = []
        conf_file = "splunk_start_defender_account"
        confs = service.confs[str(conf_file)]
        for stanza in confs:
            # get all accounts
            for name in stanza.name:
                accounts.append(stanza.name)
                break

        # get account
        circ_url = None

        for stanza in confs:
            if stanza.name == str(account):
                for key, value in stanza.content.items():
                    if key == "circ_url":
                        circ_url = value

        # end of get configuration

        # Stop here if we cannot find the submitted account
        if not account in accounts:
            return {
                "payload": {
                    'status': 'failure',
                    'message': 'The account could be found on this system, check the spelling and your configuration',
                    'account': account,
                },
                'status': 500
            }

        elif len(accounts) == 0:
            return {
                "payload": {
                    'status': 'failure',
                    'message': 'There are no account configured yet for this instance.',
                    'account': account,
                },
                'status': 500
            }

        else:

            # enforce https
            if not circ_url.startswith("https://"):
                circ_url = "https://" + str(circ_url)

            # remote trailing slash in the URL, if any
            if circ_url.endswith('/'):
                circ_url = circ_url[:-1]

            # get circ_token
            circ_token = None

            # realm
            credential_realm = '__REST_CREDENTIAL__#splunk_start_defender#configs/conf-splunk_start_defender_account'
            credential_name = str(credential_realm) + ":" + str(account) + "``"

            # extract as raw json
            bearer_token_rawvalue = ""

            for credential in storage_passwords:
                if credential.content.get('realm') == str(credential_realm) and credential.name.startswith(credential_name):
                    bearer_token_rawvalue = bearer_token_rawvalue + str(credential.content.clear_password)

            # extract a clean json object
            bearer_token_rawvalue_match = re.search('\{\"circ_token\":\s*\"(.*)\"\}', bearer_token_rawvalue)
            if bearer_token_rawvalue_match:
                circ_token = bearer_token_rawvalue_match.group(1)
            else:
                circ_token = None

        # proceed
        try:
            response = circ_start_scan(circ_token, computername, circ_url, fullscan)
            return {
                "payload": response,
                'status': 200
            }

        except Exception as e:
            return {
                "payload": {
                    'action': 'failure',
                    'exception': str(e),
                },
                'status': 500
            }

