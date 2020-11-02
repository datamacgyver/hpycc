"""
This module contains old_tests for hpycc.connection.

"""
import os
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import re
import warnings

import pandas as pd
import requests
from requests.exceptions import ConnectionError

import hpycc.connection
from hpycc.connection import check_ecl_cmd
from hpycc.utils import docker_tools


# noinspection PyPep8Naming
def setUpModule():
    docker_tools.HPCCContainer()  #tag="6.4.26-1"


# noinspection PyPep8Naming
def tearDownModule():
    docker_tools.HPCCContainer(pull=False, start=False).stop_container()


class TestConnectionTestConnectionWithNoAuth(unittest.TestCase):
    def test_test_connection_passes_successfully_with_username(self):
        conn = hpycc.connection.Connection(username="testuser")
        result = conn.test_connection()
        self.assertTrue(result)

    def test_test_connection_works_with_numeric_server(self):
        conn = hpycc.connection.Connection(username="test", server="127.0.0.1")
        result = conn.test_connection()
        self.assertTrue(result)

    def test_test_connection_fails_with_incorrect_server(self):
        with self.assertRaises(ConnectionError):
            conn = hpycc.connection.Connection(username="test", server="l")
            conn.test_connection()

    def test_test_connection_fails_with_incorrect_port(self):
        with self.assertRaises(ConnectionError):
            conn = hpycc.connection.Connection(username="test", port=9999)
            conn.test_connection()

    def test_test_connection_passes_with_password(self):
        conn = hpycc.connection.Connection(username="test", password="pw")
        result = conn.test_connection()
        self.assertTrue(result)


class TestConnectionRunECLScriptWithServer(unittest.TestCase):
    def test_run_script_runs_script(self):
        conn = hpycc.Connection("user", test_conn=False)
        good_script = "output(2);"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            self.assertTrue(conn.run_ecl_script(p, syntax_check=False,
                                                delete_workunit=False,
                                                stored={}))

    def test_run_script_returns_correct_tuple(self):
        conn = hpycc.Connection("user", test_conn=False)
        good_script = "output(2);"
        expected_out_stdout = "\r\n".join([
            "Using eclcc path ", "", "Deploying ECL Archive ", "", "Deployed",
            "   wuid: W20180627-154140", "   state: compiled", "",
            "Running deployed workunit W20180627-154140",
            "<Result>", "<Dataset name='Result 1'>",
            " <Row><Result_1>2</Result_1></Row>",
            "</Dataset>", "</Result>\r\n"
        ])
        expected_out_stderr = "\r\n".join([
            "EXEC: Creating PIPE process : ",
            "EXEC: Pipe: Waiting for process to complete 748",
            "EXEC: Pipe: process complete\r\n"
        ])
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            result = conn.run_ecl_script(p, syntax_check=False,
                                         delete_workunit=False,
                                         stored={})
        self.assertEqual(result.__class__.__name__, "Result")
        stdout_output = re.sub("path (.+?)eclcc", 'path ',
                               result.stdout)
        stdout_output1 = re.sub("Archive (.+?)test.ecl", 'Archive ',
                                stdout_output)
        stdout_output2 = re.sub("W[0-9{8}](\S*)", 'W20180627-154140',
                                stdout_output1)
        self.assertEqual(stdout_output2, expected_out_stdout)
        stderr_output = re.sub(" [0-9][0-9][0-9]", ' 748', result.stderr)
        stderr_output1 = re.sub("process : (.+?)test.ecl\"", 'process : ',
                                stderr_output)
        self.assertEqual(stderr_output1, expected_out_stderr)

    def test_run_script_fails_if_file_not_found(self):
        conn = hpycc.Connection("user", test_conn=False)
        with self.assertRaises(subprocess.SubprocessError):
            conn.run_ecl_script("test.ecl", syntax_check=False,
                                delete_workunit=False, stored={})

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_run_ecl_script_runs_delete_workunit_if_true(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        script = "OUTPUT(2);"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(script)
            conn.run_ecl_script(p, False, True, {})
        mock.assert_called()

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_get_run_ecl_script_doesnt_run_delete_workunit_if_false(
            self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        script = "OUTPUT(2);"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(script)
            conn.run_ecl_script(p, False, False, {})
        self.assertFalse(mock.called)

    def test_run_ecl_script_stored_variables_change_outputs_all_types(self):
        conn = hpycc.Connection("user", test_conn=False)

        script = ("a := 'abc' : STORED('a'); b := FALSE : STORED('b'); "
                  "c := 546 : STORED('c'); a + a; b AND TRUE; c + c;")

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(script)
            result = conn.run_ecl_script(
                p, True, True, stored={'a': 'Hello', 'b': True, 'c': 24601})

        result_stdout = str(result.stdout)

        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)

        res2 = re.search(r'<Row><Result_2>(.*?)</Result_2>',
                         result_stdout).group(1)

        res3 = re.search(r'<Row><Result_3>(.*?)</Result_3>',
                         result_stdout).group(1)

        expected1 = 'HelloHello'
        expected2 = 'true'
        expected3 = '49202'

        self.assertEqual(res1, expected1)
        self.assertEqual(res2, expected2)
        self.assertEqual(res3, expected3)

    def test_run_ecl_script_outputs_stored_wrong_key_inputs(self):
        conn = hpycc.Connection("user", test_conn=False)

        script = ("a := 'abc' : STORED('a'); b := FALSE : STORED('b'); "
                  "c := 12345 : STORED('c'); a; b; c;")

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(script)
            result = conn.run_ecl_script(
                p, True, True, stored={'d': 'Why', 'e': 'Not',
                                       'f': 'Zoidberg'})

        result_stdout = str(result.stdout)

        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)

        res2 = re.search(r'<Row><Result_2>(.*?)</Result_2>',
                         result_stdout).group(1)

        res3 = re.search(r'<Row><Result_3>(.*?)</Result_3>',
                         result_stdout).group(1)

        expected1 = 'abc'
        expected2 = 'false'
        expected3 = '12345'

        self.assertEqual(res1, expected1)
        self.assertEqual(res2, expected2)
        self.assertEqual(res3, expected3)

    def test_run_ecl_script_passes_with_missing_stored(self):
        conn = hpycc.Connection("user", test_conn=False)
        script = "str := 'xyz' : STORED('str'); str + str;"

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(script)
            result = conn.run_ecl_script(
                p, True, True, stored=None)

        result_stdout = str(result.stdout)

        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)
        expected1 = 'xyzxyz'

        self.assertEqual(res1, expected1)

    def test_run_ecl_script_output_changes_single_stored_value(self):
        conn = hpycc.Connection("user", test_conn=False)

        script = ("str_1 := 'xyz' : STORED('str_1'); str_2 := 'xyz' : "
                  "STORED('str_2'); str_1 + str_2;")

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(script)
            result = conn.run_ecl_script(
                p, True, True, stored={"str_1": "abc"})

        result_stdout = str(result.stdout)

        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)
        expected1 = 'abcxyz'
        self.assertEqual(res1, expected1)

    def test_run_ecl_script_accepts_multiple_repos(self):
        script = "OUTPUT(2);"
        with TemporaryDirectory() as d_1:
            p = os.path.join(d_1, "test.ecl")
            with open(p, "w+") as file:
                file.write(script)
            with TemporaryDirectory() as d_2:
                conn = hpycc.Connection("user", repo=[d_1, d_2])
                res = conn.run_ecl_script(p, True, True, None)
        out = re.search(
            r'<Row><Result_1>(.*?)</Result_1>', res.stdout).group(1)

        self.assertEqual("2", out)


class TestRunURLRequestWithServer(unittest.TestCase):
    def test_run_url_request_returns_response(self):
        conn = hpycc.Connection("user", test_conn=False)
        result = conn.run_url_request("http://localhost:8010", max_attempts=1,
                                      max_sleep=0)
        self.assertIsInstance(result, requests.Response)


class TestConnectionGetLogicalFileChunkWithServer(unittest.TestCase):
    def test_get_logical_file_chunk_returns_correct_dict(self):
        expected_result = {'a': ['1', '2'], 'b': ['a', 'b']}
        conn = hpycc.Connection("user")
        dic = {"a": [1, 2, 3], "b": ["a", "b", "c"]}
        with TemporaryDirectory() as d:
            p = os.path.join(d, "data.csv")
            pd.DataFrame(dic).to_csv(p, index=False)
            lf_name = "test_get_logical_file_chunk_returns_correct_json_1"
            hpycc.spray_file(conn, p, lf_name, chunk_size=3, delete_workunit=False, overwrite=True)

        result = conn.get_logical_file_chunk(
            "thor::{}".format(lf_name), 0, 2, 3, 2)
        _ = result.pop("__fileposition__")

        self.assertEqual(expected_result, result)

    def test_get_logical_file_chunk_is_zero_indexed(self):
        expected_result = {'a': ['1'], 'b': ['a'], '__fileposition__': ['0']}

        conn = hpycc.Connection("user")
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["a", "b", "c"]})
        with TemporaryDirectory() as d:
            p = os.path.join(d, "data.csv")
            df.to_csv(p, index=False)
            hpycc.spray_file(conn, p, "data", chunk_size=3, delete_workunit=False, overwrite=True)

        result = conn.get_logical_file_chunk("thor::data", 0, 1, 3, 0)

        self.assertEqual(result, expected_result)


class TestConnectionRunECLStringWithServer(unittest.TestCase):
    def test_run_ecl_string_returns_result_of_run_ecl_script(self):
        expected_out_stdout = "\r\n".join([
            "Using eclcc path ", "", "Deploying ECL Archive ", "", "Deployed",
            "   wuid: W20180627-154140", "   state: compiled", "",
            "Running deployed workunit W20180627-154140",
            "<Result>", "<Dataset name='Result 1'>",
            " <Row><Result_1>2</Result_1></Row>",
            "</Dataset>", "</Result>\r\n"
        ])
        expected_out_stderr = "\r\n".join([
            "EXEC: Creating PIPE process : ",
            "EXEC: Pipe: Waiting for process to complete 748",
            "EXEC: Pipe: process complete\r\n"
        ])
        conn = hpycc.Connection("user", test_conn=False)
        result = conn.run_ecl_string("OUTPUT(2);", syntax_check=True,
                                     delete_workunit=False,
                                     stored={})
        self.assertEqual(result.__class__.__name__, "Result")
        stdout_output = re.sub("path (.+?)eclcc", 'path ',
                               result.stdout)
        stdout_output1 = re.sub("Archive (.+?)_string.ecl", 'Archive ',
                                stdout_output)
        stdout_output2 = re.sub("W[0-9{8}](\S*)", 'W20180627-154140',
                                stdout_output1)
        self.assertEqual(stdout_output2, expected_out_stdout)
        stderr_output = re.sub(" [0-9][0-9][0-9]", ' 748', result.stderr)
        stderr_output1 = re.sub("process : (.+?).ecl\"", 'process : ',
                                stderr_output)
        self.assertEqual(stderr_output1, expected_out_stderr)

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_run_ecl_string_runs_delete_workunit_if_true(self, mock):
        script = "OUTPUT(2);"
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_ecl_string(script, False, True, {})
        mock.assert_called()

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_get_run_ecl_string_doesnt_run_delete_workunit_if_false(
            self, mock):
        script = "OUTPUT(2);"
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_ecl_string(script, False, False, {})
        self.assertFalse(mock.called)

    def test_run_ecl_string_stored_variables_change_outputs_all_types(self):
        conn = hpycc.Connection("user", test_conn=False)

        string = ("a := 'abc' : STORED('a'); b := FALSE : STORED('b'); "
                  "c := 546 : STORED('c'); a + a; b AND TRUE; c + c;")

        result = conn.run_ecl_string(string, True, True,
                                     stored={'a': 'Hello', 'b': True,
                                             'c': 24601})

        result_stdout = str(result.stdout)

        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)

        res2 = re.search(r'<Row><Result_2>(.*?)</Result_2>',
                         result_stdout).group(1)

        res3 = re.search(r'<Row><Result_3>(.*?)</Result_3>',
                         result_stdout).group(1)

        expected1 = 'HelloHello'
        expected2 = 'true'
        expected3 = '49202'

        self.assertEqual(res1, expected1)
        self.assertEqual(res2, expected2)
        self.assertEqual(res3, expected3)

    def test_run_ecl_string_outputs_stored_wrong_key_inputs(self):
        conn = hpycc.Connection("user", test_conn=False)

        string = ("a := 'abc' : STORED('a'); b := FALSE : STORED('b'); "
                  "c := 12345 : STORED('c'); a; b; c;")

        result = conn.run_ecl_string(string, True, True,
                                     stored={'d': 'Why', 'e': 'Not',
                                             'f': 'Zoidberg'})

        result_stdout = str(result.stdout)

        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)

        res2 = re.search(r'<Row><Result_2>(.*?)</Result_2>',
                         result_stdout).group(1)

        res3 = re.search(r'<Row><Result_3>(.*?)</Result_3>',
                         result_stdout).group(1)
        expected1 = 'abc'
        expected2 = 'false'
        expected3 = '12345'

        self.assertEqual(res1, expected1)
        self.assertEqual(res2, expected2)
        self.assertEqual(res3, expected3)

    def test_run_ecl_string_passes_with_missing_stored(self):
        conn = hpycc.Connection("user", test_conn=False)
        string = "str := 'xyz' : STORED('str'); str + str;"

        result = conn.run_ecl_string(string, True, True, stored=None)
        result_stdout = str(result.stdout)
        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)
        expected1 = 'xyzxyz'
        self.assertEqual(res1, expected1)

    def test_run_ecl_string_output_changes_single_stored_value(self):
        conn = hpycc.Connection("user", test_conn=False)
        string = ("str_1 := 'xyz' : STORED('str_1'); str_2 := 'xyz' : "
                  "STORED('str_2'); str_1 + str_2;")

        result = conn.run_ecl_string(string, True, True,
                                     stored={"str_1": "abc"})
        result_stdout = str(result.stdout)
        res1 = re.search(r'<Row><Result_1>(.*?)</Result_1>',
                         result_stdout).group(1)
        expected1 = 'abcxyz'
        self.assertEqual(res1, expected1)


class TestConnectionEclCmd(unittest.TestCase):
    def test_check_ecl_cmd_passes(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_ecl_cmd(cmd='ecl')
            self.assertTrue(True if not w else False)

    def test_check_ecl_cmd_fails(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_ecl_cmd(cmd='ecl123')
            self.assertTrue(False if not w else True)
