"""Implementation of the standard built-in functions."""
from __future__ import absolute_import

import abc
import datetime
import functools
import json
import math
import random
import re
import time

import arrow
import six

from tinyquery import exceptions
from tinyquery import context
from tinyquery import repeated_util
from tinyquery import tq_types
from tinyquery import tq_modes


def pass_through_none(fn):
    """Modify a unary function so when its input is None, it returns None."""
    @functools.wraps(fn)
    def new_fn(arg):
        if arg is None:
            return None
        return fn(arg)
    return new_fn


class Function(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def check_types(self, *arg_types):
        """Return the type of the result as a function of the arg types.

        Raises a TypeError if the types are disallowed.
        """

    @abc.abstractmethod
    def evaluate(self, num_rows, *arg_lists):
        """Evaluates the function on

        Arguments:
            num_rows: The number of rows that should be returned. This is used
                by zero-arg functions that can't infer the number of rows from
                the args themselves.
            arg_lists: Each argument is a list of values for the column to
                operate on. For normal functions, the length of each arugment
                must be num_rows, but for aggregate functions, num_rows will be
                1 and each arg can be any length.
        """

    @abc.abstractmethod
    def _evaluate(self, num_wors, *args):
        """Internal evaluate method, called by a function superclass.

        Functions should inherit from a subclass that provides the
        non-underscored version, and then implement the underscored version
        themselves.
        """


class AggregateFunction(Function):
    """Represents a function doing some sort of aggregation.

    The function receives no special handling of repeated fields.
    """
    def evaluate(self, num_rows, *args):
        return self._evaluate(num_rows, *args)


class ScalarFunction(Function):
    """Represents a function that operates on scalar values.

    In tinyquery, this means we want it to act the same on the values in
    non-repeated fields and the individual values within repeated fields.

    In bigquery, the behavior appears to be a little complex.  While in most
    contexts calling a scalar function on a repeated column and a normal one
    looks like the data gets flattened, you can, for instance, still do scoped
    aggregation over the result and have it work with the original row
    identity.  Thus, this is not the appropriate place for tinyquery to flatten
    the output, and we need to unflatten the results.
    """
    def evaluate(self, num_rows, *args):
        repeated_columns = [
            col for col in args if col.mode == tq_modes.REPEATED]
        num_repeated_fields = len(repeated_columns)
        if num_repeated_fields > 1:
            # As an exception, bigquery allows you to use multiple repeated
            # fields as arguments to a function when each of the fields are
            # internal to the same record field or when both of the fields are
            # derived (via function application) from the same source data.
            # When this happens, it just treats it as if the columns were
            # flattened together.
            # We, however, don't have the information to follow the data
            # provenance, so as a proxy, we check to make sure that all the
            # repeated fields have the same number of items in each row.  This
            # is more permissive than bigquery's behavior.
            # TODO(colin): insert a (probably compile-time?) check to make sure
            # tinyquery's behavior on multiple repeated fields matches that of
            # bigquery.
            repetition_counts = zip(*[
                [len(row_values)
                 for row_values in col.values]
                for col in repeated_columns
            ])
            all_have_matching_counts = all(
                # Note that 0 and 1 items are always allowed, since it's always
                # permissible to mix in a scalar or a NULL.  Bigquery only
                # allows this when the data is actually derived from a scalar
                # field, but we don't have the ability to check this, so as a
                # proxy, we check if the field looks like a scalar.
                # TODO(colin): insert a compile-time check that matches
                # bigquery's behavior.
                len(set(row_counts) - set([0, 1])) <= 1
                for row_counts in repetition_counts)
            if not all_have_matching_counts:
                raise TypeError(
                    'Cannot query the cross product of repeated fields.')
        elif num_repeated_fields == 0:
            return self._evaluate(num_rows, *args)

        repeated_column_indices = [
            idx
            for idx, col in enumerate(args)
            if col.mode == tq_modes.REPEATED]
        column_values = [col.values for col in args]
        repetition_counts, flattened_columns = (
            repeated_util.flatten_column_values(
                repeated_column_indices, column_values))
        new_row_count = len(flattened_columns[0])
        flattened_tq_columns = [
            context.Column(type=args[idx].type, mode=tq_modes.NULLABLE,
                           values=flattened_column)
            for idx, flattened_column in enumerate(flattened_columns)]
        result = self._evaluate(new_row_count, *flattened_tq_columns)

        unflattened_values = repeated_util.rebuild_column_values(
            repetition_counts, result.values, [])

        return context.Column(type=result.type, mode=tq_modes.REPEATED,
                              values=unflattened_values)


class ArithmeticOperator(ScalarFunction):
    """Basic operators like +."""
    def __init__(self, func):
        self.func = func

    def check_types(self, type1, type2):
        if not (set([type1, type2]) <= tq_types.NUMERIC_TYPE_SET):
            raise TypeError('Expected numeric type.')
        if tq_types.FLOAT in set([type1, type2]):
            return tq_types.FLOAT
        else:
            return tq_types.INT

    def _evaluate(self, num_rows, column1, column2):
        values = [None if None in (x, y) else self.func(x, y)
                  for x, y in zip(column1.values, column2.values)]
        # TODO(Samantha): Code smell incoming
        t = self.check_types(column1.type, column2.type)
        return context.Column(type=t, mode=tq_modes.NULLABLE, values=values)


class ComparisonOperator(ScalarFunction):
    def __init__(self, func):
        self.func = func

    def check_types(self, type1, type2):
        # TODO(Samantha): This would make a lot more sense if we had a column
        # here. That way we could determine in the case of string vs timestamp
        # that the string was formatted iso8601.
        # TODO(Samantha): This does not even begin to account for record types!

        column_type_set = set([type1, type2])

        # If the types are the same, this is easy.
        if type1 == type2:
            return tq_types.BOOL
        # If the types are both in the numeric set, this is also sane.
        elif column_type_set <= tq_types.NUMERIC_TYPE_SET:
            return tq_types.BOOL
        # If the types are string and timestamp, things get a bit more
        # complicated.
        elif column_type_set == set([tq_types.STRING, tq_types.TIMESTAMP]):
            return tq_types.BOOL
        else:
            raise TypeError('Unexpected types.')

    def _evaluate(self, num_rows, column1, column2):
        """Implements BigQuery type adherent comparisons on columns, converting
        to other types when necessary to properly emulate BigQuery.
        """
        values = []
        # If one and only one value we are trying to compare is a timestamp,
        # there is some special casing required due to how BQ implicitly
        # converts some types.
        if (tq_types.TIMESTAMP in set([column1.type, column2.type]) and
                column1.type != column2.type):

            (timestamp_column, other_column) = (
                (column1, column2) if column1.type == tq_types.TIMESTAMP
                else (column2, column1))
            converted = []

            if other_column.type == tq_types.STRING:
                # Convert that string to datetime if we can.
                try:
                    converted = [arrow.get(x).to('UTC').naive
                                 for x in other_column.values]
                except Exception:
                    raise TypeError('Invalid comparison on timestamp, '
                                    'expected numeric type or ISO8601 '
                                    'formatted string.')
            elif other_column.type in tq_types.NUMERIC_TYPE_SET:
                # Cast that numeric to a float accounting for microseconds and
                # then to a datetime.
                convert = pass_through_none(
                    lambda x: arrow.get(float(x) / 1E6).to('UTC').naive
                )
                converted = [convert(x) for x in other_column.values]

            else:
                # No other way to compare a timestamp with anything other than
                # itself at this point.
                raise TypeError('Invalid comparison on timestamp, expected '
                                'numeric type or ISO8601 formatted string.')

            # Reassign our column variables so we may properly run this
            # comparison.
            column1 = timestamp_column
            column2 = context.Column(type=other_column.type,
                                     mode=other_column.mode,
                                     values=converted)

        values = [None if None in (x, y) else self.func(x, y)
                  for x, y in zip(column1.values, column2.values)]
        return context.Column(type=tq_types.BOOL, mode=tq_modes.NULLABLE,
                              values=values)


class BooleanOperator(ScalarFunction):
    def __init__(self, func):
        self.func = func

    def check_types(self, type1, type2):
        if type1 != type2 != tq_types.BOOL:
            raise TypeError('Expected bool type.')
        return tq_types.BOOL

    def _evaluate(self, num_rows, column1, column2):
        values = [None if None in (x, y) else self.func(x, y)
                  for x, y in zip(column1.values, column2.values)]
        return context.Column(type=tq_types.BOOL, mode=tq_modes.NULLABLE,
                              values=values)


class UnaryIntOperator(ScalarFunction):
    def __init__(self, func):
        self.func = pass_through_none(func)

    def check_types(self, arg):
        if arg not in tq_types.INT_TYPE_SET:
            raise TypeError('Expected int type.')
        return tq_types.INT

    def _evaluate(self, num_rows, column):
        values = [self.func(x) for x in column.values]
        return context.Column(type=tq_types.INT, mode=tq_modes.NULLABLE,
                              values=values)


class UnaryBoolOperator(ScalarFunction):
    def __init__(self, func, takes_none=False):
        self.func = func if takes_none else pass_through_none(func)

    def check_types(self, arg):
        return tq_types.BOOL

    def _evaluate(self, num_rows, column):
        values = [self.func(x) for x in column.values]
        return context.Column(type=tq_types.BOOL, mode=tq_modes.NULLABLE,
                              values=values)


class LogFunction(ScalarFunction):
    def __init__(self, base=None):
        if base:
            self.func = pass_through_none(lambda arg: math.log(arg, base))
        else:
            self.func = pass_through_none(math.log)

    def check_types(self, arg):
        if arg not in tq_types.NUMERIC_TYPE_SET:
            raise TypeError('Expected numeric argument.')
        return tq_types.FLOAT

    def _evaluate(self, num_rows, column):
        values = [self.func(x) for x in column.values]
        return context.Column(type=tq_types.FLOAT, mode=tq_modes.NULLABLE,
                              values=values)


class IfFunction(ScalarFunction):
    def check_types(self, cond, arg1, arg2):
        if cond != tq_types.BOOL:
            raise TypeError('Expected bool type.')
        if arg1 == tq_types.NONETYPE:
            return arg2
        if arg2 == tq_types.NONETYPE:
            return arg1
        if arg1 != arg2:
            raise TypeError('Expected types to be the same.')
        return arg1

    def _evaluate(self, num_rows, condition_column, then_column, else_column):
        values = [arg1 if cond else arg2
                  for cond, arg1, arg2 in zip(condition_column.values,
                                              then_column.values,
                                              else_column.values)]
        t = self.check_types(condition_column.type, then_column.type,
                             else_column.type)
        return context.Column(type=t, mode=tq_modes.NULLABLE, values=values)


class IfNullFunction(ScalarFunction):
    def check_types(self, arg1, arg2):
        if arg1 == tq_types.NONETYPE:
            return arg2
        if arg2 == tq_types.NONETYPE:
            return arg1
        if arg1 != arg2:
            raise TypeError('Expected types to be the same.')
        return arg1

    def _evaluate(self, num_rows, column1, column2):
        t = self.check_types(column1.type, column2.type)
        values = [x if x is not None else y
                  for x, y in zip(column1.values, column2.values)]
        return context.Column(type=t, mode=tq_modes.NULLABLE, values=values)


class CoalesceFunction(ScalarFunction):
    def check_types(self, *args):
        # Types can be either all the same, or include some NONETYPE.
        types = set(args) - set([tq_types.NONETYPE])
        if len(types) > 1:
            raise TypeError(
                'All arguments to coalesce must have the same type.')
        elif len(types) == 0:
            return tq_types.NONETYPE
        return list(types)[0]

    def _evaluate(self, num_rows, *cols):
        result_type = self.check_types(*[col.type for col in cols])
        rows = zip(*[col.values for col in cols])

        def first_nonnull(row):
            for x in row:
                if x is not None:
                    return x
            return None
        values = [first_nonnull(r) for r in rows]
        return context.Column(type=result_type, mode=tq_modes.NULLABLE,
                              values=values)


class HashFunction(ScalarFunction):
    def check_types(self, arg):
        return tq_types.INT

    def _evaluate(self, num_rows, column):
        # TODO: Use CityHash.
        hash_fn = pass_through_none(hash)
        values = [hash_fn(x) for x in column.values]
        return context.Column(type=tq_types.INT, mode=tq_modes.NULLABLE,
                              values=values)


class FloorFunction(ScalarFunction):
    def check_types(self, arg):
        if arg not in tq_types.NUMERIC_TYPE_SET:
            raise TypeError('Expected type int or float.')
        return tq_types.FLOAT

    def _evaluate(self, num_rows, column):
        floor = pass_through_none(math.floor)
        values = [floor(x) for x in column.values]
        return context.Column(type=tq_types.FLOAT, mode=tq_modes.NULLABLE,
                              values=values)


class IntegerCastFunction(ScalarFunction):
    def check_types(self, arg):
        # Can accept any type.
        return tq_types.INT

    def _evaluate(self, num_rows, column):
        if column.type in (tq_types.INT, tq_types.FLOAT, tq_types.BOOL):
            converter = pass_through_none(int)
        elif column.type == tq_types.STRING:
            def string_converter(arg):
                try:
                    return int(arg)
                except ValueError:
                    return None
            converter = string_converter
        elif column.type == tq_types.TIMESTAMP:
            return timestamp_to_usec.evaluate(num_rows, column)
        values = [converter(x) for x in column.values]
        return context.Column(type=tq_types.INT, mode=tq_modes.NULLABLE,
                              values=values)


class RandFunction(ScalarFunction):
    def check_types(self):
        return tq_types.FLOAT

    def _evaluate(self, num_rows):
        values = [random.random() for _ in six.moves.xrange(num_rows)]
        # TODO(Samantha): Should this be required?
        return context.Column(type=tq_types.FLOAT, mode=tq_modes.NULLABLE,
                              values=values)


class LeftFunction(ScalarFunction):
    def check_types(self, type1, type2):
        if type1 != tq_types.STRING:
            raise TypeError('First argument to LEFT must be a string.')
        if type2 != tq_types.INT:
            raise TypeError('Second argument to LEFT must be an int.')
        return tq_types.STRING

    def _evaluate(self, num_rows, string_col, int_col):
        values = [s[:i] if s is not None else None
                  for s, i in zip(string_col.values, int_col.values)]
        return context.Column(type=tq_types.STRING, mode=tq_modes.NULLABLE,
                              values=values)


def _check_regexp_types(*types):
    if any(t != tq_types.STRING for t in types):
        raise TypeError('Expected string arguments.')


# This is a sentinal value that we use with _ensure_literal when there are no
# rows.  We use this rather than None since many downstream functions know how
# to handle None, and we want to ensure this value cannot be used accidentally.
NO_VALUE = object()


def _ensure_literal(elements):
    if len(elements) == 0:
        return NO_VALUE
    assert all(r == elements[0] for r in elements), "Must provide a literal."
    return elements[0]


# TODO(colin): the regexp functions here use the python re module, while
# bigquery uses the re2 library, which only has a subset of the functionality.
# Investigate pulling in re2 here.

class RegexpMatchFunction(ScalarFunction):
    def check_types(self, type1, type2):
        _check_regexp_types(type1, type2)
        return tq_types.BOOL

    def _evaluate(self, num_rows, strings, regexps):
        regexp = _ensure_literal(regexps.values)
        values = (
            [None if None in (regexp, s) else
             True if re.search(regexp, s) else False for s in strings.values])
        return context.Column(type=tq_types.BOOL, mode=tq_modes.NULLABLE,
                              values=values)


class RegexpExtractFunction(ScalarFunction):
    def check_types(self, type1, type2):
        _check_regexp_types(type1, type2)
        return tq_types.STRING

    def _evaluate(self, num_rows, strings, regexps):
        regexp = _ensure_literal(regexps.values)
        values = []
        for s in strings.values:
            if s is None:
                values.append(None)
                continue
            match_result = re.search(regexp, s)
            if match_result is None:
                values.append(None)
            else:
                assert len(match_result.groups()) == 1, (
                    "Exactly one capturing group required")
                values.append(match_result.group(1))
        return context.Column(type=tq_types.STRING, mode=tq_modes.NULLABLE,
                              values=values)


class RegexpReplaceFunction(ScalarFunction):
    def check_types(self, re_type, str_type, repl_type):
        _check_regexp_types(re_type, str_type, repl_type)
        return tq_types.STRING

    def _evaluate(self, num_rows, strings, regexps, replacements):
        regexp = _ensure_literal(regexps.values)
        replacement = _ensure_literal(replacements.values)
        values = [re.sub(regexp, replacement, s) for s in strings.values]
        return context.Column(type=tq_types.STRING, mode=tq_modes.NULLABLE,
                              values=values)


# TODO(Samantha): I'm not sure how this actually works, leaving for now.
class NthFunction(AggregateFunction):
    # TODO(alan): Enforce that NTH takes a constant as its first arg.
    def check_types(self, index_type, rep_list_type):
        # TODO(Samantha): This should probably be tq_types.INT_TYPE_SET.
        if index_type != tq_types.INT:
            raise TypeError('Expected an int index.')
        return rep_list_type

    def _evaluate(self, num_rows, index_list, column):
        index = _ensure_literal(index_list.values)
        values = [self.safe_index(rep_elem, index)
                  for rep_elem in column.values]
        return context.Column(type=column.type, mode=tq_modes.NULLABLE,
                              values=values)

    @staticmethod
    def safe_index(rep_elem, index):
        if not rep_elem:
            return None
        if index <= 0 or index > len(rep_elem):
            return None
        return rep_elem[index - 1]


class FirstFunction(AggregateFunction):
    def check_types(self, rep_list_type):
        return rep_list_type

    def _evaluate(self, num_rows, column):
        values = []
        if len(column.values) == 0:
            values = [None]

        if column.mode == tq_modes.REPEATED:
            values = [repeated_row[0] if len(repeated_row) > 0 else None
                      for repeated_row in column.values]
        else:
            values = [column.values[0]]
        return context.Column(type=column.type, mode=tq_modes.NULLABLE,
                              values=values)


class NoArgFunction(ScalarFunction):
    def __init__(self, func, return_type=tq_types.INT):
        self.func = func
        self.type = return_type

    def check_types(self):
        return self.type

    def _evaluate(self, num_rows):
        return context.Column(
            type=self.type, mode=tq_modes.NULLABLE,
            values=[self.func() for _ in six.moves.xrange(num_rows)])


class InFunction(ScalarFunction):
    def check_types(self, arg1, *arg_types):
        return tq_types.BOOL

    def _evaluate(self, num_rows, arg1, *other_args):
        values = [
            val1 in val_list
            for val1, val_list in zip(arg1.values,
                                      zip(*[x.values for x in other_args]))
        ]
        return context.Column(type=tq_types.BOOL, mode=tq_modes.NULLABLE,
                              values=values)


class ConcatFunction(AggregateFunction):
    def check_types(self, *arg_types):
        if any(arg_type != tq_types.STRING for arg_type in arg_types):
            raise TypeError('CONCAT only takes string arguments.')
        return tq_types.STRING

    def _evaluate(self, num_rows, *columns):
        values = [None if None in strs else ''.join(strs)
                  for strs in zip(*[c.values for c in columns])]
        return context.Column(tq_types.STRING, tq_modes.NULLABLE,
                              values=values)


class StringFunction(ScalarFunction):
    def check_types(self, arg_type):
        return tq_types.STRING

    def _evaluate(self, num_rows, column):
        pass_through_none_str = pass_through_none(str)
        values = [pass_through_none_str(x) for x in column.values]
        return context.Column(type=tq_types.STRING, mode=tq_modes.NULLABLE,
                              values=values)


class MinMaxFunction(AggregateFunction):
    def __init__(self, func):
        self.func = func

    def check_types(self, arg):
        return arg

    def _evaluate(self, num_rows, column):
        return context.Column(
            type=self.check_types(column.type),
            mode=tq_modes.NULLABLE,
            values=[self.func([x for x in column.values if x is not None])])


class SumFunction(AggregateFunction):
    def check_types(self, arg):
        if arg in tq_types.INT_TYPE_SET:
            return tq_types.INT
        elif arg in tq_types.NUMERIC_TYPE_SET:
            return tq_types.FLOAT
        else:
            raise TypeError('Unexpected type.')

    def _evaluate(self, num_rows, column):
        values = [sum([0 if arg is None else arg for arg in column.values])]
        return context.Column(type=self.check_types(column.type),
                              mode=tq_modes.NULLABLE,
                              values=values)


class CountFunction(AggregateFunction):
    def check_types(self, arg):
        return tq_types.INT

    def _evaluate(self, num_rows, column):
        if column.mode == tq_modes.REPEATED:
            values = [len([v for val_list in column.values for v in val_list])]
        else:
            values = [len([0 for arg in column.values if arg is not None])]
        return context.Column(type=tq_types.INT, mode=tq_modes.NULLABLE,
                              values=values)


class AvgFunction(AggregateFunction):
    def check_types(self, arg):
        if arg not in tq_types.NUMERIC_TYPE_SET:
            raise TypeError('Unexpected type.')
        return tq_types.FLOAT

    def _evaluate(self, num_rows, column):
        filtered_args = [arg for arg in column.values if arg is not None]
        values = ([None] if not filtered_args else
                  [float(sum(filtered_args)) / len(filtered_args)])
        return context.Column(type=tq_types.FLOAT, mode=tq_modes.NULLABLE,
                              values=values)


class CountDistinctFunction(AggregateFunction):
    def check_types(self, arg):
        return tq_types.INT

    def _evaluate(self, num_rows, column):
        if column.mode == tq_modes.REPEATED:
            values = [v for val_list in column.values for v in val_list]
        else:
            values = column.values
        return context.Column(type=tq_types.INT, mode=tq_modes.NULLABLE,
                              values=[len(set(values) - set([None]))])


class GroupConcatUnquotedFunction(AggregateFunction):
    def check_types(self, *arg_types):
        return tq_types.STRING

    def _evaluate(self, num_rows, column, separator_list=None):
        if separator_list:
            separator = _ensure_literal(separator_list.values)
        else:
            separator = ','
        # TODO: this implementation supports repeated fields but we have not
        # confirmed that bigquery does (if it doesn't, this should be removed)
        if column.mode == tq_modes.REPEATED:
            values = [separator.join([v
                                      for val_list in column.values
                                      for v in val_list
                                      if v])]
        else:
            values = [separator.join([v
                                      for v in column.values
                                      if v is not None])]
        return context.Column(type=self.check_types(column.type),
                              mode=tq_modes.NULLABLE,
                              values=values)


class StddevSampFunction(AggregateFunction):
    def check_types(self, arg):
        return tq_types.FLOAT

    def _evaluate(self, num_rows, column):
        # TODO(alan): Implement instead of returning 0.
        return context.Column(type=tq_types.FLOAT, mode=tq_modes.NULLABLE,
                              values=[0.0])


class QuantilesFunction(AggregateFunction):
    # TODO(alan): Enforce that QUANTILES takes a constant as its second arg.
    def check_types(self, arg_list_type, num_quantiles_type):
        if num_quantiles_type != tq_types.INT:
            raise TypeError('Expected an int number of quantiles.')
        # TODO(alan): This should actually return a repeated version of the arg
        # list type.
        return tq_types.INT

    def _evaluate(self, num_rows, column, num_quantiles_list):
        sorted_args = sorted(arg for arg in column.values if arg is not None)
        values = []
        if not sorted_args:
            values = [None]
        num_quantiles = _ensure_literal(num_quantiles_list.values)
        # Stretch the quantiles out so the first is always the min of the list
        # and the last is always the max of the list, but make sure it stays
        # within the bounds of the list so we don't get an IndexError.
        # This returns a single repeated field rather than one row per
        # quantile, so we need one more set of brackets than you might expect.
        values = [[
            sorted_args[
                min(len(sorted_args) * i // (num_quantiles - 1),
                    len(sorted_args) - 1)
            ] for i in six.moves.xrange(num_quantiles)
        ]]
        return context.Column(type=tq_types.INT, mode=tq_modes.REPEATED,
                              values=values)


class ContainsFunction(ScalarFunction):
    def check_types(self, type1, type2):
        if type1 != tq_types.STRING or type2 != tq_types.STRING:
            raise TypeError("CONTAINS must operate on strings.")
        return tq_types.BOOL

    def _evaluate(self, num_rows, column1, column2):
        if len(column1.values) == len(column2.values):
            values = [None if None in (v1, v2) else v2 in v1
                      for v1, v2 in zip(column1.values, column2.values)]
            return context.Column(type=tq_types.BOOL, mode=tq_modes.NULLABLE,
                                  values=values)


class TimestampFunction(ScalarFunction):
    def check_types(self, type1):
        if type1 not in tq_types.DATETIME_TYPE_SET:
            raise TypeError(
                'TIMESTAMP requires an ISO8601 string or unix timestamp in '
                'microseconds (or something that is already a timestamp).')
        return tq_types.TIMESTAMP

    def _evaluate(self, num_rows, column):
        if column.type == tq_types.TIMESTAMP:
            return column

        converter = lambda ts: ts
        if num_rows > 0 and column.type == tq_types.INT:
            # Bigquery accepts integer number of microseconds since the unix
            # epoch here, whereas arrow wants a unix timestamp, with possible
            # decimal part representing microseconds.
            converter = lambda ts: float(ts) / 1E6
        convert_fn = pass_through_none(
                # arrow.get parses ISO8601 strings and int/float unix
                # timestamps without a format parameter
                lambda ts: arrow.get(converter(ts)).to('UTC').naive)
        try:
            values = [convert_fn(x) for x in column.values]
        except Exception:
            raise TypeError(
                'TIMESTAMP requires an ISO8601 string or unix timestamp in '
                'microseconds (or something that is already a timestamp).')
        return context.Column(type=tq_types.TIMESTAMP, mode=tq_modes.NULLABLE,
                              values=values)


class TimestampExtractFunction(ScalarFunction):
    def __init__(self, extractor, return_type):
        self.extractor = pass_through_none(extractor)
        self.type = return_type

    def check_types(self, type1):
        if type1 != tq_types.TIMESTAMP:
            raise TypeError('Expected a timestamp, got %s.' % type1)
        return self.type

    def _evaluate(self, num_rows, column1):
        values = [self.extractor(x) for x in column1.values]
        return context.Column(type=self.type, mode=tq_modes.NULLABLE,
                              values=values)


class DateAddFunction(ScalarFunction):
    VALID_INTERVALS = ('YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND')

    def check_types(self, type1, type2, type3):
        if not (type1 == tq_types.TIMESTAMP and
                type2 == tq_types.INT and
                type3 == tq_types.STRING):
            raise TypeError(
                'DATE_ADD takes a timestamp, integer, and string specifying '
                'the interval. Got: (%s, %s, %s)' % (type1, type2, type3))

        return tq_types.TIMESTAMP

    def _evaluate(self, num_rows, timestamps, nums_intervals, interval_types):
        num_intervals = _ensure_literal(nums_intervals.values)
        interval_type = _ensure_literal(interval_types.values)
        if interval_type not in self.VALID_INTERVALS:
            raise ValueError(
                'Valid values for the DATE_ADD interval are: %s.  Got %s.' % (
                    ', '.join(self.VALID_INTERVALS), interval_type))

        if interval_type == 'MONTH':
            @pass_through_none
            def adder(ts):
                year = ts.year + (ts.month - 1 + num_intervals) // 12
                month = 1 + (ts.month - 1 + num_intervals) % 12
                return ts.replace(year=year, month=month)
            values = [adder(x) for x in timestamps.values]
        elif interval_type == 'YEAR':
            convert_fn = pass_through_none(
                    lambda ts: ts.replace(year=(ts.year + num_intervals)))
            values = [convert_fn(x) for x in timestamps.values]
        else:
            # All of the other valid options for bigquery are also valid
            # keyword arguments to datetime.timedelta, when lowercased and
            # pluralized.
            python_interval_name = interval_type.lower() + 's'
            delta = datetime.timedelta(**{python_interval_name: num_intervals})
            convert_fn = pass_through_none(lambda ts: ts + delta)
            values = [convert_fn(x) for x in timestamps.values]

        return context.Column(type=tq_types.TIMESTAMP, mode=tq_modes.NULLABLE,
                              values=values)


class DateDiffFunction(ScalarFunction):
    def check_types(self, type1, type2):
        if not (type1 == tq_types.TIMESTAMP and type2 == tq_types.TIMESTAMP):
            raise TypeError('DATEDIFF requires two timestamps.')

        return tq_types.INT

    def _evaluate(self, num_rows, lhs_ts, rhs_ts):
        values = [(None if None in (lhs, rhs)
                   else int(round((lhs - rhs).total_seconds() / 24 / 3600)))
                  for lhs, rhs in zip(lhs_ts.values, rhs_ts.values)]
        return context.Column(type=tq_types.INT, mode=tq_modes.NULLABLE,
                              values=values)


class Compose(AggregateFunction):
    """Function implementing function composition.

    Note that this is not actually a bigquery function, but a tool for
    combining them in implementations.
    """
    def __init__(self, *functions):
        self.functions = list(reversed(functions))
        assert len(self.functions) > 1, (
            'Compose requires at least two functions.')

    def check_types(self, *types):
        result = self.functions[0].check_types(*types)
        for f in self.functions[1:]:
            result = f.check_types(result)

        return result

    def _evaluate(self, num_rows, *args):
        result = self.functions[0].evaluate(num_rows, *args)
        for f in self.functions[1:]:
            result = f.evaluate(num_rows, result)
        return result


class TimestampShiftFunction(ScalarFunction):
    """Shift a timestamp to the beginning of the specified interval."""
    def __init__(self, interval):
        self.interval = interval
        assert interval in ('day', 'hour', 'month', 'year')

    def check_types(self, type1):
        if type1 != tq_types.TIMESTAMP:
            raise TypeError("Expected a timestamp.")
        return tq_types.TIMESTAMP

    def _hour_truncate(self, ts):
        return ts.replace(minute=0, second=0, microsecond=0)

    def _day_truncate(self, ts):
        return self._hour_truncate(ts).replace(hour=0)

    def _month_truncate(self, ts):
        return self._day_truncate(ts).replace(day=1)

    def _year_truncate(self, ts):
        return self._month_truncate(ts).replace(month=1)

    def _evaluate(self, num_rows, timestamps):
        truncate_fn = pass_through_none(
            getattr(self, '_%s_truncate' % self.interval))
        values = [truncate_fn(x) for x in timestamps.values]
        return context.Column(type=tq_types.TIMESTAMP, mode=tq_modes.NULLABLE,
                              values=values)


class UnixTimestampToWeekdayFunction(ScalarFunction):
    """Shift a timestamp to the beginning of the specified day in the week.

    Note that in contrast to other day of week functions, days run from
    0 == Sunday to 6 == Saturday (for consistency with bigquery).
    """
    def check_types(self, type1, type2):
        if not (type1 == tq_types.INT and type2 == tq_types.INT):
            raise TypeError(
                'Expected a unix (integer) timestamp and an integer, '
                'got %s.' % [type1, type2])
        return tq_types.TIMESTAMP

    def _weekday_from_ts(self, ts):
        # isoweekday goes from 1 == Monday to 7 == Sunday
        return ts.isoweekday() % 7

    def _evaluate(self, num_rows, unix_timestamps, weekdays):
        weekday = _ensure_literal(weekdays.values)
        timestamps = TimestampFunction().evaluate(num_rows, unix_timestamps)
        truncated = TimestampShiftFunction('day').evaluate(
            num_rows, timestamps)
        convert = pass_through_none(
                lambda ts: ts + datetime.timedelta(
                    days=(weekday - self._weekday_from_ts(ts))))
        values = [convert(x) for x in truncated.values]
        ts_result = context.Column(
            type=tq_types.TIMESTAMP, mode=tq_modes.NULLABLE, values=values)
        return timestamp_to_usec.evaluate(num_rows, ts_result)


class StrftimeFunction(ScalarFunction):
    """Format a unix timestamp in microseconds by the supplied format.

    TODO(colin): it appears that bigquery and python strftime behave
    identically.  Are there any differences?
    """
    def check_types(self, type1, type2):
        if not (type1 in tq_types.DATETIME_TYPE_SET and
                type2 == tq_types.STRING):
            raise TypeError('Expected an integer and a string, got %s.' % (
                [type1, type2]))
        return tq_types.STRING

    def _evaluate(self, num_rows, unix_timestamps, formats):
        format_str = _ensure_literal(formats.values)
        timestamps = TimestampFunction().evaluate(num_rows, unix_timestamps)
        convert = pass_through_none(lambda ts: ts.strftime(format_str))
        values = [convert(x) for x in timestamps.values]
        return context.Column(type=tq_types.STRING, mode=tq_modes.NULLABLE,
                              values=values)


class NumericArgReduceFunction(AggregateFunction):
    def __init__(self, reducer):
        self.reducer = reducer

    def check_types(self, *types):
        if len(types) < 2:
            raise ValueError("Requires at least two arguments.")
        if not all(t in tq_types.NUMERIC_TYPE_SET for t in types):
            raise TypeError("Only operates on numeric types.")

        if any(t == tq_types.FLOAT for t in types):
            return tq_types.FLOAT

        return tq_types.INT

    def _evaluate(self, num_rows, *columns):
        def apply(*args):
            # Rather than assigning NULL a numeric value, bigquery's behavior
            # is usually to return NULL if any arguments are NULL.
            if any(arg is None for arg in args):
                return None
            return functools.reduce(self.reducer, args)

        values = [apply(*vals)
                  for vals in zip(*[col.values for col in columns])]
        return context.Column(
            type=columns[0].type, mode=tq_modes.NULLABLE,
            values=values)


class JSONExtractFunction(ScalarFunction):
    """Extract from a JSON string based on a JSONPath expression.

    This impelments both the bigquery JSON_EXTRACT and JSON_EXTRACT_SCALAR
    functions, which are very similar except for:
    - JSON_EXTRACT_SCALAR returns bigquery NULL if the resulting value would
      not be a scalar (i.e. would be an object or list)
    - JSON_EXTRACT_SCALAR returns bigquery NULL if the resulting scalar value
      would be the JSON 'null' (the non-scalar version is the string 'null' in
      this case)
    - JSON_EXTRACT_SCALAR returns string values without quotation marks

    TODO(colin): are there other differences?
    """
    # JSON null becomes None, so we use this special value to distinguish
    # between a JSON null, and bigquery null, which we represent with this
    # constant.
    NO_RESULT = object()

    def __init__(self, scalar=False):
        self.scalar = scalar

    def check_types(self, type1, type2):
        if not (type1 == type2 == tq_types.STRING):
            raise TypeError('Expected string arguments, got %s.' % (
                [type1, type2]))
        return tq_types.STRING

    def _parse_property_name(self, json_path):
        if json_path[0] != '.':
            raise ValueError(
                'Invalid json path expression. Was expecting a "." '
                'before %s' % json_path)
        if len(json_path) == 1:
            raise ValueError(
                'Invalid json path expression. Cannot end in ".".')
        prop_name_plus = json_path[1:]
        next_separator_positions = [
            pos
            for pos in [prop_name_plus.find('.'), prop_name_plus.find('[')]
            if pos != -1
        ]

        if next_separator_positions:
            end_idx = min(next_separator_positions)
            return prop_name_plus[:end_idx], prop_name_plus[end_idx:]
        else:
            return prop_name_plus, ''

    def _parse_array_index(self, json_path):
        if json_path[0] != '[':
            raise ValueError(
                'Invalid json path expression. Was expecting a "[" '
                'before %s' % json_path)
        index_plus = json_path[1:]
        str_idx, sep, rest = index_plus.partition(']')
        if len(sep) == 0:
            raise ValueError(
                'Invalid json path expression. Unclosed "[". '
                'Expected a "]" in %s' % index_plus)

        idx = int(str_idx)
        if idx < 0:
            raise ValueError(
                'Invalid json path expression. Negative indices not allowed.')

        return idx, rest

    def _extract_by_json_path(self, parsed_json_expr, json_path):
        if len(json_path) == 0:
            return parsed_json_expr

        if json_path.startswith('$'):
            return self._extract_by_json_path(parsed_json_expr, json_path[1:])

        if json_path.startswith('.'):
            prop_name, rest = self._parse_property_name(json_path)
            if not isinstance(parsed_json_expr, dict):
                return self.NO_RESULT
            value = parsed_json_expr.get(prop_name, self.NO_RESULT)
            if value is self.NO_RESULT:
                return self.NO_RESULT
            if value is None:
                return None
            return self._extract_by_json_path(value, rest)

        if json_path.startswith('['):
            idx, rest = self._parse_array_index(json_path)
            if (not isinstance(parsed_json_expr, list) or
                    idx >= len(parsed_json_expr)):
                return self.NO_RESULT
            value = parsed_json_expr[idx]
            if value is None:
                return None
            return self._extract_by_json_path(value, rest)

        raise ValueError(
            'Invalid json_path_expression. Expected property access or array '
            'indexing at %s' % json_path)

    def _evaluate(self, num_rows, json_expressions, json_paths):
        json_path = _ensure_literal(json_paths.values)
        json_load = pass_through_none(json.loads)
        parsed_json = [json_load(x)
                       for x in json_expressions.values]
        if not json_path.startswith('$'):
            raise ValueError(
                'Invalid json path expression.  Must start with $.')
        values = [self._extract_by_json_path(json_val, json_path)
                  for json_val in parsed_json]
        if self.scalar:
            # One pecularity of the scalar version is that JSON nulls become
            # real bigquery nulls, rather than being converted back to JSON
            # strings.
            values = [None
                      if isinstance(val, (dict, list, type(None)))
                      or val is self.NO_RESULT
                      else str(val)
                      for val in values]
        else:
            # This ensures that values are dumped back to JSON strings, with
            # our special NO_RESULT object converted into a bigquery null,
            # rather than the JSON string 'null', which is what a None val
            # becomes.
            values = [json.dumps(val) if val is not self.NO_RESULT else None
                      for val in values]
        return context.Column(
            type=tq_types.STRING, mode=tq_modes.NULLABLE,
            values=values)


timestamp_to_usec = TimestampExtractFunction(
    lambda dt: int(1E6 * arrow.get(dt).float_timestamp),
    return_type=tq_types.INT)


_UNARY_OPERATORS = {
    '-': UnaryIntOperator(lambda a: -a),
    # Note that for NOT takes_none is intentionally False, which means that
    # `NOT NULL` is in fact `NULL`, which matches the behavior of bigquery.
    'not': UnaryBoolOperator(lambda a: not a, takes_none=False),
    'is_null': UnaryBoolOperator(lambda a: a is None, takes_none=True),
    'is_not_null': UnaryBoolOperator(lambda a: a is not None, takes_none=True),
}


_BINARY_OPERATORS = {
    '+': ArithmeticOperator(lambda a, b: a + b),
    '-': ArithmeticOperator(lambda a, b: a - b),
    '*': ArithmeticOperator(lambda a, b: a * b),
    '/': ArithmeticOperator(lambda a, b: a / b),
    '%': ArithmeticOperator(lambda a, b: a % b),
    '=': ComparisonOperator(lambda a, b: a == b),
    '==': ComparisonOperator(lambda a, b: a == b),
    '!=': ComparisonOperator(lambda a, b: a != b),
    '>': ComparisonOperator(lambda a, b: a > b),
    '<': ComparisonOperator(lambda a, b: a < b),
    '>=': ComparisonOperator(lambda a, b: a >= b),
    '<=': ComparisonOperator(lambda a, b: a <= b),
    'and': BooleanOperator(lambda a, b: a and b),
    'or': BooleanOperator(lambda a, b: a or b),
    'contains': ContainsFunction(),
}


_FUNCTIONS = {
    'abs': UnaryIntOperator(abs),
    'floor': FloorFunction(),
    'integer': IntegerCastFunction(),
    'ln': LogFunction(),
    'log': LogFunction(),
    'log10': LogFunction(10),
    'log2': LogFunction(2),
    'rand': RandFunction(),
    'nth': NthFunction(),
    'concat': ConcatFunction(),
    'string': StringFunction(),
    'pow': ArithmeticOperator(lambda a, b: a ** b),
    'now': NoArgFunction(lambda: int(time.time() * 1000000)),
    'in': InFunction(),
    'if': IfFunction(),
    'ifnull': IfNullFunction(),
    'coalesce': CoalesceFunction(),
    'hash': HashFunction(),
    'left': LeftFunction(),
    'regexp_match': RegexpMatchFunction(),
    'regexp_extract': RegexpExtractFunction(),
    'regexp_replace': RegexpReplaceFunction(),
    'least': NumericArgReduceFunction(min),
    'greatest': NumericArgReduceFunction(max),
    'timestamp': TimestampFunction(),
    'current_date': NoArgFunction(
        lambda: datetime.datetime.utcnow().strftime('%Y-%m-%d'),
        return_type=tq_types.STRING),
    'current_time': NoArgFunction(
        lambda: datetime.datetime.utcnow().strftime('%H:%M:%S'),
        return_type=tq_types.STRING),
    'current_timestamp': NoArgFunction(
        lambda: datetime.datetime.utcnow(),
        return_type=tq_types.TIMESTAMP),
    'date': Compose(
        TimestampExtractFunction(
            lambda dt: dt.strftime('%Y-%m-%d'),
            return_type=tq_types.STRING),
        TimestampFunction()),
    'date_add': DateAddFunction(),
    'datediff': DateDiffFunction(),
    'day': Compose(
        TimestampExtractFunction(
            lambda dt: dt.day,
            return_type=tq_types.INT),
        TimestampFunction()),
    'dayofweek': Compose(
        TimestampExtractFunction(
            # isoweekday uses Sunday == 7, but it's 1 in bigquery, so we need
            # to convert.
            lambda dt: (dt.isoweekday() % 7 + 1),
            return_type=tq_types.INT),
        TimestampFunction()),
    'dayofyear': Compose(
        TimestampExtractFunction(
            lambda dt: int(dt.strftime('%j'), 10),
            return_type=tq_types.INT),
        TimestampFunction()),
    'format_utc_usec': Compose(
        TimestampExtractFunction(
            lambda dt: dt.strftime('%Y-%m-%d %H:%M:%S.%f'),
            return_type=tq_types.STRING),
        TimestampFunction()),
    'hour': Compose(
        TimestampExtractFunction(
            lambda dt: dt.hour,
            return_type=tq_types.INT),
        TimestampFunction()),
    'minute': Compose(
        TimestampExtractFunction(
            lambda dt: dt.minute,
            return_type=tq_types.INT),
        TimestampFunction()),
    'month': Compose(
        TimestampExtractFunction(
            lambda dt: dt.month,
            return_type=tq_types.INT),
        TimestampFunction()),
    'msec_to_timestamp': Compose(
        TimestampFunction(),
        UnaryIntOperator(lambda msec: msec * 1E3)),
    'parse_utc_usec': Compose(
        timestamp_to_usec,
        TimestampFunction()),
    'quarter': Compose(
        TimestampExtractFunction(
            lambda dt: dt.month // 3 + 1,
            return_type=tq_types.INT),
        TimestampFunction()),
    'second': Compose(
        TimestampExtractFunction(
            lambda dt: dt.second,
            return_type=tq_types.INT),
        TimestampFunction()),
    'sec_to_timestamp': Compose(
        TimestampFunction(),
        UnaryIntOperator(lambda sec: sec * 1E6)),
    'strftime_utc_usec': StrftimeFunction(),
    'time': Compose(
        TimestampExtractFunction(
            lambda dt: dt.strftime('%H:%M:%S'),
            return_type=tq_types.STRING),
        TimestampFunction()),
    'timestamp_to_msec': TimestampExtractFunction(
        lambda dt: int(round(1E3 * arrow.get(dt).float_timestamp)),
        return_type=tq_types.INT),
    'timestamp_to_sec': TimestampExtractFunction(
        lambda dt: arrow.get(dt).timestamp,
        return_type=tq_types.INT),
    'timestamp_to_usec': timestamp_to_usec,
    'usec_to_timestamp': TimestampFunction(),
    'utc_usec_to_day': Compose(
        timestamp_to_usec,
        TimestampShiftFunction('day'),
        TimestampFunction()),
    'utc_usec_to_hour': Compose(
        timestamp_to_usec,
        TimestampShiftFunction('hour'),
        TimestampFunction()),
    'utc_usec_to_month': Compose(
        timestamp_to_usec,
        TimestampShiftFunction('month'),
        TimestampFunction()),
    'utc_usec_to_week': UnixTimestampToWeekdayFunction(),
    'utc_usec_to_year': Compose(
        timestamp_to_usec,
        TimestampShiftFunction('year'),
        TimestampFunction()),
    'week': Compose(
        TimestampExtractFunction(
            # TODO(colin): can this ever be 54?
            # Bigquery returns 1...53 inclusive
            # Python returns 0...53 inclusive
            # Both say that the first week may be < 7 days, but python calls
            # that 0, and bigquery calls that 1.
            lambda dt: int(dt.strftime('%U'), 10) + 1,
            return_type=tq_types.INT),
        TimestampFunction()),
    'year': Compose(
        TimestampExtractFunction(
            lambda dt: dt.year,
            return_type=tq_types.INT),
        TimestampFunction()),
    'json_extract': JSONExtractFunction(),
    'json_extract_scalar': JSONExtractFunction(scalar=True),
}


_AGGREGATE_FUNCTIONS = {
    'sum': SumFunction(),
    'min': MinMaxFunction(min),
    'max': MinMaxFunction(max),
    'count': CountFunction(),
    'avg': AvgFunction(),
    'count_distinct': CountDistinctFunction(),
    'group_concat_unquoted': GroupConcatUnquotedFunction(),
    'stddev_samp': StddevSampFunction(),
    'quantiles': QuantilesFunction(),
    'first': FirstFunction()
}


def get_unary_op(name):
    result = _UNARY_OPERATORS[name]
    assert isinstance(result, Function)
    return result


def get_binary_op(name):
    result = _BINARY_OPERATORS[name]
    assert isinstance(result, Function)
    return result


def get_func(name):
    if name in _FUNCTIONS:
        return _FUNCTIONS[name]
    elif name in _AGGREGATE_FUNCTIONS:
        return _AGGREGATE_FUNCTIONS[name]
    else:
        raise exceptions.CompileError('Unknown function: {}'.format(name))


def is_aggregate_func(name):
    return name in _AGGREGATE_FUNCTIONS
