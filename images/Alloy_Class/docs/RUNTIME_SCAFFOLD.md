# Runtime Scaffold (Phase 1)

This project keeps app logic in `images/Alloy_Class` and uses shared UNC tooling for runtime dependencies.

## App-side config
- `config/runtime_paths.json`

## Shared tooling root
- `\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime`

## Usage
1. Keep prototype code and prompts in this app folder.
2. Populate shared wheelhouse and locked requirements in shared runtime root.
3. Use bootstrap script from shared runtime when dependency install is needed.
4. Do not add user-local paths to scripts or configs.

## Why this split
- Reusable tooling for future Alloy apps
- No local machine path dependencies
- Fast iteration for current classification prototypes

## Inline Pipeline Alignment

When transitioning from Phase 1 experiments to inline integration planning, align against:

- `../../../docs/inline_pipeline/README.md`
- `../../../docs/inline_pipeline/runtime_contract.md`
- `../../../docs/inline_pipeline/operations_and_hardening.md`
