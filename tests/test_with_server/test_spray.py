import os
from tempfile import TemporaryDirectory
import unittest

import pandas as pd
import hpycc
from hpycc.utils import docker_tools
from hpycc.spray import _concatenate_logical_files, spray_file
from hpycc.get import get_thor_file


# noinspection PyPep8Naming
def setUpModule():
    docker_tools.HPCCContainer()  #tag="6.4.26-1"


# noinspection PyPep8Naming
def tearDownModule():
    docker_tools.HPCCContainer(pull=False, start=False).stop_container()


CONCAT_SCRIPT_BASE = "\n".join([
    "a := DATASET([{'%s', '%s'}], "
    "{STRING a; STRING b});",
    "output(a, ,'%s');"
])


def send_file_chunks(conn, a_script):
    # print(a_script)

    with TemporaryDirectory() as d:
        p = os.path.join(d, "test.ecl")
        with open(p, "w+") as file:
            file.write(a_script)
        _ = conn.run_ecl_script(p, syntax_check=True,
                                delete_workunit=True, stored={})


class Testconcatenatelogicalfiles(unittest.TestCase):
    def setUp(self):
        self.conn = hpycc.Connection("user")

    def test_concatenate_logical_files_concatenates_files(self):
        thor_file = '~thor::testsprayconcatenatelogicalfiles'
        overwrite = True
        expire = 1
        delete_workunit = True

        output_names = ['~a1', '~b1', '~c1', '~x1']
        col_1_values = ['1', '3', '5', '6']
        col_2_values = ['aa', 'ab', 'ac', 'ad']

        [send_file_chunks(self.conn, CONCAT_SCRIPT_BASE % (col1, col2, nam))
         for col1, col2, nam in zip(col_1_values, col_2_values, output_names)]
        _concatenate_logical_files(self.conn, output_names, thor_file, 'STRING a; STRING b;',
                                   overwrite, expire, delete_workunit)

        res = get_thor_file(connection=self.conn, thor_file=thor_file)[['a', 'b']].sort_values("a")
        expected_result = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values("a")

        pd.testing.assert_frame_equal(expected_result.reset_index(drop=True),
                                      res.reset_index(drop=True),
                                      check_names=False)

    def test_concatenate_logical_files_concatenates_one_file(self):
        thor_file = '~thor::test_concatenate_logical_files_concatenates_one_file'
        overwrite = True
        expire = 1
        delete_workunit = True
        conn = hpycc.Connection("user", test_conn=False)

        output_names = ['~a2']
        col_1_values = ['1']
        col_2_values = ['aa']

        [send_file_chunks(conn, CONCAT_SCRIPT_BASE % (col1, col2, nam))
         for col1, col2, nam
         in zip(col_1_values, col_2_values, output_names)]

        _concatenate_logical_files(conn, output_names,
                                   thor_file,
                                   'STRING a; STRING b;',
                                   overwrite, expire, delete_workunit)

        res = get_thor_file(connection=conn, thor_file=thor_file)[['a', 'b']].sort_values("a")
        expected_result = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values("a")

        pd.testing.assert_frame_equal(expected_result, res)


class Testsprayfiles(unittest.TestCase):
    def setUp(self):
        self.conn = hpycc.Connection("user", test_conn=False)

    def test_spray_file_df(self):
        thor_file = '~thor::test_spray_file_df'
        overwrite = True
        expire = 1
        delete_workunit = True
        chunk_size = 10000
        max_workers = 3
        conn = hpycc.Connection("user", test_conn=False)

        col_1_values = ['1', '3', '5', '6']
        col_2_values = ['aa', 'ab', 'ac', 'ad']
        df = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values('a')

        spray_file(conn, df, thor_file, overwrite, expire, chunk_size, max_workers, delete_workunit)

        res = get_thor_file(connection=conn, thor_file=thor_file)[['a', 'b']]

        pd.testing.assert_frame_equal(df, res)

    def test_spray_file_string(self):
        thor_file = '~thor::test_spray_file_string'
        overwrite = True
        expire = 1
        delete_workunit = True
        chunk_size = 10000
        max_workers = 3
        conn = hpycc.Connection("user", test_conn=False)

        col_1_values = ['1', '3', '5', '6']
        col_2_values = ['aa', 'ab', 'ac', 'ad']
        df = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values('a')

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.csv")
            df.to_csv(p, index=False)
            spray_file(conn, p, thor_file, overwrite, expire, chunk_size, max_workers, delete_workunit)

        res = get_thor_file(connection=conn, thor_file=thor_file)[['a', 'b']]

        pd.testing.assert_frame_equal(df, res)

    def test_spray_file_string_no_tilde(self):
        thor_file = 'test_spray_file_string_no_tilde'
        overwrite = True
        expire = 1
        delete_workunit = True
        chunk_size = 10000
        max_workers = 3
        conn = hpycc.Connection("user", test_conn=False)

        col_1_values = ['1', '3', '5', '6']
        col_2_values = ['aa', 'ab', 'ac', 'ad']
        df = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values('a')

        spray_file(conn, df, thor_file, overwrite, expire, chunk_size, max_workers, delete_workunit)

        res = get_thor_file(connection=conn, thor_file='thor::' + thor_file)[['a', 'b']]

        pd.testing.assert_frame_equal(df, res)

    def test_spray_file_string_small_chunks(self):
        thor_file = '~test_spray_file_string_small_chunks'
        overwrite = True
        expire = 1
        delete_workunit = True
        chunk_size = 2
        max_workers = 3
        conn = hpycc.Connection("user", test_conn=False)

        col_1_values = ['1', '3', '5', '7', '9', '11', '13']
        col_2_values = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
        df = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values('a').reset_index(drop=True)

        spray_file(conn, df, thor_file, overwrite, expire, chunk_size, max_workers, delete_workunit)

        res = get_thor_file(connection=conn, thor_file=thor_file)[['a', 'b']].sort_values('a').reset_index(drop=True)

        pd.testing.assert_frame_equal(df, res)

    def test_spray_file_string_smallest_chunks(self):
        thor_file = '~test_spray_file_string_smallest_chunks'
        overwrite = True
        expire = 1
        delete_workunit = True
        chunk_size = 1
        max_workers = 3
        conn = hpycc.Connection("user", test_conn=False)

        col_1_values = ['1', '3', '5', '7', '9', '11', '13']
        col_2_values = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
        df = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values('a').reset_index(drop=True)

        spray_file(conn, df, thor_file, overwrite, expire, chunk_size, max_workers, delete_workunit)

        res = get_thor_file(connection=conn, thor_file=thor_file)[['a', 'b']].sort_values('a').reset_index(drop=True)

        pd.testing.assert_frame_equal(df, res)

    def test_spray_file_string_smallest_chunks_many_workers(self):
        thor_file = '~test_spray_file_string_smallest_chunks_many_workers'
        overwrite = True
        expire = 1
        delete_workunit = True
        chunk_size = 1
        max_workers = 100
        conn = hpycc.Connection("user", test_conn=False)

        col_1_values = ['1', '3', '5', '7', '9', '11', '13']
        col_2_values = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
        df = pd.DataFrame({"a": col_1_values, "b": col_2_values}).sort_values('a').reset_index(drop=True)

        spray_file(conn, df, thor_file, overwrite, expire, chunk_size, max_workers, delete_workunit)

        res = get_thor_file(connection=conn, thor_file=thor_file)[['a', 'b']].sort_values('a').reset_index(drop=True)

        pd.testing.assert_frame_equal(df, res)
