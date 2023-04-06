# Splunk Add-on for Defender

## Introduction

This Add-on was designed to handle a REST API based interraction with the defender service, in SPL with two interractive generating custom commands:

_defenderstatus:_

    | defenderstatus computername=<computer name target>

_defenderscan:_

    | defenderscan computername=<computer name target> fullscan=<True|False>

It was redesigned and repackaged for the purpose of the Splunk Cloud migration, with the following evolutions:

- The custom commands need to be exectued on Splunk Cloud, but relayed to another Splunk instance running on-premise
- The Splunk Enterprise on-premise instance (a Heavy Forwarder) then receives the incoming query, and performs the action effectively
- In addition, a least privleges approach was implemented to avoid having to grant some security concerning Splunk capabilities
- To achieve this, we use REST API endpoints associated with custom capabilities, as well as a RBAC approach to grant capabilities as needed
- Finally, the application was completely redesigned to rely on the Splunk UCC framework

## References

_Splunk UCC framework and ucc-gen:_

- https://splunk.github.io/addonfactory-ucc-generator
- https://github.com/splunk/addonfactory-ucc-generator

## Requirements

To build the package and maintain evolutions over time, the following requirements must be met:

- A Linux or Mac OS based development environment
- Python3 must be available
- pip3 must be installed
- The ucc-gen command must be installed
- Internet connectivity for pip to retrieves packages as needed

### Installing ucc-gen

Installing ucc-gen is straightforward:

    python3 -m "pip3 install splunk-add-on-ucc-framework"

## Application structure and build

The application development structure is the following:

    build
    output
    package
    globalConfig.json
    version.json

### build and output directories

The build directory contains a simple build.py script which can be executed to orchestrate the generation or the final package.

To generate a new build:

    cd build
    python3 build.py

To generate a new build and retain the extracted directory in the output directory:

    cd build
    python3 build.py --keep

To update the application version, you need to update the version.json which is then taken into account automatically:

    {
    "version": "1.0.4",
    "appID": "splunk_start_defender"
    }

The Python build.py script does the following:

- It retrieves the current application version in the file version.json
- It prepares and cleans if necessary previous execution and artifacts in the output directory
- It calls the ucc-gen command including the version requirement
- It packages the generated directory and content into a tgz file
- It writes a version.txt, a build.txt and a release-sha256.txt containing the unique sha256 sum of the generated tgz file

The tgz file represents the final Splunk application, which should be submitted for deployment where needed.

The content of the output directory should be excluded from the Git repository, which is done via a .gitignore:

    # output
    output/*
    !output/README.txt

As well, some Python related artifacts should be excluded in the build directory:

    # Py build
    build/libs/__pycache__

### package directory

The `package` directory is the Splunk application structure content, any directory and its content will be picked up automatically by ucc-gen and included into the application release.

It should contain at the minimum:

    bin
    default
    lib
    static
    app.manifest

#### bin directory

The bin directory would contain executable scripts and binaries, in the case of this Addon, we have the following:

`get_defender_status.py`

- The Splunk generating custom command corresponding to the the SPL command `| defenderstatus`

`splunk_start_manager_rest_handler.py`

- This Python script contains the REST endpoints which are going to be exposed by splunkd

`start_defender.py`

- The Splunk generating custom command corresponding to the the SPL command `| defenderscan`

#### default directory

In default, we have the following configuration files:

`app.conf`

The usual Splunk app.conf, note that it **not needed to maintain versioning manually**, the ucc-gen will do it automatically.

Therefore, when creating a new release, updating the app.conf is not necessary.

`authorize.conf`

We will describe further the content of this file in the next section regarding the least privileges approach, but in short it contains:

- The custom capability
- The role definitions which inherit and enable the capability as needed

`commands.conf`

Defines the custom commands and the associated Python files.

`props.conf`

In the context of this Add-on, it is important to highlight that Python scripts (custom commands and API endpoints) generate logs effectively.

The best practice is to manage explicitely the source ingestion definition to allow a proper parsing at index time and search time.

`restmap.conf`

The restmap.conf file contains the definition for the API endpoints to be taken into account by splunk and exposed by splunkd.

**ucc-gen** generates itself a first version of the restmap.conf configuration file as it does need API endpoints too.

These API endpoints are called when performing the configuration of the Add-on via the configuration page ucc-gen generates, based on the `globalConfig.json` file.
