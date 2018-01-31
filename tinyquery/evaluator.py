# TODO(colin): fix these lint errors (http://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes)
# pep8-disable:E115,E128
import collections

import six

import context
import tq_ast
import tq_modes
import typed_ast
import tq_types


class Evaluator(object):
    def __init__(self, tables_by_name):
        self.tables_by_name = tables_by_name

    def evaluate_select(self, select_ast):
        """Given a select statement, return a Context with the results."""
        assert isinstance(select_ast, typed_ast.Select)

        table_context = self.evaluate_table_expr(select_ast.table)
        mask_column = self.evaluate_expr(select_ast.where_expr, table_context)
        select_context = context.mask_context(table_context, mask_column)

        if select_ast.group_set is not None:
            num_scoped_agg = sum(
                select_field.within_clause is not None
                for select_field in select_ast.select_fields)
            if num_scoped_agg == 1:
                for select_field in select_ast.select_fields:
                    if select_field.within_clause is not None:
                        # TODO: Extend the functionality of scoped aggregation
                        # for multiple fields
                        result = self.evaluate_within(
                            select_ast.select_fields, select_ast.group_set,
                            select_context, select_field.within_clause)
                        break
            elif num_scoped_agg > 1:
                raise NotImplementedError('Multiple fields having "WITHIN" '
                                          'clause is not supported as yet.')
            else:
                result = self.evaluate_groups(
                        select_ast.select_fields, select_ast.group_set,
                        select_context)
        else:
            result = self.evaluate_select_fields(
                select_ast.select_fields, select_context)

        having_mask = self.evaluate_expr(select_ast.having_expr, result)
        result = context.mask_context(result, having_mask)

        if select_ast.orderings is not None:
            result = self.evaluate_orderings(select_context, result,
                                             select_ast.orderings)

        if select_ast.limit is not None:
            context.truncate_context(result, select_ast.limit)
        return result

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
        # TODO: Implement GROUP BY for repeated fields.
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
        from collections import OrderedDict
        group_contexts = OrderedDict()

        # As a special case, we check if we are grouping by nothing (in other
        # words, if the query had an aggregate without any explicit GROUP BY).
        # Normally, it's fine to just use the trivial group set: every row maps
        # to the empty tuple, so we have a single aggregation over the entire
        # table. However, if the table is empty, we still want to aggregate
        # over the empty table and return a single row, so this is the one case
        # where it's possible to have a group with no rows in it. To make this
        # case work, we ensure that the trivial group key (the empty tuple)
        # always shows up for the TRIVIAL_GROUP_SET case.
        # In the long run, it might be cleaner to view TRIVIAL_GROUP_SET as a
        # completely separate case, but this approach should work.
        if group_set == typed_ast.TRIVIAL_GROUP_SET:
            trivial_ctx = context.Context(1, collections.OrderedDict(), None)
            group_contexts[trivial_ctx] = (
                context.empty_context_from_template(select_context))

        # TODO: Seems pretty ugly and wasteful to use a whole context as a
        # group key.
        for i in six.moves.xrange(select_context.num_rows):
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
        for context_key, group_context in group_contexts.items():
            group_eval_context = context.Context(
                1, context_key.columns, group_context)
            group_aggregate_result_context = self.evaluate_select_fields(
                aggregate_select_fields, group_eval_context)
            full_result_row_context = self.merge_contexts_for_select_fields(
                result_col_names, group_aggregate_result_context, context_key)
            context.append_row_to_context(full_result_row_context, 0,
                                          result_context)
        return result_context

    def evaluate_orderings(self, overall_context, select_context,
                           ordering_col):
        """
        Evaluate a context and order it by a list of given columns.

        Arguments:
            overall_context: A context with the data that the select statement
                has access to.
            select_context: A context with the data remaining after earlier
            evaluations.
            ordering_col: A list of order-by column objects having two
                properties: column_id containing the name of the column and
                is_ascending which is a boolean for the order in which the
                column has to be arranged (True for ascending and False for
                descending).

        Returns:
            A context with the results.
        """
        assert select_context.aggregate_context is None
        all_values = []
        sort_by_indexes = collections.OrderedDict()

        for ((_, column_name), column) in overall_context.columns.items():
            all_values.append(column.values)

        for order_by_column in ordering_col:
            for count, ((_, column_name), column) in enumerate(
                    overall_context.columns.items()):
                if order_by_column.column_id.name == column_name:
                    sort_by_indexes[count] = order_by_column.is_ascending
                    break
        reversed_sort_by_indexes = collections.OrderedDict(
            reversed(list(sort_by_indexes.items())))

        t_all_values = [list(z) for z in zip(*all_values)]
        for index, is_ascending in reversed_sort_by_indexes.items():
            t_all_values.sort(key=lambda x: (x[index]),
                              reverse=not is_ascending)
        ordered_values = [list(z) for z in zip(*t_all_values)]
        # If we started evaluating an ordering over 0 rows,
        # all_values was originally [[], [], [], ...], i.e. the empty list for
        # each column, but now ordered_values is just the empty list, since
        # when going to a list of rows, we lost any notion of how many columns
        # there were.  In that case, we just set back to all_values, since
        # there isn't any data to order by anyway.
        # TODO(colin): can we exit early if there's no data to order?
        if len(t_all_values) == 0:
            ordered_values = all_values

        for key in select_context.columns:
            for count, (_, overall_key) in enumerate(overall_context.columns):
                overall_context_loop_break = False
                if overall_key == key[1]:
                    select_context.columns[key] = context.Column(
                        type=select_context.columns[key].type,
                        mode=select_context.columns[key].mode,
                        values=ordered_values[count])
                    overall_context_loop_break = True
                if overall_context_loop_break:
                    break

        return select_context

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
                # TODO(Samantha): This shouldn't just be nullable.
                type=source_column.type, mode=tq_modes.NULLABLE,
                values=[source_column.values[index]])
        for alias_group in alias_groups:
            column_key = (None, alias_group)
            source_column = alias_group_result_context.columns[column_key]
            result_columns[column_key] = context.Column(
                # TODO(Samantha): This shouldn't just be nullable.
                type=source_column.type, mode=tq_modes.NULLABLE,
                values=[source_column.values[index]])
        return context.Context(1, result_columns, None)

    def empty_context_from_select_fields(self, select_fields):
        return context.Context(
            0,
            collections.OrderedDict(
                ((None, select_field.alias),
                 # TODO(Samantha): This shouldn't just be nullable
                 context.Column(type=select_field.expr.type,
                                mode=tq_modes.NULLABLE, values=[]))
                for select_field in select_fields
            ),
            None)

    def evaluate_within(self, select_fields, group_set, ctx,
                        within_clause):
        """Evaluate a list of select fields, one of which has a WITHIN or
        WITHIN RECORD clause and/or grouping by some of the values.

        Arguments:
            select_fields: A list of SelectField instances to evaluate.
            group_set: The groups (either fields in select_context or aliases
                referring to an element of select_fields) to group by.
            ctx: The "source" context that the expressions can access when
                being evaluated.

        Returns:
            A context with the results.
        """
        if within_clause == "RECORD":
            # Add an extra column of row number over which the grouping
            # will be done.
            ctx_with_primary_key = context.empty_context_from_template(ctx)
            context.append_context_to_context(ctx, ctx_with_primary_key)

            table_name = next(iter(ctx_with_primary_key.columns))
            row_nums = list(six.moves.xrange(1, ctx_with_primary_key.num_rows + 1))
            row_nums_col = context.Column(
                type=tq_types.INT, mode=tq_modes.NULLABLE, values=row_nums)
            ctx_with_primary_key.columns[(table_name,
                         'row_numbers_column_primary_key')] = row_nums_col
            group_set.field_groups.append(typed_ast.ColumnRef(
                table_name, 'row_numbers_column_primary_key', tq_types.INT))
            if len(select_fields) > 1:
            # TODO: Implement WITHIN RECORD when one or more of the
            # selected fields (except the one in the WITHIN RECORD
            # clause) has mode = REPEATED.
                for select_field in select_fields:
                    if select_field.within_clause is None:
                        if select_field.expr.mode != tq_modes.REPEATED:
                            group_set.alias_groups.add(select_field.alias)
                        else:
                            raise NotImplementedError(
                                'Cannot select fields having mode=REPEATED '
                                'for queries involving WITHIN RECORD')
        # TODO: Implement for WITHIN clause
        typed_ast.TRIVIAL_GROUP_SET = typed_ast.GroupSet(set(), [])
        return self.evaluate_groups(select_fields, group_set,
                                    ctx_with_primary_key)

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
            type=results.type, mode=results.mode,
            values=results.values)

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

    def eval_table_Join(self, table_expr):
        base_context = self.evaluate_table_expr(table_expr.base)
        rhs_tables, join_types = zip(*table_expr.tables)
        other_contexts = [self.evaluate_table_expr(x) for x in rhs_tables]

        lhs_context = base_context

        for rhs_context, join_type, conditions in zip(other_contexts,
                                                      join_types,
                                                      table_expr.conditions):

            if join_type is tq_ast.JoinType.CROSS:
                lhs_context = context.cross_join_contexts(
                    lhs_context, rhs_context)
                continue

            # We reordered the join conditions in the compilation step, so
            # column1 always refers to the lhs of the current join.
            lhs_key_refs = [cond.column1 for cond in conditions]
            rhs_key_refs = [cond.column2 for cond in conditions]
            rhs_key_contexts = {}
            for i in six.moves.xrange(rhs_context.num_rows):
                rhs_key = self.get_join_key(rhs_context, rhs_key_refs, i)
                if rhs_key not in rhs_key_contexts:
                    rhs_key_contexts[rhs_key] = (
                        context.empty_context_from_template(rhs_context))
                context.append_row_to_context(
                    src_context=rhs_context, index=i,
                    dest_context=rhs_key_contexts[rhs_key])

            result_context = context.cross_join_contexts(
                context.empty_context_from_template(lhs_context),
                context.empty_context_from_template(rhs_context))

            for i in six.moves.xrange(lhs_context.num_rows):
                lhs_key = self.get_join_key(lhs_context, lhs_key_refs, i)
                lhs_row_context = context.row_context_from_context(
                    lhs_context, i)
                if lhs_key in rhs_key_contexts:
                    new_rows = context.cross_join_contexts(
                        lhs_row_context, rhs_key_contexts[lhs_key])
                    context.append_context_to_context(new_rows, result_context)
                elif join_type is tq_ast.JoinType.LEFT_OUTER:
                    # For a left outer join, we still want to in a row with
                    # nulls on the right.
                    context.append_context_to_context(lhs_row_context,
                                                      result_context)
            lhs_context = result_context

        return lhs_context

    def get_join_key(self, table_context, key_column_refs, index):
        """Get the join key for a row in a table that is part of a join.

        Note that, while this code is similar to the code that computes group
        keys, groups are different because they need to be specifically
        selected from later (so we build a context for them), whereas join keys
        can have different column names.

        Arguments:
            table_context: A Context containing the data in one of the tables
                being joined.
            key_column_refs: A list of ColumnRef specifying the columns to use
                in the key and their order.
            index: The index of the row to compute the key for.

        Returns: A tuple of values for the key for this row.
        """
        return tuple(
            table_context.column_from_ref(col_ref).values[index]
            for col_ref in key_column_refs)

    def eval_table_Select(self, table_expr):
        """Evaluate a select table expression.

        The output matches the type context on the select rather than the
        directly-evaluated type context so that we account for any alias that
        might have been assigned.
        """
        result_context = self.evaluate_select(table_expr)
        return context.context_with_overlayed_type_context(result_context,
                                                           table_expr.type_ctx)

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

    def evaluate_Literal(self, literal, context_object):
        values = [literal.value for _ in six.moves.xrange(context_object.num_rows)]
        return context.Column(type=literal.type, mode=tq_modes.NULLABLE,
                              values=values)

    def evaluate_ColumnRef(self, column_ref, ctx):
        return ctx.columns[(column_ref.table, column_ref.column)]
