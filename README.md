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

`searchbnf.conf`

Describes the custom command options and syntax, allowing autocomplention in Splunk.

`server.conf`

This file is needed in our context as we manage via ucc-gen objects like:

- preferences (called settings)
- accounts (an account references credentials, secrets and per account settings)

ucc-gen by itself does not generate (yet) the SHC replication stanza, this is required for the settings to be properly replicated amongst the SHC members.

Without these settings, the configuration would work on a given SHC node, but not on others.

`splunk_start_defender_settings.conf`

In this file, we can preset default values for the options we made available to the Add-on via ucc-gen and the globalConfig.json.

For instance, we can preset the logging level.

`web.conf`

This file is required here to expose the REST API endpoints via Splunk Web too.

#### lib directory

`requirements.txt`

This file is a pypi file format which is used by ucc-gen to automatically retrieve the required Python librairies for the Add-on to operate.

As a minimal version, it would contain:

    splunktaucclib>=5.0.4

You can add any additional librairies that would be required to be imported by a Python logic.

Note that some librairies can be problematic if these includes compiles binaries for a certain type of processor architector.

In such a case, you can as well include manually the librairies in the lib directory, which will be included in the final package automatically.

`lib_splunk_start_defender.py`

In this Python file, we store various utility Python functions which will be imported by the custom commands, as well as by the REST API endpoints themselves.

`rest_handler.py`

This Python file is a REST API wrapper, it is used for various purposes to faciliate the management of our REST API endpoints, such as orchestrating the extraction of Metadata and organize the endpoints structure and output format.

## Least privileges approach

A typical issue with Splunk custom command and other types of advanced development techniques for Splunk relies on the fact that these require to grant users with high privileges capabilities.

In between, the following capability are problematic:

- `admin_allobjects`
- `list_settings`
- `list_storage_password`

The worst is with nio doubts the last, which allows a user with some levels of knowledge to expose any Splunk credentials that are stored in the Splunk secure credentials store, and this in a clear text format. (!)

To avoid this issue, we can leverage API REST endpoints with escalated system wide privileges, associating these with capabilities and RBAC for a full and secured control compliant with best security practices:

- When the user requests the execution of the custom command, a Python function is called, which itself is stored in a Python file stored in the `lib` directory.
- The Python function performs a REST call locally, using the splunkd_uri provided as part of the self metadata by Splunk
- The endpoints can allow be accessed by users which own the right `capability`
- If the user owns the capability, the REST API endpoints executes and estiablishes a Splunk Python SDK service using the system wide token.
- The REST API returns required information, settings and credentials in a programmatic manner back to the requesting Python function
- The rest of the logic can be executed as needed, without the need from any further privileges

Using these techniques, users can be granted the right to use the custom commands, even with very low and limited privileges.

### Exposing the REST API endpoint with passSystemAuth

The first requirement is to expose REST API endpoints with the `passSystemAuth` option and associates this with one or more capabilities:

    [script:trackme_rest_handler_secmanager]
    match                 = /splunk_start_defender/manager
    script                = splunk_start_manager_rest_handler.py
    scripttype            = persist
    handler               = splunk_start_manager_rest_handler.SplunkStartDefender_v1
    output_modes          = json
    passPayload           = true
    passSystemAuth        = true
    capability            = splunkstartdefender
    python.version = python3

When exposed this way, the REST API endpoint will automatically benefit from a special authentication token, in addition with the user based session token:

- `system_authtoken`

This special special authentication token is parsed and made available via the `rest_handler.py` Python wrapper:

    #
    # system auth
    #

    # If passSystemAuth = True, add system_authtoken
    try:
        system_authtoken = args['system_authtoken']
    except Exception as e:
        system_authtoken = None

When establishing the Python SDK service, the REST API endpoints functions stored in `splunk_start_manager_rest_handler.py` (in bin directory) use the system level token, rather than the user level token requesting the action:

    # Get service
    service = client.connect(
        owner="nobody",
        app="splunk_start_defender",
        port=request_info.connection_listening_port,
        token=request_info.system_authtoken
    )

This way, the action is performed with system level privieleges rather than limited user privileges.

Lastly, the endpoint is protected via capability:

    capability            = splunkstartdefender

This capability is defined in the file `authorize.conf`, granted to a builtin role which is part of the application.

As well, this capability needs to be explicitly enabled for the `sc_admin` role for Splunk Cloud to allow granting this role:

    # authorize.conf

    #
    # capabilities
    #

    # only roles with this capability can access to the splunk_start_defender API endpoints, and use the application accordingly
    [capability::splunkstartdefender]

    #
    # roles
    #

    # users members of this role, or roles inheriting this roles can use the app

    [role_splunk_start_defender]

    # Minimal import
    importRoles = user

    # capabilities
    splunkstartdefender = enabled

    # This is required for Splunk Cloud
    [role_sc_admin]
    splunkstartdefender = enabled

Finally, the custom commands calls a Python function which itself performs the REST call locally to splunkd, using the Python requests module:

    # get account
    try:
        # get account
        account_conf = splunk_start_defender_get_account(self._metadata.searchinfo.session_key, self._metadata.searchinfo.splunkd_uri, self.account)

    except Exception as e:
        raise Exception(str(e))

This function, stored in `lib/lib_splunk_start_defender.py` performs:

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
                if response.ok:
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

The same technique applies to other endpoints, for instance to retrieve the credentials (tokens) stored in the Splunk secure credential store, and make these available in a secured fashion to the rest of the Python process.
