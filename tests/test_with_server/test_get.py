from concurrent.futures import ThreadPoolExecutor
import os
import unittest
import warnings
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pandas as pd

import hpycc
from hpycc.get import get_thor_file
from hpycc.utils import docker_tools


# noinspection PyPep8Naming
def setUpModule():
    docker_tools.HPCCContainer()  #tag="6.4.26-1"


# noinspection PyPep8Naming
def tearDownModule():
    docker_tools.HPCCContainer(pull=False, start=False).stop_container()


def _spray_df(conn, df, name):
    with TemporaryDirectory() as d:
        p = os.path.join(d, "test.csv")
        df.to_csv(p, index=False)
        hpycc.spray_file(conn, p, name)


def _get_output_from_ecl_string(
        conn, string, syntax=True, delete_workunit=True, stored=None):
    with TemporaryDirectory() as d:
        p = os.path.join(d, "test.ecl")
        with open(p, "w+") as file:
            file.write(string)
        res = hpycc.get_output(conn, p, syntax, delete_workunit, stored)
        return res


def _get_outputs_from_ecl_string(
        conn, string, syntax=True, delete_workunit=True, stored=None):
    with TemporaryDirectory() as d:
        p = os.path.join(d, "test.ecl")
        with open(p, "w+") as file:
            file.write(string)
        res = hpycc.get_outputs(conn, p, syntax, delete_workunit, stored)
        return res


class TestGetOutputWithServer(unittest.TestCase):
    def setUp(self):
        self.conn = hpycc.Connection("user")

    def test_get_output_returns_single_value_int(self):
        script = "OUTPUT(2);"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"Result_1": 2}, index=[0])
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_returns_single_value_str(self):
        script = "OUTPUT('a');"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"Result_1": 'a'}, index=[0])
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_returns_dataset(self):
        script = "OUTPUT(DATASET([{1, 'a'}], {INTEGER a; STRING b;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": 1, "b": "a"},
                                index=[0])
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_only_returns_first_output(self):
        script = "OUTPUT('a'); OUTPUT(1);"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"Result_1": 'a'}, index=[0])
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_bools_all_true(self):
        script = "OUTPUT(DATASET([{true}, {true}], {BOOLEAN a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [True, True]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_bools_all_false(self):
        script = "OUTPUT(DATASET([{false}, {false}], {BOOLEAN a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [False, False]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_bools_true_and_false(self):
        script = "OUTPUT(DATASET([{true}, {false}], {BOOLEAN a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [True, False]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_bools_true_and_false_strings(self):
        script = "OUTPUT(DATASET([{'true'}, {'false'}], {STRING a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [True, False]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_bools_true_and_false_strings_with_blank(self):
        script = "OUTPUT(DATASET([{'true'}, {'false'}, {''}], {STRING a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [True, False, np.nan]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_blank_string_as_nan(self):
        script = "OUTPUT(DATASET([{''}], {STRING a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [np.nan]}, index=[0])
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_ints(self):
        script = "OUTPUT(DATASET([{1}, {2}], {INTEGER a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1, 2]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_floats(self):
        script = "OUTPUT(DATASET([{1.0}, {2.1}], {REAL a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1.0, 2.1]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_mixed_floats_and_ints(self):
        script = "OUTPUT(DATASET([{1}, {2.1}], {REAL a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1, 2.1]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_numbers_as_strings(self):
        script = "OUTPUT(DATASET([{'1'}, {'2.1'}], {STRING a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1, 2.1]})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_empty_dataset(self):
        script = "a := DATASET([{'a'}, {'a'}], {STRING a;});a(a != 'a');"
        with warnings.catch_warnings(record=True) as w:
            res = _get_output_from_ecl_string(self.conn, script)
            self.assertEqual(len(w), 1)
            expected_warn = ("The output does not appear to contain a "
                             "dataset. Returning an empty DataFrame.")
            self.assertEqual(str(w[-1].message), expected_warn)
        expected = pd.DataFrame()
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_parses_mixed_columns_as_strings(self):
        script = "OUTPUT(DATASET([{'1'}, {'a'}], {STRING a;}));"
        res = _get_output_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": ['1', 'a']})
        pd.testing.assert_frame_equal(expected, res)

    def test_get_output_raises_with_bad_script(self):
        script = "asa"
        with self.assertRaises(SyntaxError):
            _get_output_from_ecl_string(self.conn, script)

    @patch.object(hpycc.Connection, "check_syntax")
    def test_get_output_runs_syntax_check_if_true(self, mock):
        script = "OUTPUT(2);"
        _get_output_from_ecl_string(self.conn, script)
        mock.assert_called()

    @patch.object(hpycc.Connection, "check_syntax")
    def test_get_output_doesnt_run_syntax_check_if_false(self, mock):
        script = "OUTPUT(2);"
        _get_output_from_ecl_string(self.conn, script, syntax=False)
        self.assertFalse(mock.called)

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_get_output_runs_delete_workunit_if_true(self, mock):
        script = "OUTPUT(2);"
        _get_output_from_ecl_string(self.conn, script, delete_workunit=True)
        mock.assert_called()

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_get_output_doesnt_run_delete_workunit_if_false(self, mock):
        script = "OUTPUT(2);"
        _get_output_from_ecl_string(self.conn, script, delete_workunit=False)
        self.assertFalse(mock.called)

    def test_get_output_passes_with_missing_stored(self):
        script_one = "str := 'xyz' : STORED('str'); str + str;"
        result = _get_output_from_ecl_string(self.conn, script_one)
        expected = pd.DataFrame({"Result_1": ["xyzxyz"]})
        pd.testing.assert_frame_equal(expected, result)

    def test_output_changes_single_stored_value(self):
        script_one = ("str_1 := 'xyz' : STORED('str_1'); str_2 := 'xyz' : "
                      "STORED('str_2'); str_1 + str_2;")
        result = _get_output_from_ecl_string(self.conn, script_one,
                                             stored={"str_1": "abc"})
        expected = pd.DataFrame({"Result_1": ["abcxyz"]})
        pd.testing.assert_frame_equal(expected, result)

    def test_get_output_stored_variables_change_output_same_type_string(self):
        script_one = "str := 'xyz' : STORED('str'); str + str;"
        result = _get_output_from_ecl_string(self.conn, script_one,
                                             stored={'str': 'Hello'})
        expected = pd.DataFrame({"Result_1": ["HelloHello"]})
        pd.testing.assert_frame_equal(expected, result)

    def test_get_output_stored_variables_change_output_same_type_int(self):
        script_one = "a :=  123 : STORED('a'); a * 2;"
        result = _get_output_from_ecl_string(self.conn, script_one,
                                             stored={'a': 24601})
        expected = pd.DataFrame({"Result_1": [49202]})
        pd.testing.assert_frame_equal(expected, result)

    def test_get_output_stored_variables_change_output_same_type_bool(self):
        script_one = "a := FALSE : STORED('a'); a AND TRUE;"
        result = _get_output_from_ecl_string(self.conn, script_one,
                                             stored={'a': True})
        expected = pd.DataFrame({"Result_1": [True]})
        pd.testing.assert_frame_equal(expected, result)

    def test_get_output_stored_wrong_key_inputs(self):
        script_one = "a := 'abc' : STORED('a'); a;"
        result = _get_output_from_ecl_string(self.conn, script_one,
                                             stored={'f': 'WhyNotZoidberg'})
        expected = pd.DataFrame({"Result_1": ['abc']})
        pd.testing.assert_frame_equal(expected, result)


class TestGetOutputsWithServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = hpycc.Connection("user")
        script = ("OUTPUT(2);OUTPUT('a');OUTPUT(DATASET([{1, 'a'}], "
                  "{INTEGER a; STRING b;}), NAMED('ds'));")
        cls.res = _get_outputs_from_ecl_string(cls.conn, script)
        a = [
            {"col": "alltrue", "content": "[{true}, {true}, {true}]",
             "coltype": "BOOLEAN"},
            {"col": "allfalse", "content": "[{false}, {false}, {false}]",
             "coltype": "BOOLEAN"},
            {"col": "trueandfalse", "content": "[{true}, {false}, {true}]",
             "coltype": "BOOLEAN"},
            {"col": "truefalsestrings",
             "content": "[{'true'}, {'false'}, {'false'}]",
             "coltype": "STRING"},
           {"col": "truefalseblank", "content": "[{'true'}, {'false'}, {''}]",
             "coltype": "STRING"}
        ]
        f = [("OUTPUT(DATASET({0[content]}, {{{0[coltype]} {0[col]};}}), "
             "NAMED('{0[col]}'));").format(i) for i in a]
        cls.t_f_res = _get_outputs_from_ecl_string(cls.conn, "\n".join(f))

    def test_get_outputs_returns_single_value_int(self):
        expected = pd.DataFrame({"Result_1": 2}, index=[0])
        pd.testing.assert_frame_equal(expected, self.res["Result_1"])

    def test_get_outputs_returns_single_value_str(self):
        expected = pd.DataFrame({"Result_2": 'a'}, index=[0])
        pd.testing.assert_frame_equal(expected, self.res["Result_2"])

    def test_get_outputs_returns_dataset(self):
        expected = pd.DataFrame({"a": 1, "b": "a"},
                                index=[0])
        pd.testing.assert_frame_equal(expected, self.res["ds"])

    def test_get_outputs_returns_all_outputs(self):
        self.assertEqual(list(self.res.keys()),
                        ["Result_1", "Result_2", "ds"])

    def test_get_outputs_parses_bools_all_true(self):
        expected = pd.DataFrame({"alltrue": [True, True, True]})
        pd.testing.assert_frame_equal(expected, self.t_f_res["alltrue"])

    def test_get_outputs_parses_bools_all_false(self):
        expected = pd.DataFrame({"allfalse": [False, False, False]})
        pd.testing.assert_frame_equal(expected, self.t_f_res["allfalse"])

    def test_get_outputs_parses_bools_true_and_false(self):
        expected = pd.DataFrame({"trueandfalse": [True, False, True]})
        pd.testing.assert_frame_equal(expected, self.t_f_res["trueandfalse"])

    def test_get_outputs_parses_bools_true_and_false_strings(self):
        expected = pd.DataFrame({"truefalsestrings": [True, False, False]})
        pd.testing.assert_frame_equal(
            expected, self.t_f_res["truefalsestrings"])

    def test_get_outputs_parses_bools_true_and_false_strings_with_blank(self):
        expected = pd.DataFrame({"truefalseblank": [True, False, np.nan]})
        pd.testing.assert_frame_equal(expected,
                                      self.t_f_res["truefalseblank"])

    def test_get_outputs_parses_blank_string_as_nan(self):
        script = "OUTPUT(DATASET([{''}], {STRING a;}));"
        res = _get_outputs_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [np.nan]}, index=[0])
        pd.testing.assert_frame_equal(expected, res["Result_1"])

    def test_get_outputs_parses_ints(self):
        script = "OUTPUT(DATASET([{1}, {2}], {INTEGER a;}));"
        res = _get_outputs_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1, 2]})
        pd.testing.assert_frame_equal(expected, res["Result_1"])

    def test_get_outputs_parses_floats(self):
        script = "OUTPUT(DATASET([{1.0}, {2.1}], {REAL a;}));"
        res = _get_outputs_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1.0, 2.1]})
        pd.testing.assert_frame_equal(expected, res["Result_1"])

    def test_get_outputs_parses_mixed_floats_and_ints(self):
        script = "OUTPUT(DATASET([{1}, {2.1}], {REAL a;}));"
        res = _get_outputs_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1, 2.1]})
        pd.testing.assert_frame_equal(expected, res["Result_1"])

    def test_get_outputs_parses_numbers_as_strings(self):
        script = "OUTPUT(DATASET([{'1'}, {'2.1'}], {STRING a;}));"
        res = _get_outputs_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": [1, 2.1]})
        pd.testing.assert_frame_equal(expected, res["Result_1"])

    def test_get_outputs_parses_empty_dataset(self):
        script = ("a := DATASET([{'a'}, {'a'}], {STRING a;});a(a != 'a');"
                  "OUTPUT(2);")

        with warnings.catch_warnings(record=True) as w:
            res = _get_outputs_from_ecl_string(self.conn, script)
            self.assertEqual(len(w), 1)
            expected_warn = (
                "One or more of the outputs do not appear to contain a "
                "dataset. They have been replaced with an empty DataFrame")
            self.assertEqual(str(w[-1].message), expected_warn)
        self.assertEqual(list(res.keys()), ["Result_1", "Result_2"])
        pd.testing.assert_frame_equal(res["Result_1"], pd.DataFrame())

    def test_get_outputs_parses_mixed_columns_as_strings(self):
        script = "OUTPUT(DATASET([{'1'}, {'a'}], {STRING a;}));"
        res = _get_outputs_from_ecl_string(self.conn, script)
        expected = pd.DataFrame({"a": ['1', 'a']})
        pd.testing.assert_frame_equal(expected, res["Result_1"])

    def test_get_outputs_raises_with_bad_script(self):
        script = "asa"
        with self.assertRaises(SyntaxError):
            _get_outputs_from_ecl_string(self.conn, script)

    @patch.object(hpycc.Connection, "check_syntax")
    def test_get_outputs_runs_syntax_check_if_true(self, mock):
        script = "OUTPUT(2);"
        _get_outputs_from_ecl_string(self.conn, script)
        mock.assert_called()

    @patch.object(hpycc.Connection, "check_syntax")
    def test_get_outputs_doesnt_run_syntax_check_if_false(self, mock):
        script = "OUTPUT(2);"
        _get_outputs_from_ecl_string(self.conn, script, False)
        self.assertFalse(mock.called)

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_get_outputs_runs_delete_workunit_if_true(self, mock):
        script = "OUTPUT(2);"
        _get_outputs_from_ecl_string(self.conn, script)
        mock.assert_called()

    @patch.object(hpycc.connection.delete, "delete_workunit")
    def test_get_outputs_doesnt_run_delete_workunit_if_false(self, mock):
        script = "OUTPUT(2);"
        _get_outputs_from_ecl_string(self.conn, script, delete_workunit=False)
        self.assertFalse(mock.called)

    def test_get_outputs_stored_variables_change_output_same_type(self):
        script_one = ("a := 'abc' : STORED('a'); b := FALSE : STORED('b'); "
                      "c := 546 : STORED('c'); a + a; b AND TRUE; c + c;")
        result = _get_outputs_from_ecl_string(
            self.conn, script_one,
            stored={'a': 'Hello', 'b': True, 'c': 24601})
        expected = {
            "Result_1": pd.DataFrame({"Result_1": ["HelloHello"]}),
            "Result_2": pd.DataFrame({"Result_2": [True]}),
            "Result_3": pd.DataFrame({"Result_3": [49202]})
                    }
        for df in expected:
            pd.testing.assert_frame_equal(result[df], expected[df])

    def test_get_outputs_stored_wrong_key_inputs(self):
        script_one = ("a := 'abc' : STORED('a'); b := FALSE : STORED('b'); "
                      "c := 'ghi' : STORED('c'); a; b; c;")
        result = _get_outputs_from_ecl_string(self.conn, script_one,
                                              stored={'d': 'Why', 'e': 'Not',
                                                      'f': 'Zoidberg'})
        expected = {
            "Result_1": pd.DataFrame({"Result_1": ["abc"]}),
            "Result_2": pd.DataFrame({"Result_2": [False]}),
            "Result_3": pd.DataFrame({"Result_3": ["ghi"]})
                    }
        for df in expected:
            pd.testing.assert_frame_equal(result[df], expected[df])


class TestGetThorFile(unittest.TestCase):
    def setUp(self):
        self.conn = hpycc.Connection("user", test_conn=False)

    def test_get_thor_file_returns_empty_dataset(self):
        file_name = '~test_get_thor_file_returns_empty_dataset'
        self.conn.run_ecl_string(
            "a := DATASET([], {INTEGER int;}); "
            "OUTPUT(a, ,'%s');" % file_name,
            True,
            True,
            None
        )
        res = get_thor_file(connection=self.conn, thor_file=file_name)
        expected = pd.DataFrame(columns=["int", "__fileposition__"])

        pd.testing.assert_frame_equal(expected, res)

    def test_get_thor_file_returns_single_row_dataset(self):
        file_name = "test_get_thor_file_returns_single_row_dataset"
        self.conn.run_ecl_string(
            "a := DATASET([{1}], {INTEGER int;}); "
            "OUTPUT(a,,'~%s');" % file_name,
            True,
            True,
            None
        )
        res = get_thor_file(
            connection=self.conn,
            thor_file="test_get_thor_file_returns_single_row_dataset")
        expected = pd.DataFrame({"int": [1], "__fileposition__": 0},
                                dtype=np.int32)
        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1))

    def test_get_thor_file_returns_100_row_dataset(self):
        file_name = '~test_get_thor_file_returns_100_row_dataset'
        lots_of_1s = "[" + ",".join(["{1}"]*100) + "]"
        self.conn.run_ecl_string(
            "a := DATASET({}, {{INTEGER int;}}); "
            "OUTPUT(a,,'{}');".format(lots_of_1s, file_name),
            True,
            True,
            None
        )
        res = get_thor_file(connection=self.conn, thor_file=file_name)
        expected = pd.DataFrame({
            "__fileposition__": [i*8 for i in range(100)],
            "int": [1] * 100
        }, dtype=np.int32)
        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1))

    def test_get_thor_file_returns_1000000_row_dataset(self):
        file_name = '~test_get_thor_file_returns_1000000_row_dataset'
        lots_of_1s = "[" + ",".join(["{1}"]*1000000) + "]"
        self.conn.run_ecl_string(
            "a := DATASET({}, {{INTEGER int;}}); "
            "OUTPUT(a,,'{}');".format(lots_of_1s, file_name),
            True,
            True,
            None
        )
        res = get_thor_file(connection=self.conn, thor_file=file_name)
        expected = pd.DataFrame({
            "int": [1] * 1000000
        }, dtype=np.int32)
        pd.testing.assert_series_equal(expected.sort_index(axis=1)["int"],
                                       res.sort_index(axis=1)["int"])

    def test_get_thor_file_works_when_num_rows_less_than_chunksize(self):
        file_name = ("test_get_thor_file_works_when_num_rows_less_than_"
                     "chunksize")
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        res = get_thor_file(
            connection=self.conn, thor_file=file_name, chunk_size=2)
        expected = pd.DataFrame({"int": [1], "__fileposition__": 0},
                                dtype=np.int32)
        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1))

    def test_get_thor_file_works_when_num_rows_equal_to_chunksize(self):
        file_name = "test_get_thor_file_works_when_num_rows_equal_to_chunksize"
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        res = get_thor_file(
            connection=self.conn, thor_file=file_name, chunk_size=2)
        expected = pd.DataFrame({"int": [1, 2], "__fileposition__": [0, 8]},
                                dtype=np.int32)
        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1))

    def test_get_thor_file_works_when_num_rows_greater_than_chunksize(self):
        file_name = ("test_get_thor_file_works_when_num_rows_greater_than_"
                     "chunksize")
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        res = get_thor_file(connection=self.conn, thor_file=file_name,
                            chunk_size=1).sort_index(axis=1)
        expected = pd.DataFrame({"int": [1, 2], "__fileposition__": [0, 8]},
                                dtype=np.int32).sort_index(axis=1)
        res = res.sort_values("__fileposition__").reset_index(drop=True)
        pd.testing.assert_frame_equal(
            expected.sort_index(axis=1), res.sort_index(axis=1),
            check_dtype=False)

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_chunks_when_num_rows_less_than_chunksize(self, mock):
        file_name = "test_get_thor_file_chunks_when_num_" \
                    "rows_less_than_chunksize"
        mock.return_value = {'int': ['1'], '__fileposition__': ['0']}
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )

        get_thor_file(connection=self.conn, thor_file=file_name, chunk_size=3)
        mock.assert_called_with(file_name, 0, 1, 3, 60)

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_chunks_when_num_rows_equal_to_chunksize(self, mock):
        file_name = "test_get_thor_file_chunks_when_num_rows_equal_to_chunksize"
        mock.return_value = {'int': ['1'], '__fileposition__': ['0']}
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        get_thor_file(connection=self.conn, thor_file=file_name, chunk_size=1)
        mock.assert_called_with(file_name, 1, 1, 3, 60)

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_chunks_when_num_rows_above_chunksize(self, mock):
        file_name = "test_get_thor_file_chunks_when_" \
                    "num_rows_greater_than_chunksize"
        mock.return_value = {'int': ['1'], '__fileposition__': ['0']}
        self.conn.run_ecl_string(
           "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
           "OUTPUT(a,,'~{}');".format(file_name),
           True,
           True,
           None
        )
        get_thor_file(connection=self.conn, thor_file=file_name, chunk_size=1)
        expected = [
            unittest.mock.call(file_name, 0, 1, 3, 60),
            unittest.mock.call(file_name, 1, 1, 3, 60)
        ]

        self.assertEqual(expected, mock.call_args_list)

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_uses_generates_chunk_size_150000row_2workers(self,
                                                                        mock):
        file_name = "test_get_thor_file_uses_generates_" \
                    "chunk_size_150000row_2workers"

        mock.return_value = {'int': ['1'], '__fileposition__': ['0']}

        self.conn.run_ecl_string(
           "a := DATASET([{}], {{INTEGER int;}}); "
           "OUTPUT(a,,'~{}');".format(",".join(["{1}"]*150000), file_name),
           True,
           True,
           None
        )
        get_thor_file(connection=self.conn, thor_file=file_name, max_workers=2)
        expected = [
            unittest.mock.call(file_name, 0, 75000, 3, 60),
            unittest.mock.call(file_name, 75000, 75000, 3, 60)
        ]
        self.assertEqual(expected[0], mock.call_args_list[0])
        self.assertEqual(expected[1], mock.call_args_list[1])

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_uses_generates_chunk_size_150000row_3workers(self,
                                                                        mock):
        file_name = "test_get_thor_file_uses_generates_chunk_" \
                    "size_150000row_3workers"

        mock.return_value = {'int': ['1'], '__fileposition__': ['0']}

        self.conn.run_ecl_string(
            "a := DATASET([{}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(",".join(["{1}"] * 150000), file_name),
            True,
            True,
            None
        )
        get_thor_file(connection=self.conn, thor_file=file_name, max_workers=3)
        expected = [
            unittest.mock.call(file_name, 0, 50000, 3, 60),
            unittest.mock.call(file_name, 50000, 50000, 3, 60),
            unittest.mock.call(file_name, 100000, 50000, 3, 60)
        ]
        self.assertEqual(expected[0], mock.call_args_list[0])
        self.assertEqual(expected[1], mock.call_args_list[1])
        self.assertEqual(expected[2], mock.call_args_list[2])

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_uses_generates_chunk_size_325000row_1workers(self,
                                                                        mock):
        file_name = "test_get_thor_file_uses_generates_" \
                    "chunk_size_325000row_1workers"

        mock.return_value = {'int': ['1'], '__fileposition__': ['0']}

        self.conn.run_ecl_string(
            "a := DATASET([{}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(",".join(["{1}"] * 350000), file_name),
            True,
            True,
            None
        )
        get_thor_file(connection=self.conn, thor_file=file_name, max_workers=1)
        expected = [
            unittest.mock.call(file_name, 0, 325000, 3, 60),
            unittest.mock.call(file_name, 325000, 25000, 3, 60)
        ]
        self.assertEqual(expected[0], mock.call_args_list[0])
        self.assertEqual(expected[1], mock.call_args_list[1])

    def test_get_thor_file_works_when_chunksize_is_zero(self):
        file_name = "test_get_thor_file_works_when_chunksize_is_zero"
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        with self.assertRaises(ZeroDivisionError):
            get_thor_file(connection=self.conn, thor_file=file_name,
                          chunk_size=0)

    def test_get_thor_file_parses_column_types_correctly(self):
        i = 1
        d = 1.5
        u = "U'ABC'"
        s = "'ABC'"
        b = "TRUE"
        x = "x'ABC'"
        es = "ABC"
        types = [("INTEGER", "int", i),
                 ("INTEGER1", "int1", i),
                 ("UNSIGNED INTEGER", "unsigned_int", i),
                 ("UNSIGNED INTEGER1", "unsigned_int_1", i),
                 ("UNSIGNED8", "is_unsigned_8", i),
                 ("UNSIGNED", "usigned", i),
                 ("DECIMAL10", "dec10", d, round(d)),
                 ("DECIMAL5_3", "dec5_3", d),
                 ("UNSIGNED DECIMAL10", "unsigned_dec10", d, round(d)),
                 ("UNSIGNED DECIMAL5_3", "unsigned_decl5_3", d),
                 ("UDECIMAL10", "udec10", d, round(d)),
                 ("UDECIMAL5_3", "udec5_3", d),
                 ("REAL", "is_real", d),
                 ("REAL4", "is_real4", d),
                 ("UNICODE", "ucode", u, es),
                 ("UNICODE_de", "ucode_de", u, es),
                 ("UNICODE3", "ucode4", u, es),
                 ("UNICODE_de3", "ucode_de4", u, es),
                 ("UTF8", "is_utf8", u, es),
                 ("UTF8_de", "is_utf8_de", u, es),
                 ("STRING", "str", s, es),
                 ("STRING3", "str1", s, es),
                 ("ASCII STRING", "ascii_str", s, es),
                 ("ASCII STRING3", "ascii_str1", s, es),
                 ("EBCDIC STRING", "ebcdic_str", s, es),
                 ("EBCDIC STRING3", "ebcdic_str1", s, es),
                 ("BOOLEAN", "bool", b, True),
                 ("DATA", "is_data", x, "0ABC"),
                 ("DATA3", "is_data_16", x, "0ABC00"),
                 ("VARUNICODE", "varucode", u, es),
                 ("VARUNICODE_de", "varucode_de", u, es),
                 ("VARUNICODE3", "varucode4", u, es),
                 ("VARUNICODE_de3", "varucode_de4", u, es),
                 ("VARSTRING", "varstr", u, es),
                 ("VARSTRING3", "varstr3", u, es),
                 ("QSTRING", "qstr", s, es),
                 ("QSTRING3", "qstr8", s, es)]
        for t in types:
            file_name = ("test_get_thor_file_parses_column_types"
                         "_correctly_{}").format(t[1])
            self.conn.run_ecl_string(
                "a := DATASET([{{{}}}], {{{} {};}}); "
                "OUTPUT(a,,'~{}');".format(t[2], t[0], t[1], file_name),
                True,
                True,
                None
            )
            try:
                expected_val = t[3]
            except IndexError:
                expected_val = t[2]
            a = get_thor_file(connection=self.conn, thor_file=file_name,
                              dtype=None)
            expected = pd.DataFrame(
                {t[1]: [expected_val], "__fileposition__": [0]}, index=[0])

            pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                          a.sort_index(axis=1),
                                          check_dtype=False)

    def test_get_thor_file_parses_set_types_correctly(self):
        i = 1
        d = 1.5
        u = "U'ABC'"
        s = "'ABC'"
        b = "TRUE"
        x = "x'ABC'"
        es = "ABC"
        types = [("INTEGER", "int", i),
                 ("INTEGER1", "int1", i),
                 ("UNSIGNED INTEGER", "unsigned_int", i),
                 ("UNSIGNED INTEGER1", "unsigned_int_1", i),
                 ("UNSIGNED8", "is_unsigned_8", i),
                 ("UNSIGNED", "usigned", i),
                 ("DECIMAL10", "dec10", d, round(d)),
                 ("DECIMAL5_3", "dec5_3", d),
                 ("UNSIGNED DECIMAL10", "unsigned_dec10", d, round(d)),
                 ("UNSIGNED DECIMAL5_3", "unsigned_decl5_3", d),
                 ("UDECIMAL10", "udec10", d, round(d)),
                 ("UDECIMAL5_3", "udec5_3", d),
                 ("REAL", "is_real", d),
                 ("REAL4", "is_real4", d),
                 ("UNICODE", "ucode", u, es),
                 ("UNICODE_de", "ucode_de", u, es),
                 ("UNICODE3", "ucode4", u, es),
                 ("UNICODE_de3", "ucode_de4", u, es),
                 ("UTF8", "is_utf8", u, es),
                 ("UTF8_de", "is_utf8_de", u, es),
                 ("STRING", "str", s, es),
                 ("STRING3", "str1", s, es),
                 ("ASCII STRING", "ascii_str", s, es),
                 ("ASCII STRING3", "ascii_str1", s, es),
                 ("EBCDIC STRING", "ebcdic_str", s, es),
                 ("EBCDIC STRING3", "ebcdic_str1", s, es),
                 ("BOOLEAN", "bool", b, True),
                 ("DATA", "is_data", x, "0ABC"),
                 ("DATA3", "is_data_16", x, "0ABC00"),
                 ("VARUNICODE", "varucode", u, es),
                 ("VARUNICODE_de", "varucode_de", u, es),
                 ("VARUNICODE3", "varucode4", u, es),
                 ("VARUNICODE_de3", "varucode_de4", u, es),
                 ("VARSTRING", "varstr", u, es),
                 ("VARSTRING3", "varstr3", u, es),
                 ("QSTRING", "qstr", s, es),
                 ("QSTRING3", "qstr8", s, es)]
        for t in types:
            file_name = ("test_get_thor_file_parses_set_types_"
                         "correctly_{}").format(t[1])
            s = ("a := DATASET([{{[{}]}}], {{SET OF {} {};}}); "
                 "OUTPUT(a,,'~{}');").format(t[2], t[0], t[1], file_name)
            self.conn.run_ecl_string(s, True, False, None)
            try:
                expected_val = t[3]
            except IndexError:
                expected_val = t[2]
            a = get_thor_file(connection=self.conn, thor_file=file_name,
                              dtype=None)
            expected = pd.DataFrame(
                {t[1]: [[expected_val]], "__fileposition__": [0]}, index=[0])
            pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                          a.sort_index(axis=1),
                                          check_dtype=False)

    @patch.object(hpycc.get, "ThreadPoolExecutor")
    def test_get_thor_file_uses_default_max_workers(self, mock):
        mock.return_value = ThreadPoolExecutor(max_workers=10)
        file_name = "test_get_thor_file_uses_default_max_workers"
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        get_thor_file(self.conn, file_name)
        mock.assert_called_with(max_workers=10)

    @patch.object(hpycc.get, "ThreadPoolExecutor")
    def test_get_thor_file_uses_custom_max_workers(self, mock):
        mock.return_value = ThreadPoolExecutor(max_workers=15)
        file_name = "test_get_thor_file_uses_custom_max_workers"
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        get_thor_file(self.conn, file_name, max_workers=2)
        mock.assert_called_with(max_workers=2)

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_uses_defaults(self, mock):
        mock.return_value = {"int": [1], "__fileposition__": [0]}
        file_name = "test_get_thor_file_uses_defaults"
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            False,
            None
        )
        get_thor_file(self.conn, file_name)
        mock.assert_called_with(file_name, 0, 2, 3, 60)

    @patch.object(hpycc.connection.Connection, "get_logical_file_chunk")
    def test_get_thor_file_uses_max_sleep(self, mock):
        mock.return_value = {"int": [1], "__fileposition__": [0]}
        file_name = "test_get_thor_file_uses_max_sleep"
        self.conn.run_ecl_string(
            "a := DATASET([{{1}}, {{2}}], {{INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            False,
            None
        )
        get_thor_file(self.conn, file_name, max_sleep=120)
        mock.assert_called_with(file_name, 0, 2, 3, 120)

    # test the dtype

    def test_get_thor_file_uses_single_dtype(self):
        file_name = "test_get_thor_file_uses_single_dtype"
        self.conn.run_ecl_string(
            "a := DATASET([{{'1'}}, {{'2'}}], {{STRING int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        res = get_thor_file(self.conn, file_name, dtype=int)
        expected = pd.DataFrame({"int": [1, 2], "__fileposition__": [0, 5]},
                                dtype=np.int32)

        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1))

    def test_get_thor_file_uses_dict_of_dtypes(self):
        file_name = "test_get_thor_file_uses_dict_of_dtypes"
        self.conn.run_ecl_string(
            "a := DATASET([{{'1', TRUE, 1}}, {{'2', FALSE, 2}}], "
            "{{STRING str; BOOLEAN bool; INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        res = get_thor_file(self.conn, file_name,
                            dtype={"str": int, "bool": bool,
                                   "int": str, "__fileposition__": str})
        expected = pd.DataFrame({
            "int": ["1", "2"],
            "str": [1, 2],
            "bool": [True, False],
            "__fileposition__": ["0", "14"]}).astype(
            {"str": int, "bool": bool, "int": str, "__fileposition__": str})
        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1))

    def test_get_thor_file_uses_dict_of_dtypes_with_missing_cols(self):
        file_name = "test_get_thor_file_uses_dict_of_dtypes_with_missing__cols"
        self.conn.run_ecl_string(
            "a := DATASET([{{'1', TRUE, 1}}, {{'2', FALSE, 2}}], "
            "{{STRING str; BOOLEAN bool; INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        res = get_thor_file(self.conn, file_name,
                            dtype={"bool": bool, "int": str})
        expected = pd.DataFrame({
            "int": ["1", "2"],
            "str": ["1", "2"],
            "bool": [True, False],
            "__fileposition__": [0, 14]})
        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1), check_dtype=False)

    def test_get_thor_file_uses_dict_of_dtypes_with_extra_cols(self):
        file_name = "test_get_thor_file_uses_dict_of_dtypes_with_extra_cols"
        self.conn.run_ecl_string(
            "a := DATASET([{{'1', TRUE, 1}}, {{'2', FALSE, 2}}], "
            "{{STRING str; BOOLEAN bool; INTEGER int;}}); "
            "OUTPUT(a,,'~{}');".format(file_name),
            True,
            True,
            None
        )
        with self.assertRaises(KeyError):
            get_thor_file(self.conn, file_name,
                          dtype={"bool": bool, "int": str, "made_up": str})

    def test_get_thor_file_returns_a_set(self):
        file_name = "test_get_thor_file_returns_a_set"
        s = ("a := DATASET([{{[1, 2, 3]}}], {{SET OF INTEGER set;}}); "
             "OUTPUT(a,,'~{}');").format(file_name)
        self.conn.run_ecl_string(s, True, True, None)
        res = get_thor_file(self.conn, file_name)
        expected = pd.DataFrame({"set": [[1, 2, 3]], "__fileposition__": 0},
                                dtype=np.int32)
        self.assertEqual(res.set.values[0], [1, 2, 3])
        pd.testing.assert_frame_equal(expected.sort_index(axis=1),
                                      res.sort_index(axis=1))
