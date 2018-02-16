from __future__ import absolute_import

import collections
import re

from tinyquery import exceptions
from tinyquery import tq_types
from tinyquery import typed_ast


# TODO(Samantha): Should checking modes go here?


class TypeContext(collections.namedtuple(
        'TypeContext', ['columns', 'aliases', 'ambig_aliases',
                        'implicit_column_context', 'aggregate_context'])):
    """Defines the set of valid fields in a point in code, and their types.

    Type contexts maintain the order of their fields, which isn't needed for
    typical evaluation, but is useful in a few cases, such as SELECT * and when
    determining the final names to use for a query result.

    Fields:
        columns: An OrderedDict mapping from (table name, column name) to type.
        aliases: A dict mapping any allowed aliases to their (table, column)
            pair. For example, the "value" column on a table "table" has full
            name "table.value" but the alias "value" also refers to it (as long
            as there are no other tables with a column named "value").
        ambig_aliases: A set of aliases that cannot be used because they are
            ambiguous.
        implicit_column_context: If present, a set of columns that are allowed
            to be accessed, but aren't part of the "regular" context. For
            example, if the expression "value + 1" is used in a subquery, the
            outer query can use "value".
        aggregate_context: Either None, indicating that aggregates are not
            allowed, or a TypeContext to use if we enter into an aggregate.
    """
    @classmethod
    def from_table_and_columns(cls, table_name, columns_without_table,
                               implicit_column_context=None,
                               aggregate_context=None):
        return cls.from_full_columns(
            collections.OrderedDict(
                ((table_name, column_name), col_type)
                for column_name, col_type
                in columns_without_table.items()),
            implicit_column_context, aggregate_context)

    @staticmethod
    def assert_type(value, expected_type):
        assert isinstance(value, expected_type), (
            'Expected %s to have type %s, but was %s.' % (
                value, expected_type, type(value)))

    @classmethod
    def from_full_columns(cls, full_columns, implicit_column_context=None,
                          aggregate_context=None):
        """Given just the columns field, fill in alias information."""
        for (table_name, col_name), col_type in full_columns.items():
            if table_name is not None:
                cls.assert_type(table_name, tq_types.STRING_TYPE)
            cls.assert_type(col_name, tq_types.STRING_TYPE)
            cls.assert_type(col_type, tq_types.TYPE_TYPE)

        aliases = {}
        ambig_aliases = set()
        for table_name, column_name in full_columns:
            if column_name in ambig_aliases:
                continue
            elif column_name in aliases:
                del aliases[column_name]
                ambig_aliases.add(column_name)
            else:
                aliases[column_name] = (table_name, column_name)
        return cls(full_columns, aliases, ambig_aliases,
                   implicit_column_context, aggregate_context)

    @classmethod
    def union_contexts(cls, contexts):
        """Creates a type context from the union of others.

        This follows the semantics of the comma operator:
        -Columns are added in order, and columns already added from previous
            tables are kept in their original place.
        -All fully-qualified names are removed; columns can only be referenced
            by their direct names.
        TODO: Do better error handling with things like conflicting types.
        """
        result_columns = collections.OrderedDict()
        for context in contexts:
            assert context.aggregate_context is None

            for (_, column_name), col_type in context.columns.items():
                full_column = (None, column_name)
                if full_column in result_columns:
                    if result_columns[full_column] == col_type:
                        continue
                    raise exceptions.CompileError(
                        'Incompatible types when performing union on field '
                        '{}: {} vs. {}'.format(full_column,
                                               result_columns[full_column],
                                               col_type))
                else:
                    result_columns[full_column] = col_type
        return cls.from_full_columns(result_columns)

    @classmethod
    def join_contexts(cls, contexts):
        result_columns = collections.OrderedDict()
        for context in contexts:
            result_columns.update(context.columns)
        return cls.from_full_columns(result_columns)

    def column_ref_for_name(self, name):
        """Gets the full identifier for a column from any possible alias."""
        if name in self.columns:
            return typed_ast.ColumnRef(name, self.columns[name])

        possible_results = []

        # Try all possible ways of splitting a dot-separated string.
        for match in re.finditer('\.', name):
            left_side = name[:match.start()]
            right_side = name[match.end():]
            result_type = self.columns.get((left_side, right_side))
            if result_type is not None:
                possible_results.append(
                    typed_ast.ColumnRef(left_side, right_side, result_type))

        if name in self.aliases:
            table, column = self.aliases[name]
            result_type = self.columns[(table, column)]
            possible_results.append(
                typed_ast.ColumnRef(table, column, result_type))

        if len(possible_results) == 1:
            return possible_results[0]
        elif len(possible_results) > 1:
            raise exceptions.CompileError('Ambiguous field: {}'.format(name))
        else:
            if self.implicit_column_context is not None:
                return self.implicit_column_context.column_ref_for_name(name)
            else:
                raise exceptions.CompileError('Field not found: {}'.format(name))

    def context_with_subquery_alias(self, subquery_alias):
        """Handle the case where a subquery has an alias.

        In this case, it looks like the right approach is to only assign the
        alias to the implicit column context, not the full context.
        """
        if self.implicit_column_context is None:
            return self
        new_implicit_column_context = TypeContext.from_full_columns(
            collections.OrderedDict(
                ((subquery_alias, col_name), col_type)
                for (_, col_name), col_type
                in self.implicit_column_context.columns.items()
            )
        )
        return TypeContext(self.columns, self.aliases, self.ambig_aliases,
                           new_implicit_column_context, self.aggregate_context)

    def context_with_full_alias(self, alias):
        assert self.aggregate_context is None
        new_columns = collections.OrderedDict(
            ((alias, col_name), col_type)
            for (_, col_name), col_type in self.columns.items()
        )
        if self.implicit_column_context:
            new_implicit_column_context = (
                self.implicit_column_context.context_with_full_alias(alias))
        else:
            new_implicit_column_context = None
        return TypeContext.from_full_columns(new_columns,
                                             new_implicit_column_context)
