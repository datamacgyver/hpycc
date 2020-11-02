hpycc Readme
============

The hpycc package is intended to simplify the use of data stored on HPCC and make it easily available to both users and other servers through basic Python calls. Its long-term goal is to make access to and manipulation of HPCC data as quick and easy as any other type system. 

Docker Announcement
-------------------
HPCC seem to have pulled the images that this is based on. I've created one for the test environment I developed against
but if you want ot dev against a different one you will need to build the relevent container. I've forked the old HPCC
docker repo in case you need it or it gets removed: https://github.com/datamacgyver/docker-hpcc

Note that in the docker files I've tried the wget for HPCC is broken. You can get the new ones from
the HPCC website but there's a modified one in this repoo I used for the build.

Documentation
-------------
The below readme and package documentation is available at https://hpycc.readthedocs.io/en/latest/

The package's github is available at: https://github.com/OdinProAgrica/hpycc

This package is released under GNU GPLv3 Licence: https://www.gnu.org/licenses/gpl-3.0.en.html

Want to use this in R? Then the reticulate package is your friend! Just save as a CSV and read back in. That
or you can use an R notebook with a Python chunk.


Installation
------------
Install with:

pip install hpycc

Or, if you are still a bit old school:

python -m pip install hpycc

Current Status
--------------
Tested and working on HPCC v6.4.2 and python 3.5.2 under windows 10. Has been used on Linux systems but not extensively tested.

Dependencies
------------
The package itself mainly uses core Python, Pandas is needed for outputting dataframes.

There is a dependency for client tools to run ECL scripts (you need ecl.exe and eclcc.exe).
Make sure you install the right client tools for your HPCC version and add the dir to your system path,
e.g. C:\\Program Files (x86)\\HPCCSystems\\X.X.X\\clienttools\\bin.

Tests and docker container functions require docker to spin up HPCC environments.

Main Functions
--------------
Below summarises the key functions and non-optional parameters. For specific arguments see the relevant
function's documentation. Note that while retrieving a file is a multi-thread process, running a script
and getting the results is not. Therefore if your file is quite big you may be better off saving the
results of a script using run.run_script() with a thor file output then downloading the file with
get.get_thor_file().

connection(username, server="localhost", port=8010, repo=None, password="password", legacy=False, test_conn=True)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Create a connection to a new HPCC instance. This is then passed to any interface functions.

get_output(connection, script, ...) & save_output(connection, script, path, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Run a given ECL script and either return the first result as a pandas dataframe or save it to file.

get_outputs(connection, script, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Run a given ECL script and return all results as a dict of pandas dataframes or save them to files.

get_thor_file(connection, logical_file, path, ...) & save_thor_file(connection, logical_file, path, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Get a logical file and either return as a pandas dataframe or save it to file.

run_script(connection, script, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Run a given ECL script. 10 rows will be returned but they will be dumped, no output is given.

spray_file(connection, source_file, logical_file, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Spray a csv or pandas DataFrame into HPCC.

docker_tools.HPCCContainer(tag="6.4.26-1", ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Designed for our testing but made available generally, a collection of functions for running and managing
HPCC docker containers is also available. The above function starts a container, see help file for shutting
down and other management tasks.


Examples 
--------
The below code gives an example of functionality::

    import hpycc
    import pandas as pd
    from hpycc.utils import docker_tools
    from os import remove

    # Start an HPCC docker image for testing
    docker_tools.HPCCContainer(tag="6.4.26-1")

    # Setup stuff
    username = 'HPCC_dev'
    test_file = 'test.csv'
    f_hpcc_1 = '~temp::testfile1'
    f_hpcc_2 = '~temp::testfile2'
    ecl_script = 'ecl_script.ecl'

    # Let's create a connection object so we can interface with HPCC.
    # up with Docker
    conn = hpycc.Connection(username, server="localhost")
    try:
        # So, let's spray up some data:
        pd.DataFrame({'col1': [1, 2, 3, 4], 'col2': ['a', 'b', 'c', 'd']}).to_csv(test_file, index=False)
        hpycc.spray_file(conn, test_file, f_hpcc_1, expire=7)

        # Lovely, we can now extract that as a Thor file:
        df = hpycc.get_thor_file(conn, f_hpcc_1)
        print(df)
        # Note __fileposition__ column. This will be drop-able in future versions.

        #################################
        #   col1 col2  \__fileposition__#
        # 0    1    a                 0 #
        # 1    3    c                20 #
        # 2    2    b                10 #
        # 3    4    d                30 #
        #################################

        # If preferred data can also be extracted using an ECL script.
        with open(ecl_script, 'w') as f:
            f.writelines("DATASET('%s', {STRING col1; STRING col2;}, THOR);" % f_hpcc_1)
            # Note, all columns are currently string-ified by default
        df = hpycc.get_output(conn, ecl_script)
        print(df)

        ################
        #   col1 col2  #
        # 0    1    a  #
        # 1    3    c  #
        # 2    2    b  #
        # 3    4    d  #
        ############## #


        # get_thor_file() is optimised for large files, get_output is not (yet). To run a script and
        # download a large result you should therefore save a thor file and grab that.

        with open(ecl_script, 'w') as f:
            f.writelines("a := DATASET('%s', {STRING col1; STRING col2;}, THOR);"
                         "OUTPUT(a, , '%s');" % (f_hpcc_1, f_hpcc_2))
        hpycc.run_script(conn, ecl_script)
        df = hpycc.get_thor_file(conn, f_hpcc_2)
        print(df)

        #################################
        #   col1 col2  \__fileposition__#
        # 0    1    a                 0 #
        # 1    3    c                20 #
        # 2    2    b                10 #
        # 3    4    d                30 #
        #################################

    finally:
        # Shutdown our docker container
        docker_tools.HPCCContainer(pull=False, start=False).stop_container()
        remove(ecl_script)
        remove(test_file)

Issues, Bugs, Comments? 
-----------------------
Please use the package's github: https://github.com/OdinProAgrica/hpycc

Any contributions are also welcome.
