import sys, requests, time, os
import logging
from logging.handlers import RotatingFileHandler
import json
from os.path import join, dirname, basename
######################################################################
# developed by Oliver Zimmermann
#
######################################################################

URL_CONF = 'defender'
APP_NAME = basename(dirname(dirname(__file__)))
APP_HOME = dirname(dirname(__file__))
sys.path.append(join(APP_HOME, 'lib'))
sys.path.append(join(APP_HOME, 'bin'))
splunkhome = os.environ['SPLUNK_HOME']

# set logging
filehandler = RotatingFileHandler('%s/var/log/splunk/%s.log' % (splunkhome, APP_NAME), mode='a', maxBytes=10000000, backupCount=1)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(funcName)s %(lineno)d %(message)s')
logging.Formatter.converter = time.gmtime
filehandler.setFormatter(formatter)
log = logging.getLogger()  # root logger - Good to get it only once.
for hdlr in log.handlers[:]:  # remove the existing file handlers
    if isinstance(hdlr,logging.FileHandler):
        log.removeHandler(hdlr)
log.addHandler(filehandler)      # set the new handler
# set the log level to INFO, DEBUG as the default is ERROR
log.setLevel(logging.INFO)

try:
    from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
except Exception as e:
    logging.error(e)

# import additional libs
from lib_splunk_start_defender import splunk_start_defender_get_conf, splunk_start_defender_get_account, \
    circ_get_status, circ_start_scan, \
    circ_relay_get_status, circ_relay_start_scan

@Configuration()
class StartDefender(GeneratingCommand):

    account = Option(
        doc='''
        **Syntax:** **account=****
        **Description:** account to be used for the query.''',
        require=False, default="circapi_defender", validate=validators.Match("account", r"^.*$"))

    computername = Option(
        doc='''
        **Syntax:** **computername=****
        **Description:** computername to be used for the query.''',
        require=True, default=None, validate=validators.Match("computername", r"^.*$"))

    fullscan = Option(
        doc='''
        **Syntax:** **computername=****
        **Description:** computername to be used for the query.''',
        require=False, default=False, validate=validators.Boolean())

    def generate(self):

        # get instance_role
        try:
            start_defender_conf = splunk_start_defender_get_conf(self._metadata.searchinfo.session_key, self._metadata.searchinfo.splunkd_uri)
            instance_role = start_defender_conf['role']['instance_role']

        except Exception as e:
            raise Exception(str(e))

        # get account
        try:
            # get account
            account_conf = splunk_start_defender_get_account(self._metadata.searchinfo.session_key, self._metadata.searchinfo.splunkd_uri, self.account)

        except Exception as e:
            raise Exception(str(e))

        # Process
        try:

            # act depending on the context
            if instance_role in ('splunk_cloud'):

                relay_url = account_conf.get('relay_url')
                relay_token = account_conf.get('relay_token')

                # run call
                yield_record = {
                    '_time': time.time(),
                    '_raw': {
                        'action': 'requested',
                        'requester': self._metadata.searchinfo.username,
                        'computername': self.computername,
                        'fullscan': self.fullscan,
                        'account': self.account,
                        'response': 'sending start_defender request to relay=\"{}\"'.format(relay_url),
                    },
                }
                logging.info(json.dumps(yield_record, indent=2))
                yield yield_record

                # run call
                try:
                    response = circ_relay_start_scan(self.account, relay_token, self.computername, relay_url, self.fullscan)
                    yield_record = {
                    '_time': time.time(),
                    '_raw': response,
                    }
                    logging.info(json.dumps(yield_record, indent=2))
                    yield yield_record

                except Exception as e:
                    yield_record = {
                    '_time': time.time(),
                    '_raw': {
                        'action': 'failure',
                        'exception': str(e),
                        },
                    }
                    logging.error(json.dumps(yield_record, indent=2))
                    yield yield_record

            else:

                circ_url = account_conf.get('circ_url')
                circ_token = account_conf.get('circ_token')
            
                # run call
                yield_record = {
                    '_time': time.time(),
                    '_raw': {
                        'action': 'requested',
                        'requester': self._metadata.searchinfo.username,
                        'computername': self.computername,
                        'fullscan': self.fullscan,
                        'account': self.account,
                        'response': 'sending start_defender request to circ=\"{}\"'.format(circ_url),
                    },
                }
                logging.info(json.dumps(yield_record, indent=2))
                yield yield_record

                # run call
                try:
                    response = circ_start_scan(circ_token, self.computername, circ_url, self.fullscan)
                    yield_record = {
                    '_time': time.time(),
                    '_raw': response,
                    }
                    logging.info(json.dumps(yield_record, indent=2))
                    yield yield_record

                except Exception as e:
                    yield_record = {
                    '_time': time.time(),
                    '_raw': {
                        'action': 'failure',
                        'exception': str(e),
                        },
                    }
                    logging.error(json.dumps(yield_record, indent=2))
                    yield yield_record

        except Exception as e:

            msg = "start_defender, an exception was encountered, exception=\"{}\"".format(str(e))
            yield {
                '_raw': msg,
                '_time': time.time()
                }
            logging.error(msg)


dispatch(StartDefender, sys.argv, sys.stdin, sys.stdout, __name__)
