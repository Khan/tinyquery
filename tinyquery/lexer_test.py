from __future__ import absolute_import

import unittest

from tinyquery import lexer


plus = ('PLUS', '+')
minus = ('MINUS', '-')
star = ('STAR', '*')
divided_by = ('DIVIDED_BY', '/')
mod = ('MOD', '%')
equals = ('EQUALS', '=')
doubleequals = ('EQUALS', '==')
not_equal = ('NOT_EQUAL', '!=')
greater_than = ('GREATER_THAN', '>')
less_than = ('LESS_THAN', '<')
greater_than_or_equal = ('GREATER_THAN_OR_EQUAL', '>=')
less_than_or_equal = ('LESS_THAN_OR_EQUAL', '<=')
not_tok = ('NOT', 'not')
is_tok = ('IS', 'is')
null_tok = ('NULL', 'null')
true_tok = ('TRUE', 'true')
false_tok = ('FALSE', 'false')
in_tok = ('IN', 'in')
select = ('SELECT', 'select')
as_tok = ('AS', 'as')
from_tok = ('FROM', 'from')
where = ('WHERE', 'where')
join = ('JOIN', 'join')
on = ('ON', 'on')
group = ('GROUP', 'group')
by = ('BY', 'by')
each = ('EACH', 'each')
left = ('LEFT', 'left')
outer = ('OUTER', 'outer')
cross = ('CROSS', 'cross')
order = ('ORDER', 'order')
asc = ('ASC', 'asc')
desc = ('DESC', 'desc')
limit = ('LIMIT', 'limit')
lparen = ('LPAREN', '(')
rparen = ('RPAREN', ')')
comma = ('COMMA', ',')
dot = ('DOT', '.')
case = ('CASE', 'case')
when = ('WHEN', 'when')
then = ('THEN', 'then')
else_ = ('ELSE', 'else')
end = ('END', 'end')
contains = ('CONTAINS', 'contains')
within = ('WITHIN', 'within')
record = ('RECORD', 'record')
count = ('COUNT', 'count')


def int_(n):
    return 'INTEGER', n


def flt(f):
    return 'FLOAT', f


def ident(name):
    return 'ID', name


def string(s):
    return 'STRING', s


class LexerTest(unittest.TestCase):
    def assert_tokens(self, text, expected_tokens):
        tokens = lexer.lex_text(text)
        self.assertEqual(expected_tokens,
                         [(tok.type, tok.value) for tok in tokens])

    def test_lex_simple_select(self):
        self.assert_tokens('SELECT 0', [select, int_(0)])

    def test_lex_addition(self):
        self.assert_tokens('SELECT 1 + 2', [select, int_(1), plus, int_(2)])

    def test_arithmetic_operators(self):
        self.assert_tokens(
            'SELECT 0 + 1 - 2 * 3 / 4 % 5',
            [select, int_(0), plus, int_(1), minus, int_(2), star, int_(3),
             divided_by, int_(4), mod, int_(5)])

    def test_select_from_table(self):
        self.assert_tokens(
            'SELECT foo FROM bar',
            [select, ident('foo'), from_tok, ident('bar')])

    def test_comparisons(self):
        self.assert_tokens(
            'SELECT 1 > 2 <= 3 = 4 != 5 < 6 >= 7',
            [select, int_(1), greater_than, int_(2), less_than_or_equal,
             int_(3), equals, int_(4), not_equal, int_(5), less_than, int_(6),
             greater_than_or_equal, int_(7)]
        )

    def test_parens(self):
        self.assert_tokens(
            'SELECT 2 * (3 + 4)',
            [select, int_(2), star, lparen, int_(3), plus, int_(4), rparen]
        )

    def test_negative_numbers(self):
        self.assert_tokens(
            'SELECT -5',
            [select, minus, int_(5)]
        )

    def test_floating_numbers(self):
        self.assert_tokens(
            'SELECT 5.3',
            [select, flt(5.3)]
        )
        self.assert_tokens(
            'SELECT 5.3E4',
            [select, flt(53000.0)]
        )
        self.assert_tokens(
            'SELECT 5.3e2',
            [select, flt(530.0)]
        )

    def test_function_call(self):
        self.assert_tokens(
            'SELECT ABS(-5), POW(x, 3), NOW() FROM test_table',
            [select, ident('ABS'), lparen, minus, int_(5), rparen, comma,
             ident('POW'), lparen, ident('x'), comma, int_(3), rparen, comma,
             ident('NOW'), lparen, rparen, from_tok, ident('test_table')]
        )

    def test_select_where(self):
        self.assert_tokens(
            'SELECT foo FROM bar WHERE foo > 3',
            [select, ident('foo'), from_tok, ident('bar'), where, ident('foo'),
             greater_than, int_(3)]
        )

    def test_multiple_select(self):
        self.assert_tokens(
            'SELECT a AS foo, b bar, a + 1 baz FROM test_table',
            [select, ident('a'), as_tok, ident('foo'), comma, ident('b'),
             ident('bar'), comma, ident('a'), plus, int_(1), ident('baz'),
             from_tok, ident('test_table')])

    def test_aggregates(self):
        self.assert_tokens(
            'SELECT MAX(foo) FROM bar',
            [select, ident('MAX'), lparen, ident('foo'), rparen, from_tok,
             ident('bar')]
        )

    def test_group_by(self):
        self.assert_tokens(
            'SELECT foo FROM bar GROUP BY baz',
            [select, ident('foo'), from_tok, ident('bar'), group, by,
             ident('baz')])

    def test_select_multiple_tales(self):
        self.assert_tokens(
            'SELECT foo FROM table1, table2',
            [select, ident('foo'), from_tok, ident('table1'), comma,
             ident('table2')])

    def test_subquery(self):
        self.assert_tokens(
            'SELECT foo FROM (SELECT val + 1 AS foo FROM test_table)',
            [select, ident('foo'), from_tok, lparen, select, ident('val'),
             plus, int_(1), as_tok, ident('foo'), from_tok,
             ident('test_table'), rparen]
        )

    def test_join(self):
        self.assert_tokens(
            'SELECT foo FROM table1 JOIN table2 ON table1.bar = table2.bar',
            [select, ident('foo'), from_tok, ident('table1'), join,
             ident('table2'), on, ident('table1'), dot, ident('bar'), equals,
             ident('table2'), dot, ident('bar')]
        )

    def test_null_comparisons(self):
        self.assert_tokens(
            'SELECT foo IS NULL, bar IS NOT NULL FROM table1',
            [select, ident('foo'), is_tok, null_tok, comma, ident('bar'),
             is_tok, not_tok, null_tok, from_tok, ident('table1')]
        )

    def test_group_each_by(self):
        self.assert_tokens(
            'SELECT 0 FROM table GROUP EACH BY foo',
            [select, int_(0), from_tok, ident('table'), group, each, by,
             ident('foo')]
        )

    def test_string_literal(self):
        self.assert_tokens(
            'SELECT foo = "hello", bar == \'world\' FROM table',
            [select, ident('foo'), equals, string('hello'), comma,
             ident('bar'), doubleequals, string('world'), from_tok,
             ident('table')]
        )
        self.assert_tokens(
            'SELECT foo = r"hello", bar == r\'world\' FROM table',
            [select, ident('foo'), equals, string('hello'), comma,
             ident('bar'), doubleequals, string('world'), from_tok,
             ident('table')]
        )

    def test_other_literals(self):
        self.assert_tokens(
            'SELECT true, false, null',
            [select, true_tok, comma, false_tok, comma, null_tok])

    def test_in(self):
        self.assert_tokens(
            'SELECT 1 IN (1, 2)',
            [select, int_(1), in_tok, lparen, int_(1), comma, int_(2), rparen])

    def test_comment(self):
        self.assert_tokens(
            """
            SELECT -- This selects things
                foo -- The first field
                FROM bar
            """,
            [select, ident('foo'), from_tok, ident('bar')])
        self.assert_tokens(
            """
            SELECT # This selects things
                foo # The first field
                FROM bar
            """,
            [select, ident('foo'), from_tok, ident('bar')])
        self.assert_tokens(
            """
            SELECT // This selects things
                foo // The first field
                FROM bar
            """,
            [select, ident('foo'), from_tok, ident('bar')])

    def test_left_outer_join(self):
        self.assert_tokens(
            'SELECT foo FROM t1 LEFT OUTER JOIN EACH t2 ON t1.foo = t2.bar',
            [select, ident('foo'), from_tok, ident('t1'), left, outer, join,
             each, ident('t2'), on, ident('t1'), dot, ident('foo'), equals,
             ident('t2'), dot, ident('bar')])

    def test_cross_join(self):
        self.assert_tokens(
            'SELECT 0 FROM t1 CROSS JOIN t2',
            [select, int_(0), from_tok, ident('t1'), cross, join, ident('t2')]
        )

    def test_limit(self):
        self.assert_tokens(
            'SELECT * FROM my_table LIMIT 10',
            [select, star, from_tok, ident('my_table'), limit, int_(10)]
        )

    def test_order_by(self):
        self.assert_tokens(
            'SELECT * FROM my_table ORDER BY val DESC, val2 ASC,',
            [select, star, from_tok, ident('my_table'), order, by,
             ident('val'), desc, comma, ident('val2'), asc, comma]
        )

    def test_square_brackets(self):
        # It looks like square brackets are handled at lex time. For example,
        # putting a space between the square brackets and the table name isn't
        # allowed.
        self.assert_tokens(
            'SELECT [max](val) FROM [2014.test_table]',
            [select, ident('max'), lparen, ident('val'), rparen, from_tok,
             ident('2014.test_table')]
        )

    def test_contains(self):
        self.assert_tokens(
            'SELECT a CONTAINS b',
            [select, ident('a'), contains, ident('b')]
        )

    def test_within_record(self):
        self.assert_tokens(
            'SELECT COUNT(*) WITHIN RECORD AS something FROM bar',
            [select, count, lparen, star, rparen, within, record,
             as_tok, ident('something'), from_tok, ident('bar')]
        )

    def test_within_clause(self):
        self.assert_tokens(
            'SELECT COUNT(citiesLived.yearsLived) WITHIN citiesLived AS '
            'numberOfTimesInEachCity FROM table',
            [select, count, lparen, ident('citiesLived'), dot,
             ident('yearsLived'), rparen, within, ident('citiesLived'), as_tok,
             ident('numberOfTimesInEachCity'), from_tok, ident('table')]
        )

    def test_case(self):
        self.assert_tokens(
            'SELECT CASE WHEN x = 1 THEN 1 WHEN x = 2 THEN 4 ELSE 9 END',
            [select, case, when, ident('x'), equals, int_(1), then, int_(1),
             when, ident('x'), equals, int_(2), then, int_(4), else_, int_(9),
             end]
        )
