import os
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

import hpycc
from hpycc.utils import docker_tools

# noinspection PyPep8Naming
def setUpModule():
    docker_tools.HPCCContainer()  #tag="6.4.26-1"


# noinspection PyPep8Naming
def tearDownModule():
    docker_tools.HPCCContainer(pull=False, start=False).stop_container()


class TestRunWithServer(unittest.TestCase):

    def test_run_script_saves_logical_file(self):
        conn = hpycc.Connection("user", test_conn=False)
        good_script = "\n".join([
            "a:= DATASET([{'1', 'a'}], "
            "{STRING a; STRING b});",
            "output(a, ,'testrunscriptsaveslogicalfile');"
        ])

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            res = conn.run_ecl_script(p, syntax_check=True,
                                      delete_workunit=False, stored={})
            self.assertTrue(res)
            res = conn.get_logical_file_chunk("thor::testrunscriptsaveslogicalfile", 0, 1, 3, 1)

        expected = {"a": ["1"], "b": ["a"], "__fileposition__": ["0"]}
        self.assertEqual(expected, res)

    def test_run_script_deletes_workunit(self):
        conn = hpycc.Connection("user", test_conn=False)
        check_wu_ecl = "ecl getwuid -u user -pw 1234 -s localhost -n test_run_script_deletes_workunit"
        good_script = "#WORKUNIT('name','test_run_script_deletes_workunit'); OUTPUT(2);"

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            hpycc.run_script(conn, p)
        res = conn._run_command(check_wu_ecl)

        self.assertEqual("", res.stdout)

    def test_run_script_does_not_delete_workunit(self):
        conn = hpycc.Connection("user", test_conn=False)
        check_wu_ecl = "ecl getwuid -u user -pw 1234 -s localhost -n test_run_script_deletes_workunit"
        good_script = ("#WORKUNIT('name','test_run_script_deletes_workunit');"
                       "OUTPUT(2);")

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            hpycc.run_script(conn, p, delete_workunit=False)
        res = conn._run_command(check_wu_ecl)
        self.assertRegex(res.stdout, "W[0-9]{8}-[0-9]{6}")

    def test_run_script_returns_true(self):
        conn = hpycc.Connection("user", test_conn=False)
        good_script = "OUTPUT(2);"
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            res = hpycc.run_script(conn, p, delete_workunit=False)
        self.assertTrue(res)

    def test_run_script_uses_stored(self):
        conn = hpycc.Connection("user", test_conn=False)
        file_name = "test_run_script_uses_stored"
        good_script = "str := 'abc' : STORED('str'); " \
                      "z := DATASET([{{str + str}}], {{STRING str;}}); " \
                      "OUTPUT(z,,'~{}', EXPIRE(1));".format(file_name)
        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            hpycc.run_script(conn, p,
                             stored={'str': 'Shouldbethecorrectoutput'})
        res = hpycc.get_thor_file(conn, file_name)
        expected = pd.DataFrame({
            "str": ["ShouldbethecorrectoutputShouldbethecorrectoutput"],
            "__fileposition__": [0]})
        pd.testing.assert_frame_equal(expected.sort_index(axis=1), res.sort_index(axis=1), check_dtype=False)

    def test_run_script_does_nothing_when_not_using_stored(self):
        conn = hpycc.Connection("user", test_conn=False)
        file_name = "test_run_script_does_nothing_when_not_using_stored_"
        good_script = "str := 'abc' : STORED('str');" \
                      " z := DATASET([{{str + str}}]," \
                      " {{STRING str;}}); OUTPUT(z,,'~{}', " \
                      "EXPIRE(1));".format(file_name)

        with TemporaryDirectory() as d:
            p = os.path.join(d, "test.ecl")
            with open(p, "w+") as file:
                file.write(good_script)
            hpycc.run_script(conn, p, stored={'b': 'Shouldbethecorrectoutput'})
        res = hpycc.get_thor_file(conn, file_name)
        expected = pd.DataFrame({"str": ["abcabc"], "__fileposition__": [0]})
        pd.testing.assert_frame_equal(expected.sort_index(axis=1), res.sort_index(axis=1), check_dtype=False)
