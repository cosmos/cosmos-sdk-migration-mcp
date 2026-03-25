# Cosmos SDK Migration MCP Server

An MCP (Model Context Protocol) server for migrating Cosmos SDK chains from
`v0.50+` to `v0.54`.

This repository packages the migration server, the YAML migration specs, the
orchestration guide, and the bundled upgrade-doc resources it exposes over MCP.

## Install

```bash
pip install cosmos-migration-mcp
```

Or for local development:

```bash
git clone https://github.com/cosmos/cosmos-sdk-migration-mcp.git
cd cosmos-sdk-migration-mcp
pip install -e .
```

## Run

The package exposes a `cosmos-migration-mcp` console script:

```bash
cosmos-migration-mcp
```

You can also run it as a module:

```bash
python -m cosmos_migration_mcp
```

## Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cosmos-migration": {
      "command": "cosmos-migration-mcp"
    }
  }
}
```

## Claude Code

```bash
claude mcp add cosmos-migration -- cosmos-migration-mcp
```

## Reference

- **[Canonical Cosmos SDK Upgrade Guide](https://github.com/cosmos/cosmos-sdk/blob/main/UPGRADING.md)** — The official upstream source for breaking changes and migration instructions for all Cosmos SDK versions.

> This MCP server bundles snapshots of the v0.54 upgrade documentation and migration specs. Always consult the canonical upstream guide for the latest information and breaking changes.

## Tools

| Tool | Description |
|---|---|
| `scan_chain_tool` | Detect SDK version and which specs apply to a chain |
| `get_migration_plan` | Preview all changes without modifying files |
| `apply_spec` | Apply a single spec, including go.mod edits, arg rewrites, and special cases |
| `verify_spec_tool` | Run verification checks for one spec |
| `verify_all_specs` | Run verification for an explicit spec list or for currently detectable specs |
| `verify_build` | Run `go build ./...` and return structured results |
| `run_go_mod_tidy` | Run `go mod tidy` and return structured results |
| `run_tests` | Run `go test ./...` and return structured results |
| `show_diff` | Show git diff of changes in the chain directory |
| `list_specs` | List all available migration specs |
| `get_spec` | Get full content of a specific spec |
| `check_warnings` | Check for fatal blocks and warnings |

## Resources

| URI | Description |
|---|---|
| `specs://v50-to-v54/{id}` | Read a spec as YAML text |
| `specs://v50-to-v54/index` | List all specs with metadata |
| `agents://orchestration` | Read the bundled orchestration guide |
| `docs://upgrading/v0.54` | Read the bundled v0.54 upgrade guide |
| `docs://upgrade-checklist/v0.54` | Read the bundled upgrade checklist section |
| `docs://changelog/v0.54-breaking` | Read the bundled v0.54 breaking changes section |
| `docs://release-notes/v0.54` | Read the bundled v0.54 release notes |

## Prompts

| Prompt | Description |
|---|---|
| `migrate_chain` | Full workflow: scan → plan → apply → verify → report |
| `assess_chain` | Scan-only: detect version, estimate effort, no changes |
| `debug_build_failure` | Diagnose post-migration build errors |
