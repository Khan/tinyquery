"""Implementation of the TinyQuery service."""
import collections

import compiler
import context
import typed_ast


class TinyQuery(object):
    def __init__(self):
        self.tables_by_name = {}

    def load_table(self, table):
        """Create a table.

        Arguments:
            name: The name of the table.
            data: A dict mapping column name to list of values.
        """
        self.tables_by_name[table.name] = table

    def get_all_tables(self):
        return self.tables_by_name

    def evaluate_query(self, query):
        select_ast = compiler.compile_text(query, self.tables_by_name)
        return self.evaluate_select(select_ast)

    def evaluate_select(self, select_ast):
        """Given a select statement, return a Context with the results."""
        assert isinstance(select_ast, typed_ast.Select)

        table_context = self.evaluate_table_expr(select_ast.table)
        mask_column = self.evaluate_expr(select_ast.where_expr, table_context)
        select_context = context.mask_context(table_context, mask_column)

        if select_ast.group_set is not None:
            return self.evaluate_groups(
                select_ast.select_fields, select_ast.group_set, select_context)
        else:
            return self.evaluate_select_fields(
                select_ast.select_fields, select_context)

    def evaluate_groups(self, select_fields, group_set, select_context):
        """Evaluate a list of select fields, grouping by some of the values.

        Arguments:
            select_fields: A list of SelectField instances to evaluate.
            group_set: The groups (either fields in select_context or aliases
                referring to an element of select_fields) to group by.
            select_context: A context with the data that the select statement
                has access to.

        Returns:
            A context with the results.
        """
        field_groups = group_set.field_groups
        alias_groups = group_set.alias_groups
        alias_group_list = sorted(alias_groups)

        group_key_select_fields = [
            f for f in select_fields if f.alias in alias_groups]
        aggregate_select_fields = [
            f for f in select_fields if f.alias not in alias_groups]

        alias_group_result_context = self.evaluate_select_fields(
            group_key_select_fields, select_context)

        # Dictionary mapping (singleton) group key context to the context of
        # values for that key.
        group_contexts = {}
        # TODO: Seems pretty ugly and wasteful to use a whole context as a
        # group key.
        for i in xrange(select_context.num_rows):
            key = self.get_group_key(
                field_groups, alias_group_list, select_context,
                alias_group_result_context, i)
            if key not in group_contexts:
                new_group_context = context.empty_context_from_template(
                    select_context)
                group_contexts[key] = new_group_context
            group_context = group_contexts[key]
            context.append_row_to_context(src_context=select_context, index=i,
                                          dest_context=group_context)

        result_context = self.empty_context_from_select_fields(select_fields)
        result_col_names = [field.alias for field in select_fields]
        for context_key, group_context in group_contexts.iteritems():
            group_eval_context = context.Context(
                1, context_key.columns, group_context)
            group_aggregate_result_context = self.evaluate_select_fields(
                aggregate_select_fields, group_eval_context)
            full_result_row_context = self.merge_contexts_for_select_fields(
                result_col_names, group_aggregate_result_context, context_key)
            context.append_row_to_context(full_result_row_context, 0,
                                          result_context)
        return result_context

    def merge_contexts_for_select_fields(self, col_names, context1, context2):
        """Build a context that combines columns of two contexts.

        The col_names argument is a list of strings that specifies the order of
        the columns in the result. Note that not every column must be used, and
        columns in context1 take precedence over context2 (this happens in
        practice with non-alias groups that are part of the group key).
        """
        assert context1.num_rows == context2.num_rows
        assert context1.aggregate_context is None
        assert context2.aggregate_context is None
        # Select fields always have the None table.
        col_keys = [(None, col_name) for col_name in col_names]
        columns1, columns2 = context1.columns, context2.columns
        return context.Context(context1.num_rows, collections.OrderedDict(
            (col_key, columns1.get(col_key) or columns2[col_key])
            for col_key in col_keys
        ), None)

    def get_group_key(self, field_groups, alias_groups, select_context,
                      alias_group_result_context, index):
        """Computes a singleton context with the values for a group key.

        The evaluation has already been done; this method just selects the
        values out of the right contexts.

        Arguments:
            field_groups: A list of ColumnRefs for the field groups to use.
            alias_groups: A list of strings of alias groups to use.
            select_context: A context with the data for the table expression
                being selected from.
            alias_group_result_context: A context with the data for the
                grouped-by select fields.
            index: The row index to use from each context.
        """
        result_columns = collections.OrderedDict()
        for field_group in field_groups:
            column_key = (field_group.table, field_group.column)
            source_column = select_context.columns[column_key]
            result_columns[column_key] = context.Column(
                source_column.type, [source_column.values[index]])
        for alias_group in alias_groups:
            column_key = (None, alias_group)
            source_column = alias_group_result_context.columns[column_key]
            result_columns[column_key] = context.Column(
                source_column.type, [source_column.values[index]])
        return context.Context(1, result_columns, None)

    def empty_context_from_select_fields(self, select_fields):
        return context.Context(
            0,
            collections.OrderedDict(
                ((None, select_field.alias),
                 context.Column(select_field.expr.type, []))
                for select_field in select_fields
            ),
            None)

    def evaluate_select_fields(self, select_fields, ctx):
        """Evaluate a table result given the data the fields have access to.

        Arguments:
            select_fields: A list of typed_ast.SelectField values to evaluate.
            context: The "source" context that the expressions can access when
                being evaluated.
        """
        return context.Context(
            ctx.num_rows,
            collections.OrderedDict(
                self.evaluate_select_field(select_field, ctx)
                for select_field in select_fields),
            None)

    def evaluate_select_field(self, select_field, ctx):
        """Given a typed select field, return a resulting column entry."""
        assert isinstance(select_field, typed_ast.SelectField)
        results = self.evaluate_expr(select_field.expr, ctx)
        return (None, select_field.alias), context.Column(
            select_field.expr.type, results)

    def evaluate_table_expr(self, table_expr):
        """Given a table expression, return a Context with its values."""
        try:
            method = getattr(self,
                             'eval_table_' + table_expr.__class__.__name__)
        except AttributeError:
            raise NotImplementedError(
                'Missing handler for table type {}'.format(
                    table_expr.__class__.__name__))
        return method(table_expr)

    def eval_table_NoTable(self, table_expr):
        # If the user isn't selecting from any tables, just specify that there
        # is one column to return and no table accessible.
        return context.Context(1, collections.OrderedDict(), None)

    def eval_table_Table(self, table_expr):
        """Get the values from the table.

        The type context in the table expression determines the actual column
        names to output, since that accounts for any alias on the table.
        """
        table = self.tables_by_name[table_expr.name]
        return context.context_from_table(table, table_expr.type_ctx)

    def eval_table_TableUnion(self, table_expr):
        result_context = context.empty_context_from_type_context(
            table_expr.type_ctx)
        for table in table_expr.tables:
            table_result = self.evaluate_table_expr(table)
            context.append_partial_context_to_context(table_result,
                                                      result_context)
        return result_context

    def eval_table_Select(self, table_expr):
        return self.evaluate_select(table_expr)

    def evaluate_expr(self, expr, context):
        """Computes the raw data for the output column for the expression."""
        try:
            method = getattr(self, 'evaluate_' + expr.__class__.__name__)
        except AttributeError:
            raise NotImplementedError(
                'Missing handler for type {}'.format(expr.__class__.__name__))
        return method(expr, context)

    def evaluate_FunctionCall(self, func_call, context):
        arg_results = [self.evaluate_expr(arg, context)
                       for arg in func_call.args]
        return func_call.func.evaluate(context.num_rows, *arg_results)

    def evaluate_AggregateFunctionCall(self, func_call, context):
        # Switch to the aggregate context when evaluating the arguments to the
        # aggregate.
        assert context.aggregate_context is not None, (
            'Aggregate function called without a valid aggregate context.')
        arg_results = [self.evaluate_expr(arg, context.aggregate_context)
                       for arg in func_call.args]
        return func_call.func.evaluate(context.num_rows, *arg_results)

    def evaluate_Literal(self, literal, context):
        return [literal.value for _ in xrange(context.num_rows)]

    def evaluate_ColumnRef(self, column_ref, ctx):
        column = ctx.columns[(column_ref.table, column_ref.column)]
        return column.values
