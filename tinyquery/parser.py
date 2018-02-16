"""The parser turns a stream of tokens into an AST."""
from __future__ import absolute_import

import os

from ply import yacc

from tinyquery import tq_ast
from tinyquery import lexer


tokens = lexer.tokens

precedence = (
    ('left', 'AND', 'OR'),  # TODO(colin): is this correct?
    ('left', 'EQUALS', 'NOT_EQUAL', 'GREATER_THAN', 'LESS_THAN',
     'GREATER_THAN_OR_EQUAL', 'LESS_THAN_OR_EQUAL', 'IS'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'STAR', 'DIVIDED_BY', 'MOD', 'CONTAINS', 'IN'),
)


def p_select(p):
    """select : SELECT select_field_list optional_limit
              | SELECT select_field_list FROM full_table_expr optional_where \
                    optional_group_by optional_having optional_order_by \
                    optional_limit
    """
    if len(p) == 4:
        p[0] = tq_ast.Select(p[2], None, None, None, None, None, p[3], None)
    elif len(p) == 10:
        p[0] = tq_ast.Select(p[2], p[4], p[5], p[6], p[7], p[8], p[9], None)
    else:
        assert False, 'Unexpected number of captured tokens.'


def p_optional_where(p):
    """optional_where :
                      | WHERE expression
    """
    if len(p) == 1:
        p[0] = None
    else:
        p[0] = p[2]


def p_optional_having(p):
    """optional_having :
                       | HAVING expression
    """
    if len(p) == 1:
        p[0] = None
    else:
        p[0] = p[2]


def p_optional_group_by(p):
    """optional_group_by :
                         | GROUP BY column_id_list
                         | GROUP EACH BY column_id_list
    """
    if len(p) == 1:
        p[0] = None
    else:
        p[0] = p[len(p) - 1]


def p_optional_order_by(p):
    """optional_order_by :
                         | ORDER BY order_by_list"""
    if len(p) == 1:
        p[0] = None
    else:
        p[0] = p[3]


def p_order_by_list(p):
    """order_by_list : strict_order_by_list
                     | strict_order_by_list COMMA"""
    p[0] = p[1]


def p_strict_order_by_list(p):
    """strict_order_by_list : ordering
                            | strict_order_by_list COMMA ordering"""
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[1].append(p[3])
        p[0] = p[1]


def p_ordering_asc(p):
    """ordering : column_id
                | column_id ASC"""
    p[0] = tq_ast.Ordering(p[1], True)


def p_ordering_desc(p):
    """ordering : column_id DESC"""
    p[0] = tq_ast.Ordering(p[1], False)


def p_column_id_list(p):
    """column_id_list : strict_column_id_list
                      | strict_column_id_list COMMA"""
    p[0] = p[1]


def p_strict_column_id_list(p):
    """strict_column_id_list : column_id
                             | strict_column_id_list COMMA column_id
    """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[1].append(p[3])
        p[0] = p[1]


def p_optional_limit(p):
    """optional_limit :
                      | LIMIT INTEGER
    """
    if len(p) == 1:
        p[0] = None
    else:
        p[0] = p[2]


def p_table_expr_table_or_union(p):
    """full_table_expr : aliased_table_expr_list"""
    # Unions are special in their naming rules, so we only call a table list a
    # union if it has at least two tables. Otherwise, it's just a table.
    if len(p[1]) == 1:
        p[0] = p[1][0]
    else:
        p[0] = tq_ast.TableUnion(p[1])


def p_non_cross_join(p):
    """non_cross_join : LEFT OUTER JOIN
                      | LEFT OUTER JOIN EACH
                      | LEFT JOIN
                      | LEFT JOIN EACH
                      | JOIN
                      | JOIN EACH
    """
    if p[1].upper() == 'LEFT':
        p[0] = tq_ast.JoinType.LEFT_OUTER
    else:
        p[0] = tq_ast.JoinType.INNER


def p_cross_join(p):
    """cross_join : CROSS JOIN
                  | CROSS JOIN EACH
    """
    p[0] = tq_ast.JoinType.CROSS


def p_partial_join(p):
    """partial_join : non_cross_join aliased_table_expr ON expression
                    | cross_join aliased_table_expr
    """
    if p[1] is tq_ast.JoinType.CROSS:
        p[0] = tq_ast.PartialJoin(p[2], p[1], None)
    else:
        p[0] = tq_ast.PartialJoin(p[2], p[1], p[4])


def p_join_tail(p):
    """join_tail : partial_join join_tail
                 | partial_join
    """
    if len(p) == 2:
        # This is the last part of the join
        p[0] = [p[1]]
    else:
        p[0] = [p[1]] + p[2]


def p_join(p):
    """full_table_expr : aliased_table_expr join_tail"""
    p[0] = tq_ast.Join(p[1], p[2])


def p_aliased_table_expr_list(p):
    """aliased_table_expr_list : strict_aliased_table_expr_list
                               | strict_aliased_table_expr_list COMMA"""
    p[0] = p[1]


def p_strict_aliased_table_expr_list(p):
    """strict_aliased_table_expr_list : aliased_table_expr
                                      | strict_aliased_table_expr_list COMMA \
                                            aliased_table_expr
    """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[1].append(p[3])
        p[0] = p[1]


def p_aliased_table_expr(p):
    """aliased_table_expr : table_expr
                          | table_expr ID
                          | table_expr AS ID"""
    if len(p) == 2:
        p[0] = p[1]
    else:
        if isinstance(p[1], tq_ast.TableId):
            p[0] = tq_ast.TableId(p[1].name, p[len(p) - 1])
        elif isinstance(p[1], tq_ast.Select):
            p[0] = tq_ast.Select(p[1].select_fields, p[1].table_expr,
                                 p[1].where_expr, p[1].groups,
                                 p[1].having_expr, p[1].orderings, p[1].limit,
                                 p[len(p) - 1])
        else:
            assert False, 'Unexpected table_expr type: %s' % type(p[1])


def p_table_id(p):
    """table_expr : id_component_list"""
    p[0] = tq_ast.TableId(p[1], None)


def p_select_table_expression(p):
    """table_expr : select"""
    p[0] = p[1]


def p_table_expression_parens(p):
    """table_expr : LPAREN table_expr RPAREN"""
    p[0] = p[2]


def p_select_field_list(p):
    """select_field_list : strict_select_field_list
                         | strict_select_field_list COMMA"""
    p[0] = p[1]


def p_strict_select_field_list(p):
    """strict_select_field_list : select_field
                                | strict_select_field_list COMMA select_field
    """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[1].append(p[3])
        p[0] = p[1]


def p_select_field(p):
    """select_field : expression
                    | expression ID
                    | expression AS ID
                    | expression WITHIN RECORD AS ID
                    | expression WITHIN expression AS ID
    """
    within_record_type = None
    if len(p) > 2:
        alias = p[len(p) - 1]
        if len(p) > 3:
            if 'within' in p:
                within_record_type = p[len(p) - 3]
                if within_record_type == 'record':
                    within_record_type = within_record_type.upper()
                else:
                    within_record_type = within_record_type.name
    else:
        alias = None
    p[0] = tq_ast.SelectField(p[1], alias, within_record_type)


def p_select_star(p):
    """select_field : STAR"""
    p[0] = tq_ast.Star()


def p_expression_parens(p):
    """expression : LPAREN expression RPAREN"""
    p[0] = p[2]


def p_expression_is_null(p):
    """expression : expression IS NULL"""
    p[0] = tq_ast.UnaryOperator('is_null', p[1])


def p_expression_is_not_null(p):
    """expression : expression IS NOT NULL"""
    p[0] = tq_ast.UnaryOperator('is_not_null', p[1])


def p_expression_unary(p):
    """expression : MINUS expression
                  | NOT expression
    """
    p[0] = tq_ast.UnaryOperator(p[1], p[2])


def p_expression_binary(p):
    """expression : expression PLUS expression
                  | expression MINUS expression
                  | expression STAR expression
                  | expression DIVIDED_BY expression
                  | expression MOD expression
                  | expression EQUALS expression
                  | expression NOT_EQUAL expression
                  | expression GREATER_THAN expression
                  | expression LESS_THAN expression
                  | expression GREATER_THAN_OR_EQUAL expression
                  | expression LESS_THAN_OR_EQUAL expression
                  | expression AND expression
                  | expression OR expression
                  | expression CONTAINS expression
    """
    p[0] = tq_ast.BinaryOperator(p[2], p[1], p[3])


def p_expression_func_call(p):
    """expression : ID LPAREN arg_list RPAREN
                  | LEFT LPAREN arg_list RPAREN
    """
    # Note: we have to special-case LEFT, since it's both a keyword appearing
    # in LEFT JOIN, as well as a function.
    p[0] = tq_ast.FunctionCall(p[1].lower(), p[3])


def p_expression_count(p):
    """expression : COUNT LPAREN arg_list RPAREN"""
    p[0] = tq_ast.FunctionCall('count', p[3])


def p_expression_count_distinct(p):
    """expression : COUNT LPAREN DISTINCT arg_list RPAREN"""
    p[0] = tq_ast.FunctionCall('count_distinct', p[4])


def p_expression_count_star(p):
    """expression : COUNT LPAREN parenthesized_star RPAREN"""
    # Treat COUNT(*) as COUNT(1).
    p[0] = tq_ast.FunctionCall('count', [tq_ast.Literal(1)])


def p_parenthesized_star(p):
    """parenthesized_star : STAR
                          | LPAREN parenthesized_star RPAREN"""


def p_arg_list(p):
    """arg_list :
                | expression
                | arg_list COMMA expression"""
    if len(p) == 1:
        p[0] = []
    elif len(p) == 2:
        p[0] = [p[1]]
    elif len(p) == 4:
        p[1].append(p[3])
        p[0] = p[1]
    else:
        assert False, 'Unexpected number of captured tokens.'


def p_expression_in(p):
    """expression : expression IN LPAREN constant_list RPAREN"""
    p[0] = tq_ast.FunctionCall('in', [p[1]] + p[4])


def p_constant_list(p):
    """constant_list : strict_constant_list
                     | strict_constant_list COMMA"""
    p[0] = p[1]


def p_strict_constant_list(p):
    """strict_constant_list : constant
                            | strict_constant_list COMMA constant"""
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[1].append(p[3])
        p[0] = p[1]


def p_expression_constant(p):
    """expression : constant"""
    p[0] = p[1]


def p_int_literal(p):
    """constant : INTEGER"""
    p[0] = tq_ast.Literal(p[1])


def p_float_literal(p):
    """constant : FLOAT"""
    p[0] = tq_ast.Literal(p[1])


def p_string_literal(p):
    """constant : STRING"""
    p[0] = tq_ast.Literal(p[1])


def p_true_literal(p):
    """constant : TRUE"""
    p[0] = tq_ast.Literal(True)


def p_false_literal(p):
    """constant : FALSE"""
    p[0] = tq_ast.Literal(False)


def p_null_literal(p):
    """constant : NULL"""
    p[0] = tq_ast.Literal(None)


def p_expr_column_id(p):
    """expression : column_id"""
    p[0] = p[1]


def p_column_id(p):
    """column_id : id_component_list
                 | id_component_list DOT STAR"""
    if len(p) == 2:
        p[0] = tq_ast.ColumnId(p[1])
    else:
        p[0] = tq_ast.ColumnId(p[1] + '.*')


def p_id_component_list(p):
    """id_component_list : ID
                         | id_component_list DOT ID"""
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = p[1] + '.' + p[3]


def p_case_clause_else(p):
    """case_clause_else : ELSE expression"""
    p[0] = tq_ast.CaseClause(tq_ast.Literal(True), p[2])


def p_case_clause_when(p):
    """case_clause_when : WHEN expression THEN expression"""
    p[0] = tq_ast.CaseClause(p[2], p[4])


def p_case_body(p):
    """case_body : case_clause_when
                 | case_body case_clause_else
                 | case_clause_when case_body"""
    if len(p) == 2:
        # Just a bare when
        p[0] = [p[1]]
    elif isinstance(p[1], list):
        # body ELSE expression
        p[0] = p[1] + [p[2]]
    else:
        # WHEN ... THEN ... body
        p[0] = [p[1]] + p[2]


def p_expression_case(p):
    """expression : CASE case_body END"""
    p[0] = tq_ast.CaseExpression(p[2])


def p_error(p):
    raise SyntaxError('Unexpected token: %s' % p)


def parse_text(text):
    # If you're making changes to the parser, you need to run the the code with
    # SHOULD_REBUILD_PARSER=1 in order to update it.
    should_rebuild_parser = int(os.getenv('SHOULD_REBUILD_PARSER', '0'))
    if should_rebuild_parser:
        parser = yacc.yacc()
    else:
        from tinyquery import parsetab
        parser = yacc.yacc(debug=0, write_tables=0, tabmodule=parsetab)
    return parser.parse(text, lexer=lexer.get_lexer())
