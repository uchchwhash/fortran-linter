""" Basic tests for parser combinators. """
import unittest

from .. import exact, Failure, EOF, singleton, succeed, regex
from .. import spaces, word, digit, digits

class TestBasic(unittest.TestCase):
    """ Basic test cases. """
    def setUp(self):
        """ Nothing to do. """
        pass

    def match(self, test, text, value, end=None):
        """ Check if a parser returns the intended value. """
        success = test.scan(text)

        self.assertEqual(success.value, value)
        if end is not None:
            self.assertEqual(success.end, end)

    def mismatch(self, test, text, expected, start=None):
        """ Check if a parser fails. """
        with self.assertRaises(Failure) as failure:
            test.scan(text)

        self.assertEqual(failure.exception.expected, expected)
        if start is not None:
            self.assertEqual(failure.exception.start, start)

    def test_exact(self):
        """ Test exact string matches. """
        text = "this"

        self.match(exact("this"), text, text, len(text))
        self.match(exact("th"), text, "th", len("th"))

        self.mismatch(exact("is"), text, repr("is"), 0)


    def test_succeed(self):
        """ Test the `succeed` parser that always succeeds. """
        text = "hello world"

        self.match(succeed(True), text, True, 0)

    def test_ignore(self):
        """ Test parsers that ignore parts of the input. """
        text = "hello world"

        test = exact("hello") >> exact(" ") >> exact("world")
        self.match(test, text, "world", len(text))
        self.match(test >> succeed("!"), text, "!", len(text))
        self.match(test >> EOF, text, None, len(text))

        self.mismatch(exact("hello") >> EOF, text, "<EOF>", len("hello"))


    def test_choice_no_backtrack(self):
        """ Test alternative choices of parsers. """
        text = "mocha"

        test = exact("mocha") ^ exact("latte")
        self.match(test, text, "mocha", len("mocha"))

        test = exact("latte") ^ exact("mocha")
        self.match(test, text, "mocha", len("mocha"))

        test = exact("hi") ^ exact("there")
        self.mismatch(test, text, "'hi' or 'there'", 0)

    def test_choice(self):
        """ Test backtracking choices of parsers. """
        text = "interpol"

        first = exact("inter") >> exact("national")
        second = exact("inter") >> exact("pol") >> succeed("police")
        test = first | second

        self.match(test, text, "police", len("interpol"))

    def test_label(self):
        """ Test labelled parsers and their fail messages. """
        text = "rising sun"

        first = exact("rising") >> exact(" ")
        second = (exact("venus") | exact("mercury")) % "planet"
        test = first >> second

        self.mismatch(test, text, "planet", len("rising "))


    def test_map(self):
        """ Test mapping a function over the parse results. """
        text = "hello world"

        first = exact("hello") // singleton
        second = (exact(" ") >> exact("world")) // singleton
        test = first + second

        self.match(test, text, ["hello", "world"])

    def test_many(self):
        """ Test repetitions. """
        text = "AAAABBBBCCCC"

        test = exact("A").between(2, 5)
        self.match(test, text, ['A'] * 4, 4)

        test = exact("A") * 3
        self.match(test, text, ['A'] * 3, 3)

        test = exact("A") * 5
        self.mismatch(test, text, repr('A'), 4)

        test = exact("A") * 3 + -exact("A") + ~exact("A") + ~exact("B")
        self.match(test, text, ['A'] * 4 + ['B'] * 4, 8)

        test = ~exact("A") + -exact("D") + +exact("B")
        self.match(test, text, ['A'] * 4 + ['B'] * 4, 8)

        test = ~exact("A") + +exact("D")
        self.mismatch(test, text, repr('D'), 4)


    def test_chars(self):
        """ Test simple tokenizers. """
        self.match(spaces, "    if    ", ' ' * 4, 4)

        text = 'bighero6'
        test = word + digits
        self.match(test, text, text, len(text))

        text = 'g6'
        test = word + digits
        self.match(test, text, text, len(text))

        text = '71'
        test = digit + digit
        self.match(test, text, text, len(text))

    def test_regex(self):
        """ Test regex parsers. """
        text = "email me at someone@example.com"

        test = exact("email me at") >> spaces >> regex(r"(\w+)@(\w+)\.(\w+)")
        match = test.scan(text)
        self.assertEqual(match.value.groups(0), ("someone", "example", "com"))



if __name__ == '__main__':
    unittest.main()
