# Changelog Entry Template

Use this template when drafting entries for `docs/CHANGELOG.md`.
Omit any field or section marked **optional** when it does not apply.

---

```markdown
## [ISSUE_NUMBER] Title — YYYY-MM-DD

Tags: `tag1` `tag2`
PR: [#PR_NUMBER](https://github.com/OWNER/REPO/pull/PR_NUMBER)
<!-- For multiple PRs use PRs: [#111](url), [#222](url) -->
<!-- For a PR in a sibling repo, qualify it: PRs: [api#111](url), [web#88](url) -->
Builds on: #XXXXX, #XXXXX  <!-- optional: issue numbers this one extends or depends on -->

### What was built
<!-- Bullet list of concrete deliverables visible in the diff:
     new opcodes, bcOS routines, bdio calls, B functions, programs, devices, tests, etc.
     One bullet per meaningful unit of work. Be specific — include file/class names. -->

### Key decisions reflected in the diff
<!-- Notable trade-offs, patterns chosen, or intentional omissions visible in the code.
     Omit this section if there is nothing worth calling out. -->  <!-- optional -->
```

---

## Tag taxonomy

Apply all tags that fit. The tags follow the sections of
`docs/specs/memory/design-decisions.md` (Global, Emulator, Assembler, Compiler, bcOS, bdos), so
the spec planner can match changelog entries with the decisions that govern them.

| Tag | Use when the story… |
|---|---|
| `emulator` | changes the bc8183 CPU or the emulator core (`src/bc64.py`, `src/bc64/bc8183_cpu.py`) |
| `devices` | adds or changes an emulated peripheral or its port protocol (`src/bc64/bc64_io.py`) |
| `assembler` | changes bc81asmc grammar, encoding, directives or `.btap` output (`src/bc81asmc/`) |
| `compiler` | changes the B language, preprocessor, code generation or the asm runtime (`src/bc/`) |
| `b-stdlib` | changes the B libraries `std.b`, `stdio.b`, `strings.b`, `stdmem.b` |
| `bcos` | changes the ROM monitor: routines, commands, boot sequence (`src/bc81asmc/bcOS/`) |
| `bdos` | changes the boot loader, shell or bdio layer (`boot.basm`, `bdos.b`, `bdio.b`, `bdioh.b`, `bdosh.b`) |
| `filesystem` | changes the BFS disk format, catalog or allocation |
| `apps` | adds or changes a disc program (`ls`, `cp`, `rm`, `cat`, `cha`, `format`, `texted`, …) |
| `abi` | changes a cross-component contract: os_metatab numbers, bdio call numbers, the memory map, the register convention, opcode encoding |
| `build` | changes build scripts, `ftool.py`, `makedisc`, the disc layout or the committed build outputs |
| `tests` | adds or changes unit tests only |
| `docs` | changes documentation or memory-bank files only |

---

## Rules

- **Diff is authoritative.** Do not describe things the spec planned but the diff does not show.
- **Key decisions** — only include decisions that are *visible in the code*; do not copy-paste spec rationale that has no code counterpart.
- **Builds on** — link to prior issues whose infrastructure or contracts this one directly uses or extends.
- **Spec-only PRs** — if the PR only contains a spec plan file, do not draft an entry; flag it as "spec-only, implementation not yet merged".
- Entries in `docs/CHANGELOG.md` are ordered **newest merge date first**.
