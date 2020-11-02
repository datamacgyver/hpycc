"""
**TEMPORARILY DEPRICATED! Just use get and save teh result. Trust us, it's
cleaner**

Functions to get data out of an HPCC instance and save
them to disk.

This modules functions closely mirror those in `get`.
In fact all they really do is wrap `get`'s functions
around csv writing tasks. The first input to all
functions is an instance of `Connection`.

Functions
---------
- `save_output` -- Save the first output of an ECL script.
- `save_outputs` -- Save all outputs of an ECL script.
- `save_thor_file` -- Save the contents of a thor file.

"""

from hpycc import get_output, get_thor_file


def save_output(connection, script, path_or_buf=None, syntax_check=True,
                delete_workunit=True, stored=None, **kwargs):
    """
    Save the first output of an ECL script as a csv. See
    save_outputs() for saving multiple outputs to file and
    get_output() for returning as a DataFrame.

    Parameters
    ----------
    connection: `Connection`
        HPCC Connection instance, see also `Connection`.
    script: str
        Path of script to execute.
    path_or_buf : string or file handle, default None
        File path or object, if None is provided the result is returned as
        a string.
    syntax_check: bool, optional
        Should script be syntax checked before execution. True by
        default.
    delete_workunit: bool, optional
        Delete workunit once completed. True by default.
    stored : dict or None, optional
        Key value pairs to replace stored variables within the
        script. Values should be str, int or bool. None by default.
    kwargs
        Additional parameters to be provided to
        pandas.DataFrame.to_csv().

    Returns
    -------
    None or str
        if path_or_buf is not None, else a string representation of
        the output csv.
    """
    result = get_output(connection=connection, script=script,
                        syntax_check=syntax_check,
                        delete_workunit=delete_workunit,
                        stored=stored)
    return result.to_csv(path_or_buf=path_or_buf, **kwargs)


# def save_outputs(connection, script, directory=".", overwrite=True,
#                  prefix='', syntax_check=True, delete_workunit=True,
#                  stored=None, **kwargs):
#     """
#     Save all outputs of an ECL script as csvs. See get_outputs()
#     for returning DataFrames and save_output() for writing a single
#     output to file. Names of CSVs are inhereted from the result
#     names of your OUTPUT statements. Use NAME() in ECL to specify.
#     A list of assigned names will be returned for reference.
#
#     Parameters
#     ----------
#     connection : hpycc.Connection
#         HPCC Connection instance, see also `Connection`.
#     script : str
#          Path of script to execute.
#     directory : str, optional
#         Directory to save output files in. "." by default.
#     overwrite : bool
#         Should files be overwritten if they already exist? True by
#         default. Because you should know better.
#     prefix : str, optional
#         Prefix to prepend to all file names. None by default.
#     syntax_check : bool, optional
#         Should the script be syntax checked before execution. True by
#         default.
#     delete_workunit : bool, optional
#         Delete workunit once completed. True by default.
#     stored : dict or None, optional
#         Key value pairs to replace stored variables within the
#         script. Values should be str, int or bool. None by default.
#     kwargs
#         Additional parameters to be provided to
#         pandas.DataFrame.to_csv().
#
#
#     Returns
#     -------
#     str
#         list of written CSVs
#
#     Raises
#     ------
#     IndexError
#         If `filenames` is of different length to the number of
#         outputs.
#     """
#     results = hpycc.get_outputs(
#         connection, script, syntax_check, delete_workunit, stored)
#
#     paths = [os.path.join(directory, prefix + res + ".csv") for res in results]
#     if not overwrite and any([os.path.isfile(f) for f in paths]):
#         raise FileExistsError("Target file already exists and overwrite is False. Aborting.")
#
#     for path, result in zip(paths, results.items()):
#         result[1].to_csv(path, **kwargs)
#
#     return paths


def save_thor_file(connection, thor_file, path_or_buf=None,
                   max_workers=15, chunk_size='auto', max_attempts=3,
                   max_sleep=60, dtype=None,
                   **kwargs):
    """
    Save a logical file to disk, see `get_thor_file()` for returning a
    DataFrame.

    Parameters
    ----------
    connection: `Connection`
        HPCC Connection instance, see also `Connection`.
    thor_file: str
        Logical file to be downloaded
    path_or_buf : string or file handle, default None
        File path or object, if None is provided the result is returned as
        a string.
    max_workers: int, optional
        Number of concurrent threads to use when downloading.
        Warning: too many will likely cause either your machine or
        your cluster to crash! 15 by default.
    chunk_size: int, optional.
        Size of chunks to use when downloading file. 10000 by
        default.
    max_attempts: int, optional
        Maximum number of times a chunk should attempt to be
        downloaded in the case of an exception being raised.
        3 by default.
    max_sleep: int, optional
        Maximum time, in seconds, to sleep between attempts.
        The true sleep time is a random int between `max_sleep` and
        `max_sleep` * 0.75.
    dtype: type name or dict of col -> type, optional
        Data type for data or columns. E.g. {'a': np.float64, 'b':
        np.int32}. If converters are specified, they will be applied
        INSTEAD of dtype conversion. If None, or columns are missing
        from the provided dict, they will be converted to one of
        bool, str or int based on the HPCC datatype. None by default.
    kwargs
        Additional parameters to be provided to
        pandas.DataFrame.to_csv().

    Returns
    -------
    None or str
        if path_or_buf is not None, else a string
        representation of the output csv.

    """

    file = get_thor_file(
        connection, thor_file, max_workers=max_workers, chunk_size=chunk_size,
        max_attempts=max_attempts, max_sleep=max_sleep, dtype=dtype)

    return file.to_csv(path_or_buf, **kwargs)
