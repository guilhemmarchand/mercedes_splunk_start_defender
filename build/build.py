#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys
import time
import shutil
import tarfile
import json
import logging
import argparse
import glob
import subprocess
import configparser
import hashlib

# load libs
sys.path.append('libs')
from tools import cd

# Args
parser = argparse.ArgumentParser()
parser.add_argument('--debug', dest='debug', action='store_true')
parser.add_argument('--keep', dest='keep', action='store_true')
parser.set_defaults(debug=False)
parser.set_defaults(keep=False)
args = parser.parse_args()

# Set debug boolean
if args.debug:
    debug = True
else:
    debug = False

# Set keep boolean
if args.keep:
    keep = True
else:
    keep = False

# set logging
root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

if debug:
    root.setLevel(logging.DEBUG)
    handler.setLevel(logging.DEBUG)
else:
    root.setLevel(logging.INFO)
    handler.setLevel(logging.INFO)

# version file
version_file = "../version.json"

# build_dir
build_dir = "../build"

# package dir
package_dir = "../package"

# output_dir
output_dir = "../output"


#
# functions
#

# get release number
def get_release_number():

    # Get the version release number
    try:
        with open(version_file) as f:
            version_data = json.load(f)
            version_release_number = version_data['version']
            logging.info('**** package generation, version=\"{}\" ****'.format(version_release_number))

    except Exception as e:
        logging.error("Failed to retrieve the version release number, exception=\"{}\"".format(e))
        version_release_number = "1.0.0"

    # return
    return version_release_number


# get app id
def get_app_id():

    # Get the version release number
    try:
        with open(version_file) as f:
            version_data = json.load(f)
            logging.info("version_data=\"{}\"".format(version_data))
            appID = version_data['appID']
            logging.info('**** app generation, appID=\"{}\" ****'.format(appID))

    except Exception as e:
        logging.error("Failed to retrieve the appID, exception=\"{}\"".format(e))
        raise ValueError("Failed to retrieve the appID, exception=\"{}\"".format(e))

    # return
    return appID


# gen organisation applications
def gen_app():

    # get release number
    version_release_number = get_release_number()

    # get app ID
    appID = get_app_id()

    # Purge any existing tgz in the output directory
    files = glob.glob(os.path.join(output_dir, '*.tgz'))
    for file_name in files:
        logging.debug('Attempting to remove existing tgz archive=\"{}\"'.format(file_name))
        if os.path.isfile(file_name):
            try:
                os.remove(file_name)
                logging.debug('Archive=\"{}\" was deleted successfully'.format(file_name))
            except Exception as e:
                logging.error('Archive=\"{}\" could not be deleted, exception=\"{}\"'.format(file_name, e))

    # Set app_root
    app_root = os.path.join(output_dir, appID)

    # Remove current app if it exists
    if os.path.isdir(app_root):
        logging.debug("appID=\"{}\" purging existing directory app_root=\"{}\"".format(appID, app_root))
        try:
            shutil.rmtree(app_root)
        except Exception as e:
            logging.error("appID=\"{}\", failed to purge the existing build directory=\"{}\" with exception=\"{}\"".format(appID, app_root, e))
            raise ValueError("appID=\"{}\", failed to purge the existing build directory=\"{}\" with exception=\"{}\"".format(appID, app_root, e))

    # Package
    with cd("../"):
        logging.info("Call ucc-gen")
        subprocess.run(["ucc-gen", "--ta-version", version_release_number])

    # Package
    with cd(output_dir):

        # read app.conf to retrieve the current build
        try:
            config = configparser.ConfigParser()
            config.read(os.path.join(app_root, "default", "app.conf"))
            build_number = config['install']['build']

        except Exception as e:
            logging.error("failed to retrieve the build number with exception=\"{}\"".str(e))
            sys.exit(1)

        # save the version number to a simple text file for further usage
        version_number_file = "version.txt"
        with open(version_number_file, "w") as f:
            f.write(str(version_release_number).replace(".", "") + "\n")

        # save the build number to a simple text file for further usage
        build_number_file = "build.txt"
        with open(build_number_file, "w") as f:
            f.write(build_number + "\n")

        # gen tar
        tar_file = str(app_root) + '_v' + str(version_release_number).replace(".", "") + "_" + str(build_number) + '.tgz'
        out = tarfile.open(tar_file, mode='w:gz')

        try:
            out.add(str(appID))
        except Exception as e:
            logging.error("appID=\"{}\", archive file=\"{}\" creation failed with exception=\"{}\"".format(appID, tar_file, e))
            raise ValueError("appID=\"{}\", archive file=\"{}\" creation failed with exception=\"{}\"".format(appID, tar_file, e))
        finally:
            logging.info('"appID=\"{}\", Achive tar file creation, archive_file=\"{}\"'.format(appID, tar_file))
            out.close()

        # get sha256
        logging.info("Get and store the sha256 control sum")

        with open(tar_file, "rb") as f:
            bytes = f.read() # read entire file as bytes
            readable_hash = hashlib.sha256(bytes).hexdigest()
            logging.info("sha256 control sum=\"{}\"".format(readable_hash))

        sha256_file = "release-sha256.txt"
        with open(sha256_file, "w") as f:
            f.write(readable_hash + "\t" + str(appID) + '_v' + str(version_release_number).replace(".", "") + "_" + str(build_number) + '.tgz' + "\n")

        # log info
        logging.info('**** app generation terminated, appID=\"{}\", build_number=\"{}\", sha256=\"{}\" ****'.format(appID, build_number, readable_hash))

    # Remove build directories
    if not keep:
        if os.path.isdir(app_root):
            logging.debug("appID=\"{}\", purging existing directory app_root=\"{}\"".format(appID, app_root))
            try:
                shutil.rmtree(app_root)
            except Exception as e:
                logging.error("appID=\"{}\", failed to purge the build directory=\"{}\" with exception=\"{}\"".format(appID, app_root, e))
                raise ValueError("appID=\"{}\", failed to purge the build directory=\"{}\" with exception=\"{}\"".format(appID, app_root, e))


# Generate the application release
gen_app()
sys.exit(0)
