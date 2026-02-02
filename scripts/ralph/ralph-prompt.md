# Ralph Iteration Instructions - Plan A (AG-UI State-Driven)

You are running in **Ralph autonomous mode**. This is an automated iteration of a larger development workflow. Follow this workflow precisely to complete one story from the PRD.

> **Important:** The current story details are in the "Ralph Context" section above. Use the spec file to understand requirements.

## Your Mission

Complete exactly ONE story from `prd_plan_a.json`, then exit so the next iteration can begin.

---

## Step 0: Environment Verification

Before starting any story work, verify the development environment:

1. **Check Python/uv setup:**
   ```bash
   cd validator-agent
   uv sync
   ```
   If `uv sync` fails, fix dependency issues before proceeding.

2. **Check frontend setup:**
   ```bash
   cd webapp
   npm install
   ```
   If `npm install` fails, fix dependency issues before proceeding.

3. **Verify project imports (if app/ exists):**
   ```bash
   cd validator-agent && python -c "import app" 2>&1 || echo "app not yet importable"
   ```

4. **Check backend health (if backend is running):**
   ```bash
   curl -s http://localhost:8080/health 2>&1 || echo "backend not running"
   ```

If any critical setup is broken, fix it before proceeding to the story.

---

## Step 1: Read Current State

First, understand the context:

1. **Read the spec file** (from Ralph Context) — A self-contained markdown file with everything you need: summary, TDD approach, implementation details, acceptance criteria, testing, and commit message. Spec files are at `validator-agent/docs/phases/phase-*.md`
2. **Read `prd_plan_a.json`** — Find the current story and verify it's incomplete (`passes: false`). Note the `qualityCheck` field for this story (if present)
3. **Read `progress-prd_plan_a.txt`** — Contains learnings from previous iterations
4. **Read `CLAUDE.md`** — Contains project patterns and conventions

---

## Step 2: Understand the Story

The story in Ralph Context has a `spec` field that is a file path like:
```
validator-agent/docs/phases/phase-01-scaffold-models.md#story-1.1
```

Each spec section contains these parts — read them all:

| Section | What It Tells You |
|---------|-------------------|
| **Test (write first):** | TDD test code to write first (RED phase) |
| **Implementation:** | Code to implement (GREEN phase) |
| **Success criteria:** | Checklist of requirements |
| **Commit message:** | Exact commit message to use |

---

## Step 3: Implement the Story

### 3.1 Follow TDD from the Spec

Every spec section has test and implementation guidance:

1. **RED** — Write the failing tests first. The spec provides test code or describes what to test. Create the test file(s) and run them to confirm they fail:
   ```bash
   # For Python stories
   cd validator-agent && pytest tests/ -v

   # For frontend stories
   cd webapp && npx vitest run

   # For Terraform stories
   cd validator-agent && terraform -chdir=deployment/terraform validate

   # For CI/CD stories — validate YAML syntax
   python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
   ```

2. **GREEN** — Implement the minimum code to make all tests pass. Follow the **Implementation** section in the spec.

3. **REFACTOR** — Clean up while keeping tests green.

### 3.2 Run Quality Checks

Run the primary quality check for the story type:

```bash
# Python stories (primary)
cd validator-agent && pytest tests/ -v

# Frontend stories
cd webapp && npm run build && npx vitest run

# Lint (Python)
cd validator-agent && ruff check . && ruff format --check .

# Terraform stories
cd validator-agent && terraform -chdir=deployment/terraform validate

# CI/CD stories — validate YAML
python3 -c "import yaml; yaml.safe_load(open('path/to/workflow.yml'))"
```

If the story has a `qualityCheck` field in `prd_plan_a.json`, run that exact command.

### 3.3 Verify Acceptance Criteria

Check every item in the story's `acceptanceCriteria` array in `prd_plan_a.json` and in the spec file. Each must be satisfied.

---

## Step 4: Verify Completion

The story is complete when:

1. All files from the spec exist
2. All tests pass (GREEN state)
3. Quality checks pass
4. Every acceptance criterion is satisfied

**Create a verification summary:**
```markdown
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Test file created | PASS | tests/path/test_file.py exists |
| Tests pass (GREEN) | PASS | pytest output: N passed |
| Quality check | PASS | qualityCheck command exit 0 |
| Acceptance criteria | PASS | All items checked |
```

---

## Step 5: Commit Changes

### 5.1 Review Changes
```bash
git status
git diff
```

### 5.2 Stage Specific Files (NOT git add -A)
```bash
git add path/to/file1.py
git add path/to/file2.py
git add tests/test_file.py
```

### 5.3 Commit with Spec's Message

Use the **Commit message:** from the spec section:
```bash
git commit -m "$(cat <<'EOF'
feat(scope): description from spec

- Detail 1
- Detail 2

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

---

## Step 6: Update Tracking Files

### 6.1 Update prd_plan_a.json

Mark the story as complete by setting `passes: true`:
```json
{
  "id": "1.1",
  "title": "Scaffold project with Agent Starter Pack CLI",
  "phase": 1,
  "spec": "validator-agent/docs/phases/phase-01-scaffold-models.md#story-1.1",
  "passes": true
}
```

### 6.2 Update progress-prd_plan_a.txt

Append to the Iteration Log:
```markdown
### Story X.Y: Story title
**Completed:** [datetime]
**Phase:** N - Phase Title

**What Was Done:**
- Summary of files created/modified
- Key implementation details

**Verification:**
- pytest: PASS (N passed)
- Acceptance criteria: All satisfied

**Learnings:**
- [Any patterns or gotchas discovered]
```

### 6.3 Commit Tracking Files

```bash
git add prd_plan_a.json progress-prd_plan_a.txt
git commit -m "$(cat <<'EOF'
chore: update tracking files for story X.Y

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

---

## Step 7: Check for Completion

After updating tracking files:

```bash
# Count remaining stories
jq '[.stories[] | select(.passes == false)] | length' prd_plan_a.json
```

### If stories remain:
End your response normally. Ralph will spawn the next iteration.

### If ALL stories are complete:
Output this exact signal:
```
<promise>COMPLETE</promise>
```

---

## Handling Issues

### Story is blocked

If you can't complete the story (missing dependency, unclear spec):

1. Do NOT mark as `passes: true`
2. Add to the story in prd_plan_a.json:
   ```json
   {
     "id": "1.1",
     "passes": false,
     "blocked": true,
     "blockReason": "Describe the issue"
   }
   ```
3. Document in progress-prd_plan_a.txt
4. End iteration — Ralph will show the blocked status

### Tests fail repeatedly

1. Re-read the spec's test and implementation sections carefully
2. Check if it's a pre-existing issue vs your changes
3. If stuck after 3 attempts, mark as blocked

### Spec is unclear

1. Look at similar completed stories for patterns
2. If still unclear, make a reasonable implementation and note assumptions in progress-prd_plan_a.txt

### Story is too large

If a story requires more work than fits in one iteration:
1. Implement as much as possible
2. Do NOT mark as `passes: true`
3. Document what was done and what remains in progress-prd_plan_a.txt
4. End iteration — the next iteration will continue

---

## Important Reminders

1. **One story per iteration** — Complete exactly one story
2. **Follow the spec** — Each phase file at `validator-agent/docs/phases/phase-*.md` is the source of truth
3. **TDD strictly** — RED (write tests, confirm fail) -> GREEN (implement, confirm pass) -> REFACTOR
4. **Run quality checks** — `pytest tests/ -v` (Python) and `npx vitest run` (frontend) must pass before committing
5. **Atomic commits** — One implementation commit + one tracking commit per story
6. **Update both files** — prd_plan_a.json AND progress-prd_plan_a.txt
7. **Stage specific files** — Never use `git add -A`
8. **Use spec's commit message** — From the **Commit message:** section

---

## Quick Reference

| File | Purpose |
|------|---------|
| `prd_plan_a.json` | Story tracking — mark `passes: true` when done |
| `progress-prd_plan_a.txt` | Learnings log — append iteration summary |
| `validator-agent/docs/phases/phase-*.md` | Spec files — self-contained implementation guides |
| `CLAUDE.md` | Project conventions |
