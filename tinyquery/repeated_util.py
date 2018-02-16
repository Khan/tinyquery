"""Helper functions for dealing with repeated fields.

It comes up in a few places that we need to flatten or unflatten repeated
columns when using them in conjunction with other repeated or scalar fields.
These functions allow us to flatten into non-repeated columns to apply various
operations and then unflatten back into repeated columns afterwards.
"""
from __future__ import absolute_import

from tinyquery import tq_modes


def rebuild_column_values(repetitions, values, result):
    """Rebuild a repeated column from flattened results.

    Args:
        repetitions: a list of how many repeated values go in a row for
            each of the rows to process.
        values: a list of all the values that need to be packed into lists
        result: a (partial) result list to which the rows will be appended.
    Returns:
        a list of lists of values representing len(repetitions) rows, each
            of which with a number of values corresponding to that row's
            entry in repetitions
    """
    if len(repetitions) == 0:
        return result
    curr_repetition = repetitions[0]
    # For rows with no values, we supplied a None, so we need to pop
    # off one value no matter what.  If that value is None, we go back
    # to an empty list, otherwise we put the value in a list.
    curr_values = normalize_repeated_null(values[:max(curr_repetition, 1)])

    return rebuild_column_values(
        repetitions[1:],
        values[max(curr_repetition, 1):],
        result + [curr_values])


def normalize_column_to_length(col, desired_count):
    """Given the value(s) for a column, normalize to a desired length.

    If `col` is a scalar, it's duplicated in a list the desired number of
    times.  If `col` is a list, it must have 0, 1, or the desired number of
    elements, in which cases `None` or the single element is duplicated, or
    the original list is returned.
    """
    desired_count = max(desired_count, 1)
    if isinstance(col, list) and len(col) == desired_count:
        return col
    elif isinstance(col, list):
        assert len(col) in (0, 1), (
            'Unexpectedly got a row with the incorrect number of '
            'repeated values.')
        return (col or [None]) * desired_count
    else:
        return [col] * desired_count


def flatten_column_values(repeated_column_indices, column_values):
    """Take a list of columns and flatten them.

    We need to acomplish three things during the flattening:
    1. Flatten out any repeated fields.
    2. Keep track of how many repeated values were in each row so that we
        can go back
    3. If there are other columns, duplicate their values so that we have
        the same number of entries in all columns after flattening.

    Args:
        repeated_column_indices: the indices of the columns that
            are repeated; if there's more than one repeated column, this
            function assumes that we've already checked that the lengths of
            these columns will match up, or that they have 0 or 1 element.
        column_values: a list containing a list for each column's values.
    Returns:
        (repetition_counts, flattened_columns): a tuple
        repetition_counts: a list containing one number per row,
            representing the number of repeated values in that row
        flattened_columns: a list containing one list for each column's
            values.  The list for each column will not contain nested
            lists.
    """
    # wrapping in list for python 3 support
    rows = list(zip(*column_values))
    repetition_counts = [
        max(max(len(row[idx]) for idx in repeated_column_indices), 1)
        for row in rows
    ]

    rows_with_repetition_normalized = [
        [
            normalize_column_to_length(col, count)
            for col in row
        ]
        for row, count in zip(rows, repetition_counts)
    ]
    normalized_columns = zip(*rows_with_repetition_normalized)
    flattened_columns = [
        [val for arr in col for val in arr]
        for col in normalized_columns]
    return (repetition_counts, flattened_columns)


def columns_have_allowed_repetition_counts(ref_col, col):
    """Determine if we could select col along with ref_col.

    We assume ref_col is repeated.  In tinyquery this is allowable if any of
    the following is true:
    - col is not repeated
    - col is repeated but every row has only 0 or 1 element
    - col is repeated but every row with more than 1 element matches the number
      of elements in ref_col
    """
    if col.mode != tq_modes.REPEATED:
        return True

    ref_counts = [len(val) for val in ref_col.values]
    counts = [len(val) for val in col.values]
    return all(
        rc == c or c in (0, 1) or rc in (0, 1)
        for rc, c in zip(ref_counts, counts))


def normalize_repeated_null(value):
    """Normalze the way we represent null in repeated fields.

    There's 3 equivalent options: `None`, [], and `[None]`.  We chose [] to be
    the standard for repeated fields, so this turns any of these into [].
    """
    if value is None or value == [None]:
        return []
    return value
