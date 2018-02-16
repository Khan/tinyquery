"""The lexer turns a query string into a stream of tokens."""
from __future__ import absolute_import

from ply import lex


# The keys here should all be lowercase, since we convert tokens to lowercase
# before looking them up in this map.
reserved_words = {
    'select': 'SELECT',
    'as': 'AS',
    'from': 'FROM',
    'where': 'WHERE',
    'having': 'HAVING',
    'join': 'JOIN',
    'on': 'ON',
    'group': 'GROUP',
    'by': 'BY',
    'each': 'EACH',
    'left': 'LEFT',
    'outer': 'OUTER',
    'cross': 'CROSS',
    'order': 'ORDER',
    'asc': 'ASC',
    'desc': 'DESC',
    'limit': 'LIMIT',
    'and': 'AND',
    'or': 'OR',
    'not': 'NOT',
    'is': 'IS',
    'null': 'NULL',
    'true': 'TRUE',
    'false': 'FALSE',
    'in': 'IN',
    'count': 'COUNT',
    'distinct': 'DISTINCT',
    'case': 'CASE',
    'when': 'WHEN',
    'then': 'THEN',
    'else': 'ELSE',
    'end': 'END',
    'contains': 'CONTAINS',
    'within': 'WITHIN',
    'record': 'RECORD'
}

tokens = [
    'PLUS',
    'MINUS',
    'STAR',
    'DIVIDED_BY',
    'MOD',
    'EQUALS',
    'NOT_EQUAL',
    'GREATER_THAN',
    'LESS_THAN',
    'GREATER_THAN_OR_EQUAL',
    'LESS_THAN_OR_EQUAL',
    'LPAREN',
    'RPAREN',
    'COMMA',
    'DOT',
    'INTEGER',
    'FLOAT',
    'ID',
    'STRING'
] + list(reserved_words.values())  # wrapping with list() to support python 3


t_PLUS = r'\+'
t_MINUS = r'-'
t_STAR = r'\*'
t_DIVIDED_BY = r'/'
t_MOD = r'%'
t_EQUALS = r'==|='
t_NOT_EQUAL = r'!='
t_GREATER_THAN = r'>'
t_LESS_THAN = r'<'
t_GREATER_THAN_OR_EQUAL = r'>='
t_LESS_THAN_OR_EQUAL = r'<='
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_COMMA = r','
t_DOT = r'\.'


def string_regex(delim):
    # TODO(colin): do strings with the 'r' prefix get treated any differently
    # by bigquery?
    return 'r?{0}[^{0}]*{0}'.format(delim)


@lex.TOKEN(string_regex("'") + '|' + string_regex('"'))
def t_STRING(t):
    # TODO: Escaped quotation marks and other escapes.
    t.value = t.value.strip('r')[1:-1]
    return t


def t_FLOAT(token):
    r"""\d+\.\d+((e|E)\d+)?"""
    token.value = float(token.value)
    return token


def t_INTEGER(token):
    r"""\d+((e|E)\d+)?"""
    try:
        token.value = int(token.value)
    except ValueError:
        print("Integer value too large %d", token.value)
        token.value = 0
    return token


# Taken from example at http://www.dabeaz.com/ply/ply.html#ply_nn6
def t_ID(t):
    r"""[a-zA-Z_][a-zA-Z_0-9]*"""
    # Specific tokens should be lower-cased here, but functions can't be
    # lower-cased at lex time since we don't know what IDs are functions vs.
    # columns or tables. We lower-case function names at parse time.
    if t.value.lower() in reserved_words:
        t.value = t.value.lower()
        t.type = reserved_words[t.value.lower()]
    else:
        t.type = 'ID'
    return t


def t_brackets_id(t):
    r"""\[[a-zA-Z_0-9\.]*\]"""
    # Tokens can be surrounded with square brackets, in which case they're
    # allowed to start with numbers and contain dots. Tokens specified this way
    # are NOT allowed to be regular keywords, so we don't do that check like in
    # t_ID.
    t.value = t.value[1:-1]
    t.type = 'ID'
    return t


def t_COMMENT(t):
    r"""--.*|\#.*|//.*"""


t_ignore = ' \t\n'


def t_error(t):
    raise SyntaxError('Unexpected token: ' + str(t))


def lex_text(text):
    lexer = get_lexer()
    lexer.input(text)
    result = []
    while True:
        token = lex.token()
        if token:
            result.append(token)
        else:
            break
    return result


def get_lexer():
    return lex.lex()
