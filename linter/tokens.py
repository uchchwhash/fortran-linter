"""
Some lowest-level parsers, that is, tokenizers.
"""
import re

from .parsers import parser, join
from .parsers import Success, Failure


def exact(string, ignore_case=False):
    """ Only matches the exact `string`. """
    if ignore_case:
        string = string.lower()

    @parser(repr(string))
    def inner(text, start):
        """ A parser for the `string`. """
        whole = len(string)

        segment = text[start: start + whole]
        if ignore_case:
            segment = segment.lower()

        if segment == string:
            return Success(text, start, start + whole, string)
        else:
            raise Failure(text, start, repr(string))

    return inner


def satisfies(predicate, desc):
    """ Recognize a character satisfying given `predicate`. """
    @parser(desc)
    def inner(text, start):
        """ A parser that applies the `predicate`. """
        if start < len(text) and predicate(text[start]):
            return Success(text, start, start + 1, text[start])
        else:
            raise Failure(text, start, desc)
    return inner


def one_of(chars):
    """ Recognize any of the given characters `chars`. """
    return satisfies(lambda c: c in chars, "one of {}".format(chars))


def none_of(chars):
    """ Consumes a character that is not on the list `chars`. """
    return satisfies(lambda c: c not in chars, "none of {}".format(chars))


#: succeeds for any character
wildcard = satisfies(lambda c: True, "")

#: matches a space character
space = satisfies(lambda c: c.isspace(), "whitespace")

#: matches whitespace
spaces = (+space // join) % "whitespaces"

#: matches optional whitespace
whitespace = (~space // join) % "optional whitespace"

#: matches a letter
letter = satisfies(lambda c: c.isalpha(), "letter")

#: matches a word
word = (+letter // join) % "word"

#: matches a digit
digit = satisfies(lambda c: c.isdigit(), "digit")

#: matches a list of digits
digits = (+digit // join) % "digits"

#: matches one alphanumeric character
alphanumeric = satisfies(lambda c: c.isalnum(), "alphanumeric")

#: matches multiple alphanumeric characters
alphanumerics = (+alphanumeric // join) % "alphanumerics"


def separated_by(prsr, sep, empty=None):
    """ A list of `prsr` parsers separated by `sep` parsers. """
    @parser
    def inner(text, start):
        """ A parser that returns the list of values parsed by `prsr`. """
        head = prsr.scan(text, start)
        tail = (~(sep >> prsr)).scan(text, head.end)
        return Success(text, start, tail.end, [head.value] + tail.value)

    if empty is None:
        return inner
    else:
        return inner | empty


def liberal(prsr):
    """ No fuss about surrounding whitespace. """
    return whitespace >> prsr << whitespace


def regex(exp, flags=0):
    """ Match a regex. Perhaps too powerful. """
    if isinstance(exp, str):
        exp = re.compile(exp, flags)

    @parser
    def inner(text, start):
        """ A parser that applies the regex. """
        match = exp.match(text, start)

        if match:
            return Success(text, match.start(), match.end(), match)
        else:
            raise Failure(text, start, exp.pattern)
    return inner
