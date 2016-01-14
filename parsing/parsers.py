import types
import copy
from itertools import chain

def location(text, index):
    if isinstance(text, str):
        line, start = text.count('\n', 0, index), text.rfind('\n', 0, index)
        column = index - (start + 1)
        return "{}:{}".format(line + 1, column + 1)
    else:
        return str(index + 1)


class Failure(Exception):
    def __init__(self, text, start, expected):
        self.text = text
        self.start = start
        self.expected = expected

        self.msg = "expected {} at {}".format(expected, location(text, start))
        super(Failure, self).__init__(self.msg)


class Success(object):
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


def parser(param):
    class ParsingFunction(AbstractParser):
        def __init__(self, me, expected):
            '''this `me` function should return a `Success` object if successful,
            or raise a `Failure` exception if not'''
            self.me = me
            self.expected = expected

        def scan(self, text, start=0):
	    try:
                return self.me(text, start)
	    except Failure as failure:
		if self.expected is None:
                    raise failure
                else:
		    raise Failure(text, start, self.expected)

    if isinstance(param, str) or isinstance(param, unicode):
        expected = param

        def inner(me):
	    return ParsingFunction(me, expected)

        return inner

    elif isinstance(param, types.FunctionType):
	expected = None
	me = param

	return ParsingFunction(me, expected)

    else:
	raise ValueError("param {} is neither a string nor a function"
		         .format(param))


class AbstractParser(object):

    def scan(self, text, start=0):
	'''virtual method that subclasses should override
        returns a `Success` object or raises `Failure`'''
        raise NotImplementedError("scan not implemented in AbstractParser")

    def parse(self, text, start=0):
        '''apply parser and return success value'''
        return self.scan(text, start).value

    def ignore(self, other):
        '''apply self, ignore result, and apply other
        (shortcut: >>)'''
	@parser
	def inner(text, start):
	    success_self = self.scan(text, start)
	    success_other = other.scan(text, success_self.end)
	    return Success(text, start, success_other.end, success_other.value)
	return inner

    def __rshift__(self, other):
        '''>> is shortcut for ignore'''
        return self.ignore(other)

    def ignore_following(self, other):
        '''apply self, apply other, return result of self
        (shortcut: <<)'''
        @parser
        def inner(text, start):
            success_self = self.scan(text, start)
            success_other = other.scan(text, success_self.end)
            return Success(text, start, success_other.end, success_self.value)
        return inner

    def __lshift__(self, other):
        '''<< is shortcut for ignore_following'''
        return self.ignore_following(other)

    def choice_no_backtrack(self, other):
        '''if self fails and does not consume anything, applies other
        (shortcut: ^)'''
        return ChoiceNoBacktrackParser(self, other)

    def __xor__(self, other):
        '''^ is shortcut for choice'''
        return self.choice_no_backtrack(other)

    def choice(self, other):
        '''if self fails, applies other (shortcut: |)'''
        return ChoiceParser(self, other)

    def __or__(self, other):
        '''| is shortcut for try_choice'''
        return self.choice(other)

    def seq(self, other):
        '''applies self, then applies other, and returns the sum of results
        (shortcut: +)'''
        return SequenceParser(self, other)

    def __add__(self, other):
        '''+ is shortcut for seq'''
        return self.seq(other)

    def label(self, expected):
        '''labels a failure with `expected` (shortcut: %)'''
	@parser(expected)
	def inner(text, start):
	    return self.scan(text, start)
	return inner

    def __mod__(self, expected):
        '''% is shortcut for label'''
        return self.label(expected)

    def map(self, function):
        '''a parser that applies `function` on the result of self
        (shortcut: //)'''
        @parser
        def inner(text, start):
            success = self.scan(text, start)
            return Success(text, success.start, success.end,
                           function(success.value))
        return inner

    def __floordiv__(self, function):
        '''// is shortcut for map'''
        return self.map(function)

    def guard(self, predicate, desc):
        @parser
        def inner(text, start):
            success = self.scan(text, start)
            if predicate(success.value):
                return success
            else:
                raise Failure(text, start, desc)
        return inner

    def between(self, n, m):
        '''parser that applies self between `n` and `m` times
        and returns a list of values'''
        @parser
        def inner(text, start):
            result = []
            count = 0

            current = start

            while count < m:
                try:
                    success = self.scan(text, current)
                    result += [success.value]
                    current = success.end
                    count = count + 1

                except Failure as failure:
                    if count >= n:
                        break
                    raise failure

            return Success(text, start, current, result)
        return inner

    def times(self, n):
        '''match exactly `n` times (shortcut: *)
        this is not the Kleene star (shortcut: ~)'''
        return self.between(n, n)

    def __mul__(self, n):
        '''* is shortcut for times'''
        return self.times(n)

    def optional(self):
        '''optionally matches self (shortcut: -)'''
        return self.between(0, 1)

    def __neg__(self):
        '''- is shortcut for optional'''
        return self.optional()

    def many(self):
        '''matches zero or more occurrences (shortcut: ~)'''
        return self.between(0, float('inf'))

    def __invert__(self):
        '''~ is shortcut for many'''
        return self.many()

    def at_least_once(self):
        '''matches self at least once (shortcut: +)'''
        return self.between(1, float('inf'))

    def __pos__(self):
        '''+ is shortcut for at_least_once'''
        return self.at_least_once()

def merge_parser_lists(this, that, kind):
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
        if this.expected is None:
            return that.expected
        elif that.expected is None:
            return this.expected
        else:
            return this.expected + conjunction + that.expected


class ChoiceNoBacktrackParser(AbstractParser):
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
    def __init__(self, this, that):
        self.expected = merge_expected(this, that, " or ")
        self.parsers = merge_parser_lists(this, that, ChoiceParser)

    def scan(self, text, start=0):
        for this in self.parsers:
            try:
                return this.scan(text, start)
            except Failure as f:
                pass

        raise Failure(text, start, self.expected)


class SequenceParser(AbstractParser):
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
    '''a parser that fails without consuming input by raising
    an exception with message `desc`'''
    @parser(desc)
    def inner(text, start):
        raise Failure(text, start, desc)
    return inner


def succeed(value):
    '''a parser which always succeeds without consuming input
    and returns given `value`
    equivalent to `return` in Haskell'''
    @parser("never")
    def inner(text, start):
	return Success(text, start, start, value)
    return inner


def _EOF():
    '''only matches EOF'''
    @parser("<EOF>")
    def inner(text, start):
        if start >= len(text):
            return Success(text, start, start, None)
        else:
            raise Failure(text, start, "<EOF>")
    return inner


EOF = _EOF()

def singleton(string):
    # interesting alternative names: capture, lift
    '''return a list with a single member
    useful when collecting result of parsers chained by `seq`'''
    return [string]


def concat(ls):
    return list(chain(*ls))


def join(ls):
    return "".join(ls)


def matches(me, text, start=0):
    try:
        _ = me.scan(text, start)
        return True
    except Failure:
        return False
