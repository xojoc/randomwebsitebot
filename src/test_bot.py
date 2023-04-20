import unittest

from src import bot


class UnitGetRandomWebsite(unittest.TestCase):
    def test_get_random_website(self):
        for grwf in bot.random_website_functions:
            assert grwf() is not None  # noqa: S101
