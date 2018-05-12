"""
The module contains functions to send files to HPCC.
"""
import concurrent.futures

import pandas as pd

from hpycc.delete import delete_logical_file
from hpycc.utils.filechunker import make_chunks

# TODO make sure this shouts at the user if they use bad column names
# TODO tests
# TODO numpy docstrings

def _spray_stringified_data(connection, data, record_set, logical_file,
                            overwrite):
    """
    Spray stringified data to a HPCC logical file. To generate the
    stringified data and recordset, see `stringify_rows()` &
    `make_record_set()`

    Parameters
    ----------
    :param connection: `Connection`
        HPCC Connection instance, see also `Connection`.
    :param data: str
        Stringified data generated by `stringify_rows()`.
    :param record_set: str
        Recordset generated by `make_record_set()`.
    :param logical_file: str
        Logical file name on THOR.
    :param overwrite: bool
        Should the file overwrite any pre-existing logical file.
    """
    script_content = ("a := DATASET([{}], {{{}}});\nOUTPUT(a, ,'{}' , "
                      "EXPIRE(1)").format(
        data, record_set, logical_file)
    if overwrite:
        script_content += ", OVERWRITE"
    script_content += ");"
    connection.run_ecl_string(script_content, True)


def _get_type(typ):
    """
    Return the HPCC data type equivalent of a pandas/ numpy dtype.

    Parameters
    ----------
    :param typ: dtype
        Numpy or pandas dtype.

    Returns
    -------
    :return type: string
        ECL data type.
    """
    typ = str(typ)
    if 'float' in typ:
        # return 'DECIMAL32_12'
        pass
    elif 'int' in typ:
        # return 'INTEGER'
        pass
    elif 'bool' in typ:
        # return 'BOOLEAN'
        pass
    else:
        # return 'STRING'
        pass
    #  TODO: do we need to convert dates more cleanly?
    # TODO: at present we just return string as we have an issue with nans in
    # ECL
    return 'STRING'


def _stringify_rows(df, start_row, num_rows):
    """
    Return rows of a DataFrame as a HPCC ready string.

    Parameters
    ----------
    :param df: DataFrame
        DataFrame to stringify.
    :param start_row: int
        Start index number.
    :param num_rows: int
        Number of rows to include.

    Returns
    -------
    :return: str
        ECL ready string of the slice.
    """
    sliced_df = df.loc[start_row:start_row + num_rows, df.columns]

    for col in sliced_df.columns:
        dtype = sliced_df.dtypes[col]
        ecl_type = _get_type(dtype)
        if ecl_type == "STRING":
            sliced_df[col] = sliced_df[col].fillna("").str.replace("'", "\\'")
            sliced_df[col] = "'" + sliced_df[col] + "'"
        else:
            sliced_df[col] = sliced_df[col].fillna(0)
    sliced_df.reset_index(inplace=True)

    return ','.join(
        ["{" + ','.join(i) + "}" for i in
         sliced_df.astype(str).values.tolist()]
    )


def spray_file(connection, source_file, logical_file, overwrite=False,
               chunk_size=10000, max_workers=3):
    """
    Spray a file to a HPCC logical file.

    Parameters
    ----------
    :param connection: `Connection`
        HPCC Connection instance, see also `Connection`.
    :param source_file: str, pd.DataFrame
         A pandas DataFrame or the path to a csv.
    :param logical_file: str
         Logical file name on THOR.
    :param overwrite: bool, optional
        Should the file overwrite any pre-existing logical file.
        False by default.
    :param chunk_size: int, optional
        Size of chunks to use when spraying file. 10000 by
        default.
    :param max_workers: int, optional
        Number of concurrent threads to use when spraying.
        Warning: too many will likely cause either your machine or
        your cluster to crash! 3 by default.

    Returns
    -------
    :return: None

    """
    if isinstance(source_file, pd.DataFrame):
        df = source_file
    elif isinstance(source_file, str):
        df = pd.read_csv(source_file, encoding='latin')
    else:
        raise TypeError

    record_set = _make_record_set(df)

    chunks = make_chunks(len(df), logical_csv=False,
                         chunk_size=chunk_size)

    stringified_rows = (_stringify_rows(df, start_row, num_rows)
                        for start_row, num_rows in chunks)
    target_names = ["TEMPHPYCC::{}from{}to{}".format(
            logical_file, start_row, start_row + num_rows)
        for start_row, num_rows in chunks]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as \
            executor:
        futures = [
            executor.submit(_spray_stringified_data, connection, row,
                            record_set, name, overwrite)
            for row, name in zip(stringified_rows, target_names)]
        _, __ = concurrent.futures.wait(futures)

    concatenate_logical_files(connection, target_names, logical_file,
                              record_set, overwrite)

    for tmp in target_names:
        delete_logical_file(connection, tmp)


def _make_record_set(df):
    """
    Make an ECL recordset from a DataFrame.

    Parameters
    ----------
    :param df: DataFrame
        DataFrame to make recordset from.

    Returns
    -------
    :return: record_set: string
        String recordset.
    """
    record_set = ";".join([" ".join((col, _get_type(dtype))) for col, dtype in
                           df.dtypes.to_dict().items()])
    return record_set


def concatenate_logical_files(connection, to_concat, logical_file, record_set,
                              overwrite):
    """
    Concatenate a list of logical files (with the same recordset)
    into a single logical file.

    Parameters
    ----------
    :param connection: `Connection`
        HPCC Connection instance, see also `Connection`.
    :param to_concat: list, iterable.
        Iterable of pre-existing logical file names to concatenate.
    :param logical_file: str
        Logical file name to concatenate into.
    :param record_set: str
        Common recordset of all logical files, see `make_record_set()`.
    :param overwrite: bool
        Should the file overwrite any pre-existing logical file.

    Returns
    -------
    :return: None
    """
    # TODO add an expire
    read_files = ["DATASET('{}', {{{}}}, THOR)".format(
        nam, record_set) for nam in to_concat]
    read_files = '+\n'.join(read_files)

    script = "a := {};\nOUTPUT(a, ,'{}' "
    if overwrite:
        script += ", OVERWRITE"
    script += ");"
    script = script.format(read_files, logical_file)

    connection.run_ecl_string(script, True)
