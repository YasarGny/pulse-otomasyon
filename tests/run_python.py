"""Run the unchanged Python discovery suite with readable CI failure annotations."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

suite = unittest.defaultTestLoader.discover('tests', pattern='test_*.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
for test, detail in result.failures + result.errors:
    message = (str(test) + '\n' + detail)[-3500:]
    message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print('::error title=Python test failure::' + message, flush=True)
print(f'::notice title=Python test suite::{result.testsRun} tests; {len(result.failures)} failures; {len(result.errors)} errors', flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
