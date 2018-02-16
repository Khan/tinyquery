"""A set of AST classes that correspond to the code.

This AST format is desinged to be easy to parse into. See typed_ast for the AST
format that is used during the evaluation step.
"""
from __future__ import absolute_import

import collections


class Select(collections.namedtuple(
        'Select', ['select_fields', 'table_expr', 'where_expr', 'groups',
                   'having_expr', 'orderings', 'limit', 'alias'])):
    """Represents a top-level select statement.

    Fields:
        select_fields: A list of SelectField objects.
        table_expr: A table expression referring to the data to select from, or
            None if there is no table specified.
        where_expr: An expression for the WHERE filter, or None if there is
            no WHERE filter.
        groups: A list of strings for fields to group by, or None if there is
            no GROUP BY clause.
        having_expr: An expression for the HAVING filter, or None if there is
            no HAVING filter.
        orderings: A list of Ordering instances, or None if there was no
            ORDER BY clause.
        limit: An integer limit
        alias: For subqueries, a name given to the subquery, or None if no name
            was given (or if this is an outermost query).
    """
    def __str__(self):
        result = 'SELECT {}'.format(
            ', '.join([str(field) for field in self.select_fields]))
        if self.table_expr:
            result += ' FROM {}'.format(self.table_expr)
        if self.where_expr:
            result += ' WHERE {}'.format(self.where_expr)
        if self.groups:
            result += ' GROUP BY {}'.format(
                ', '.join(str(group) for group in self.groups))
        if self.having_expr:
            result += ' HAVING {}'.format(self.having_expr)
        if self.orderings:
            result += ' ORDER BY {}'.format(
                ', '.join(str(ordering) for ordering in self.orderings))
        if self.limit:
            result += ' LIMIT {}'.format(self.limit)
        return result


class SelectField(collections.namedtuple('SelectField', ['expr', 'alias',
                                                         'within_record'])):
    def __str__(self):
        if self.alias is not None:
            if self.within_record is not None:
                return '{} WITHIN {} AS {}'.format(
                    self.expr, self.within_record, self.alias)
            else:
                return '{} AS {}'.format(self.expr, self.alias)
        else:
            return str(self.expr)


class Star(collections.namedtuple('Star', [])):
    def __str__(self):
        return '*'


class UnaryOperator(collections.namedtuple(
        'UnaryOperator', ['operator', 'expr'])):
    def __str__(self):
        return '({}{})'.format(self.operator, self.expr)


class BinaryOperator(collections.namedtuple(
        'BinaryOperator', ['operator', 'left', 'right'])):
    def __str__(self):
        return '({}{}{})'.format(self.left, self.operator, self.right)


class FunctionCall(collections.namedtuple('FunctionCall', ['name', 'args'])):
    def __str__(self):
        return '({}({}))'.format(self.name, self.args)


class Literal(collections.namedtuple('Literal', ['value'])):
    def __str__(self):
        return str(self.value)


class ColumnId(collections.namedtuple('ColumnId', ['name'])):
    def __str__(self):
        return self.name


class Ordering(collections.namedtuple('Ordering',
                                      ['column_id', 'is_ascending'])):
    def __str__(self):
        if self.is_ascending:
            return '{} ASC'.format(self.column_id)
        else:
            return '{} DESC'.format(self.column_id)


class TableId(collections.namedtuple('TableId', ['name', 'alias'])):
    """Table expression referencing a table to select from.

    Fields:
        name: The name of the table to select from.
        alias: An alias to assign to use for this table, or None if no alias
            was specified.
    """
    def __str__(self):
        return self.name


class TableUnion(collections.namedtuple('TableUnion', ['tables'])):
    """Table expression for a union of tables (the comma operator).

    The tables can be arbitrary table expressions.
    """
    def __str__(self):
        return ', '.join(str(table) for table in self.tables)


class JoinType(object):
    """A namespace for holding constants for different types of join.

    TODO(colin): if/when running python 3.5+ replace with an enum.
    """
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '%s JOIN' % self.name

JoinType.LEFT_OUTER = JoinType('LEFT OUTER')
JoinType.INNER = JoinType('INNER')
JoinType.CROSS = JoinType('CROSS')


class PartialJoin(collections.namedtuple('PartialJoin',
                                         ['table_expr', 'join_type',
                                          'condition'])):
    """Expression for the right side of a join, its type, and condition.

    This represents something like `LEFT JOIN [dataset.table] ON x = y`
    """
    def __str__(self):
        if self.join_type is JoinType.CROSS:
            return '%s %s' % (self.join_type, self.table_expr)
        else:
            return '%s %s ON %s' % (
                self.join_type, self.table_expr, self.condition)


class Join(collections.namedtuple('Join', ['base', 'join_parts'])):
    """Expression for a join of two or more tables.

    base is the expression in the leftmost part of the join
    join_parts is an array of one or more `PartialJoin`s
    """
    def __str__(self):
        return '%s %s' % (self.base,
                          ' '.join(str(part) for part in self.join_parts))


class CaseClause(collections.namedtuple('CaseClause',
                                        ['condition', 'result_expr'])):
    """Expression for a single clause from a CASE / WHEN / END statement.

    ELSE is just expressed as a final WHEN with a condition of TRUE.
    """
    def __str__(self):
        return 'WHEN {} THEN {}'.format(self.condition, self.result_expr)


class CaseExpression(collections.namedtuple('CaseExpression', ['clauses'])):
    """Case expression with one or more WHEN clauses and optional ELSE."""
    def __str__(self):
        return 'CASE {} END'.format(
            ' '.join(str(clause) for clause in self.clauses))
