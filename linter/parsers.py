"""
Some useful parser combinators.
"""

import types
from itertools import chain


def location(text, index):
    """
    Location of `index` in the `text`. Report row and column numbers when
    appropriate.

    """
    if isinstance(text, str):
        line, start = text.count('\n', 0, index), text.rfind('\n', 0, index)
        column = index - (start + 1)
        return "{}:{}".format(line + 1, column + 1)
    else:
        return str(index + 1)


class Failure(Exception):
    """ Represents parsing failure. Can be raised as an :class:`Exception`. """
    def __init__(self, text, start, expected):
        self.text = text
        self.start = start
        self.expected = expected

        self.msg = "expected {} at {}".format(expected, location(text, start))
        super(Failure, self).__init__(self.msg)

    def __str__(self):
        return self.msg

    def __repr__(self):
        return ("Failure({}, {}, {})"
                .format(self.text, self.start, self.expected))


class Success(object):
    """ Represents parsing success. Stores the parsed value. """
    def __init__(self, text, start, end, value):
        self.text = text
        self.start = start
        self.end = end
        self.value = value

    def __str__(self):
        return ("value {} from {} to {}"
                .format(self.value, location(self.text, self.start),
                        location(self.text, self.end)))

    def __repr__(self):
        return ("Success({}, {}, {}, {})"
                .format(self.text, location(self.text, self.start),
                        location(self.text, self.end),
                        self.value))


class AbstractParser(object):
    """
    A base class for parser objects.
    """

    def scan(self, text, start=0):
        """
        A virtual method that subclasses should override.
        Returns a :class:`Success` object or raises :class:`Failure`.
        """
        raise NotImplementedError("scan not implemented in AbstractParser")

    def parse(self, text, start=0):
        """ Apply the parser and return success value assuming it succeeds. """
        return self.scan(text, start).value

    def ignore(self, other):
        """
        Apply `self`, ignore result, and apply `other` (shortcut: ``>>``).
        """
        @parser
        def inner(text, start):
            """ The function doing the actual parsing. """
            success_self = self.scan(text, start)
            success_other = other.scan(text, success_self.end)
            return Success(text, start, success_other.end, success_other.value)
        return inner

    def __rshift__(self, other):
        """ ``>>`` is shortcut for `ignore`. """
        return self.ignore(other)

    def ignore_following(self, other):
        """
        Apply `self`, apply `other`, return result of `self`
        (shortcut: ``<<``).
        """
        @parser
        def inner(text, start):
            """ The function doing the actual parsing. """
            success_self = self.scan(text, start)
            success_other = other.scan(text, success_self.end)
            return Success(text, start, success_other.end, success_self.value)
        return inner

    def __lshift__(self, other):
        """ ``<<`` is shortcut for `ignore_following`. """
        return self.ignore_following(other)

    def choice_no_backtrack(self, other):
        """
        If `self` fails and does not consume anything,
        applies `other` (shortcut: ``^``).
        """
        return ChoiceNoBacktrackParser(self, other)

    def __xor__(self, other):
        """ ``^`` is shortcut for `choice_no_backtrack`. """
        return self.choice_no_backtrack(other)

    def choice(self, other):
        """ If `self` fails, applies `other` (shortcut: ``|``). """
        return ChoiceParser(self, other)

    def __or__(self, other):
        """ ``|`` is shortcut for `choice`. """
        return self.choice(other)

    def seq(self, other):
        """
        Applies `self`, then applies `other`,
        and returns the sum of results (shortcut: ``+``).
        """
        return SequenceParser(self, other)

    def __add__(self, other):
        """ ``+`` is shortcut for `seq`. """
        return self.seq(other)

    def label(self, expected):
        """ Labels a failure with `expected` (shortcut: ``%``). """
        @parser(expected)
        def inner(text, start):
            """ The function doing the actual parsing. """
            return self.scan(text, start)
        return inner

    def __mod__(self, expected):
        """ ``%`` is shortcut for `label`. """
        return self.label(expected)

    def map(self, function):
        """
        A parser that applies `function` on the result of `self`
        (shortcut: ``//``).
        """
        @parser
        def inner(text, start):
            """ The function doing the actual parsing. """
            success = self.scan(text, start)
            return Success(text, success.start, success.end,
                           function(success.value))
        return inner

    def __floordiv__(self, function):
        """ ``//`` is shortcut for `map`. """
        return self.map(function)

    def guard(self, predicate, desc):
        """ Check if the parse result satisfies a `predicate`. """
        @parser
        def inner(text, start):
            """ The function doing the actual parsing. """
            success = self.scan(text, start)
            if predicate(success.value):
                return success
            else:
                raise Failure(text, start, desc)
        return inner

    def between(self, minimum, maximum):
        """
        A parser that applies `self` between `minimum`
        and `maximum` times and returns a list of values.
        """
        @parser
        def inner(text, start):
            """ The function doing the actual parsing. """
            result = []
            count = 0

            current = start

            while count < maximum:
                try:
                    success = self.scan(text, current)
                    result += [success.value]
                    current = success.end
                    count = count + 1

                except Failure as failure:
                    if count >= minimum:
                        break
                    raise failure

            return Success(text, start, current, result)
        return inner

    def times(self, exact):
        """
        Match `exact` number of times (shortcut: ``*``).
        This is not the Kleene star (shortcut: ``~``).
        """
        return self.between(exact, exact)

    def __mul__(self, exact):
        """ ``*`` is shortcut for `times`. """
        return self.times(exact)

    def optional(self):
        """ Optionally matches `self` (shortcut: ``-``). """
        return self.between(0, 1)

    def __neg__(self):
        """ ``-`` is shortcut for `optional`. """
        return self.optional()

    def many(self):
        """ Matches zero or more occurrences (shortcut: ``~``). """
        return self.between(0, float('inf'))

    def __invert__(self):
        """ ``~`` is shortcut for `many`. """
        return self.many()

    def at_least_once(self):
        """ Matches self at least once (shortcut: prefix ``+``). """
        return self.between(1, float('inf'))

    def __pos__(self):
        """ ``+`` is shortcut for `at_least_once`. """
        return self.at_least_once()


def parser(param):
    """
    Construct a parser from either a given function object
    or a string to match.
    """
    class ParsingFunction(AbstractParser):
        """
        A class to hold the parsing function.
        """
        def __init__(self, this, expected):
            """
            The function `this` should return a :class:`Success` object if successful,
            or raise a :class:`Failure` exception if not.
            """
            self.this = this
            self.expected = expected

        def scan(self, text, start=0):
            """
            Run the parsing function.
            """
            try:
                return self.this(text, start)
            except Failure as failure:
                if self.expected is None:
                    raise failure
                else:
                    raise Failure(text, start, self.expected)

    if isinstance(param, str) or isinstance(param, unicode):
        expected = param

        def inner(this):
            """ Convert `this` to a :class:`ParsingFunction`. """
            return ParsingFunction(this, expected)

        return inner

    elif isinstance(param, types.FunctionType):
        expected = None
        this = param

        return ParsingFunction(this, expected)

    else:
        raise ValueError("param {} is neither a string nor a function"
                         .format(param))


def merge_parser_lists(this, that, kind):
    """ Merge two lists containing parsers. """
    if isinstance(this, kind):
        if isinstance(that, kind):
            return this.parsers + that.parsers
        else:
            return this.parsers + [that]
    else:
        if isinstance(that, kind):
            return [this] + that.parsers
        else:
            return [this, that]


def merge_expected(this, that, conjunction):
    """ Returns a description to be printed when parsing fails. """
    if this.expected is None:
        return that.expected
    elif that.expected is None:
        return this.expected
    else:
        return this.expected + conjunction + that.expected


class ChoiceNoBacktrackParser(AbstractParser):
    """
    A parser that matches any of a list of choices. Fails if any input is
    consumed when trying out a choice that ultimately fails.
    """
    def __init__(self, this, that):
        self.expected = merge_expected(this, that, " or ")
        self.parsers = merge_parser_lists(this, that, ChoiceNoBacktrackParser)

    def scan(self, text, start=0):
        for this in self.parsers:
            try:
                return this.scan(text, start)
            except Failure as failure:
                if failure.start != start:
                    raise Failure
                else:
                    pass

        raise Failure(text, start, self.expected)


class ChoiceParser(AbstractParser):
    """
    A parser that matches any of a list of choices. Backtracks
    to the beginning of consumption in case of failure.
    """
    def __init__(self, this, that):
        self.expected = merge_expected(this, that, " or ")
        self.parsers = merge_parser_lists(this, that, ChoiceParser)

    def scan(self, text, start=0):
        for this in self.parsers:
            try:
                return this.scan(text, start)
            except Failure:
                pass

        raise Failure(text, start, self.expected)


class SequenceParser(AbstractParser):
    """ A list of parsers to be applied sequentially. """
    def __init__(self, this, that):
        self.expected = merge_expected(this, that, " followed by ")
        self.parsers = merge_parser_lists(this, that, SequenceParser)

    def scan(self, text, start=0):
        success = self.parsers[0].scan(text, start)
        result = success.value

        for this in self.parsers[1:]:
            success = this.scan(text, success.end)
            result += success.value

        return Success(text, start, success.end, result)


def fail(desc):
    """
    A parser that fails without consuming input by raising
    an exception with message `desc`.
    """
    @parser(desc)
    def inner(text, start):
        """ Fail unconditionally. """
        raise Failure(text, start, desc)
    return inner


def succeed(value):
    """
    A parser which always succeeds without consuming input
    and returns given `value`.
    Equivalent to ``return`` in Haskell.
    """
    @parser("never")
    def inner(text, start):
        """ Succeed unconditionally. """
        return Success(text, start, start, value)
    return inner


def _eof():
    """ Only matches EOF. """
    @parser("<EOF>")
    def inner(text, start):
        """ Parse `None` when EOF, fail otherwise. """
        if start >= len(text):
            return Success(text, start, start, None)
        else:
            raise Failure(text, start, "<EOF>")
    return inner


#: a parser to detect EOF
EOF = _eof()


def singleton(string):
    """
    Return a list with a single member.
    Useful when collecting result of parsers chained by `seq`.
    """
    # interesting alternative names: capture, lift
    return [string]


def concat(list_of_lists):
    """ Concatenates a list of lists. """
    return list(chain(*list_of_lists))


def join(list_of_str):
    """ Joins a list of strings. """
    return "".join(list_of_str)


def matches(this, text, start=0):
    """ Returns whether the parser `this` matches the `text`. """
    try:
        _ = this.scan(text, start)
        return True
    except Failure:
        return False
