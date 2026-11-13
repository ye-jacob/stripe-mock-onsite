"""Run by check_env.py to prove that pytest works on this machine."""


def test_pytest_collects_and_runs_tests():
    assert sorted([3, 1, 2]) == [1, 2, 3]
