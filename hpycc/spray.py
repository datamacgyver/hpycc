"""
The module contains functions to send files to HPCC.
"""
import concurrent.futures

import pandas as pd

from hpycc.delete import delete_logical_file
from hpycc.utils.filechunker import make_chunks


def _spray_stringified_data(connection, data, record_set, logical_file,
                            overwrite, delete_workunit):
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
    delete_workunit: bool
        Delete the workunit once completed
    """
    script_content = ("a := DATASET([{}], {{{}}});\nOUTPUT(a, ,'{}' , "
                      "EXPIRE(1)").format(
        data, record_set, logical_file)
    if overwrite:
        script_content += ", OVERWRITE"
    script_content += ");"
    connection.run_ecl_string(script_content, True, delete_workunit)


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

    return 'STRING'


def _stringify_rows(df, start_row, num_rows):
    """
    Return rows of a DataFrame as a HPCC ready string. Note: this ignores the
    index

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
            sliced_df[col] = sliced_df[col].fillna(
                "").astype(str).str.replace("'", "\\'")
            sliced_df[col] = "'" + sliced_df[col] + "'"
        else:
            sliced_df[col] = sliced_df[col].fillna(0)

    return ','.join(
        ["{" + ','.join(i) + "}" for i in
         sliced_df.astype(str).values.tolist()]
    )


def spray_file(connection, source_file, logical_file, overwrite=False,
               chunk_size=10000, max_workers=3, delete_workunit=True):
    """
    Spray a file to a HPCC logical file.

    Parameters
    ----------
    :connection: `Connection`
        HPCC Connection instance, see also `Connection`.
    source_file: str, pd.DataFrame
         A pandas DataFrame or the path to a csv.
    logical_file: str
         Logical file name on THOR.
    overwrite: bool, optional
        Should the file overwrite any pre-existing logical file.
        False by default.
    chunk_size: int, optional
        Size of chunks to use when spraying file. 10000 by
        default.
    max_workers: int, optional
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
                              record_set, overwrite, delete_workunit)

    for tmp in target_names:
        delete_logical_file(connection, tmp, delete_workunit)


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
    record_set = ";".join([" ".join((_get_type(dtype), col)) for col, dtype in
                           df.dtypes.to_dict().items()])
    return record_set


def concatenate_logical_files(connection, to_concat, logical_file, record_set,
                              overwrite, delete_workunit=True):
    """
    Concatenate a list of logical files (with the same recordset)
    into a single logical file.

    Parameters
    ----------
    connection: `Connection`
        HPCC Connection instance, see also `Connection`.
    to_concat: list, iterable.
        Iterable of pre-existing logical file names to concatenate.
    logical_file: str
        Logical file name to concatenate into.
    record_set: str
        Common recordset of all logical files, see `make_record_set()`.
    overwrite: bool
        Should the file overwrite any pre-existing logical file.
    delete_workunit: bool
        Delete workunit once completed. True by default.
    Returns
    -------
    :return: None
    """
    read_files = ["DATASET('{}', {{{}}}, THOR)".format(
        nam, record_set) for nam in to_concat]
    read_files = '+\n'.join(read_files)

    script = "a := {};\nOUTPUT(a, ,'{}' "
    if overwrite:
        script += ", OVERWRITE"
    script += ");"
    script = script.format(read_files, logical_file)

    connection.run_ecl_string(script, True, delete_workunit)
