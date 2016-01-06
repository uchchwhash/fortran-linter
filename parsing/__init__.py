
def location(text, index):
    line, start = text.count('\n', 0, index), text.rfind('\n', 0, index)
    column = index - (start + 1)
    return "{}:{}".format(line + 1, column + 1)


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
        return "value {} from {} to {}".format(self.value, 
                location(self.text, self.start), location(self.text, self.end))

    def __repr__(self):
        return "Success({}, {}, {}, {})".format(self.text,
                location(self.text, self.start), location(self.text, self.end),
                self.value)


class parser(object):
    def __init__(self, me):
        '''this `me` function should return a `Success` object if successful,
        or raise a `Failure` exception if not'''
        if isinstance(me, str):
            desc = me

            def inner(f):
                self.me = f
                self.desc = desc
            return inner

        self.me = me
        self.desc = None

    def parse(self, text, start=0):
        '''apply the parser to `text` at position `start`'''
        return self.me(text, start)

    def bind(self, function):
        '''the `function`, given a `Success` object, should return a parser
        that acts on the rest of the input
        (shortcut: >=)'''
        @parser
        def inner(text, start):
            success_self = self.parse(text, start)
            then = function(success_self)
            success_then = then.parse(text, success_self.end)
            return Success(text, start, success_then.end, success_then.value)
        return inner

    def __ge__(self, function):
        '''>= is shortcut for bind'''
        return self.bind(function)

    def ignore(self, other):
        '''apply self, ignore result, and apply other
        (shortcut: >>)'''
        #@parser
        #def inner(text, start):
        #    success = self.parse(text, start)
        #    return other.parse(text, success.start)
        #return inner
        return self >= (lambda _: other)

    def __rshift__(self, other):
        '''>> is shortcut for ignore'''
        return self.ignore(other)

    def ignore_following(self, other):
        '''apply self, apply other, return result of self
        (shortcut: <<)'''
        @parser
        def inner(text, start):
            success_self = self.parse(text, start)
            success_other = other.parse(text, success_self.end)
            return Success(text, start, success_other.end, success_self.value)
        return inner

    def __lshift__(self, other):
        '''<< is shortcut for ignore_following'''
        return self.ignore_following(other)

    def choice(self, other):
        '''if self fails and does not consume anything, applies other
        (shortcut: ^)'''
        @parser
        def inner(text, start):
            try:
                return self.parse(text, start)
            except Failure as failure:
                if failure.start != start:
                    raise failure
                else:
                    return other.parse(text, start)
        return inner

    def __xor__(self, other):
        '''^ is shortcut for choice'''
        return self.choice(other)

    def try_choice(self, other):
        '''if self fails, applies other (shortcut: |)'''
        @parser
        def inner(text, start):
            try:
                return self.parse(text, start)
            except Failure:
                return other.parse(text, start)
        return inner

    def __or__(self, other):
        '''| is shortcut for try_choice'''
        return self.try_choice(other)

    def seq(self, other):
        '''applies self, then applies other, and returns the sum of results
        (shortcut: +)'''
        @parser
        def inner(text, start):
            success_self = self.parse(text, start)
            success_other = other.parse(text, success_self.end)
            return Success(text, start, success_other.end, 
                    success_self.value + success_other.value)
        return inner

    def __add__(self, other):
        '''+ is shortcut for seq'''
        return self.seq(other)

    def label(self, desc):
        '''labels a failure with `desc` (shortcut: %)'''
        return self | fail(desc)

    def __mod__(self, desc):
        '''% is shortcut for label'''
        return self.label(desc)

    def map(self, function):
        '''a parser that applies `function` on the result of self
        (shortcut: //)'''
        #return self >= (lambda success: 
        #        parser(lambda text, index:
        #            Success(text, index, function(success.value))))
        @parser
        def inner(text, start):
            success = self.parse(text, start)
            return Success(text, success.start, success.end, function(success.value))
        return inner

    def __floordiv__(self, function):
        '''// is shortcut for map'''
        return self.map(function)

    def guard(self, predicate, desc):
        @parser
        def inner(text, start):
            success = self.parse(text, start)
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
                    success = self.parse(text, current)
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


def fail(desc):
    '''a parser that fails without consuming input by raising
    an exception with message `desc`'''
    @parser
    def inner(text, start):
        raise Failure(text, start, desc)
    return inner


def succeed(value):
    '''a parser which always succeeds without consuming input
    and returns given `value`
    equivalent to `return` in Haskell'''
    return parser(lambda text, start: Success(text, start, start, value))


def terminal(string):
    '''only matches the exact `string`'''
    @parser 
    def inner(text, start):
        whole = len(string)

        if text[start: start + whole] == string:
            return Success(text, start, start + whole, string)
        else:
            raise Failure(text, start, repr(string))

    return inner


def _EOF():
    '''only matches EOF'''
    @parser
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


def satisfy(predicate, desc):
    '''recognize a character satisfying given `predicate`'''
    @parser
    def inner(text, start):
        if start < len(text) and predicate(text[start]):
            return Success(text, start, start + 1, text[start])
        else:
            raise Failure(text, start, desc)
    return inner


def one_of(ls):
    '''recognize any of the given characters'''
    return satisfy(lambda c: c in ls, "one of {}".format(ls))


def none_of(ls):
    '''consumes a character that is not on the list `ls`'''
    return satisfy(lambda c: c not in ls, "none of {}".format(ls))


#def join(zero=None):
#    '''join for a monoid'''
#    if zero is None:
#        zero = ''
#
#    def inner(ls):
#        result = zero
#
#        for e in ls:
#            result += e
#
#        return result
#    return inner
def join(ls):
    return "".join(ls)


space = satisfy(lambda c: c.isspace(), "whitespace")

spaces = (+space // join) % "whitespaces"

whitespace = (~space // join) % "optional whitespace"

letter = satisfy(lambda c: c.isalpha(), "letter")

word = (+letter // join) % "word"

digit = satisfy(lambda c: c.isdigit(), "digit")

digits = (+digit // join) % "digits"

alphanumeric = satisfy(lambda c: c.isalnum(), "alphanumeric")

alphanumerics = (+alphanumeric // join) % "alphanumerics"


def separated_by(me, sep, empty=None):
    'list of `me` parsers separated by `sep` parsers'''
    @parser
    def inner(text, start):
        head = me.parse(text, start)
        tail = (~(sep >> me)).parse(text, head.end)
        return Success(text, start, tail.end, [head.value] + tail.value)
    
    if empty is None:
        return inner
    else:
        return inner | empty

def token(me):
    '''no fuss about surrounding whitespace'''
    return whitespace >> me << whitespace 


# not sure about this
import re
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


