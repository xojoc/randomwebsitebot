# Copyright 2023 Alexandru Cojocaru AGPLv3 or later - no warranty!
import unittest

from . import bot


class UnitGetRandomWebsite(unittest.TestCase):
    def test_get_random_website(self):
        for grwf in bot.random_website_functions:
            assert grwf() is not None, grwf.__name__
