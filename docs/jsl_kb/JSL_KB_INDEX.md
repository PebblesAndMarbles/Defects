# JSL Knowledge Base Index

This index is intended to speed up future modifications and troubleshooting of:
- [AMEct 1278 Inline Defects Fleet Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl)
- [AMEct 1278 Inline Defects Chamber Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl)
- [AMEct 1278 Surf Scan Fleet Dispo.jsl](../../AMEct%201278%20Surf%20Scan%20Fleet%20Dispo.jsl)
- [AMEct 1278 Surf Scan Chamber Dispo.jsl](../../AMEct%201278%20Surf%20Scan%20Chamber%20Dispo.jsl)

## Primary references

- Script behavior overview: [JSL_FLEET_CHAMBER_DISPO_UNDERSTANDING.md](../../JSL_FLEET_CHAMBER_DISPO_UNDERSTANDING.md)
- Surf-scan fleet rollout tracker: [SURF_SCAN_FLEET_IMPLEMENTATION_TODO.md](SURF_SCAN_FLEET_IMPLEMENTATION_TODO.md)
- Troubleshooting playbook: [JSL_TROUBLESHOOTING_PLAYBOOK.md](JSL_TROUBLESHOOTING_PLAYBOOK.md)
- Modification checklist: [JSL_MODIFICATION_CHECKLIST.md](JSL_MODIFICATION_CHECKLIST.md)
- Data contracts and dependencies: [JSL_DATA_CONTRACTS_AND_DEPENDENCIES.md](JSL_DATA_CONTRACTS_AND_DEPENDENCIES.md)
- Quick validation runbook: [JSL_VALIDATION_QUICKRUN.md](JSL_VALIDATION_QUICKRUN.md)

## Related pipeline context

- Update entrypoint: [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py)
- Defect coordinate pipeline stage: [BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py](../../BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py)
- Image reconcile and prune: [BE_QUERY_FILES/reconcile_prune_images.py](../../BE_QUERY_FILES/reconcile_prune_images.py)
- Pipeline path model: [BE_QUERY_FILES/pipeline_config.py](../../BE_QUERY_FILES/pipeline_config.py)

## When to use which file

- Starting a feature change:
  - Read [JSL_MODIFICATION_CHECKLIST.md](JSL_MODIFICATION_CHECKLIST.md)
- Debugging mismatched charts, selections, or table counts:
  - Start with [JSL_TROUBLESHOOTING_PLAYBOOK.md](JSL_TROUBLESHOOTING_PLAYBOOK.md)
- Verifying source/column assumptions before coding:
  - Check [JSL_DATA_CONTRACTS_AND_DEPENDENCIES.md](JSL_DATA_CONTRACTS_AND_DEPENDENCIES.md)
- Validating a candidate fix quickly:
  - Follow [JSL_VALIDATION_QUICKRUN.md](JSL_VALIDATION_QUICKRUN.md)
