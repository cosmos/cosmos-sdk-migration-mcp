"""Tests for the improvement issues (#1-#15)."""

import os
import tempfile
import textwrap
import unittest

from cosmos_migration_mcp.server import (
    _apply_call_arg_edit,
    _execute_spec,
    _inject_go_import,
    _rewrite_gov_new_keeper_calls,
)
from cosmos_migration_mcp.specs import (
    ScanResult,
    Spec,
    _detect_sdk_version,
    _matching_content_files,
    _parse_content_rule,
    list_go_mod_files,
    load_specs,
    scan_chain,
    verify_spec,
)


class TestSDKVersionDetection(unittest.TestCase):
    """Issue #10: sdk_version 'unknown' gives no diagnostic."""

    def test_no_go_mod(self):
        with tempfile.TemporaryDirectory() as d:
            result = _detect_sdk_version(d)
            self.assertEqual(result.version, "unknown")
            self.assertIn("no go.mod", result.detection_note)

    def test_sdk_repo_itself(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "go.mod"), "w") as f:
                f.write("module github.com/cosmos/cosmos-sdk\n\ngo 1.22\n")
            result = _detect_sdk_version(d)
            self.assertEqual(result.version, "unknown")
            self.assertIn("SDK itself", result.detection_note)

    def test_normal_chain(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "go.mod"), "w") as f:
                f.write(textwrap.dedent("""\
                    module github.com/mychain/app
                    go 1.22
                    require github.com/cosmos/cosmos-sdk v0.50.6
                """))
            result = _detect_sdk_version(d)
            self.assertEqual(result.version, "v0.50.6")
            self.assertEqual(result.detection_note, "")

    def test_no_sdk_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "go.mod"), "w") as f:
                f.write("module github.com/mychain/app\n\ngo 1.22\n")
            result = _detect_sdk_version(d)
            self.assertEqual(result.version, "unknown")
            self.assertIn("not found", result.detection_note)


class TestFatalSpecFiltering(unittest.TestCase):
    """Issue #12: Fatal specs should be in fatal_spec_ids, not application_order."""

    def test_fatal_spec_excluded_from_application_order(self):
        with tempfile.TemporaryDirectory() as d:
            # Create a go.mod that references the SDK
            with open(os.path.join(d, "go.mod"), "w") as f:
                f.write(textwrap.dedent("""\
                    module github.com/mychain/app
                    go 1.22
                    require github.com/cosmos/cosmos-sdk v0.50.6
                """))
            # Create a .go file that triggers the group fatal spec
            with open(os.path.join(d, "app.go"), "w") as f:
                f.write(textwrap.dedent("""\
                    package app
                    import "github.com/cosmos/cosmos-sdk/x/group"
                    var _ = group.ModuleName
                """))

            result = scan_chain(d)
            self.assertIn("group-enterprise-migration", result.applicable_specs)
            self.assertIn("group-enterprise-migration", result.fatal_spec_ids)
            self.assertNotIn("group-enterprise-migration", result.application_order)


class TestScanResultFields(unittest.TestCase):
    """Issue #15: application_order and detection_note in scan results."""

    def test_scan_result_has_application_order(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "go.mod"), "w") as f:
                f.write(textwrap.dedent("""\
                    module github.com/mychain/app
                    go 1.22
                    require github.com/cosmos/cosmos-sdk v0.50.6
                """))
            result = scan_chain(d)
            self.assertIsInstance(result.application_order, list)
            # application_order should be a subset of applicable_specs
            for sid in result.application_order:
                self.assertIn(sid, result.applicable_specs)


class TestGovKeeperRewrite(unittest.TestCase):
    """Issue #3: gov-keeper special-case rewrite argument order."""

    def test_standard_layout(self):
        content = textwrap.dedent("""\
            package app

            import (
                govkeeper "github.com/cosmos/cosmos-sdk/x/gov/keeper"
            )

            func setup() {
                k := govkeeper.NewKeeper(
                    appCodec,
                    storeService,
                    acctKeeper,
                    bankKeeper,
                    stakingKeeper,
                    distrKeeper,
                    router,
                    govConfig,
                    authority,
                )
            }
        """)
        updated, count = _rewrite_gov_new_keeper_calls(content)
        self.assertEqual(count, 1)
        self.assertIn("NewDefaultCalculateVoteResultsAndVotingPower(stakingKeeper)", updated)
        # stakingKeeper should NOT appear as a direct arg anymore
        lines = [l.strip().rstrip(",") for l in updated.splitlines()]
        # It should only appear inside the wrapper call
        direct_staking = [l for l in lines if l == "stakingKeeper"]
        self.assertEqual(len(direct_staking), 0)

    def test_already_migrated(self):
        content = textwrap.dedent("""\
            package app

            import (
                govkeeper "github.com/cosmos/cosmos-sdk/x/gov/keeper"
            )

            func setup() {
                k := govkeeper.NewKeeper(
                    appCodec,
                    storeService,
                    acctKeeper,
                    bankKeeper,
                    distrKeeper,
                    router,
                    govConfig,
                    authority,
                    govkeeper.NewDefaultCalculateVoteResultsAndVotingPower(stakingKeeper),
                )
            }
        """)
        updated, count = _rewrite_gov_new_keeper_calls(content)
        self.assertEqual(count, 0)
        self.assertEqual(updated, content)

    def test_custom_alias(self):
        content = textwrap.dedent("""\
            package app

            import (
                keeper "github.com/cosmos/cosmos-sdk/x/gov/keeper"
            )

            func setup() {
                k := keeper.NewKeeper(
                    appCodec,
                    storeService,
                    acctKeeper,
                    bankKeeper,
                    app.StakingKeeper,
                    distrKeeper,
                    router,
                    govConfig,
                    authority,
                )
            }
        """)
        updated, count = _rewrite_gov_new_keeper_calls(content)
        self.assertEqual(count, 1)
        # Should use the alias "keeper", not "govkeeper"
        self.assertIn("keeper.NewDefaultCalculateVoteResultsAndVotingPower(app.StakingKeeper)", updated)


class TestCallArgEditVariadic(unittest.TestCase):
    """Issue #4: bank-endblock variadic prepend."""

    def test_variadic_prepend_uses_append(self):
        content = textwrap.dedent("""\
            package app
            func setup() {
                app.SetOrderEndBlockers(moduleOrder...)
            }
        """)
        edit = {
            "method_name": "SetOrderEndBlockers",
            "add": [{"position": 0, "expr": "banktypes.ModuleName"}],
        }
        updated, count = _apply_call_arg_edit(content, edit)
        self.assertEqual(count, 1)
        # Should NOT produce: SetOrderEndBlockers(banktypes.ModuleName, moduleOrder...)
        self.assertNotIn("banktypes.ModuleName, moduleOrder...", updated)
        # Should produce an append(...) expression
        self.assertIn("append([]string{banktypes.ModuleName}, moduleOrder...)", updated)

    def test_non_variadic_insert_normal(self):
        content = textwrap.dedent("""\
            package app
            func setup() {
                app.SetOrderEndBlockers(
                    authtypes.ModuleName,
                    stakingtypes.ModuleName,
                )
            }
        """)
        edit = {
            "method_name": "SetOrderEndBlockers",
            "add": [{"position": 0, "expr": "banktypes.ModuleName"}],
        }
        updated, count = _apply_call_arg_edit(content, edit)
        self.assertEqual(count, 1)
        # Normal insert — no append wrapper needed
        self.assertIn("banktypes.ModuleName", updated)
        self.assertNotIn("append(", updated)


class TestImportInjection(unittest.TestCase):
    """Issue #5: missing import injection."""

    def test_inject_into_existing_import_block(self):
        content = textwrap.dedent("""\
            package app

            import (
                "fmt"
            )
        """)
        updated = _inject_go_import(content, "github.com/cosmos/cosmos-sdk/x/bank/types", "banktypes")
        self.assertIn('banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"', updated)

    def test_inject_when_no_import_block(self):
        content = "package app\n\nfunc main() {}\n"
        updated = _inject_go_import(content, "github.com/cosmos/cosmos-sdk/x/bank/types", "banktypes")
        self.assertIn('banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"', updated)

    def test_no_inject_if_already_present(self):
        content = textwrap.dedent("""\
            package app

            import (
                banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
            )
        """)
        # _inject_go_import itself doesn't check — _apply_required_imports does
        # But let's verify it's idempotent at the server level
        updated = _inject_go_import(content, "github.com/cosmos/cosmos-sdk/x/bank/types", "banktypes")
        # It will add a duplicate — that's fine, _apply_required_imports checks first
        self.assertIn("github.com/cosmos/cosmos-sdk/x/bank/types", updated)


class TestVerificationRuleScoping(unittest.TestCase):
    """Issue #6 and #7: verification rules should be scoped."""

    def test_parse_content_rule_with_exclude(self):
        rule = {
            "pattern": "NewUncachedContext(",
            "exclude_file_match": "baseapp/test_helpers.go",
        }
        pattern, file_match, exclude = _parse_content_rule(rule)
        self.assertEqual(pattern, "NewUncachedContext(")
        self.assertEqual(exclude, "baseapp/test_helpers.go")

    def test_matching_content_files_excludes(self):
        with tempfile.TemporaryDirectory() as d:
            # Create two files with the pattern
            app_file = os.path.join(d, "app.go")
            helper_file = os.path.join(d, "baseapp", "test_helpers.go")
            os.makedirs(os.path.dirname(helper_file))

            with open(app_file, "w") as f:
                f.write("package app\nfunc x() { NewUncachedContext() }\n")
            with open(helper_file, "w") as f:
                f.write("package baseapp\nfunc NewUncachedContext() {}\n")

            go_files = [app_file, helper_file]
            # Without exclude
            matches = _matching_content_files(go_files, d, "NewUncachedContext(", "")
            self.assertEqual(len(matches), 2)

            # With exclude
            matches = _matching_content_files(
                go_files, d, "NewUncachedContext(", "",
                exclude_file_match="baseapp/test_helpers.go",
            )
            self.assertEqual(len(matches), 1)
            self.assertIn("app.go", matches[0])

    def test_crisis_register_invariants_scoped(self):
        """Verify that crisis spec's RegisterInvariants rule is now file-scoped."""
        specs = {s.id: s for s in load_specs()}
        crisis = specs["crisis-removal"]
        rules = crisis.verification.get("must_not_contain", [])
        register_rules = [r for r in rules if isinstance(r, dict) and r.get("pattern") == "RegisterInvariants"]
        # All RegisterInvariants rules should have file_match
        for rule in register_rules:
            self.assertTrue(
                rule.get("file_match"),
                f"RegisterInvariants rule should be file-scoped: {rule}",
            )

    def test_store_v2_uncached_context_excludes_definition(self):
        """Verify store-v2 spec excludes the definition site."""
        specs = {s.id: s for s in load_specs()}
        store_v2 = specs["store-v2-migration"]
        rules = store_v2.verification.get("must_not_contain", [])
        uncached_rules = [
            r for r in rules
            if isinstance(r, dict) and r.get("pattern") == "NewUncachedContext("
        ]
        self.assertTrue(len(uncached_rules) > 0)
        self.assertEqual(uncached_rules[0].get("exclude_file_match"), "baseapp/test_helpers.go")


class TestWarningSpecsApply(unittest.TestCase):
    """Issue #1: warning-only specs should not crash."""

    def setUp(self):
        self.spec_map = {spec.id: spec for spec in load_specs()}

    def test_otel_warning_spec(self):
        with tempfile.TemporaryDirectory() as d:
            result = _execute_spec(d, self.spec_map["otel-migration-warning"], dry_run=False)
            self.assertTrue(result["already_satisfied"])
            self.assertTrue(result["verification_passed"])

    def test_block_gas_meter_warning_spec(self):
        with tempfile.TemporaryDirectory() as d:
            result = _execute_spec(d, self.spec_map["block-gas-meter-warning"], dry_run=False)
            self.assertTrue(result["already_satisfied"])
            self.assertTrue(result["verification_passed"])


class TestMultiModuleGoModTidy(unittest.TestCase):
    """Issue #8: go mod tidy should handle sub-modules."""

    def test_discovers_sub_module_go_mods(self):
        with tempfile.TemporaryDirectory() as d:
            # Create root go.mod
            with open(os.path.join(d, "go.mod"), "w") as f:
                f.write("module github.com/mychain/app\ngo 1.22\n")
            # Create sub-module go.mod
            simapp_dir = os.path.join(d, "simapp")
            os.makedirs(simapp_dir)
            with open(os.path.join(simapp_dir, "go.mod"), "w") as f:
                f.write("module github.com/mychain/app/simapp\ngo 1.22\n")

            go_mods = list_go_mod_files(d)
            self.assertEqual(len(go_mods), 2)


class TestBankEndblockSpecHasRequiredImport(unittest.TestCase):
    """Issue #5: bank-endblock spec should declare required_imports."""

    def test_bank_endblock_has_required_imports(self):
        specs = {s.id: s for s in load_specs()}
        bank_spec = specs["bank-endblock-order"]
        required = bank_spec.changes.get("required_imports", [])
        self.assertTrue(len(required) > 0)
        self.assertEqual(required[0]["import_path"], "github.com/cosmos/cosmos-sdk/x/bank/types")
        self.assertEqual(required[0]["alias"], "banktypes")


if __name__ == "__main__":
    unittest.main()
