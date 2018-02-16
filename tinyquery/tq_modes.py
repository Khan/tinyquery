""" Defines the valid modes. Currently we just use strings to identify them.
"""
from __future__ import absolute_import

NULLABLE = "NULLABLE"
REQUIRED = "REQUIRED"
REPEATED = "REPEATED"

MODE_SET = set([NULLABLE, REQUIRED, REPEATED])


def check_mode(value, expected_mode):
    if value is None:
        return expected_mode == NULLABLE
    elif isinstance(value, list):
        return expected_mode == REPEATED
    else:
        return True
