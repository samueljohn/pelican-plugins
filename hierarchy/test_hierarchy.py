import unittest
import os
import locale
import logging

from tempfile import mkdtemp
from pelican import Pelican
from pelican.settings import read_settings
from shutil import rmtree

CUR_DIR = os.path.dirname(__file__)

import hierarchy


# todo
# build hierarchic dirs and files in temp to test
#

class TestHierarchy(unittest.TestCase):
    def setUp(self, override=None):
        self.temp_path = mkdtemp(prefix='pelicantests.')
        settings = {
            'PATH': os.path.join(os.path.dirname(CUR_DIR), '..',
                                 'test_data', 'content'),
            'OUTPUT_PATH': self.temp_path,
            'PLUGINS': ['hierarchy'],
            'LOCALE': locale.normalize('en_US'),
        }
        if override:
            settings.update(override)

        self.settings = read_settings(override=settings)
        pelican = Pelican(settings=self.settings)

        pelican.run()

    def tearDown(self):
        rmtree(self.temp_path)

    def test_scan_dir_r():
        pass

    # def test_existence(self):
    #     assert os.path.exists(os.path.join(self.temp_path,
    #                                        'pdf',
    #                                        'this-is-a-super-article.pdf'))
