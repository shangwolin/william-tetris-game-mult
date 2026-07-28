# Context
Swarm: default

## Decisions
- Standard QA profile (reviewer + test_engineer for every task)
- Parallel execution enabled
- Auto-proceed between phases enabled

## Pending QA Gate Selection
profile: standard
parallelization_enabled: true
auto_proceed: true
confirmed: true

## Agent Activity

| Tool | Calls | Success | Failed | Avg Duration |
|------|-------|---------|--------|--------------|
| read | 101 | 101 | 0 | 16ms |
| edit | 81 | 81 | 0 | 15ms |
| bash | 45 | 45 | 0 | 1849ms |
| grep | 39 | 39 | 0 | 656ms |
| glob | 26 | 26 | 0 | 55ms |
| write | 25 | 25 | 0 | 6ms |
| update_task_status | 22 | 22 | 0 | 116ms |
| task | 14 | 14 | 0 | 145350ms |
| todowrite | 9 | 9 | 0 | 3ms |
| declare_scope | 8 | 8 | 0 | 17ms |
| get_approved_plan | 4 | 4 | 0 | 2ms |
| syntax_check | 4 | 4 | 0 | 60ms |
| pre_check_batch | 4 | 4 | 0 | 85ms |
| phase_complete | 4 | 4 | 0 | 3798ms |
| save_plan | 3 | 3 | 0 | 141ms |
| set_qa_gates | 2 | 2 | 0 | 45ms |
| check_gate_status | 2 | 2 | 0 | 100ms |
| skill | 1 | 1 | 0 | 238ms |
| spec_write | 1 | 1 | 0 | 4ms |
| pr_workflow_status | 1 | 1 | 0 | 66ms |
| context_status | 1 | 1 | 0 | 30ms |
| write_retro | 1 | 1 | 0 | 139ms |
| write_drift_evidence | 1 | 1 | 0 | 16ms |
| swarm_command | 1 | 1 | 0 | 2ms |
