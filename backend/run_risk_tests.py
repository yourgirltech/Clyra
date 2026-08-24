"""Small test runner to execute deterministic risk rule unit tests without pytest.

Run: python run_risk_tests.py
"""
from importlib import import_module


def run_tests():
    mod = import_module('tests.test_risk_engine')
    tests = [name for name in dir(mod) if name.startswith('test_')]
    results = []
    for name in tests:
        fn = getattr(mod, name)
        try:
            fn()
            results.append((name, 'PASS'))
        except AssertionError as e:
            results.append((name, f'FAIL: {e}'))
        except Exception as e:
            results.append((name, f'ERROR: {e}'))

    for name, outcome in results:
        print(f'{name}: {outcome}')

    fails = [r for r in results if not r[1].startswith('PASS')]
    if fails:
        print('\nSome tests failed')
        raise SystemExit(1)
    print('\nAll tests passed')


if __name__ == '__main__':
    run_tests()
