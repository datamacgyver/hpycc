from collections import namedtuple
import os
import random
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from json import JSONDecodeError
from simplejson.errors import JSONDecodeError as simpleJSONDecodeError

import requests
from requests import HTTPError

import hpycc
import hpycc.connection
from hpycc.utils import docker_tools


class TestConnectionDefaultAttributes(unittest.TestCase):
    def setUp(self):
        self.conn = hpycc.connection.Connection("username", test_conn=False)

    def test_server(self):
        self.assertEqual(self.conn.server, "localhost")

    def test_port(self):
        self.assertEqual(self.conn.port, 8010)

    def test_repo(self):
        self.assertEqual(self.conn.repo, None)

    def test_password(self):
        self.assertEqual(self.conn.password, "password")

    def test_legacy(self):
        self.assertEqual(self.conn.legacy, False)

    def test_username_raises_error_if_blank(self):
        with self.assertRaises(AttributeError):
            hpycc.Connection("", test_conn=False)

    def test_username_raises_error_if_not_string(self):
        with self.assertRaises(AttributeError):
            # noinspection PyTypeChecker
            hpycc.Connection(123, test_conn=False)

    def test_password_raises_error_if_blank(self):
        with self.assertRaises(AttributeError):
            hpycc.Connection("a", password="", test_conn=False)

    # noinspection PyTypeChecker
    def test_password_raises_error_if_not_string(self):
        with self.assertRaises(AttributeError):
            hpycc.Connection("a", password=123, test_conn=False)

    def test_password_raises_error_if_spaces(self):
        with self.assertRaises(AttributeError):
            hpycc.Connection("a", password="  ", test_conn=False)


class TestConnectionTestConn(unittest.TestCase):
    @patch.object(hpycc.Connection, "test_connection")
    def test_test_conn_default(self, mock):
        hpycc.Connection("user")
        mock.assert_called()

    @patch.object(hpycc.Connection, "test_connection")
    def test_test_conn_false(self, mock):
        hpycc.Connection("user", test_conn=False)
        self.assertFalse(mock.called)


class TestConnectionCustomAttributes(unittest.TestCase):
    def setUp(self):
        self.conn = hpycc.connection.Connection(
            "some_user", "some_server", 9000, "some_repo", "p", True,
            test_conn=False)

    def test_username(self):
        self.assertEqual(self.conn.username, "some_user")

    def test_server(self):
        self.assertEqual(self.conn.server, "some_server")

    def test_port(self):
        self.assertEqual(self.conn.port, 9000)

    def test_repo(self):
        self.assertEqual(self.conn.repo, "some_repo")

    def test_password(self):
        self.assertEqual(self.conn.password, "p")

    def test_legacy(self):
        self.assertEqual(self.conn.legacy, True)


class TestConnectionInitTestConnection(unittest.TestCase):
    @patch.object(hpycc.connection.Connection, "test_connection")
    def test_calls_test_connection_on_init(self, mock):
        hpycc.connection.Connection("usrname")
        mock.assert_called()


class TestConnectionRunCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = hpycc.connection.Connection("user", test_conn=False)
        cls.Result = namedtuple("Result", ["stdout", "stderr"])


class TestConnectionCheckSyntax(unittest.TestCase):
    @patch.object(hpycc.Connection, "_run_command")
    def test_check_syntax_builds_correct_path_with_no_legacy_or_repo(self, mock):
        conn = hpycc.Connection("user", legacy=False, repo=None, test_conn=False)
        conn.check_syntax("non.ecl")
        mock.assert_called_with(["eclcc", "-syntax", "non.ecl"])

    @patch.object(hpycc.Connection, "_run_command")
    def test_check_syntax_builds_correct_path_with_legacy(self, mock):
        conn = hpycc.Connection("user", legacy=True, repo=None, test_conn=False)
        conn.check_syntax("non.ecl")
        mock.assert_called_with(["eclcc", "-syntax", "-legacy", "non.ecl"])

    @patch.object(hpycc.Connection, "_run_command")
    def test_check_syntax_builds_correct_path_with_legacy_and_repo(self, mock):
        conn = hpycc.Connection("user", legacy=True, repo="./dir", test_conn=False)
        conn.check_syntax("non.ecl")
        mock.assert_called_with(["eclcc", "-syntax", "-legacy", "-I=./dir",
                                 "non.ecl"])

    @patch.object(hpycc.Connection, "_run_command")
    def test_check_syntax_builds_correct_path_with_repo(self, mock):
        conn = hpycc.Connection("user", legacy=False, repo="./dir", test_conn=False)
        conn.check_syntax("non.ecl")
        mock.assert_called_with(["eclcc", "-syntax", "-I=./dir", "non.ecl"])

    @patch.object(hpycc.Connection, "_run_command")
    def test_check_syntax_calls_run_command(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        conn.check_syntax("non.ecl")
        mock.assert_called()

    def test_check_syntax_passes_with_good_script(self):
        conn = hpycc.Connection("user", test_conn=False)
        with TemporaryDirectory() as d:
            p = os.path.join(d, "tmp.ecl")
            with open(p, "w+") as file:
                file.write("output(2);")
            self.assertIsNone(conn.check_syntax(p))

    @patch.object(hpycc.Connection, "_run_command")
    def test_check_syntax_uses_repo_if_list(self, mock):
        conn = hpycc.Connection("user", test_conn=False, repo=["C:", "D:"])
        conn.check_syntax("test.ecl")
        mock.assert_called_with(['eclcc', '-syntax', "-I=C:", "-I=D:", 'test.ecl'])

    def test_check_syntax_passes_with_warnings(self):
        conn = hpycc.Connection("user", test_conn=False)
        warning_string = "\n".join([
            "a := DATASET([{1,2}], {INTEGER a; INTEGER b});",
            "a;",
            "b := DATASET([{1,2}], {INTEGER a; INTEGER b});",
            "b;",
            "groupREC := RECORD",
            "STRING a := a.a;",
            "STRING b := a.b;",
            "INTEGER n := count(group);",
            "END;",
            "TABLE(a, groupREC, a)"
        ])
        with TemporaryDirectory() as d:
            p = os.path.join(d, "tmp.ecl")
            with open(p, "w+") as file:
                file.write(warning_string)
            self.assertIsNone(conn.check_syntax(p))

    def test_check_syntax_fails_with_errors(self):
        conn = hpycc.Connection("user", test_conn=False)
        with TemporaryDirectory() as d:
            p = os.path.join(d, "tmp.ecl")
            with open(p, "w+") as file:
                file.write("sdfdsf")
            with self.assertRaises(SyntaxError):
                conn.check_syntax(p)

    def test_check_syntax_returns_syntax_errors(self):
        conn = hpycc.Connection("user", test_conn=False)
        expected_err = "error C3002"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "tmp.ecl")
            with open(p, "w+") as file:
                file.write("sdfdsf")
            with self.assertRaisesRegex(SyntaxError, expected_err):
                conn.check_syntax(p)


class TestConnectionRunECLScript(unittest.TestCase):
    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_uses_server_port_and_username(self, mock):
        conn = hpycc.Connection("user", test_conn=False, server="abc",
                                port=123)
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_called_with(['ecl', 'run', '-v', '--server=abc',
                                 '--port=123', '--username=user',
                                 '--password=password',
                                 'thor', 'test.ecl'])

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_uses_password(self, mock):
        conn = hpycc.Connection("user", password="abc", test_conn=False)
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})

        mock.assert_called_with(['ecl', 'run', '-v', '--server=localhost',
                                 '--port=8010', '--username=user',
                                 '--password=abc',
                                 'thor', 'test.ecl'])

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_works_with_special_password_chars(
            self, mock):
        conn = hpycc.Connection("user", password="a\nb", test_conn=False)
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_called_with(['ecl', 'run', '-v', '--server=localhost',
                                 '--port=8010', '--username=user',
                                 '--password=a\nb',
                                 'thor', 'test.ecl'])

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_uses_legacy(self, mock):
        conn = hpycc.Connection("user", legacy=True, test_conn=False)
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_called_with(['ecl', 'run', '-v', '--server=localhost',
                                 '--port=8010', '--username=user',
                                 '--password=password', '-legacy',
                                 'thor', 'test.ecl'])

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_uses_legacy_if_none(self, mock):
        conn = hpycc.Connection("user", legacy=None, test_conn=False)
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_called_with(['ecl', 'run', '-v', '--server=localhost',
                                 '--port=8010', '--username=user',
                                 '--password=password',
                                 'thor', 'test.ecl'])

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_uses_repo(self, mock):
        conn = hpycc.Connection("user", test_conn=False, repo="C:")
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_called_with(['ecl', 'run', '-v', '--server=localhost',
                                 '--port=8010', '--username=user',
                                 '--password=password',
                                 'thor', 'test.ecl', '-I=C:'])

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_uses_repo_if_none(self, mock):
        conn = hpycc.Connection("user", test_conn=False, repo=None)
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_called_with(['ecl', 'run', '-v', '--server=localhost',
                                 '--port=8010', '--username=user',
                                 '--password=password',
                                 'thor', 'test.ecl'])

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_script_command_uses_repo_if_list(self, mock):
        conn = hpycc.Connection("user", test_conn=False, repo=["C:", "D:"])
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_called_with(['ecl', 'run', '-v', '--server=localhost',
                                 '--port=8010', '--username=user',
                                 '--password=password',
                                 'thor', 'test.ecl', "-I=C:", "-I=D:"])

    @patch.object(hpycc.Connection, "_run_command")
    @patch.object(hpycc.Connection, "check_syntax")
    def test_run_script_checks_syntax_if_true(self, mock, _):
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_ecl_script("test.ecl", syntax_check=True,
                            delete_workunit=False, stored={})
        mock.assert_called()

    @patch.object(hpycc.Connection, "_run_command")
    @patch.object(hpycc.Connection, "check_syntax")
    def test_run_script_does_not_check_syntax_if_false(self, mock, _):
        conn = hpycc.Connection("user", test_conn=False,)
        conn.run_ecl_script("test.ecl", syntax_check=False,
                            delete_workunit=False, stored={})
        self.assertFalse(mock.called)

    def test_run_script_fails_syntax_check_with_bad_script(self):
        conn = hpycc.Connection("user", test_conn=False, repo=None)
        bad_script = "sdf"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(bad_script)
            with self.assertRaises(SyntaxError):
                conn.run_ecl_script(p, syntax_check=True,
                                    delete_workunit=False, stored={})

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_script_passes_syntax_check_with_good_script(self, mock):
        conn = hpycc.Connection("user", test_conn=False, repo=None)
        good_script = "output(2);"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            conn.run_ecl_script(p, syntax_check=True, delete_workunit=False, stored={})
        mock.assert_called()

    @patch.object(hpycc.Connection, "_run_command")
    def test_run_script_calls_run_command(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        good_script = "output(2);"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            conn.run_ecl_script(p, syntax_check=False, delete_workunit=False,
                                stored={})
        mock.assert_called()

    def test_run_script_fails_if_server_unavailable(self):
        conn = hpycc.Connection("user", test_conn=False, repo=None)
        good_script = "output(2);"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            with self.assertRaises(subprocess.SubprocessError):
                conn.run_ecl_script(p, syntax_check=False,
                                    delete_workunit=False, stored={})


class TestConnectionGetLogicalFileChunk(unittest.TestCase):
    @patch.object(hpycc.Connection, "run_url_request")
    def test_get_logical_file_chunk_uses_correct_url(self, mock):
        mock.json.return_value = {"WUResultResponse": 123}
        conn = hpycc.Connection("user", server="aa", port=123, test_conn=False)
        with TemporaryDirectory() as td:
            p = os.path.join(td, "data.csv")
            conn.get_logical_file_chunk("file", 1, 2, 1, 0)
            mock.assert_called()

    @patch.object(hpycc.Connection, "run_url_request")
    def test_get_logical_file_chunk_fails_with_no_json(self, mock):
        mock.return_value = requests.Response()
        conn = hpycc.Connection("user", server="aa", port=123, test_conn=False)
        with TemporaryDirectory() as td:
            p = os.path.join(td, "data.csv")
            with self.assertRaises(simpleJSONDecodeError):
                conn.get_logical_file_chunk("file", 1, 2, 1, 0)


class TestConnectionRunURLRequest(unittest.TestCase):
    @patch.object(requests, "get")
    def test_run_url_request_uses_all_attempts(self, mock):
        final_response = requests.Response()
        final_response.status_code = 200
        side_effects = (ValueError, ValueError, ValueError, ValueError, final_response)
        mock.side_effect = side_effects
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_url_request("dfsd.dfd", max_attempts=5, max_sleep=3)
        self.assertEqual(mock.call_count, 5)

    @patch.object(requests, "get")
    def test_run_url_request_counts_404_as_error(self, mock):
        bad_response = requests.Response()
        bad_response.status_code = 404
        mock.return_value = bad_response
        conn = hpycc.Connection("user", test_conn=False)
        with self.assertRaises(requests.exceptions.RetryError):
            conn.run_url_request("dfsd.dfd", max_attempts=2, max_sleep=0)

    @patch.object(requests, "get")
    def test_run_url_request_counts_500_as_error(self, mock):
        bad_response = requests.Response()
        bad_response.status_code = 500
        mock.return_value = bad_response
        conn = hpycc.Connection("user", test_conn=False)
        with self.assertRaises(requests.exceptions.RetryError):
            conn.run_url_request("dfsd.dfd", max_attempts=2, max_sleep=0)

    @patch.object(requests, "get")
    def test_run_url_request_uses_auth(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_url_request("dfsd.dfd", max_attempts=5, max_sleep=0)
        mock.assert_called_with('dfsd.dfd', auth=('user', "password"))

    @patch.object(random, "randint")
    def test_run_url_request_uses_custom_max_sleep(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        with self.assertRaises(requests.exceptions.RetryError):
            conn.run_url_request("dfsd.dfd", max_attempts=1, max_sleep=0)
        mock.assert_called_with(0, 0)

    @patch.object(requests, "get")
    def test_run_url_request_uses_max_attempts_default_3(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        mock.side_effect = ValueError
        with self.assertRaises(requests.exceptions.RetryError):
            conn.run_url_request("dfsd.dfd", max_attempts=3, max_sleep=0)
        self.assertEqual(mock.call_count, 3)

    @patch.object(requests, "get")
    def test_run_url_request_uses_max_attempts_custom(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        mock.side_effect = ValueError
        with self.assertRaises(requests.exceptions.RetryError):
            conn.run_url_request("dfsd.dfd", max_attempts=4, max_sleep=0)
        self.assertEqual(mock.call_count, 4)

    @patch.object(requests, "get")
    def test_run_url_request_raises_retry_error_when_exceeded(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        mock.side_effect = ValueError
        with self.assertRaises(requests.exceptions.RetryError):
            conn.run_url_request("dfsd.dfd", max_attempts=1, max_sleep=0)

    @patch.object(requests, "get")
    def test_run_url_request_returns_response_after_single_error(self, mock):
        r = requests.Response()
        r.status_code = 200
        mock.side_effect = (ValueError, r)
        conn = hpycc.Connection("user", test_conn=False)
        result = conn.run_url_request("dfsd.dfd", max_attempts=3, max_sleep=0)
        self.assertIsInstance(result, requests.Response)


class TestConnectionTestConnectionWithAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docker_tools.HPCCContainer(users=("madeup", "complicated_password"))  #tag="6.4.26-1",
        cls.error_string = ("401 Client Error: Unauthorized for url: "
                            "http://localhost:8010/")

    @classmethod
    def tearDownClass(cls):
        docker_tools.HPCCContainer(pull=False, start=False).stop_container()

    def test_test_connection_passes_with_correct_auth(self):
        conn = hpycc.connection.Connection(username="madeup", password="complicated_password")
        result = conn.test_connection()
        self.assertTrue(result)

    def test_test_connection_fails_auth_with_incorrect_username(self):
        with self.assertRaisesRegex(HTTPError, self.error_string):
            conn = hpycc.connection.Connection(username="abc", password="1234")
            conn.test_connection()

    def test_test_connection_fails_auth_with_incorrect_password(self):
        with self.assertRaisesRegex(HTTPError, self.error_string):
            conn = hpycc.connection.Connection(username="test1", password="12")
            conn.test_connection()


class TestConnectionRunECLString(unittest.TestCase):
    @patch.object(hpycc.Connection, "run_ecl_script")
    def test_run_ecl_string_calls_run_ecl_script(self, mock):
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_ecl_string("aa", syntax_check=False, delete_workunit=False,
                            stored={})
        mock.assert_called()

    @patch.object(hpycc.Connection, "check_syntax")
    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_string_checks_syntax_if_flag_is_true(self, _, mock):
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_ecl_string("OUTPUT(2);", syntax_check=True,
                            delete_workunit=False, stored={})
        mock.assert_called()

    @patch.object(hpycc.Connection, "check_syntax")
    @patch.object(hpycc.Connection, "_run_command")
    def test_run_ecl_string_checks_syntax_if_flag_is_true(self, _, mock):
        conn = hpycc.Connection("user", test_conn=False)
        conn.run_ecl_string("OUTPUT(2);", syntax_check=False,
                            delete_workunit=False, stored={})
        mock.assert_not_called()

    def test_run_ecl_string_raises_if_syntax_check_fails(self):
        conn = hpycc.Connection("user", test_conn=False)
        with self.assertRaises(subprocess.SubprocessError):
            conn.run_ecl_string("OUTPUT(2);", syntax_check=True,
                                delete_workunit=False, stored={})
