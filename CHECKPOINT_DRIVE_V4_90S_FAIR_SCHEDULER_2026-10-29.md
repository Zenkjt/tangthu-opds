# Checkpoint — V4 scheduler: 90s/shelf + continue after checkpoint

Date: 2026-10-29

## Decision
- Increase maximum processing time for one shelf from 45s to 90s.
- If a shelf is still incomplete after 90s, save its checkpoint and continue to the next due shelf.
- The scheduler must never `return` merely because one shelf needs another execution to finish.
- The next scheduler run resumes the incomplete shelf from its saved checkpoint.
- Global execution budget remains 4 minutes.

## Important implementation detail
The 90s budget is a single budget for the whole shelf scan, not 90s for quick scan plus another 90s for full scan. A shelf deadline is created when `scanPriorityShelf_()` starts and is passed into both quick and full scan functions.

## Result
A large L3 shelf such as `Kho NCN bigg` may require multiple scheduler executions to complete its baseline, but it no longer blocks other L1/L2/L3 shelves that are due.

## Priority rules unchanged
- L1: every 30 minutes; never auto-drops.
- L2: every 2 days; 10 unchanged scans -> L3.
- L3: every 7 days; 2 changed scans -> L2.
- L2 never auto-promotes to L1.
- Reload does not alter priority.
