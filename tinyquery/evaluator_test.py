# TODO(colin): fix these lint errors (http://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes)
# pep8-disable:E122,E127,E128
from __future__ import absolute_import

import collections
import contextlib
import datetime
import mock
import unittest

from tinyquery import context
from tinyquery import tinyquery
from tinyquery import tq_modes
from tinyquery import tq_types


# TODO(Samantha): Not all modes are nullable.


class fake_datetime(object):
    """A mock version of the datetime.datetime class

    Unfortunately we can't just mock out methods on datetime.datetime as
    needed, since datetime.datetime is defined in native code.
    """
    fake_curr_dt = datetime.datetime(2019, 1, 3, 4, 43, 23)

    @classmethod
    def utcnow(cls):
        return cls.fake_curr_dt


@contextlib.contextmanager
def dt_patch():
    """Mock out the datetime class.

    TODO(colin): for reasons I don't quite understand, using mock.patch does
    not interact correctly with the KA webapp's mocking of datetimes, and the
    tests thus fail.  Figure out how to eliminate this workaround.
    """
    old_dt = datetime.datetime
    datetime.datetime = fake_datetime
    try:
        yield
    finally:
        datetime.datetime = old_dt


class EvaluatorTest(unittest.TestCase):
    def setUp(self):
        self.tq = tinyquery.TinyQuery()
        self.tq.load_table_or_view(tinyquery.Table(
            'test_table',
            5,
            collections.OrderedDict([
                ('val1', context.Column(type=tq_types.INT,
                                        mode=tq_modes.NULLABLE,
                                        values=[4, 1, 8, 1, 2])),
                ('val2', context.Column(type=tq_types.INT,
                                        mode=tq_modes.NULLABLE,
                                        values=[8, 2, 4, 1, 6]))
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'test_table_2',
            2,
            collections.OrderedDict([
                ('val3', context.Column(type=tq_types.INT,
                                        mode=tq_modes.NULLABLE,
                                        values=[3, 8])),
                ('val2', context.Column(type=tq_types.INT,
                                        mode=tq_modes.NULLABLE,
                                        values=[2, 7])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'test_table_3',
            5,
            collections.OrderedDict([
                ('foo', context.Column(type=tq_types.INT,
                                       mode=tq_modes.NULLABLE,
                                       values=[1, 2, 4, 5, 1])),
                ('bar', context.Column(type=tq_types.INT,
                                       mode=tq_modes.NULLABLE,
                                       values=[2, 7, 3, 1, 1])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'null_table',
            4,
            collections.OrderedDict([
                ('foo', context.Column(type=tq_types.INT,
                                       mode=tq_modes.NULLABLE,
                                       values=[1, None, None, 5])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'string_table',
            2,
            collections.OrderedDict([
                ('str', context.Column(type=tq_types.STRING,
                                       mode=tq_modes.NULLABLE,
                                       values=['hello', 'world'])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'string_table_with_null',
            3,
            collections.OrderedDict([
                ('str', context.Column(type=tq_types.STRING,
                                       mode=tq_modes.NULLABLE,
                                       values=['hello', 'world', None])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'string_table_2',
            2,
            collections.OrderedDict([
                ('str', context.Column(type=tq_types.STRING,
                                       mode=tq_modes.NULLABLE,
                                       values=['hello', 'world'])),
                ('letters', context.Column(type=tq_types.STRING,
                                           mode=tq_modes.NULLABLE,
                                           values=['h', 'i'])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'string_table_3',
            4,
            collections.OrderedDict([
                ('str1', context.Column(type=tq_types.STRING,
                                       mode=tq_modes.NULLABLE,
                                       values=['hello', 'to',
                                               'the', 'world'])),
                ('str2', context.Column(type=tq_types.STRING,
                                           mode=tq_modes.NULLABLE,
                                           values=['h', 'i', 'i', 't'])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'empty_table',
            0,
            collections.OrderedDict([
                ('foo', context.Column(type=tq_types.INT,
                                       mode=tq_modes.NULLABLE, values=[])),
            ])))
        self.tq.load_table_or_view(tinyquery.Table(
            'rainbow_table',
            3,
            collections.OrderedDict([
                ('ints', context.Column(type=tq_types.INT,
                                        mode=tq_modes.NULLABLE,
                                        values=[-2147483649, -0, 2147483648])),
                ('floats', context.Column(type=tq_types.FLOAT,
                                          mode=tq_modes.NULLABLE,
                                          values=[1.41, 2.72,
                                                  float('infinity')])),
                ('bools', context.Column(type=tq_types.BOOL,
                                         mode=tq_modes.NULLABLE,
                                         values=[True, False, True])),
                ('strings', context.Column(type=tq_types.STRING,
                                           mode=tq_modes.NULLABLE,
                                           values=["infrared", "indigo",
                                                   "ultraviolet"])),
                ('times', context.Column(type=tq_types.TIMESTAMP,
                                         mode=tq_modes.NULLABLE,
                                         values=[
                                             datetime.datetime(1969, 12, 31,
                                                               23, 59, 59),
                                             datetime.datetime(1999, 12, 31,
                                                               23, 59, 59),
                                             datetime.datetime(2038, 1, 19,
                                                               3, 14, 8)]))])))
        self.tq.load_table_or_view(tinyquery.Table(
            'some_nulls_table',
            3,
            collections.OrderedDict([
                ('val1', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.NULLABLE,
                    values=[1, None, 3])),
                ('val2', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.REQUIRED,
                    values=[1, 2, 3])),
                ('val3', context.Column(
                    type=tq_types.TIMESTAMP,
                    mode=tq_modes.NULLABLE,
                    values=[
                        datetime.datetime(2016, 4, 5, 10, 37, 0, 123456),
                        datetime.datetime(1970, 1, 1, 0, 0, 0, 0),
                        None])),
                ('val4', context.Column(
                    type=tq_types.TIMESTAMP,
                    mode=tq_modes.REQUIRED,
                    values=[
                        datetime.datetime(2018, 4, 5, 10, 37, 0, 123456),
                        datetime.datetime(2019, 4, 5, 10, 37, 0, 123456),
                        datetime.datetime(2020, 4, 5, 10, 37, 0, 123456)]))])))

        self.tq.load_table_or_view(tinyquery.Table(
            'timely_table',
            1,
            collections.OrderedDict([
                ('ts', context.Column(
                    type=tq_types.TIMESTAMP,
                    mode=tq_modes.NULLABLE,
                    values=[datetime.datetime(2016, 4, 5, 10, 37, 0, 123456)]
                ))])))

        self.tq.load_table_or_view(tinyquery.Table(
            'record_table',
            2,
            collections.OrderedDict([
                ('r1.i', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.NULLABLE,
                    values=[4, 5])),
                ('r1.s', context.Column(
                    type=tq_types.STRING,
                    mode=tq_modes.NULLABLE,
                    values=['four', 'five'])),
                ('r2.i', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.NULLABLE,
                    values=[6, 7]))])))

        self.tq.load_table_or_view(tinyquery.Table(
            'repeated_table',
            4,
            collections.OrderedDict([
                ('i', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.REPEATED,
                    values=[[1, 2, 1], [1, 4, 5], [], [6]])),
                ('i_clone', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.REPEATED,
                    values=[[1, 2, 1], [1, 4, 5], [], [6]])),
                ('different_repetition', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.REPEATED,
                    values=[[1], [4, 5], [1], [6, 7]])),
                ('repeated_but_only_single_values', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.REPEATED,
                    values=[[1], [], [8], [9]])),
                ('j', context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.NULLABLE,
                    values=[1, 1, 1, 1]))])))

        self.tq.load_table_or_view(tinyquery.Table(
            'record_table_2',
            3,
            collections.OrderedDict([
                ('kind', context.Column(
                    type=tq_types.STRING, mode=tq_modes.NULLABLE, values=[
                        u'person', u'person', u'person'])),
                ('fullName', context.Column(
                    type=tq_types.STRING, mode=tq_modes.NULLABLE, values=[
                        u'John Doe', u'Mike Jones', u'Anna Karenina'])),
                ('age', context.Column(
                    type=tq_types.INT, mode=tq_modes.NULLABLE, values=[
                        u'22', u'35', u'45'])),
                ('gender', context.Column(
                    type=tq_types.STRING, mode=tq_modes.NULLABLE, values=[
                        u'Male', u'Male', u'Female'])),
                ('phoneNumber.areaCode', context.Column(
                    type=tq_types.INT, mode=tq_modes.NULLABLE, values=[
                        u'206', u'622', u'425'])),
                ('phoneNumber.number', context.Column(
                    type=tq_types.INT, mode=tq_modes.NULLABLE, values=[
                        u'1234567', u'1567845', u'1984783'])),
                ('children.name', context.Column(
                    type=tq_types.STRING, mode=tq_modes.REPEATED, values=[
                        [u'Jane', u'John'], [u'Earl', u'Sam', u'Kit'], []])),
                ('children.gender', context.Column(
                    type=tq_types.STRING, mode=tq_modes.REPEATED, values=[
                        [u'Female', u'Male'], [u'Male', u'Male', u'Male'],
                        []])),
                ('children.age', context.Column(
                    type=tq_types.INT, mode=tq_modes.REPEATED, values=[
                        [u'6', u'15'], [u'10', u'6', u'8'], []])),
                ('citiesLived.place', context.Column(
                    type=tq_types.STRING, mode=tq_modes.REPEATED, values=[
                        [u'Seattle', u'Stockholm'],
                        [u'Los Angeles', u'Washington DC', u'Portland',
                         u'Austin'],
                        [u'Stockholm', u'Russia', u'Austin']])),
                ('citiesLived.yearsLived', context.Column(
                    type=tq_types.INT, mode=tq_modes.REPEATED, values=[
                        [[u'1995'], [u'2005']], [
                        [u'1989', u'1993', u'1998', u'2002'],
                        [u'1990', u'1993', u'1998', u'2008'],
                        [u'1993', u'1998', u'2003', u'2005'],
                        [u'1973', u'1998', u'2001', u'2005']], [
                        [u'1992', u'1998', u'2000', u'2010'],
                        [u'1998', u'2001', u'2005'],
                        [u'1995', u'1999']]]))])))

    def assert_query_result(self, query, expected_result):
        result = self.tq.evaluate_query(query)
        self.assertEqual(expected_result, result)

    def make_context(self, name_type_values_triples, repeated=False):
        num_rows = len(name_type_values_triples[0][2])
        # The constructor does all relevant invariant checks, so we don't have
        # to do that here.
        mode = tq_modes.REPEATED if repeated else tq_modes.NULLABLE
        return context.Context(
            num_rows,
            collections.OrderedDict(
                ((None, name), context.Column(type=col_type,
                                              mode=mode,
                                              values=values))
                for name, col_type, values in name_type_values_triples),
            None)

    def make_context_with_mode(self, name_type_mode_value_tuples):
        # TODO(colin): consolidate with make_context
        num_rows = len(name_type_mode_value_tuples[0][3])
        # The constructor does all relevant invariant checks, so we don't have
        # to do that here.
        return context.Context(
            num_rows,
            collections.OrderedDict(
                ((None, name), context.Column(type=col_type,
                                              mode=mode,
                                              values=values))
                for name, col_type, mode, values
                in name_type_mode_value_tuples),
            None)

    def test_select_literal(self):
        self.assert_query_result(
            'SELECT 0',
            self.make_context([('f0_', tq_types.INT, [0])])
        )

    def test_select_repeated(self):
        expected_column = self.tq.tables_by_name['repeated_table'].columns['i']
        self.assert_query_result(
            'SELECT i FROM repeated_table',
            context.Context(
                len(expected_column.values),
                collections.OrderedDict([((None, 'i'), expected_column)]),
                None))

    def test_multiple_repeated(self):
        expected_column = self.tq.tables_by_name['repeated_table'].columns['i']
        # Ok to use two repeated fields as long as the count in each row
        # matches.
        self.assert_query_result(
            'SELECT IF(i == 2, i, i_clone) AS i FROM repeated_table',
            context.Context(
                len(expected_column.values),
                collections.OrderedDict([((None, 'i'), expected_column)]),
                None))

        # Error to use two repeated fields if the count in each row is
        # different.
        self.assertRaises(
            TypeError,
            lambda: self.tq.evaluate_query(
                'SELECT IF(i == 2, i, different_repetition) AS i '
                'FROM repeated_table'))

        # Ok to use a second repeated field if it only contains scalar data.
        self.assert_query_result(
            'SELECT IF(i == 2, i, repeated_but_only_single_values) AS i '
            'FROM repeated_table',
            context.Context(
                len(expected_column.values),
                collections.OrderedDict([((None, 'i'), context.Column(
                    type=tq_types.INT,
                    mode=tq_modes.REPEATED,
                    values=[[1, 2, 1], [None, None, None], [8], [9]]))]),
                None))

    def test_simple_arithmetic(self):
        self.assert_query_result(
            'SELECT 1 + 2',
            self.make_context([('f0_', tq_types.INT, [3])])
        )

    def test_null_arithmetic(self):
        self.assert_query_result(
            'SELECT val1 + val2 FROM some_nulls_table',
            self.make_context([('f0_', tq_types.INT, [2, None, 6])])
        )

    def test_float_arithmetic(self):
        self.assert_query_result(
            'SELECT 1.0 + 2.0',
            self.make_context([('f0_', tq_types.FLOAT, [3.0])])
        )

    def test_mixed_arithmetic(self):
        self.assert_query_result(
            'SELECT 1 + 2.0',
            self.make_context([('f0_', tq_types.FLOAT, [3.0])])
        )

    def test_precedence(self):
        self.assert_query_result(
            'SELECT 2 * (3 + 1) + 2 * 3',
            self.make_context([('f0_', tq_types.INT, [14])])
        )

    def test_negative_number(self):
        self.assert_query_result(
            'SELECT -3',
            self.make_context([('f0_', tq_types.INT, [-3])])
        )

    def test_equality(self):
        self.assert_query_result(
            'SELECT 3 == 3',
            self.make_context([('f0_', tq_types.BOOL, [True])]))
        self.assert_query_result(
            'SELECT 3 = 3',
            self.make_context([('f0_', tq_types.BOOL, [True])]))

    def test_simple_arithmetic_repeated(self):
        self.assert_query_result(
            'SELECT i + j FROM repeated_table',
            self.make_context_with_mode([
                ('f0_', tq_types.INT, tq_modes.REPEATED, [
                    [2, 3, 2],
                    [2, 5, 6],
                    [],
                    [7]])]))

    def test_contains_when_true_both_literals(self):
        self.assert_query_result(
            'SELECT "xyz" CONTAINS "y"',
            self.make_context([('f0_', tq_types.BOOL, [True])]))

    def test_contains_when_false_both_literals(self):
        self.assert_query_result(
            'SELECT "xyz" CONTAINS "q"',
            self.make_context([('f0_', tq_types.BOOL, [False])]))

    def test_contains_lhs_literal(self):
        self.assert_query_result(
            'SELECT "tinyquery" CONTAINS letters FROM string_table_2',
            self.make_context([('f0_', tq_types.BOOL, [False, True])]))

    def test_contains_rhs_literal(self):
        self.assert_query_result(
            'SELECT str CONTAINS "h" FROM string_table_2',
            self.make_context([('f0_', tq_types.BOOL, [True, False])]))

    def test_contains_both_columns(self):
        self.assert_query_result(
            'SELECT str CONTAINS letters FROM string_table_2',
            self.make_context([('f0_', tq_types.BOOL, [True, False])]))

    def test_contains_null(self):
        self.assert_query_result(
            'SELECT STRING(NULL) contains STRING(NULL), '
            '"asdf" CONTAINS STRING(NULL), STRING(NULL) CONTAINS "asdf"',
            self.make_context([
                ('f0_', tq_types.BOOL, [None]),
                ('f1_', tq_types.BOOL, [None]),
                ('f2_', tq_types.BOOL, [None])]))

    def test_bad_string_timestamp_comparison(self):
        # Strings and timestamps are totally fine to compare typewise in the
        # compiler, it's only in the evaluator that we're able to tell if those
        # strings are iso8601.
        with self.assertRaises(TypeError) as context:
            self.tq.evaluate_query('SELECT times < strings FROM rainbow_table')
        self.assertTrue('Invalid comparison' in str(context.exception))

    def test_null_comparisons(self):
        self.assert_query_result(
            'SELECT val1 < val2, val3 < val4 FROM some_nulls_table',
            self.make_context([('f0_', tq_types.BOOL, [False, None, False]),
                               ('f1_', tq_types.BOOL, [True, True, None])]))

    def test_function_calls(self):
        with mock.patch('time.time', lambda: 15):
            self.assert_query_result(
                'SELECT ABS(-2), POW(2, 3), NOW()',
                self.make_context([
                    ('f0_', tq_types.INT, [2]),
                    ('f1_', tq_types.INT, [8]),
                    ('f2_', tq_types.INT, [15000000]),
                ])
            )

    def test_integer_cast(self):
        self.assert_query_result(
            'SELECT INTEGER(3.7) AS i1, INTEGER(2.2) AS i2, '
            '       INTEGER(TIMESTAMP("2016-01-01")) AS i3, '
            '       INTEGER("abcd") AS i4, INTEGER("7") AS i5',
            self.make_context([
                ('i1', tq_types.INT, [3]),
                ('i2', tq_types.INT, [2]),
                ('i3', tq_types.INT, [1451606400000000]),
                ('i4', tq_types.INT, [None]),
                ('i5', tq_types.INT, [7]),
            ]))

    def test_boolean_not(self):
        self.assert_query_result(
            'SELECT NOT TRUE AS f, NOT FALSE AS t, NOT NULL AS n',
            self.make_context([('f', tq_types.BOOL, [False]),
                               ('t', tq_types.BOOL, [True]),
                               ('n', tq_types.BOOL, [None])]))

    def test_null_checks(self):
        self.assert_query_result(
            'SELECT NULL IS NULL AS t, NULL IS NOT NULL AS f',
            self.make_context([('t', tq_types.BOOL, [True]),
                               ('f', tq_types.BOOL, [False])]))

    def test_case_expressions(self):
        self.assert_query_result(
            'SELECT CASE WHEN TRUE THEN 1 ELSE 0 END',
            self.make_context([('f0_', tq_types.INT, [1])]))

    def test_select_from_table(self):
        self.assert_query_result(
            'SELECT val1 FROM test_table',
            self.make_context([('val1', tq_types.INT, [4, 1, 8, 1, 2])])
        )

    def test_select_comparison(self):
        self.assert_query_result(
            'SELECT val1 = val2 FROM test_table',
            self.make_context([
                ('f0_', tq_types.BOOL, [False, False, False, True, False])
            ])
        )

    def test_where(self):
        self.assert_query_result(
            'SELECT val1 + 2 FROM test_table WHERE val2 > 3',
            self.make_context([('f0_', tq_types.INT, [6, 10, 4])])
        )

    def test_where_multiple_repeated(self):
        self.assert_query_result(
            'SELECT i_clone '
            'FROM repeated_table '
            'WHERE i = 1',
            self.make_context(
                [('i_clone', tq_types.INT, [[1, 1], [1]])],
                repeated=True))

        self.assert_query_result(
            'SELECT j '
            'FROM repeated_table '
            'WHERE i = 1',
            self.make_context([('j', tq_types.INT, [1, 1])]))

    def test_having(self):
        self.assert_query_result(
            'SELECT val1 + 2 AS x FROM test_table HAVING x > 4',
            self.make_context([('x', tq_types.INT, [6, 10])])
        )

    def test_having_with_out_of_scope_variable(self):
        self.assertRaises(
            Exception,
            lambda: self.tq.evaluate_query(
                'SELECT val1 + 2 AS x FROM test_table HAVING val2 > 3'))

    def test_multiple_select(self):
        self.assert_query_result(
            'SELECT val1 + 1 foo, val2, val2 * 2'
            'FROM test_table WHERE val1 < 5',
            self.make_context([
                ('foo', tq_types.INT, [5, 2, 2, 3]),
                ('val2', tq_types.INT, [8, 2, 1, 6]),
                ('f0_', tq_types.INT, [16, 4, 2, 12]),
            ])
        )

    def test_simple_aggregate(self):
        self.assert_query_result(
            'SELECT SUM(val1) + MIN(val2) FROM test_table',
            self.make_context([('f0_', tq_types.INT, [17])])
        )

    def test_null_minmax(self):
        self.assert_query_result(
            'SELECT MIN(val1), max(val1) FROM some_nulls_table',
            self.make_context([
                ('f0_', tq_types.INT, [1]),
                ('f1_', tq_types.INT, [3])]))

    def test_aggregate_evaluation(self):
        self.assert_query_result(
            'SELECT 2 * SUM(val1 + 1) FROM test_table WHERE val1 < 5',
            self.make_context([('f0_', tq_types.INT, [24])])
        )

    def test_group_by_field(self):
        result = self.tq.evaluate_query(
            'SELECT SUM(val2) FROM test_table GROUP BY val1')
        self.assertEqual([3, 4, 6, 8],
                         sorted(result.columns[(None, 'f0_')].values))

    def test_group_by_used_field(self):
        result = self.tq.evaluate_query(
            'SELECT val1 + SUM(val2) FROM test_table GROUP BY val1')
        self.assertEqual([4, 8, 12, 12],
                         sorted(result.columns[(None, 'f0_')].values))

    def test_group_by_alias(self):
        result = self.tq.evaluate_query(
            'SELECT val1 % 3 AS cat, MAX(val1) FROM test_table GROUP BY cat')
        result_rows = zip(result.columns[(None, 'cat')].values,
                          result.columns[(None, 'f0_')].values)
        self.assertEqual([(1, 4), (2, 8)], sorted(result_rows))

    def test_mixed_group_by(self):
        result = self.tq.evaluate_query(
            'SELECT val2 % 2 AS foo, SUM(val2) AS bar '
            'FROM test_table GROUP BY val1, foo')
        result_rows = zip(result.columns[(None, 'foo')].values,
                          result.columns[(None, 'bar')].values)
        self.assertEqual([(0, 2), (0, 4), (0, 6), (0, 8), (1, 1)],
                         sorted(result_rows))

    def test_order_by_field(self):
        self.assert_query_result(
            'SELECT val1, val2 FROM test_table ORDER BY val1 DESC, val2',
            self.make_context([
                ('val1', tq_types.INT, [8, 4, 2, 1, 1]),
                ('val2', tq_types.INT, [4, 8, 6, 1, 2]),
            ])
        )

    def test_order_by_field2(self):
        self.assert_query_result(
            'SELECT val1, val2 FROM test_table ORDER BY val2 DESC, val1',
            self.make_context([
                ('val1', tq_types.INT, [4, 2, 8, 1, 1]),
                ('val2', tq_types.INT, [8, 6, 4, 2, 1]),
            ])
        )

    def test_order_by_field3(self):
        self.assert_query_result(
            'SELECT val2 FROM test_table ORDER BY val1, val2 DESC',
            self.make_context([
                ('val2', tq_types.INT, [2, 1, 6, 8, 4]),
            ])
        )

    def test_order_by_string_fields(self):
        self.assert_query_result(
            'SELECT str1, str2 FROM string_table_3 ORDER BY str2 DESC, str1',
            self.make_context([
                ('str1', tq_types.STRING, ['world', 'the', 'to', 'hello']),
                ('str2', tq_types.STRING, ['t', 'i', 'i', 'h']),
            ])
        )

    def test_order_no_rows(self):
        self.assert_query_result(
            'SELECT str FROM string_table WHERE str CONTAINS "bye" '
            'ORDER BY str',
            self.make_context([
                ('str', tq_types.STRING, [])]))

    def test_order_aggregate(self):
        self.skipTest("Ordering by an aggregate field is not yet supported")
        # TODO: this is not yet supported
        self.assert_query_result(
            'SELECT val1, MAX(val2) as m FROM test_table GROUP BY val1 ORDER BY m',
            self.make_context([
                ('val1', tq_types.INT, [1, 2, 8, 4]),
                ('m', tq_types.INT, [2, 4, 6, 8]),
            ]))

    def test_select_multiple_tables(self):
        self.assert_query_result(
            'SELECT val1, val2, val3 FROM test_table, test_table_2',
            self.make_context([
                ('val1', tq_types.INT, [4, 1, 8, 1, 2, None, None]),
                ('val2', tq_types.INT, [8, 2, 4, 1, 6, 2, 7]),
                ('val3', tq_types.INT, [None, None, None, None, None, 3, 8]),
            ])
        )

    def test_subquery(self):
        self.assert_query_result(
            'SELECT foo * 2, foo + 1 '
            'FROM (SELECT val1 + val2 AS foo FROM test_table)',
            self.make_context([
                ('f0_', tq_types.INT, [24, 6, 24, 4, 16]),
                ('f1_', tq_types.INT, [13, 4, 13, 3, 9]),
            ])
        )

    def test_fully_qualified_name(self):
        self.assert_query_result(
            'SELECT test_table.val1 FROM test_table',
            self.make_context([
                ('test_table.val1', tq_types.INT, [4, 1, 8, 1, 2])])
        )

    def test_table_alias(self):
        self.assert_query_result(
            'SELECT t.val1 FROM test_table t',
            self.make_context([('t.val1', tq_types.INT, [4, 1, 8, 1, 2])]))

    def test_join(self):
        result = self.tq.evaluate_query(
            'SELECT bar'
            '    FROM test_table JOIN test_table_3'
            '    ON test_table.val1 = test_table_3.foo')
        result_rows = result.columns[(None, 'bar')].values
        # Four results for the 1 key, then one each for 2 and 4.
        self.assertEqual([1, 1, 2, 2, 3, 7], sorted(result_rows))

    def test_multiple_condition_join(self):
        result = self.tq.evaluate_query(
            'SELECT foo, bar'
            '    FROM test_table t1 JOIN test_table_3 t2'
            '    ON t1.val1 == t2.foo AND t2.bar = t1.val2')
        result_rows = zip(result.columns[(None, 'foo')].values,
                          result.columns[(None, 'bar')].values)
        self.assertEqual([(1, 1), (1, 2)], sorted(result_rows))

    def test_left_outer_join(self):
        result = self.tq.evaluate_query(
            'SELECT t1.val1, t3.bar'
            '   FROM test_table t1'
            '   LEFT JOIN test_table_3 t3'
            '   ON t1.val1 = t3.foo')
        result_rows = zip(result.columns[(None, 't1.val1')].values,
                          result.columns[(None, 't3.bar')].values)
        self.assertEqual(
            [
                (1, 1),
                (1, 1),
                (1, 2),
                (1, 2),
                (2, 7),
                (4, 3),
                (8, None),
            ],
            sorted(result_rows))

    def test_left_outer_join_2(self):
        self.assert_query_result(
            'SELECT * FROM test_table t1 '
            'LEFT OUTER JOIN EACH test_table_2 t2 ON t1.val1 = t2.val3',
            self.make_context([
                ('t1.val1', tq_types.INT, [4, 1, 8, 1, 2]),
                ('t1.val2', tq_types.INT, [8, 2, 4, 1, 6]),
                ('t2.val3', tq_types.INT, [None, None, 8, None, None]),
                ('t2.val2', tq_types.INT, [None, None, 7, None, None])
            ])
        )

    def test_cross_join(self):
        result = self.tq.evaluate_query(
            'SELECT t1.val1, val3'
            '    FROM test_table t1'
            '    CROSS JOIN test_table_2 t2')
        result_rows = zip(result.columns[(None, 't1.val1')].values,
                          result.columns[(None, 'val3')].values)
        self.assertEqual(
            [
                (1, 3),
                (1, 3),
                (1, 8),
                (1, 8),
                (2, 3),
                (2, 8),
                (4, 3),
                (4, 8),
                (8, 3),
                (8, 8),
            ],
            sorted(result_rows))

    def test_cross_join_2(self):
        self.assert_query_result(
            'SELECT * FROM string_table t1 CROSS JOIN test_table_2 t2',
            self.make_context([
                ('t1.str', tq_types.STRING, ['hello', 'hello',
                                             'world', 'world']),
                ('t2.val3', tq_types.INT, [3, 8, 3, 8]),
                ('t2.val2', tq_types.INT, [2, 7, 2, 7])
            ])
        )

    def test_multiple_way_join(self):
        result = self.tq.evaluate_query(
            'SELECT t1.val1, t3.bar, t2.val2'
            '   FROM test_table t1'
            '   LEFT JOIN test_table_3 t3'
            '   ON t1.val1 = t3.foo'
            '   JOIN test_table_2 t2'
            '   ON t2.val3 = t3.bar')
        result_rows = zip(result.columns[(None, 't1.val1')].values,
                          result.columns[(None, 't3.bar')].values,
                          result.columns[(None, 't2.val2')].values)
        self.assertEqual(
            [
                (4, 3, 2),
            ],
            sorted(result_rows))

    def test_repeated_select_from_join(self):
        expected_column = self.tq.tables_by_name['repeated_table'].columns['i']
        self.assert_query_result(
            'SELECT i FROM repeated_table '
            'LEFT JOIN (SELECT 1 AS x) AS join_table '
            'ON repeated_table.j = join_table.x',
            context.Context(
                len(expected_column.values),
                collections.OrderedDict([((None, 'i'), expected_column)]),
                None))

    def test_join_ordering(self):
        # Using aliases
        self.assert_query_result(
            'SELECT t1.val1 as v1, t1.val2 as v2, t3.foo as foo, t3.bar as bar FROM test_table t1'
            '    JOIN test_table_3 t3 ON t1.val1 = t3.foo ORDER BY v2, bar',
            self.make_context([
                ('v1', tq_types.INT, [1, 1, 1, 1, 2, 4]),
                ('v2', tq_types.INT, [1, 1, 2, 2, 6, 8]),
                ('foo', tq_types.INT, [1, 1, 1, 1, 2, 4]),
                ('bar', tq_types.INT, [1, 2, 1, 2, 7, 3]),
            ]))
        # Not using aliases
        self.assert_query_result(
            'SELECT t1.val1, t1.val2, t3.foo, t3.bar FROM test_table t1'
            '    JOIN test_table_3 t3 ON t1.val1 = t3.foo ORDER BY val2, bar',
            self.make_context([
                ('t1.val1', tq_types.INT, [1, 1, 1, 1, 2, 4]),
                ('t1.val2', tq_types.INT, [1, 1, 2, 2, 6, 8]),
                ('t3.foo', tq_types.INT, [1, 1, 1, 1, 2, 4]),
                ('t3.bar', tq_types.INT, [1, 2, 1, 2, 7, 3]),
            ]))

    def test_join_ordering_duplicate_column_names(self):
        self.assert_query_result(
            'SELECT t1.val1 as v1, t2.val2 as v2 FROM test_table t1'
            '    JOIN test_table_2 t2 ON t1.val1 = t2.val3'
            '    ORDER BY v2',
            self.make_context([
                ('v1', tq_types.INT, [8]),
                ('v2', tq_types.INT, [7]),
            ]))

    def test_order_without_select(self):
        self.assert_query_result(
            'SELECT val1 FROM test_table ORDER BY val2',
            self.make_context([
                ('val1', tq_types.INT, [1, 1, 8, 2, 4])
            ]))
        self.assert_query_result(
            'SELECT t1.val1, t1.val2, t3.foo FROM test_table t1'
            '    JOIN test_table_3 t3 ON t1.val1 = t3.foo ORDER BY val2, bar',
            self.make_context([
                ('t1.val1', tq_types.INT, [1, 1, 1, 1, 2, 4]),
                ('t1.val2', tq_types.INT, [1, 1, 2, 2, 6, 8]),
                ('t3.foo', tq_types.INT, [1, 1, 1, 1, 2, 4]),
            ]))

    def test_null_test(self):
        self.assert_query_result(
            'SELECT foo IS NULL, foo IS NOT NULL FROM null_table',
            self.make_context([
                ('f0_', tq_types.BOOL, [False, True, True, False]),
                ('f1_', tq_types.BOOL, [True, False, False, True]),
            ]))

    def test_if_null(self):
        self.assert_query_result(
            'SELECT IFNULL(val1, val2) FROM some_nulls_table',
            self.make_context([('f0_', tq_types.INT, [1, 2, 3])]))

    def test_coalesce(self):
        self.assert_query_result(
            'SELECT COALESCE(NULL, 3, 7)',
            self.make_context([('f0_', tq_types.INT, [3])]))
        self.assert_query_result(
            'SELECT COALESCE(0, NULL, 7)',
            self.make_context([('f0_', tq_types.INT, [0])]))
        self.assert_query_result(
            'SELECT COALESCE(NULL, NULL, 7)',
            self.make_context([('f0_', tq_types.INT, [7])]))

    def test_hash(self):
        self.assert_query_result(
            'SELECT HASH(floats) FROM rainbow_table',
            self.make_context([
                ('f0_', tq_types.INT,
                 map(hash, [1.41, 2.72, float('infinity')]))]))

    def test_null_hash(self):
        self.assert_query_result(
            'SELECT HASH(val1) FROM some_nulls_table',
            self.make_context([
                ('f0_', tq_types.INT, [hash(1), None, hash(3)])]))

    def test_string_functon(self):
        self.assert_query_result(
            'SELECT STRING(val1) FROM some_nulls_table',
            self.make_context([('f0_', tq_types.STRING, ["1", None, "3"])]))

    def test_string_concat(self):
        self.assert_query_result(
            'SELECT CONCAT(STRING(val1), STRING(val2)) FROM some_nulls_table',
            self.make_context([('f0_', tq_types.STRING, ["11", None, "33"])]))

    def test_string_comparison(self):
        self.assert_query_result(
            'SELECT str = "hello" FROM string_table',
            self.make_context([
                ('f0_', tq_types.BOOL, [True, False])]))

    def test_boolean_literals(self):
        self.assert_query_result(
            'SELECT false OR true',
            self.make_context([
                ('f0_', tq_types.BOOL, [True])
            ])
        )

    def test_null_literal(self):
        self.assert_query_result(
            'SELECT NULL IS NULL',
            self.make_context([
                ('f0_', tq_types.BOOL, [True])
            ])
        )

    def test_in_literals(self):
        self.assert_query_result(
            'SELECT 2 IN (1, 2, 3), 4 in (1, 2, 3)',
            self.make_context([
                ('f0_', tq_types.BOOL, [True]),
                ('f1_', tq_types.BOOL, [False]),
            ])
        )

    def test_literals_when_no_rows_present(self):
        """Check we handle providing a literal when there are no rows.

        (At one point we would have crashed because a literal is represented as
        a column with all the same value, and there would be no values.)
        """
        self.assert_query_result(
            'SELECT REGEXP_REPLACE(str, "e(l|q)lo", "i") FROM string_table'
            '    WHERE str CONTAINS "bye"',
            self.make_context([
                ('f0_', tq_types.STRING, [])
            ]))

    def test_if(self):
        self.assert_query_result(
            'SELECT IF(val1 % 2 = 0, "a", "b") FROM test_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['a', 'b', 'a', 'b', 'a'])
            ]))

    def test_join_subquery(self):
        self.assert_query_result(
            'SELECT t2.val '
            'FROM test_table t1 JOIN (SELECT 1 AS val) t2 ON t1.val1 = t2.val',
            self.make_context([
                ('t2.val', tq_types.INT, [1, 1])
            ])
        )

    def test_count(self):
        self.assert_query_result(
            'SELECT COUNT(1) FROM test_table WHERE val1 = 1',
            self.make_context([
                ('f0_', tq_types.INT, [2])]))

    def test_null_count(self):
        self.assert_query_result(
            'SELECT COUNT(val1) FROM some_nulls_table',
            self.make_context([('f0_', tq_types.INT, [2])]))

    def test_count_empty_table(self):
        self.assert_query_result(
            'SELECT COUNT(*) FROM empty_table',
            self.make_context([
                ('f0_', tq_types.INT, [0])
            ])
        )

    def test_count_distinct(self):
        self.assert_query_result(
            'SELECT COUNT(DISTINCT val1) FROM test_table',
            self.make_context([
                ('f0_', tq_types.INT, [4])
            ]))
        self.assert_query_result(
            'SELECT COUNT(DISTINCT i) FROM repeated_table',
            self.make_context([
                ('f0_', tq_types.INT, [5])
            ]))

    def test_null_count_distinct(self):
        self.assert_query_result(
            'SELECT COUNT(DISTINCT val1) FROM some_nulls_table',
            self.make_context([('f0_', tq_types.INT, [2])]))

    def test_group_concat_unquoted(self):
        self.assert_query_result(
            'SELECT GROUP_CONCAT_UNQUOTED(str) FROM string_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['hello,world'])
            ]))
        self.assert_query_result(
            'SELECT GROUP_CONCAT_UNQUOTED(children.name) FROM record_table_2',
            self.make_context([
                ('f0_', tq_types.STRING, ['Jane,John,Earl,Sam,Kit'])
            ]))

    def test_null_group_concat_unquoted(self):
        self.assert_query_result(
            'SELECT GROUP_CONCAT_UNQUOTED(str) FROM string_table_with_null',
            self.make_context([
                ('f0_', tq_types.STRING, ['hello,world'])
            ]))

    def test_group_concat_unquoted_separator(self):
        self.assert_query_result(
            'SELECT GROUP_CONCAT_UNQUOTED(str, \' || \') FROM string_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['hello || world'])
            ]))

    def test_count_star(self):
        self.assert_query_result(
            'SELECT COUNT(foo), COUNT(*) FROM null_table',
            self.make_context([
                ('f0_', tq_types.INT, [2]),
                ('f1_', tq_types.INT, [4]),
            ])
        )

    def test_repeated_count(self):
        self.assert_query_result(
            'SELECT COUNT(children.name) AS numberOfChildren FROM '
            'record_table_2',
            self.make_context([
                ('numberOfChildren', tq_types.INT, [5])])
        )

    def test_select_star_from_table(self):
        self.assert_query_result(
            'SELECT * FROM test_table_3',
            self.make_context([
                ('foo', tq_types.INT, [1, 2, 4, 5, 1]),
                ('bar', tq_types.INT, [2, 7, 3, 1, 1])
            ])
        )

    def test_select_star_from_join(self):
        self.assert_query_result(
            'SELECT * '
            'FROM test_table t1 JOIN test_table_2 t2 ON t1.val1 = t2.val3',
            self.make_context([
                ('t1.val1', tq_types.INT, [8]),
                ('t1.val2', tq_types.INT, [4]),
                ('t2.val3', tq_types.INT, [8]),
                ('t2.val2', tq_types.INT, [7])
            ])
        )

    def test_limit(self):
        self.assert_query_result(
            'SELECT * from test_table LIMIT 3',
            self.make_context([
                ('val1', tq_types.INT, [4, 1, 8]),
                ('val2', tq_types.INT, [8, 2, 4])
            ])
        )

    def test_group_by_fully_qualified_column(self):
        result = self.tq.evaluate_query(
            'SELECT COUNT(*) FROM test_table t GROUP BY t.val1')
        result_rows = result.columns[(None, 'f0_')].values
        self.assertEqual([1, 1, 1, 2], sorted(result_rows))

    def test_various_functions(self):
        self.assert_query_result(
            'SELECT CONCAT("foo", "bar", "baz"), FLOOR(7 / 2), STRING(2)',
            self.make_context([
                ('f0_', tq_types.STRING, ['foobarbaz']),
                ('f1_', tq_types.FLOAT, [3.0]),
                ('f2_', tq_types.STRING, ['2']),
            ])
        )

    def test_quantiles(self):
        self.assert_query_result(
            'SELECT NTH(1, QUANTILES(val1, 3)),'
            '       NTH(2, QUANTILES(val1, 3)),'
            '       NTH(3, QUANTILES(val1, 3))'
            'FROM test_table',
            self.make_context([
                ('f0_', tq_types.INT, [1]),
                ('f1_', tq_types.INT, [2]),
                ('f2_', tq_types.INT, [8]),
            ])
        )

    def test_avg(self):
        self.assert_query_result(
            'SELECT AVG(foo) FROM null_table',
            self.make_context([
                ('f0_', tq_types.FLOAT, [3.0])
            ])
        )

    def test_timestamp(self):
        self.assert_query_result(
            'SELECT TIMESTAMP("2016-01-01 01:00:00")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP,
                 [datetime.datetime(2016, 1, 1, 1, 0, 0)])
            ]))
        self.assert_query_result(
            'SELECT TIMESTAMP("2016-01-01")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP,
                 [datetime.datetime(2016, 1, 1, 0, 0, 0)])
            ]))
        self.assert_query_result(
            'SELECT TIMESTAMP(1451610000000000)',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP,
                 [datetime.datetime(2016, 1, 1, 1, 0, 0)])
            ]))
        self.assert_query_result(
            'SELECT TIMESTAMP(STRING(NULL))',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [None])]))
        with self.assertRaises(TypeError) as context:
            self.tq.evaluate_query('SELECT TIMESTAMP("infrared")')
        self.assertTrue('TIMESTAMP requires' in str(context.exception))

    def test_current_dt_functions(self):
        with dt_patch():
            self.assert_query_result(
                'SELECT CURRENT_TIMESTAMP()',
                self.make_context([
                    ('f0_', tq_types.TIMESTAMP,
                     [fake_datetime.fake_curr_dt])]))

            self.assert_query_result(
                'SELECT CURRENT_TIME()',
                self.make_context([
                    ('f0_', tq_types.STRING, ['04:43:23'])]))

            self.assert_query_result(
                'SELECT CURRENT_DATE()',
                self.make_context([
                    ('f0_', tq_types.STRING, ['2019-01-03'])]))

    def test_timestamp_extraction_functions(self):
        self.assert_query_result(
            'SELECT DATE(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['2016-04-05'])]))

        self.assert_query_result(
            'SELECT DAY(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [5])]))

        self.assert_query_result(
            'SELECT DAYOFWEEK(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [3])]))

        self.assert_query_result(
            'SELECT DAYOFYEAR(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [96])]))

        self.assert_query_result(
            'SELECT FORMAT_UTC_USEC(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['2016-04-05 10:37:00.123456'])]))

        self.assert_query_result(
            'SELECT HOUR(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [10])]))

        self.assert_query_result(
            'SELECT MINUTE(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [37])]))

        self.assert_query_result(
            'SELECT MONTH(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [4])]))

        self.assert_query_result(
            'SELECT QUARTER(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [2])]))

        self.assert_query_result(
            'SELECT SECOND(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [0])]))

        self.assert_query_result(
            'SELECT TIME(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['10:37:00'])]))

        self.assert_query_result(
            'SELECT TIMESTAMP_TO_MSEC(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [1459852620123])]))

        self.assert_query_result(
            'SELECT TIMESTAMP_TO_SEC(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [1459852620])]))

        self.assert_query_result(
            'SELECT TIMESTAMP_TO_USEC(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [1459852620123456])]))

        self.assert_query_result(
            'SELECT WEEK(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [15])]))

        self.assert_query_result(
            'SELECT YEAR(ts) FROM timely_table',
            self.make_context([
                ('f0_', tq_types.INT, [2016])]))

    def test_other_timestamp_functions(self):
        # These query test cases are taken from the examples in the bigquery
        # documentation, with some additions.

        self.assert_query_result(
            'SELECT DATE_ADD(TIMESTAMP("2012-10-01 02:03:04"), 5, "YEAR")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2017, 10, 1, 2, 3, 4)])]))

        self.assert_query_result(
            'SELECT DATE_ADD(TIMESTAMP("2012-10-01 02:03:04"), -5, "YEAR")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2007, 10, 1, 2, 3, 4)])]))

        self.assert_query_result(
            'SELECT DATE_ADD(TIMESTAMP("2012-10-01 02:03:04"), 5, "MONTH")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2013, 3, 1, 2, 3, 4)])]))

        self.assert_query_result(
            'SELECT DATE_ADD(TIMESTAMP("2012-10-01 02:03:04"), -5, "MONTH")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2012, 5, 1, 2, 3, 4)])]))

        self.assert_query_result(
            'SELECT DATE_ADD(TIMESTAMP("2012-10-01 02:03:04"), 5, "DAY")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2012, 10, 6, 2, 3, 4)])]))

        self.assert_query_result(
            'SELECT DATE_ADD(TIMESTAMP("2012-10-01 02:03:04"), -5, "DAY")',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2012, 9, 26, 2, 3, 4)])]))

        self.assert_query_result(
            'SELECT DATEDIFF(TIMESTAMP("2012-10-02 05:23:48"),'
            '                 TIMESTAMP("2011-06-24 12:18:35"))',
            self.make_context([
                ('f0_', tq_types.INT, [466])]))

        self.assert_query_result(
            'SELECT MSEC_TO_TIMESTAMP(1349053323000)',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2012, 10, 1, 1, 2, 3)])]))

        self.assert_query_result(
            'SELECT PARSE_UTC_USEC("2012-10-01 02:03:04")',
            self.make_context([
                ('f0_', tq_types.INT, [1349056984000000])]))

        self.assert_query_result(
            'SELECT SEC_TO_TIMESTAMP(1355968987)',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2012, 12, 20, 2, 3, 7)])]))

        self.assert_query_result(
            'SELECT STRFTIME_UTC_USEC(1274259481071200, "%Y-%m-%d")',
            self.make_context([
                ('f0_', tq_types.STRING, ['2010-05-19'])]))

        self.assert_query_result(
            'SELECT USEC_TO_TIMESTAMP(1349053323000000)',
            self.make_context([
                ('f0_', tq_types.TIMESTAMP, [
                    datetime.datetime(2012, 10, 1, 1, 2, 3)])]))

        self.assert_query_result(
            'SELECT UTC_USEC_TO_DAY(1274259481071200)',
            self.make_context([
                ('f0_', tq_types.INT, [1274227200000000])]))

        self.assert_query_result(
            'SELECT UTC_USEC_TO_HOUR(1274259481071200)',
            self.make_context([
                ('f0_', tq_types.INT, [1274256000000000])]))

        self.assert_query_result(
            'SELECT UTC_USEC_TO_MONTH(1274259481071200)',
            self.make_context([
                ('f0_', tq_types.INT, [1272672000000000])]))

        self.assert_query_result(
            'SELECT UTC_USEC_TO_WEEK(1207929480000000, 2)',
            self.make_context([
                ('f0_', tq_types.INT, [1207612800000000])]))

        self.assert_query_result(
            'SELECT UTC_USEC_TO_YEAR(1274259481071200)',
            self.make_context([
                ('f0_', tq_types.INT, [1262304000000000])]))

    def test_first(self):
        # Test over the equivalent of a GROUP BY
        self.assert_query_result(
            'SELECT FIRST(val1) FROM test_table',
            self.make_context([
                ('f0_', tq_types.INT, [4])
            ])
        )
        # Test over something repeated
        self.assert_query_result(
            'SELECT FIRST(QUANTILES(val1, 3)) FROM test_table',
            self.make_context([
                ('f0_', tq_types.INT, [1])
            ])
        )

        # TODO(colin): test behavior on empty list in both cases

    def test_left(self):
        self.assert_query_result(
            'SELECT LEFT(str, 3) FROM string_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['hel', 'wor'])]))

    def test_regexp_match(self):
        self.assert_query_result(
            'SELECT REGEXP_MATCH(str, "e(l|q)lo") FROM string_table',
            self.make_context([
                ('f0_', tq_types.BOOL, [True, False]),
            ]))

    def test_regexp_extract(self):
        self.assert_query_result(
            'SELECT REGEXP_EXTRACT(str, "e(l|q)lo") '
            'FROM string_table_with_null',
            self.make_context([
                ('f0_', tq_types.STRING, ['l', None, None])
            ]))

    def test_regexp_replace(self):
        self.assert_query_result(
            'SELECT REGEXP_REPLACE(str, "e(l|q)lo", "i") FROM string_table',
            self.make_context([
                ('f0_', tq_types.STRING, ['hi', 'world'])
            ]))

    def test_least_greatest(self):
        self.assert_query_result(
            'SELECT LEAST(val1, val2) FROM test_table',
            self.make_context([
                ('f0_', tq_types.INT, [4, 1, 4, 1, 2])]))

        self.assert_query_result(
            'SELECT GREATEST(val1, val2) FROM test_table',
            self.make_context([
                ('f0_', tq_types.INT, [8, 2, 8, 1, 6])]))

    def test_record(self):
        self.assert_query_result(
            'SELECT r1.* FROM record_table',
            self.make_context([
                ('r1.i', tq_types.INT, [4, 5]),
                ('r1.s', tq_types.STRING, ['four', 'five'])]))

    def test_log(self):
        self.assert_query_result(
            'SELECT LOG2(32)',
            self.make_context([
                ('f0_', tq_types.FLOAT, [5.0])]))

    def test_json_functions(self):
        self.assert_query_result(
            'SELECT JSON_EXTRACT_SCALAR(\'{"a": ["x", {"b": 3}]}\', '
            '                           "$.a[1].b")',
            self.make_context([
                ('f0_', tq_types.STRING, ['3'])]))

        self.assert_query_result(
            'SELECT JSON_EXTRACT(\'{"a": ["x", {"b": 3}]}\', '
            '                    "$.a[1]")',
            self.make_context([
                ('f0_', tq_types.STRING, ['{"b": 3}'])]))

        self.assert_query_result(
            'SELECT JSON_EXTRACT_SCALAR(\'{"a": ["x", {"b": 3}]}\', '
            '                           "$.a[1]")',
            self.make_context([
                ('f0_', tq_types.STRING, [None])]))

        self.assert_query_result(
            'SELECT JSON_EXTRACT(\'{"a": ["x", {"b": 3}]}\', '
            '                    "$.a.q.z")',
            self.make_context([
                ('f0_', tq_types.STRING, [None])]))

        self.assert_query_result(
            'SELECT JSON_EXTRACT(\'{"a": ["x", {"b": "q"}]}\', '
            '                    "$.a[1].b")',
            self.make_context([
                ('f0_', tq_types.STRING, ['"q"'])]))

        self.assert_query_result(
            'SELECT JSON_EXTRACT_SCALAR(\'{"a": ["x", {"b": "q"}]}\', '
            '                           "$.a[1].b")',
            self.make_context([
                ('f0_', tq_types.STRING, ['q'])]))

    def test_within_record_multiple_fields(self):
        self.assert_query_result(
            'SELECT fullName, gender, COUNT(children.name) WITHIN RECORD '
            'AS numberOfChildren FROM record_table_2',
            self.make_context([
                ('fullName', tq_types.STRING, [
                    u'John Doe', u'Mike Jones', u'Anna Karenina']),
                ('gender', tq_types.STRING, [
                    u'Male', u'Male', u'Female']),
                ('numberOfChildren', tq_types.INT, [2, 3, 0])])
        )

    def test_within_record(self):
        self.assert_query_result(
            'SELECT COUNT(children.name) WITHIN RECORD '
            'AS numberOfChildren FROM record_table_2',
            self.make_context([
                ('numberOfChildren', tq_types.INT, [2, 3, 0])])
        )

    def test_within_clause_error(self):
        with self.assertRaises(NotImplementedError) as context:
            self.tq.evaluate_query(
                'SELECT COUNT(citiesLived.yearsLived) WITHIN '
                'citiesLived AS count_years, COUNT(citiesLived.place) '
                'WITHIN citiesLived AS count_places FROM record_table_2'
            )
        self.assertTrue('Multiple fields having "WITHIN" '
                        'clause is not supported as yet'
                        in str(context.exception))
