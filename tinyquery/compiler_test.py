# TODO(colin): fix these lint errors (http://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes)
# pep8-disable:E122
from __future__ import absolute_import

import collections
import datetime
import unittest

from tinyquery import exceptions
from tinyquery import compiler
from tinyquery import context
from tinyquery import runtime
from tinyquery import tinyquery
from tinyquery import tq_ast
from tinyquery import tq_modes
from tinyquery import tq_types
from tinyquery import type_context
from tinyquery import typed_ast


class CompilerTest(unittest.TestCase):
    def setUp(self):
        self.table1 = tinyquery.Table(
            'table1',
            0,
            collections.OrderedDict([
                ('value', context.Column(type=tq_types.INT,
                                         mode=tq_modes.NULLABLE, values=[])),
                ('value2', context.Column(type=tq_types.INT,
                                          mode=tq_modes.NULLABLE, values=[]))
            ]))
        self.table1_type_ctx = self.make_type_context(
            [('table1', 'value', tq_types.INT),
             ('table1', 'value2', tq_types.INT)]
        )

        self.table2 = tinyquery.Table(
            'table2',
            0,
            collections.OrderedDict([
                ('value', context.Column(type=tq_types.INT,
                                         mode=tq_modes.NULLABLE, values=[])),
                ('value3', context.Column(type=tq_types.INT,
                                          mode=tq_modes.NULLABLE, values=[]))
            ])
        )
        self.table2_type_ctx = self.make_type_context(
            [('table2', 'value', tq_types.INT),
             ('table2', 'value3', tq_types.INT)]
        )

        self.table3 = tinyquery.Table(
            'table3',
            0,
            collections.OrderedDict([
                ('value', context.Column(type=tq_types.INT,
                                         mode=tq_modes.NULLABLE, values=[])),
            ])
        )
        self.table3_type_ctx = self.make_type_context(
            [('table3', 'value', tq_types.INT)]
        )

        self.rainbow_table = tinyquery.Table(
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
                                                               3, 14, 8)]))]))
        self.rainbow_table_type_ctx = self.make_type_context(
            [('rainbow_table', 'ints', tq_types.INT),
             ('rainbow_table', 'floats', tq_types.FLOAT),
             ('rainbow_table', 'bools', tq_types.BOOL),
             ('rainbow_table', 'strings', tq_types.STRING),
             ('rainbow_table', 'times', tq_types.TIMESTAMP)]
        )

        self.record_table = tinyquery.Table(
            'record_table',
            0,
            collections.OrderedDict([
                ('r1.i', context.Column(type=tq_types.INT,
                                        mode=tq_modes.NULLABLE, values=[])),
                ('r1.s', context.Column(type=tq_types.STRING,
                                        mode=tq_modes.NULLABLE, values=[])),
                ('r2.i', context.Column(type=tq_types.INT,
                                        mode=tq_modes.NULLABLE, values=[])),
            ])
        )
        self.record_table_type_ctx = self.make_type_context(
            [('record_table', 'r1.i', tq_types.INT),
             ('record_table', 'r1.s', tq_types.STRING),
             ('record_table', 'r2.i', tq_types.INT)]
        )

        self.tables_by_name = {
            'table1': self.table1,
            'table2': self.table2,
            'table3': self.table3,
            'rainbow_table': self.rainbow_table,
            'record_table': self.record_table,
        }

    def assert_compiled_select(self, text, expected_ast):
        ast = compiler.compile_text(text, self.tables_by_name)
        self.assertEqual(expected_ast, ast)

    def assert_compile_error(self, text):
        self.assertRaises(exceptions.CompileError, compiler.compile_text,
                          text, self.tables_by_name)

    def make_type_context(self, table_column_type_triples,
                          implicit_column_context=None):
        return type_context.TypeContext.from_full_columns(
            collections.OrderedDict(
                ((table, column), col_type)
                for table, column, col_type in table_column_type_triples
            ), implicit_column_context)

    def test_compile_simple_select(self):
        self.assert_compiled_select(
            'SELECT value FROM table1',
            typed_ast.Select(
                [typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'value', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'value', tq_types.INT)],
                    self.make_type_context([('table1', 'value', tq_types.INT)])
                ))
        )

    def test_unary_operator(self):
        self.assert_compiled_select(
            'SELECT -5',
            typed_ast.Select(
                [typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_unary_op('-'),
                        [typed_ast.Literal(5, tq_types.INT)],
                        tq_types.INT),
                    'f0_', None
                )],
                typed_ast.NoTable(),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'f0_', tq_types.INT)],
                    self.make_type_context([]))
            )
        )

    def test_mistyped_unary_operator(self):
        with self.assertRaises(exceptions.CompileError) as context:
            compiler.compile_text('SELECT -strings FROM rainbow_table',
                                  self.tables_by_name)
        self.assertTrue('Invalid type for operator' in str(context.exception))

    def test_strange_arithmetic(self):
        try:
            compiler.compile_text('SELECT times + ints + floats + bools FROM '
                                  'rainbow_table', self.tables_by_name)
        except exceptions.CompileError:
            self.fail('Compiler exception on arithmetic across all numeric '
                      'types.')

    def test_mistyped_binary_operator(self):
        with self.assertRaises(exceptions.CompileError) as context:
            compiler.compile_text('SELECT ints CONTAINS strings FROM '
                                  'rainbow_table',
                                  self.tables_by_name)
        self.assertTrue('Invalid types for operator' in str(context.exception))

    def test_function_calls(self):
        self.assert_compiled_select(
            'SELECT ABS(-3), POW(2, 3), NOW()',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_func('abs'),
                        [typed_ast.FunctionCall(
                            runtime.get_unary_op('-'),
                            [typed_ast.Literal(3, tq_types.INT)],
                            tq_types.INT
                        )],
                        tq_types.INT),
                    'f0_', None),
                typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_func('pow'), [
                            typed_ast.Literal(2, tq_types.INT),
                            typed_ast.Literal(3, tq_types.INT)],
                        tq_types.INT
                    ),
                    'f1_', None
                ),
                typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_func('now'), [], tq_types.INT
                    ),
                    'f2_', None
                )],
                typed_ast.NoTable(),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context([
                    (None, 'f0_', tq_types.INT), (None, 'f1_', tq_types.INT),
                    (None, 'f2_', tq_types.INT)],
                    self.make_type_context([]))
            )
        )

    def test_mistyped_function_call(self):
        with self.assertRaises(exceptions.CompileError) as context:
            compiler.compile_text('SELECT SUM(strings) FROM rainbow_table',
                                  self.tables_by_name)
        self.assertTrue('Invalid types for function' in str(context.exception))

    def test_case(self):
        self.assert_compiled_select(
            'SELECT CASE WHEN TRUE THEN 1 WHEN FALSE THEN 2 END',
            typed_ast.Select(
                select_fields=[
                    typed_ast.SelectField(
                        typed_ast.FunctionCall(
                            runtime.get_func('if'),
                        [
                            typed_ast.Literal(True, tq_types.BOOL),
                            typed_ast.Literal(1, tq_types.INT),
                            typed_ast.FunctionCall(
                                runtime.get_func('if'),
                                [
                                    typed_ast.Literal(False, tq_types.BOOL),
                                    typed_ast.Literal(2, tq_types.INT),
                                    typed_ast.Literal(None, tq_types.NONETYPE),
                                ],
                                tq_types.INT)
                        ],
                        tq_types.INT),
                    'f0_', None)
                ],
                table=typed_ast.NoTable(),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=None,
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=None,
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'f0_', tq_types.INT)],
                    self.make_type_context([]))))

    def test_where(self):
        self.assert_compiled_select(
            'SELECT value FROM table1 WHERE value > 3',
            typed_ast.Select(
                [typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'value', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.FunctionCall(
                    runtime.get_binary_op('>'),
                    [typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                     typed_ast.Literal(3, tq_types.INT)],
                    tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'value', tq_types.INT)],
                    self.make_type_context(
                        [('table1', 'value', tq_types.INT)]))
            )
        )

    def test_having(self):
        self.assert_compiled_select(
            'SELECT value FROM table1 HAVING value > 3',
            typed_ast.Select(
                [typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'value', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.FunctionCall(
                    runtime.get_binary_op('>'),
                    [typed_ast.ColumnRef(None, 'value', tq_types.INT),
                     typed_ast.Literal(3, tq_types.INT)],
                    tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'value', tq_types.INT)],
                    self.make_type_context(
                        [('table1', 'value', tq_types.INT)]))
            )
        )

    def test_multiple_select(self):
        self.assert_compiled_select(
            'SELECT value * 3 AS foo, value, value + 1, value bar, value - 1 '
            'FROM table1',
            typed_ast.Select(
                [typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_binary_op('*'),
                        [typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                         typed_ast.Literal(3, tq_types.INT)],
                        tq_types.INT),
                    'foo', None),
                 typed_ast.SelectField(
                     typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                     'value', None),
                 typed_ast.SelectField(
                     typed_ast.FunctionCall(
                         runtime.get_binary_op('+'),
                         [typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                          typed_ast.Literal(1, tq_types.INT)],
                         tq_types.INT),
                     'f0_', None),
                 typed_ast.SelectField(
                     typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                     'bar', None),
                 typed_ast.SelectField(
                     typed_ast.FunctionCall(
                         runtime.get_binary_op('-'),
                         [typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                          typed_ast.Literal(1, tq_types.INT)],
                         tq_types.INT),
                     'f1_', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context([
                    (None, 'foo', tq_types.INT),
                    (None, 'value', tq_types.INT),
                    (None, 'f0_', tq_types.INT), (None, 'bar', tq_types.INT),
                    (None, 'f1_', tq_types.INT)],
                    self.make_type_context(
                        [('table1', 'value', tq_types.INT)]
                    ))
            )
        )

    def test_duplicate_aliases_not_allowed(self):
        self.assert_compile_error(
            'SELECT 0 AS foo, value foo FROM table1')

    def test_aggregates(self):
        self.assert_compiled_select(
            'SELECT MAX(value), MIN(value) FROM table1',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.AggregateFunctionCall(
                        runtime.get_func('max'),
                        [typed_ast.ColumnRef('table1', 'value', tq_types.INT)],
                        tq_types.INT
                    ),
                    'f0_', None),
                typed_ast.SelectField(
                    typed_ast.AggregateFunctionCall(
                        runtime.get_func('min'),
                        [typed_ast.ColumnRef('table1', 'value', tq_types.INT)],
                        tq_types.INT
                    ),
                    'f1_', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                typed_ast.GroupSet(set(), []),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context([
                    (None, 'f0_', tq_types.INT),
                    (None, 'f1_', tq_types.INT)],
                    self.make_type_context([]))))

    def mixed_aggregate_non_aggregate_not_allowed(self):
        self.assert_compile_error(
            'SELECT value, SUM(value) FROM table1')

    def mixed_aggregate_non_aggregate_single_field_not_allowed(self):
        self.assert_compile_error(
            'SELECT value + SUM(value) FROM table1')

    def test_group_by_alias(self):
        self.assert_compiled_select(
            'SELECT 0 AS foo FROM table1 GROUP BY foo',
            typed_ast.Select(
                [typed_ast.SelectField(
                    typed_ast.Literal(0, tq_types.INT), 'foo', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                typed_ast.GroupSet(
                    alias_groups={'foo'},
                    field_groups=[]
                ),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'foo', tq_types.INT)],
                    self.make_type_context([]))
            )
        )

    def test_group_by_field(self):
        self.assert_compiled_select(
            'SELECT SUM(value) FROM table1 GROUP BY value2',
            typed_ast.Select(
                [typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_func('sum'),
                        [typed_ast.ColumnRef('table1', 'value', tq_types.INT)],
                        tq_types.INT
                    ),
                    'f0_', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                typed_ast.GroupSet(
                    alias_groups=set(),
                    field_groups=[
                        typed_ast.ColumnRef('table1', 'value2', tq_types.INT)]
                ),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'f0_', tq_types.INT)],
                    self.make_type_context([]))
            ))

    def test_order_by_field(self):
        self.assert_compiled_select(
            'SELECT value FROM table1 ORDER BY value2 DESC',
            typed_ast.Select(
                select_fields=[typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'value', None)],
                table=typed_ast.Table('table1', self.table1_type_ctx),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=None,
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=[tq_ast.Ordering(tq_ast.ColumnId('value2'), False)],
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'value', tq_types.INT)],
                    self.make_type_context([('table1', 'value',
                                             tq_types.INT)]))
            ))

    def test_order_by_multiple_fields(self):
        self.assert_compiled_select(
            'SELECT value FROM table1 ORDER BY value2, value DESC',
            typed_ast.Select(
                select_fields=[typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'value', None)],
                table=typed_ast.Table('table1', self.table1_type_ctx),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=None,
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=[tq_ast.Ordering(tq_ast.ColumnId('value2'), True),
                           tq_ast.Ordering(tq_ast.ColumnId('value'), False)],
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'value', tq_types.INT)],
                    self.make_type_context([('table1', 'value', tq_types.INT)
                                            ]))
            ))

    def test_select_grouped_and_non_grouped_fields(self):
        self.assert_compiled_select(
            'SELECT value, SUM(value2) FROM table1 GROUP BY value',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'value', None),
                typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_func('sum'),
                        [typed_ast.ColumnRef('table1', 'value2',
                                             tq_types.INT)],
                        tq_types.INT),
                    'f0_', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                typed_ast.GroupSet(
                    alias_groups={'value'},
                    field_groups=[]
                ),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'value', tq_types.INT),
                     (None, 'f0_', tq_types.INT)],
                    self.make_type_context(
                        [('table1', 'value', tq_types.INT)]))
            )
        )

    def test_grouped_fields_require_aggregates(self):
        self.assert_compile_error(
            'SELECT value + 1 AS foo, foo FROM table1 GROUP BY foo')

    def test_select_multiple_tables(self):
        # Union of columns should be taken, with no aliases.
        unioned_type_ctx = self.make_type_context(
            [(None, 'value', tq_types.INT), (None, 'value2', tq_types.INT),
             (None, 'value3', tq_types.INT)])

        self.assert_compiled_select(
            'SELECT value, value2, value3 FROM table1, table2',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef(None, 'value', tq_types.INT),
                    'value', None),
                typed_ast.SelectField(
                    typed_ast.ColumnRef(None, 'value2', tq_types.INT),
                    'value2', None),
                typed_ast.SelectField(
                    typed_ast.ColumnRef(None, 'value3', tq_types.INT),
                    'value3', None)],
                typed_ast.TableUnion([
                    typed_ast.Table('table1', self.table1_type_ctx),
                    typed_ast.Table('table2', self.table2_type_ctx)],
                    unioned_type_ctx
                ),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'value', tq_types.INT),
                     (None, 'value2', tq_types.INT),
                     (None, 'value3', tq_types.INT)],
                    self.make_type_context(
                        [(None, 'value', tq_types.INT),
                         (None, 'value2', tq_types.INT),
                         (None, 'value3', tq_types.INT)]))
            )
        )

    def test_subquery(self):
        self.assert_compiled_select(
            'SELECT foo, foo + 1 FROM (SELECT value + 1 AS foo FROM table1)',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef(None, 'foo', tq_types.INT), 'foo',
                    None),
                typed_ast.SelectField(
                    typed_ast.FunctionCall(
                        runtime.get_binary_op('+'), [
                            typed_ast.ColumnRef(None, 'foo', tq_types.INT),
                            typed_ast.Literal(1, tq_types.INT)],
                        tq_types.INT),
                    'f0_', None
                )],
                typed_ast.Select(
                    [typed_ast.SelectField(
                        typed_ast.FunctionCall(
                            runtime.get_binary_op('+'), [
                                typed_ast.ColumnRef('table1', 'value',
                                                    tq_types.INT),
                                typed_ast.Literal(1, tq_types.INT)],
                            tq_types.INT),
                        'foo', None
                    )],
                    typed_ast.Table('table1', self.table1_type_ctx),
                    typed_ast.Literal(True, tq_types.BOOL),
                    None,
                    typed_ast.Literal(True, tq_types.BOOL),
                    None,
                    None,
                    self.make_type_context(
                        [(None, 'foo', tq_types.INT)],
                        self.make_type_context(
                            [('table1', 'value', tq_types.INT)]
                        ))
                ),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'foo', tq_types.INT), (None, 'f0_', tq_types.INT)],
                    self.make_type_context([(None, 'foo', tq_types.INT)]))
            )
        )

    def test_table_aliases(self):
        self.assert_compiled_select(
            'SELECT t.value FROM table1 t',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef('t', 'value', tq_types.INT),
                    't.value', None)],
                typed_ast.Table('table1', self.make_type_context(
                    [('t', 'value', tq_types.INT),
                     ('t', 'value2', tq_types.INT)])),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 't.value', tq_types.INT)],
                    self.make_type_context(
                        [('t', 'value', tq_types.INT)]
                    ))
            )
        )

    def test_implicitly_accessed_column(self):
        self.assert_compiled_select(
            'SELECT table1.value FROM (SELECT value + 1 AS foo FROM table1)',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'table1.value', None)],
                typed_ast.Select([
                    typed_ast.SelectField(
                        typed_ast.FunctionCall(
                            runtime.get_binary_op('+'), [
                                typed_ast.ColumnRef('table1', 'value',
                                                    tq_types.INT),
                                typed_ast.Literal(1, tq_types.INT)
                            ],
                            tq_types.INT
                        ),
                        'foo', None)],
                    typed_ast.Table('table1', self.table1_type_ctx),
                    typed_ast.Literal(True, tq_types.BOOL),
                    None,
                    typed_ast.Literal(True, tq_types.BOOL),
                    None,
                    None,
                    self.make_type_context(
                        [(None, 'foo', tq_types.INT)],
                        self.make_type_context(
                            [('table1', 'value', tq_types.INT)]))),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'table1.value', tq_types.INT)],
                    self.make_type_context(
                        [('table1', 'value', tq_types.INT)]
                    )))
        )

    def test_subquery_aliases(self):
        self.assert_compiled_select(
            'SELECT t.value FROM (SELECT value FROM table1) t',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef('t', 'value', tq_types.INT),
                    't.value', None)],
                typed_ast.Select([
                    typed_ast.SelectField(
                        typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                        'value', None)],
                    typed_ast.Table('table1', self.table1_type_ctx),
                    typed_ast.Literal(True, tq_types.BOOL),
                    None,
                    typed_ast.Literal(True, tq_types.BOOL),
                    None,
                    None,
                    self.make_type_context(
                        [(None, 'value', tq_types.INT)],
                        self.make_type_context(
                            [('t', 'value', tq_types.INT)]))
                ),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 't.value', tq_types.INT)],
                    self.make_type_context(
                        [('t', 'value', tq_types.INT)]))
            )
        )

    def test_simple_join(self):
        self.assert_compiled_select(
            'SELECT value2 '
            'FROM table1 t1 JOIN table2 t2 ON t1.value = t2.value',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef('t1', 'value2', tq_types.INT),
                    'value2', None
                )],
                typed_ast.Join(
                    typed_ast.Table('table1',
                                    self.make_type_context([
                                        ('t1', 'value', tq_types.INT),
                                        ('t1', 'value2', tq_types.INT),
                                    ])),
                    [(typed_ast.Table('table2',
                                      self.make_type_context([
                                          ('t2', 'value', tq_types.INT),
                                          ('t2', 'value3', tq_types.INT),
                                      ])),
                      tq_ast.JoinType.INNER)],
                    [[typed_ast.JoinFields(
                        typed_ast.ColumnRef('t1', 'value', tq_types.INT),
                        typed_ast.ColumnRef('t2', 'value', tq_types.INT)
                    )]],
                    self.make_type_context([
                        ('t1', 'value', tq_types.INT),
                        ('t1', 'value2', tq_types.INT),
                        ('t2', 'value', tq_types.INT),
                        ('t2', 'value3', tq_types.INT),
                    ])
                ),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context(
                    [(None, 'value2', tq_types.INT)],
                    self.make_type_context([('t1', 'value2', tq_types.INT)])
                )
            )
        )

    def test_join_multiple_fields(self):
        self.assert_compiled_select(
            'SELECT 0 '
            'FROM table1 t1 JOIN table2 t2 '
            'ON t1.value == t2.value AND t2.value3 = t1.value2',
            typed_ast.Select(
                select_fields=[
                    typed_ast.SelectField(
                        typed_ast.Literal(0, tq_types.INT), 'f0_', None)],
                table=typed_ast.Join(
                    base=typed_ast.Table('table1',
                                         self.make_type_context([
                                             ('t1', 'value', tq_types.INT),
                                             ('t1', 'value2', tq_types.INT),
                                         ])),
                    tables=[
                        (typed_ast.Table(
                            'table2',
                            self.make_type_context([
                                ('t2', 'value', tq_types.INT),
                                ('t2', 'value3', tq_types.INT),
                            ])),
                         tq_ast.JoinType.INNER)],
                    conditions=[[
                        typed_ast.JoinFields(
                            typed_ast.ColumnRef('t1', 'value', tq_types.INT),
                            typed_ast.ColumnRef('t2', 'value', tq_types.INT)
                        ), typed_ast.JoinFields(
                            typed_ast.ColumnRef('t1', 'value2', tq_types.INT),
                            typed_ast.ColumnRef('t2', 'value3', tq_types.INT)
                        )]],
                    type_ctx=self.make_type_context([
                        ('t1', 'value', tq_types.INT),
                        ('t1', 'value2', tq_types.INT),
                        ('t2', 'value', tq_types.INT),
                        ('t2', 'value3', tq_types.INT),
                    ])
                ),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=None,
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=None,
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'f0_', tq_types.INT)],
                    self.make_type_context([]))
            )
        )

    def test_multi_way_join(self):
        self.assert_compiled_select(
            'SELECT 0 '
            'FROM table1 t1 JOIN table2 t2 ON t1.value = t2.value '
            'LEFT JOIN table3 t3 ON t2.value3 = t3.value',
            typed_ast.Select(
                select_fields=[
                    typed_ast.SelectField(
                        typed_ast.Literal(0, tq_types.INT), 'f0_', None)],
                table=typed_ast.Join(
                    base=typed_ast.Table('table1',
                                         self.make_type_context([
                                             ('t1', 'value', tq_types.INT),
                                             ('t1', 'value2', tq_types.INT),
                                         ])),
                    tables=[
                        (typed_ast.Table(
                            'table2',
                            self.make_type_context([
                                ('t2', 'value', tq_types.INT),
                                ('t2', 'value3', tq_types.INT),
                            ])),
                         tq_ast.JoinType.INNER),
                        (typed_ast.Table(
                            'table3',
                            self.make_type_context([
                                ('t3', 'value', tq_types.INT)
                            ])),
                         tq_ast.JoinType.LEFT_OUTER
                         )],
                    conditions=[
                        [typed_ast.JoinFields(
                            typed_ast.ColumnRef('t1', 'value', tq_types.INT),
                            typed_ast.ColumnRef('t2', 'value', tq_types.INT)
                        )], [typed_ast.JoinFields(
                            typed_ast.ColumnRef('t2', 'value3', tq_types.INT),
                            typed_ast.ColumnRef('t3', 'value', tq_types.INT)
                        )]],
                    type_ctx=self.make_type_context([
                        ('t1', 'value', tq_types.INT),
                        ('t1', 'value2', tq_types.INT),
                        ('t2', 'value', tq_types.INT),
                        ('t2', 'value3', tq_types.INT),
                        ('t3', 'value', tq_types.INT),
                    ])
                ),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=None,
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=None,
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'f0_', tq_types.INT)],
                    self.make_type_context([]))
            )
        )

    def test_select_star(self):
        self.assert_compiled_select(
            'SELECT * FROM table1',
            typed_ast.Select([
                typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value', tq_types.INT),
                    'value', None),
                typed_ast.SelectField(
                    typed_ast.ColumnRef('table1', 'value2', tq_types.INT),
                    'value2', None)],
                typed_ast.Table('table1', self.table1_type_ctx),
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                typed_ast.Literal(True, tq_types.BOOL),
                None,
                None,
                self.make_type_context([
                    (None, 'value', tq_types.INT),
                    (None, 'value2', tq_types.INT)],
                    self.make_type_context([
                        ('table1', 'value', tq_types.INT),
                        ('table1', 'value2', tq_types.INT)]))))

    def test_select_record(self):
        self.assert_compiled_select(
            'SELECT r1.s FROM record_table',
            typed_ast.Select(
                select_fields=[
                    typed_ast.SelectField(
                        typed_ast.ColumnRef('record_table', 'r1.s',
                                            tq_types.STRING),
                        'r1.s', None)],
                table=typed_ast.Table('record_table',
                                      self.record_table_type_ctx),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=None,
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=None,
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'r1.s', tq_types.STRING)],
                    self.make_type_context([
                        ('record_table', 'r1.s', tq_types.STRING)]))))

    def test_record_star(self):
        self.assert_compiled_select(
            'SELECT r1.* FROM record_table',
            typed_ast.Select(
                select_fields=[
                    typed_ast.SelectField(
                        typed_ast.ColumnRef('record_table', 'r1.i',
                                            tq_types.INT),
                        'r1.i', None),
                    typed_ast.SelectField(
                        typed_ast.ColumnRef('record_table', 'r1.s',
                                            tq_types.STRING),
                        'r1.s', None),
                ],
                table=typed_ast.Table('record_table',
                                      self.record_table_type_ctx),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=None,
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=None,
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'r1.i', tq_types.INT),
                     (None, 'r1.s', tq_types.STRING)],
                    self.make_type_context([
                        ('record_table', 'r1.i', tq_types.INT),
                        ('record_table', 'r1.s', tq_types.STRING)]))))

    def test_within_record(self):
        self.assert_compiled_select(
            'SELECT r1.s, COUNT(r1.s) WITHIN RECORD AS num_s_in_r1 '
            'FROM record_table',
            typed_ast.Select(
                select_fields=[
                    typed_ast.SelectField(
                        typed_ast.ColumnRef('record_table', 'r1.s',
                                            tq_types.STRING),
                        'r1.s', None),
                    typed_ast.SelectField(typed_ast.FunctionCall(
                        runtime.get_func('count'),
                        [typed_ast.ColumnRef('record_table', 'r1.s',
                                             tq_types.STRING)],
                        tq_types.INT
                    ), 'num_s_in_r1', 'RECORD')],
                table=typed_ast.Table('record_table',
                                      self.record_table_type_ctx),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=typed_ast.GroupSet(set(), []),
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=None,
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'r1.s', tq_types.STRING),
                     (None, 'num_s_in_r1', tq_types.INT)],
                    self.make_type_context([]))))

    def test_within_clause(self):
        self.assert_compiled_select(
            'SELECT r1.s, COUNT(r1.s) WITHIN r1 AS num_s_in_r1 '
            'FROM record_table',
            typed_ast.Select(
                select_fields=[
                    typed_ast.SelectField(
                        typed_ast.ColumnRef('record_table', 'r1.s',
                                            tq_types.STRING),
                        'r1.s', None),
                    typed_ast.SelectField(typed_ast.FunctionCall(
                        runtime.get_func('count'),
                        [typed_ast.ColumnRef('record_table', 'r1.s',
                                             tq_types.STRING)],
                        tq_types.INT
                    ), 'num_s_in_r1', 'r1')],
                table=typed_ast.Table('record_table',
                                      self.record_table_type_ctx),
                where_expr=typed_ast.Literal(True, tq_types.BOOL),
                group_set=typed_ast.GroupSet(set(), []),
                having_expr=typed_ast.Literal(True, tq_types.BOOL),
                orderings=None,
                limit=None,
                type_ctx=self.make_type_context(
                    [(None, 'r1.s', tq_types.STRING),
                     (None, 'num_s_in_r1', tq_types.INT)],
                    self.make_type_context([]))))

    def test_within_clause_error(self):
        with self.assertRaises(exceptions.CompileError) as context:
            compiler.compile_text(
                'SELECT r1.s, COUNT(r1.s) WITHIN r2 AS '
                'num_s_in_r1 FROM record_table',
                self.tables_by_name)
            self.assertTrue('WITHIN clause syntax error' in
                            str(context.exception))
