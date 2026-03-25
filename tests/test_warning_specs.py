import tempfile
import unittest

from cosmos_migration_mcp.server import _execute_spec
from cosmos_migration_mcp.specs import load_specs


class WarningSpecRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec_map = {spec.id: spec for spec in load_specs()}

    def test_warning_specs_normalize_empty_verification_mapping(self) -> None:
        for spec_id in ("otel-migration-warning", "block-gas-meter-warning"):
            with self.subTest(spec_id=spec_id):
                spec = self.spec_map[spec_id]
                self.assertEqual(spec.verification, {})
                self.assertIsInstance(spec.changes, dict)

    def test_warning_specs_apply_without_null_dereference(self) -> None:
        with tempfile.TemporaryDirectory() as chain_dir:
            for spec_id in ("otel-migration-warning", "block-gas-meter-warning"):
                with self.subTest(spec_id=spec_id):
                    result = _execute_spec(chain_dir, self.spec_map[spec_id], dry_run=False)
                    self.assertTrue(result["verification_passed"])
                    self.assertTrue(result["already_satisfied"])
                    self.assertGreaterEqual(len(result["warnings"]), 1)


if __name__ == "__main__":
    unittest.main()
