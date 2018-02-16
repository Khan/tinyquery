"""A context is similar to a table, but doesn't have a specific name.

It is the basic container for intermediate data when evaluating a query.
"""
from __future__ import absolute_import

import collections
import itertools
import logging

import six

from tinyquery import repeated_util
from tinyquery import tq_modes


class Context(object):
    """Represents the columns accessible when evaluating an expression.

    Fields:
        num_rows: The number of rows for all columns in this context.
        columns: An OrderedDict from (table_name, column_name) name to Column.
            The table_name can be None. These should match the values in the
            corresponding TypeContext.
        aggregate_context: Either None, indicating that aggregate functions
            aren't allowed, or another Context to use whenever we enter into an
            aggregate function.
    """
    def __init__(self, num_rows, columns, aggregate_context):
        assert isinstance(columns, collections.OrderedDict)
        for (table_name, col_name), column in columns.items():
            assert len(column.values) == num_rows, (
                'Column %s had %s rows, expected %s.' % (
                    (table_name, col_name), len(column.values), num_rows))
        if aggregate_context is not None:
            assert isinstance(aggregate_context, Context)
        self.num_rows = num_rows
        self.columns = columns
        self.aggregate_context = aggregate_context

    def column_from_ref(self, column_ref):
        """Given a ColumnRef, return the corresponding column."""
        return self.columns[(column_ref.table, column_ref.column)]

    def __repr__(self):
        return 'Context({}, {}, {})'.format(self.num_rows, self.columns,
                                            self.aggregate_context)

    def __eq__(self, other):
        return ((self.num_rows, self.columns, self.aggregate_context) ==
                (other.num_rows, other.columns, other.aggregate_context))

    def __hash__(self):
        return hash((
            self.num_rows,
            tuple(tuple(column.values) for column in self.columns.values()),
            self.aggregate_context))


class Column(collections.namedtuple('Column', ['type', 'mode', 'values'])):
    """Represents a single column of data.

    Fields:
        type: A constant from the tq_types module.
        values: A list of raw values for the column contents.
    """


def context_from_table(table, type_context):
    """Given a table and a type context, build a context with those values.

    The order of the columns in the type context must match the order of the
    columns in the table.
    """
    any_column = table.columns[next(iter(table.columns))]
    new_columns = collections.OrderedDict([
        (column_name, column)
        for (column_name, column) in zip(type_context.columns,
                                         table.columns.values())
    ])
    return Context(len(any_column.values), new_columns, None)


def context_with_overlayed_type_context(context, type_context):
    """Given a context, use the given type context for all column names."""
    any_column = context.columns[next(iter(context.columns))]
    new_columns = collections.OrderedDict([
        (column_name, column)
        for (column_name, column) in zip(type_context.columns,
                                         context.columns.values())
    ])
    return Context(len(any_column.values), new_columns, None)


def empty_context_from_type_context(type_context):
    assert type_context.aggregate_context is None
    result_columns = collections.OrderedDict(
        # TODO(Samantha): Fix this. Mode is not always nullable
        (col_name, Column(type=col_type, mode=tq_modes.NULLABLE, values=[]))
        for col_name, col_type in type_context.columns.items()
    )
    return Context(0, result_columns, None)


def mask_context(context, mask):
    """Apply a row filter to a given context.

    Arguments:
        context: A Context to filter.
        mask: A column of type bool. Each row in this column should be True if
            the row should be kept for the whole context and False otherwise.
    """
    assert context.aggregate_context is None, (
        'Cannot mask a context with an aggregate context.')
    # If the mask column is repeated, we need to handle it specially.
    # There's several possibilities here, which are described inline.
    # TODO(colin): these have the same subtle differences from bigquery's
    # behavior as function evaluation on repeated fields.  Fix.
    if mask.mode == tq_modes.REPEATED:
        num_rows = len(
            [r for r in (any(row) for row in mask.values) if r]
        )
        new_columns = collections.OrderedDict()
        for col_name, col in context.columns.items():
            if col.mode == tq_modes.REPEATED:
                allowable = True
                new_values = []
                for mask_row, col_row in zip(mask.values, col.values):
                    if not any(mask_row):
                        # No matter any of the other conditions, if there's no
                        # truthy values in the mask in a row we want to skip
                        # the whole row.
                        continue
                    if len(mask_row) == 1:
                        # We already know this single value is truthy, or else
                        # we'd have matched the previous block.  Just pass on
                        # the whole row in this case.
                        new_values.append(
                            repeated_util.normalize_repeated_null(col_row))
                    elif len(mask_row) == len(col_row):
                        # As for function evaluation, when the number of values
                        # in a row matches across columns, we match them up
                        # individually.
                        new_values.append(
                            repeated_util.normalize_repeated_null(
                                list(itertools.compress(col_row, mask_row))))
                    elif len(col_row) in (0, 1):
                        # If the column has 0 or 1 values, we need to fill out
                        # to the length of the mask.
                        norm_row = repeated_util.normalize_column_to_length(
                            col_row, len(mask_row))
                        new_values.append(
                            repeated_util.normalize_repeated_null(
                                list(itertools.compress(norm_row, mask_row))))
                    else:
                        # If none of these conditions apply, we can't match up
                        # the number of values in the mask and a column.  This
                        # *may* be ok, since at this point this might be a
                        # column that we're not going to select in the final
                        # result anyway.  In this case, since we can't do
                        # anything sensible, we're going to discard it from the
                        # output.  Since this is a little unexpected, we log a
                        # warning too.  This is preferable to leaving it in,
                        # since a missing column will be a hard error, but one
                        # with a strange number of values might allow a
                        # successful query that just does something weird.
                        allowable = False
                        break
                if not allowable:
                    logging.warn(
                        'Ignoring unselectable repeated column %s' % (
                            col_name,))
                    continue
            else:
                # For non-repeated columns, we retain the row if any of the
                # items in the mask will be retained.
                new_values = list(itertools.compress(
                    col.values,
                    (any(mask_row) for mask_row in mask.values)))

            new_columns[col_name] = Column(
                type=col.type,
                mode=col.mode,
                values=new_values)
    else:
        orig_column_values = [
            col.values for col in context.columns.values()]
        mask_values = mask.values
        num_rows = len([v for v in mask.values if v])
        new_values = [
            Column(
                type=col.type,
                mode=col.mode,
                values=list(itertools.compress(values, mask_values)))
            for col, values in zip(context.columns.values(),
                                   orig_column_values)]
        new_columns = collections.OrderedDict([
            (name, col) for name, col in zip(context.columns,
                                             new_values)])

    return Context(
        num_rows,
        new_columns,
        None)


def empty_context_from_template(context):
    """Returns a new context that has the same columns as the given context."""
    return Context(
        num_rows=0,
        columns=collections.OrderedDict(
            (name, empty_column_from_template(column))
            for name, column in context.columns.items()
        ),
        aggregate_context=None)


def empty_column_from_template(column):
    """Returns a new empty column with the same type as the given one."""
    return Column(type=column.type, mode=column.mode, values=[])


def append_row_to_context(src_context, index, dest_context):
    """Take row i from src_context and append it to dest_context.

    The schemas of the two contexts must match.
    """
    dest_context.num_rows += 1
    for name, column in dest_context.columns.items():
        column.values.append(src_context.columns[name].values[index])


def append_partial_context_to_context(src_context, dest_context):
    """Modifies dest_context to include all rows in src_context.

    The schemas don't need to match exactly; src_context just needs to have a
    subset, and all other columns will be given a null value.

    Also, it is assumed that the destination context only uses short column
    names rather than fully-qualified names.
    """
    dest_context.num_rows += src_context.num_rows
    # Ignore fully-qualified names for this operation.
    short_named_src_column_values = {
        col_name: column.values
        for (_, col_name), column in src_context.columns.items()}

    for (_, col_name), dest_column in dest_context.columns.items():
        src_column_values = short_named_src_column_values.get(col_name)
        if src_column_values is None:
            dest_column.values.extend([None] * src_context.num_rows)
        else:
            dest_column.values.extend(src_column_values)


def append_context_to_context(src_context, dest_context):
    """Adds all rows in src_context to dest_context.

    The columns must be a subset, but all fully-qualified names are taken into
    account.
    """
    dest_context.num_rows += src_context.num_rows
    for dest_column_key, dest_column in dest_context.columns.items():
        src_column = src_context.columns.get(dest_column_key)
        if src_column is None:
            dest_column.values.extend([None] * src_context.num_rows)
        else:
            dest_column.values.extend(src_column.values)


def row_context_from_context(src_context, index):
    """Pull a specific row out of a context as its own context."""
    assert src_context.aggregate_context is None
    columns = collections.OrderedDict(
        (col_name, Column(type=col.type, mode=col.mode,
         values=[col.values[index]]))
        for col_name, col in src_context.columns.items()
    )
    return Context(1, columns, None)


def cross_join_contexts(context1, context2):
    assert context1.aggregate_context is None
    assert context2.aggregate_context is None
    result_columns = collections.OrderedDict(
        [(col_name, Column(type=col.type, mode=col.mode, values=[]))
         for col_name, col in context1.columns.items()] +
        [(col_name, Column(type=col.type, mode=col.mode, values=[]))
         for col_name, col in context2.columns.items()])

    for index1 in six.moves.xrange(context1.num_rows):
        for index2 in six.moves.xrange(context2.num_rows):
            for col_name, column in context1.columns.items():
                result_columns[col_name].values.append(column.values[index1])
            for col_name, column in context2.columns.items():
                result_columns[col_name].values.append(column.values[index2])
    return Context(context1.num_rows * context2.num_rows, result_columns, None)


def truncate_context(context, limit):
    """Modify the given context to have at most the given number of rows."""
    assert context.aggregate_context is None
    # BigQuery adds non-int limits, so we need to allow floats up until now.
    limit = int(limit)
    if context.num_rows <= limit:
        return
    context.num_rows = limit

    for column in context.columns.values():
        column.values[limit:] = []
