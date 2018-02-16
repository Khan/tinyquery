from __future__ import absolute_import

import unittest

from tinyquery import api_client
from tinyquery import tq_types
from tinyquery import tinyquery


class ApiClientTest(unittest.TestCase):
    def setUp(self):
        self.tinyquery = tinyquery.TinyQuery()
        self.tq_service = api_client.TinyQueryApiClient(self.tinyquery)

    @staticmethod
    def table_ref(table_name):
        return {
            'projectId': 'test_project',
            'datasetId': 'test_dataset',
            'tableId': table_name,
        }

    def insert_simple_table(self):
        self.tq_service.tables().insert(
            projectId='test_project',
            datasetId='test_dataset',
            body={
                'tableReference': self.table_ref('test_table'),
                'schema': {
                    'fields': [
                        {'name': 'foo', 'type': 'INTEGER', 'mode': 'NULLABLE'},
                        {'name': 'bar', 'type': 'BOOLEAN', 'mode': 'NULLABLE'},
                    ]
                }
            }).execute()

    def run_query(self, query):
        query_job_info = self.tq_service.jobs().insert(
            projectId='test_project',
            body={
                'projectId': 'test_project',
                'configuration': {
                    'query': {
                        'query': query
                    }
                }
            }
        ).execute()
        query_result = self.tq_service.jobs().getQueryResults(
            projectId='test_project',
            jobId=query_job_info['jobReference']['jobId']
        ).execute()
        return query_result

    def query_to_table(self, query, dest_dataset, dest_table):
        self.tq_service.jobs().insert(
            projectId='test_project',
            body={
                'projectId': 'test_project',
                'configuration': {
                    'query': {
                        'query': query,
                        'destinationTable': {
                            'projectId': 'test_project',
                            'datasetId': dest_dataset,
                            'tableId': dest_table
                        }
                    },
                }
            }
        ).execute()
        # Normally, we'd need to block until it's complete, but in tinyquery we
        # know that the query gets executed immediately.

    def test_table_management(self):
        self.insert_simple_table()
        table_info = self.tq_service.tables().get(
            projectId='test_project', datasetId='test_dataset',
            tableId='test_table').execute()
        self.assertEqual(
            {'name': 'bar', 'type': 'BOOLEAN', 'mode': 'NULLABLE'},
            table_info['schema']['fields'][1])

        self.tq_service.tables().delete(
            projectId='test_project', datasetId='test_dataset',
            tableId='test_table').execute()

        try:
            self.tq_service.tables().get(
                projectId='test_project', datasetId='test_dataset',
                tableId='test_table').execute()
            self.fail('Expected exception to be raised.')
        except api_client.FakeHttpError as e:
            self.assertTrue('404' in e.content)

        try:
            self.tq_service.tables().delete(
                projectId='test_project', datasetId='test_dataset',
                tableId='test_table').execute()
            self.fail('Expected exception to be raised.')
        except api_client.FakeHttpError as e:
            self.assertTrue('404' in e.content)

    def test_full_job_query(self):
        job_info = self.tq_service.jobs().insert(
            projectId='test_project',
            body={
                'projectId': 'test_project',
                'configuration': {
                    'query': {
                        'query': 'SELECT 7 as foo',
                    }
                }
            }
        ).execute()
        query_result = self.tq_service.jobs().getQueryResults(
            projectId='test_project', jobId=job_info['jobReference']['jobId']
        ).execute()
        self.assertEqual('7', query_result['rows'][0]['f'][0]['v'])
        self.assertEqual(
            {'name': 'foo', 'type': tq_types.INT},
            query_result['schema']['fields'][0])

    def test_sync_query(self):
        # As a convenience, BigQuery also makes it possible to run a query
        # synchronously in a single API request.
        query_result = self.tq_service.jobs().query(
            projectId='test_project',
            body={
                'query': 'SELECT 7 as foo',
            }
        ).execute()
        self.assertEqual('7', query_result['rows'][0]['f'][0]['v'])

    def test_table_copy(self):
        self.tq_service.jobs().insert(
            projectId='test_project',
            body={
                'projectId': 'test_project',
                'configuration': {
                    'query': {
                        'query': 'SELECT 7 as foo',
                        'destinationTable': self.table_ref('table1')
                    },
                },
            }
        ).execute()

        for _ in range(5):
            self.tq_service.jobs().insert(
                projectId='test_project',
                body={
                    'projectId': 'test_project',
                    'configuration': {
                        'copy': {
                            'sourceTable': self.table_ref('table1'),
                            'destinationTable': self.table_ref('table2'),
                            'createDisposition': 'CREATE_IF_NEEDED',
                            'writeDisposition': 'WRITE_APPEND',
                        }
                    }
                }
            ).execute()

        query_result = self.run_query('SELECT foo FROM test_dataset.table2')
        self.assertEqual(5, len(query_result['rows']))

    def test_patch(self):
        self.insert_simple_table()
        # Should not crash. TODO: Allow the new expiration time to be read.
        self.tq_service.tables().patch(
            projectId='test_project',
            datasetId='test_dataset',
            tableId='test_table',
            body={
                'expirationTime': 1000000000
            }
        ).execute()

    def test_create_and_query_view(self):
        self.insert_simple_table()
        self.tq_service.tables().insert(
            projectId='test_project',
            datasetId='test_dataset',
            body={
                'tableReference': self.table_ref('test_view'),
                'view': {
                    'query': 'SELECT COUNT(*) AS num_rows '
                             'FROM test_dataset.test_table'
                }
            }
        ).execute()
        # Test regular field selection.
        query_result = self.run_query('SELECT num_rows '
                                      'FROM test_dataset.test_view')
        self.assertEqual('0', query_result['rows'][0]['f'][0]['v'])

        # Test field selection with a table alias.
        query_result = self.run_query('SELECT t.num_rows '
                                      'FROM test_dataset.test_view t')
        self.assertEqual('0', query_result['rows'][0]['f'][0]['v'])

        # Test field selection with the fully-qualified name.
        query_result = self.run_query('SELECT test_dataset.test_view.num_rows '
                                      'FROM test_dataset.test_view')
        self.assertEqual('0', query_result['rows'][0]['f'][0]['v'])

    def test_list_tables(self):
        self.insert_simple_table()
        self.tq_service.jobs().insert(
            projectId='test_project',
            body={
                'projectId': 'test_project',
                'configuration': {
                    'query': {
                        'query': 'SELECT 7 as foo',
                        'destinationTable': self.table_ref('another_table')
                    },
                }
            }
        ).execute()
        response = self.tq_service.tables().list(
            projectId='test_project',
            datasetId='test_dataset',
            pageToken=None,
            maxResults=5
        ).execute()
        table_list = response['tables']
        self.assertEqual(2, len(table_list))
        self.assertEqual('another_table',
                         table_list[0]['tableReference']['tableId'])
        self.assertEqual('test_table',
                         table_list[1]['tableReference']['tableId'])

    def test_list_tabledata(self):
        self.query_to_table(
            """
            SELECT * FROM
                (SELECT 0 AS foo, 'hello' AS bar),
                (SELECT 7 AS foo, 'goodbye' AS bar)
            """,
            'test_dataset', 'test_table_2')
        list_response = self.tq_service.tabledata().list(
            projectId='test_project', datasetId='test_dataset',
            tableId='test_table_2').execute()
        self.assertEqual('0', list_response['rows'][0]['f'][0]['v'])
        self.assertEqual('hello', list_response['rows'][0]['f'][1]['v'])
        self.assertEqual('7', list_response['rows'][1]['f'][0]['v'])
        self.assertEqual('goodbye', list_response['rows'][1]['f'][1]['v'])
