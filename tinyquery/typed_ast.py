"""A set of AST classes with types and aliases filled in."""
from __future__ import absolute_import

import collections

from tinyquery import tq_modes


class Select(collections.namedtuple(
        'Select', ['select_fields', 'table', 'where_expr', 'group_set',
                   'having_expr', 'orderings', 'limit', 'type_ctx'])):
    """A compiled query.

    Fields:
        select_fields: A list of SelectField, one for each item being selected.
        table: The table expression to select from.
        where_expr: A filter to apply on the selected table expression. Note
            that this filter should always be valid; if the user didn't specify
            a WHERE clause, this is the literal true.
        group_set: Either None, indicating that no grouping should be done, or
            a GroupSet object. If there were groups explicitly specified by
            GROUP BY, then the GroupSet always exists and is nonempty. If there
            was no GROUP BY but the select is an aggregate select, the GroupSet
            exists and is empty (since grouping by nothing puts everything into
            the same group).
        having_expr: A filter to apply on the result of the select expresion.
            Note that this filter should always be valid; if the user didn't
            specify a HAVING clause, this is the literal true.
        orderings: Either None, indicating that no ordering should be done, or
            an OrderBySet object. If there were ordering instances explicitly
            specified by ORDER BY, then the OrderBySet always exists and is
            nonempty.
        limit: Either a number with the number of rows to limit the results to,
            or None if there is no limit.
        type_ctx: A type context describing the names and types of the fields
            returned from this select clause.

    """
    def with_type_ctx(self, type_ctx):
        return Select(self.select_fields, self.table, self.where_expr,
                      self.group_set, self.having_expr, self.orderings,
                      self.limit, type_ctx)


class SelectField(collections.namedtuple('SelectField', ['expr', 'alias',
                                                         'within_clause'])):
    pass


class GroupSet(collections.namedtuple(
        'GroupSet', ['alias_groups', 'field_groups'])):
    """Information about the groups to use for a query.

    Fields:
        alias_groups: A set of string names of aliases for select fields that
            we should group by. These are special because they need to be
            compiled and evaluated differently from normal select fields.
        field_groups: A list of ColumnRefs referencing columns in the table
            expression of the SELECT statement.
    """
# This special GroupSet means "group by nothing". In other words, everything
# should end up in the same group (which happens when an aggregate function is
# used, but no GROUP BY groups are specified explicitly). It's almost enough to
# just omit all alias and field groups, but we also need to make sure that we
# include the group even if there are no rows in the table being selected.
TRIVIAL_GROUP_SET = GroupSet(set(), [])


class TableExpression(object):
    """Abstract class for all table expression ASTs."""
    def __init__(self, *_, **__):
        assert hasattr(self, 'type_ctx')


class NoTable(collections.namedtuple('NoTable', []), TableExpression):
    @property
    def type_ctx(self):
        from tinyquery import type_context  # To avoid circular import
        return type_context.TypeContext.from_full_columns(
            collections.OrderedDict())


class Table(collections.namedtuple('Table', ['name', 'type_ctx']),
            TableExpression):
    def with_type_ctx(self, type_ctx):
        return Table(self.name, type_ctx)


class TableUnion(collections.namedtuple('TableUnion', ['tables', 'type_ctx']),
                 TableExpression):
    pass


class Join(collections.namedtuple('Join', ['base', 'tables', 'conditions',
                                           'type_ctx']),
           TableExpression):
    """Table expression for a join operation.

    Fields:
        base: A table expression on the left side of the join
        tables: A list of (table expression, join type) tuples.
        conditions: A list of JoinFields objects, each of which specifies a
            field from one of the tables joined on a field from another of the
            tables.
        type_ctx: The resulting type context.
    """


class JoinFields(collections.namedtuple('JoinFields', ['column1', 'column2'])):
    """A single pair of fields to join on.

    Fields:
        column1: A ColumnRef referencing table1.
        column2: A ColumnRef referencing table2.
    """


class Expression(object):
    """Abstract interface for all expression ASTs."""
    def __init__(self, *args):
        assert hasattr(self, 'type')


class FunctionCall(collections.namedtuple(
        'FunctionCall', ['func', 'args', 'type']), Expression):
    """Expression representing a call to a built-in function.

    Fields:
        func: A runtime.Function for the function to call.
        args: A list of expressions to pass in as the function's arguments.
        type: The result type of the expression.
    """


class AggregateFunctionCall(collections.namedtuple(
        'AggregateFunctionCall', ['func', 'args', 'type']), Expression):
    """Expression representing a call to a built-in aggregate function.

    Aggregate functions are called differently from regular functions, so we
    need to have a special case for them in the AST format.

    Fields:
        func: A runtime.Function for the function to call.
        args: A list of expressions to pass in as the function's arguments.
        type: The result type of the expression.
    """


class Literal(collections.namedtuple(
        'Literal', ['value', 'type']), Expression):
    pass


class ColumnRef(collections.namedtuple(
        'ColumnRef', ['table', 'column', 'type', 'mode']), Expression):
    """References a column from the current context."""


ColumnRef.__new__.__defaults__ = (tq_modes.NULLABLE,)
