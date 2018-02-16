# TODO(colin): fix these lint errors (http://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes)
# pep8-disable:E265
"""TinyQuery wrapper that acts like BigQuery's Python API Client.

This can be used in place of the value returned by apiclient.discovery.build().
"""
from __future__ import absolute_import

import functools
import json

import six


class TinyQueryApiClient(object):
    def __init__(self, tq_service):
        self.tq_service = tq_service

    def tables(self):
        return TableServiceApiClient(self.tq_service)

    def jobs(self):
        return JobServiceApiClient(self.tq_service)

    def tabledata(self):
        return TabledataServiceApiClient(self.tq_service)


class FakeHttpError(Exception):
    """Replace this with a real HttpError class if your code catches one."""
    def __init__(self, response, content):
        super(FakeHttpError, self).__init__(content)
        self.response = response
        self.content = content


class FakeHttpRequest(object):
    def __init__(self, func, args, kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def execute(self, http=None, num_retries=0):
        # It probably doesn't make sense to support http or num_retries in
        # a mock, but we need to accept them as kwargs to avoid errors
        return self.func(*self.args, **self.kwargs)


def http_request_provider(func):
    """Given a function, turn

    For example, if we decorate a function get(projectId, datasetId, tableId),
    the returned function will return a FakeHttpRequest object that, when
    executed, will actually call the get function.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return FakeHttpRequest(func, args, kwargs)
    return wrapper


class TableServiceApiClient(object):
    def __init__(self, tq_service):
        """Service object for creating and managing tables.

        :type tq_service: tinyquery.TinyQuery
        """
        self.tq_service = tq_service

    @http_request_provider
    def insert(self, projectId, datasetId, body):
        """Create an empty table or a view."""
        table_reference = body['tableReference']
        table_name = (table_reference['datasetId'] + '.' +
                      table_reference['tableId'])
        if 'view' in body:
            # The new table is actually a view.
            table_reference = body['tableReference']
            view = self.tq_service.make_view(table_name, body['view']['query'])
            self.tq_service.load_table_or_view(view)
        else:
            #The new table is a regular table.
            raw_schema = body['schema']
            table = self.tq_service.make_empty_table(table_name, raw_schema)
            self.tq_service.load_table_or_view(table)

    @http_request_provider
    def get(self, projectId, datasetId, tableId):
        try:
            return self.tq_service.get_table_info(
                projectId, datasetId, tableId)
        except KeyError:
            raise FakeHttpError(None, json.dumps({
                'error': {
                    'code': 404,
                    'message': 'Table not found: %s.%s' % (datasetId, tableId)
                }
            }))

    @http_request_provider
    def list(self, projectId, datasetId, pageToken=None, maxResults=None):
        # TODO(alan): Support paging.
        all_tables = self.tq_service.get_all_table_info_in_dataset(
            projectId, datasetId)
        return {
            'tables': all_tables[:maxResults]
        }

    @http_request_provider
    def delete(self, projectId, datasetId, tableId):
        try:
            return self.tq_service.delete_table(datasetId, tableId)
        except KeyError:
            raise FakeHttpError(None, json.dumps({
                'error': {
                    'code': 404,
                    'message': 'Table not found: %s.%s' % (datasetId, tableId)
                }
            }))

    @http_request_provider
    def patch(self, projectId, datasetId, tableId, body):
        # TODO: Implement this instead of making it a no-op.
        pass


class JobServiceApiClient(object):
    def __init__(self, tq_service):
        """Service object for creating and managing jobs.

        :type tq_service: tinyquery.TinyQuery
        """
        self.tq_service = tq_service

    @http_request_provider
    def insert(self, projectId, body):
        if 'query' in body['configuration']:
            config = body['configuration']['query']
            query = config['query']
            dest_dataset, dest_table = self._get_config_table(
                config, 'destinationTable')
            create_disposition = config.get('createDisposition',
                                            'CREATE_IF_NEEDED')
            write_disposition = config.get('writeDisposition', 'WRITE_EMPTY')
            return self.tq_service.run_query_job(
                projectId, query, dest_dataset, dest_table, create_disposition,
                write_disposition)
        elif 'copy' in body['configuration']:
            config = body['configuration']['copy']
            src_dataset, src_table = self._get_config_table(
                config, 'sourceTable')
            dest_dataset, dest_table = self._get_config_table(
                config, 'destinationTable')
            create_disposition = config.get('createDisposition',
                                            'CREATE_IF_NEEDED')
            write_disposition = config.get('writeDisposition', 'WRITE_EMPTY')
            return self.tq_service.run_copy_job(
                projectId, src_dataset, src_table, dest_dataset, dest_table,
                create_disposition, write_disposition)
        else:
            assert False, 'Unknown job type: {}'.format(
                list(body['configuration'].keys()))

    @staticmethod
    def _get_config_table(config, key):
        """Return the dataset_id, table_id, if any."""
        dest_table_config = config.get(key)
        if dest_table_config:
            return dest_table_config['datasetId'], dest_table_config['tableId']
        else:
            return None, None

    @http_request_provider
    def get(self, projectId, jobId):
        return self.tq_service.get_job_info(jobId)

    @http_request_provider
    def getQueryResults(self, projectId, jobId):
        result_table = self.tq_service.get_query_result_table(jobId)
        result_rows = rows_from_table(result_table)
        result_schema = schema_from_table(result_table)

        # TODO: Also add the schema.
        return {
            'rows': result_rows,
            'schema': result_schema
        }

    @http_request_provider
    def query(self, projectId, body):
        # TODO(alan): Disallow things that are allowed for full jobs but not
        # for simple query calls, such as the destination table.
        job_insert_result = self.insert(projectId=projectId, body={
            'projectId': projectId,
            'configuration': {
                'query': body
            }
        }).execute()
        return self.getQueryResults(
            projectId=projectId,
            jobId=job_insert_result['jobReference']['jobId']).execute()


class TabledataServiceApiClient(object):
    def __init__(self, tq_service):
        """Service object for working with data within tables.

        :type tq_service: tinyquery.TinyQuery
        """
        self.tq_service = tq_service

    @http_request_provider
    def list(self, projectId, datasetId, tableId, pageToken=None,
             maxResults=None):
        # TODO(alan): Support paging.
        try:
            table = self.tq_service.get_table(datasetId, tableId)
            return {
                'rows': rows_from_table(table)
            }
        except KeyError:
            raise FakeHttpError(None, json.dumps({
                'error': {
                    'code': 404,
                    'message': 'Table not found: %s.%s' % (datasetId, tableId)
                }
            }))


def schema_from_table(table):
    """Given a tinyquery.Table, build an API-compatible schema."""
    return {'fields': [
        {'name': name, 'type': col.type}
        for name, col in table.columns.items()
    ]}


def rows_from_table(table):
    """Given a tinyquery.Table, build an API-compatible rows object."""
    result_rows = []
    for i in six.moves.xrange(table.num_rows):
        field_values = [{'v': str(col.values[i])}
                        for col in table.columns.values()]
        result_rows.append({
            'f': field_values
        })
    return result_rows
