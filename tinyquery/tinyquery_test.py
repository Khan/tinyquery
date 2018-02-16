from __future__ import absolute_import

import json
import unittest

from tinyquery import tinyquery


class TinyQueryTest(unittest.TestCase):
    def setUp(self):
        self.record_schema = {
            'fields': [
                {
                    'name': 'i',
                    'type': 'INTEGER',
                    'mode': 'NULLABLE',
                },
                {
                    'name': 'rr',
                    'type': 'RECORD',
                    'mode': 'REPEATED',
                    'fields': [
                        {
                            'name': 'inner_non_repeated',
                            'type': 'STRING',
                            'mode': 'NULLABLE',
                        },
                        {
                            'name': 'inner_repeated',
                            'type': 'STRING',
                            'mode': 'REPEATED',
                        },
                    ],
                },
                {
                    'name': 'r',
                    'type': 'RECORD',
                    'mode': 'NULLABLE',
                    'fields': [
                        {
                            'name': 's',
                            'type': 'STRING',
                            'mode': 'NULLABLE',
                        },
                        {
                            'name': 'inner_repeated',
                            'type': 'STRING',
                            'mode': 'REPEATED',
                        },
                        {
                            'name': 'r2',
                            'type': 'RECORD',
                            'mode': 'NULLABLE',
                            'fields': [
                                {
                                    'name': 'd2',
                                    'type': 'INTEGER',
                                    'mode': 'NULLABLE',
                                },
                            ],
                        },
                    ],
                },
            ],
        }

    def test_make_empty_table(self):
        table = tinyquery.TinyQuery.make_empty_table(
            'test_table', self.record_schema)
        self.assertIn('r.r2.d2', table.columns)

    def test_load_table_from_newline_delimited_json(self):
        record_json = json.dumps({
            'i': 1,
            'r': {
                's': 'hello!',
                'r2': {
                    'd2': 3,
                },
            },
        })
        tq = tinyquery.TinyQuery()
        tq.load_table_from_newline_delimited_json(
            'test_table',
            json.dumps(self.record_schema['fields']),
            [record_json])
        self.assertIn('test_table', tq.tables_by_name)
        table = tq.tables_by_name['test_table']
        self.assertIn('r.r2.d2', table.columns)
        self.assertIn(3, table.columns['r.r2.d2'].values)

    def test_load_json_with_null_records(self):
        record_json = json.dumps({
            'i': 1,
            'r': {
                's': 'hello!',
                'r2': None,
            },
        })
        tq = tinyquery.TinyQuery()
        tq.load_table_from_newline_delimited_json(
            'test_table',
            json.dumps(self.record_schema['fields']),
            [record_json])
        self.assertIn('test_table', tq.tables_by_name)
        table = tq.tables_by_name['test_table']
        self.assertIn('r.r2.d2', table.columns)
        self.assertIn(None, table.columns['r.r2.d2'].values)

    def test_load_json_with_repeated_records(self):
        record_json = json.dumps({
            'rr': [
                {
                    'inner_non_repeated': 'x',
                    'inner_repeated': ['a', 'b', 'c'],
                },
                {
                    'inner_non_repeated': 'y',
                    'inner_repeated': ['d', 'e'],
                },
            ],
            'r': {
                'inner_repeated': ['l', 'm', 'n'],
            },
        })

        tq = tinyquery.TinyQuery()
        tq.load_table_from_newline_delimited_json(
            'test_table',
            json.dumps(self.record_schema['fields']),
            [record_json])
        self.assertIn('test_table', tq.tables_by_name)
        table = tq.tables_by_name['test_table']
        self.assertEqual(table.columns['rr.inner_non_repeated'].values[0],
                         ['x', 'y'])
        self.assertEqual(table.columns['rr.inner_repeated'].values[0],
                         ['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(table.columns['r.inner_repeated'].values[0],
                         ['l', 'm', 'n'])
