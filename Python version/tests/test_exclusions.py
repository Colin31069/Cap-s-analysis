from __future__ import annotations

import unittest

from skin_analysis.exclusions import max_excluded_samples


class ExclusionPolicyTests(unittest.TestCase):
    def test_max_excluded_samples_uses_twenty_percent_floor_with_minimum_n(self) -> None:
        cases = {
            0: 0,
            4: 0,
            5: 1,
            9: 1,
            10: 2,
            14: 2,
            15: 3,
        }

        for sample_count, expected in cases.items():
            with self.subTest(sample_count=sample_count):
                self.assertEqual(max_excluded_samples(sample_count), expected)


if __name__ == "__main__":
    unittest.main()
