"""
Module contains functions to check ECL scripts prior to runtime, therefore
saving resources on the main server.
"""
import os
import logging
import hpycc.utils.datarequests


def syntax_check(script, hpcc_server):
    """
    Use ECLCC to run a syntax check on a script.

    :param script: str
        Path of script to execute.
    :param repo: str
        Path to the root of local ECL repository if applicable.
    :param legacy: bool
        should the -legacy flag be added to the call?

    :return: parsed: list of tuples
        List of processed tuples in the form
        [(output_name, output_xml)].
    """

    legacy = hpcc_server['legacy']
    repo = hpcc_server['repo']

    logger = logging.getLogger('syntaxcheck')
    logger.debug('Checking %s using repo %s and legacy %s' % (script, repo, legacy))

    if not os.path.isfile(script):
        raise FileNotFoundError('Script %s not found' % script)

    repo_flag = " " if repo is None else "-I {}".format(repo)
    legacy_flag = '-legacy ' if legacy else ''

    command = "eclcc -syntax {}{} {}".format(legacy_flag, repo_flag, script)

    result = hpycc.utils.datarequests.run_command(command)
    err = result['stderr']

    if err and ': error' in err.lower():
        raise EnvironmentError('Script %s does not compile! Errors: \n %s' % (script, err))
    elif err and ': warning' in err.lower():
        logger.warning('Script %s raises the following warnings: \n %s' % (script, err))
    elif err and ': warning' not in err.lower():
        raise EnvironmentError('Script %s contains unhandled feedback: \n %s' % (script, err))
    else:
        logger.debug("Script %s passes syntax check" % script)
