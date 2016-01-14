from .parsers import parser, join
from .parsers import Success, Failure

import re

def exact(string):
    '''only matches the exact `string`'''
    @parser(repr(string))
    def inner(text, start):
        whole = len(string)

        if text[start: start + whole] == string:
            return Success(text, start, start + whole, string)
        else:
            raise Failure(text, start, repr(string))

    return inner


def satisfies(predicate, desc):
    '''recognize a character satisfying given `predicate`'''
    @parser(desc)
    def inner(text, start):
        if start < len(text) and predicate(text[start]):
            return Success(text, start, start + 1, text[start])
        else:
            raise Failure(text, start, desc)
    return inner


def one_of(ls):
    '''recognize any of the given characters'''
    return satisfies(lambda c: c in ls, "one of {}".format(ls))


def none_of(ls):
    '''consumes a character that is not on the list `ls`'''
    return satisfies(lambda c: c not in ls, "none of {}".format(ls))


wildcard = satisfies(lambda c: True, "")

space = satisfies(lambda c: c.isspace(), "whitespace")

spaces = (+space // join) % "whitespaces"

whitespace = (~space // join) % "optional whitespace"

letter = satisfies(lambda c: c.isalpha(), "letter")

word = (+letter // join) % "word"

digit = satisfies(lambda c: c.isdigit(), "digit")

digits = (+digit // join) % "digits"

alphanumeric = satisfies(lambda c: c.isalnum(), "alphanumeric")

alphanumerics = (+alphanumeric // join) % "alphanumerics"


def separated_by(me, sep, empty=None):
    'list of `me` parsers separated by `sep` parsers'''
    @parser
    def inner(text, start):
        head = me.scan(text, start)
        tail = (~(sep >> me)).scan(text, head.end)
        return Success(text, start, tail.end, [head.value] + tail.value)

    if empty is None:
        return inner
    else:
        return inner | empty


def token(me):
    '''no fuss about surrounding whitespace'''
    return whitespace >> me << whitespace


# not sure about this
def regex(exp, flags=0):
    '''match a regex'''
    if isinstance(exp, str):
        exp = re.compile(exp, flags)

    @parser
    def inner(text, start):
        match = exp.match(text, start)

        if match:
            return Success(text, match.start(), match.end(), match)
        else:
            raise Failure(text, start, exp.pattern)
    return inner

