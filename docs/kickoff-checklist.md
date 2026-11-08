# Per-event checklist

## Two days before
- [ ] Create the event repo from this kit (Use this template, private)
- [ ] Add every teammate as a collaborator
- [ ] Everyone runs `gh auth status` and it passes
- [ ] Ask organizers: credits, rules (pre-built code and data allowed?), judging criteria, submission format

## Day before
- [ ] Open an issue from the Message board template and pin it (if not #1, everyone sets `BOARD_ISSUE`)
- [ ] Every machine: `tools/board whoami`, then `tools/board post "[Name's Claude] test"`
- [ ] Someone else runs `tools/board unread` and sees each test post
- [ ] Start Claude Code at the repo root; the session opens with "Team board (GitHub issue #N)"
- [ ] Fill Project facts in AGENTS.md and the ECC short list in CLAUDE.md
- [ ] Time one prompt with ECC + board hooks; turn off ECC hooks you don't need if slow
- [ ] Pre-write agent prompts and test data, if the rules allow

## First hour
- [ ] Fill the owner table in AGENTS.md and split folders (run the planner agent)
- [ ] Agree shared contracts: API shapes, schemas, env vars
- [ ] Post the plan on the board
- [ ] Each agent arms one background `tools/board wait`

## Middle
- [ ] Post on every merge that changes a contract
- [ ] Re-run the demo path after each merge (tester agent)

## Feature freeze: [time]
- [ ] Stop new features; fixes only
- [ ] Planner agent reviews open issues and cuts what will not land

## Final hours
- [ ] Run demo-polisher: README, demo script, submission text
- [ ] Record a backup demo video
- [ ] Submit with an hour of buffer
