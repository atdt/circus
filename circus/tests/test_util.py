import unittest
from psutil import Popen

from circus.util import (get_info, bytes2human, to_bool, parse_env,
                         env_to_str)


class TestUtil(unittest.TestCase):

    def test_get_info(self):

        worker = Popen(["python -c 'import time;time.sleep(5)'"], shell=True)
        try:
            info = get_info(worker)
        finally:
            worker.terminate()

        self.assertTrue(isinstance(info['pid'], int))
        self.assertEqual(info['nice'], 0)

    def test_bytes2human(self):
        self.assertEqual(bytes2human(10000), '9K')
        self.assertEqual(bytes2human(100001221), '95M')

    def test_tobool(self):
        for value in ('True ', '1', 'true'):
            self.assertTrue(to_bool(value))

        for value in ('False', '0', 'false'):
            self.assertFalse(to_bool(value))

        for value in ('Fal', '344', ''):
            self.assertRaises(ValueError, to_bool, value)

    def test_parse_env(self):
        env = 'test=1,booo=2'
        parsed = parse_env(env)
        self.assertEqual(env_to_str(parsed), env)
