#!/bin/bash
#
# Ralph - Autonomous AI Agent Loop for Claude Code
#
# Adapted for Plan A - AG-UI State-Driven React Cards project.
# Repeatedly spawns Claude Code instances until all stories are complete.
#
# Usage: ./scripts/ralph/ralph.sh [max_iterations]
# Examples:
#   ./scripts/ralph/ralph.sh 50    # 50 iterations
#   ./scripts/ralph/ralph.sh       # 10 iterations (default)
#

set -euo pipefail

# Configuration
MAX_ITERATIONS="${1:-10}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROMPT_FILE="$SCRIPT_DIR/ralph-prompt.md"
PRD_FILE="$PROJECT_ROOT/prd_plan_a.json"
PROGRESS_FILE="$PROJECT_ROOT/progress-prd_plan_a.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[RALPH]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[RALPH]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[RALPH]${NC} $1"
}

log_error() {
    echo -e "${RED}[RALPH]${NC} $1"
}

# Validate prerequisites
validate_setup() {
    log_info "Validating Ralph setup..."

    # Check for Claude CLI
    if ! command -v claude &> /dev/null; then
        log_error "Claude CLI not found. Please install Claude Code."
        exit 1
    fi

    # Check for prompt file
    if [ ! -f "$PROMPT_FILE" ]; then
        log_error "Prompt file not found: $PROMPT_FILE"
        exit 1
    fi

    # Check for PRD file
    if [ ! -f "$PRD_FILE" ]; then
        log_error "PRD file not found: $PRD_FILE"
        log_info "Generate prd_plan_a.json from phases first."
        exit 1
    fi

    # Check for jq (required)
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not found. Install with: brew install jq"
        exit 1
    fi

    # Validate PRD JSON
    if ! jq empty "$PRD_FILE" 2>/dev/null; then
        log_error "Invalid JSON in prd_plan_a.json"
        exit 1
    fi

    # Count incomplete stories (uses .stories[] not .userStories[])
    TOTAL=$(jq '.stories | length' "$PRD_FILE")
    INCOMPLETE=$(jq '[.stories[] | select(.passes == false)] | length' "$PRD_FILE")
    COMPLETE=$((TOTAL - INCOMPLETE))

    log_info "Stories: $COMPLETE/$TOTAL complete ($INCOMPLETE remaining)"

    log_success "Setup validated"
}

# Initialize progress file if needed
init_progress() {
    if [ ! -f "$PROGRESS_FILE" ]; then
        log_info "Initializing progress-prd_plan_a.txt..."
        cat > "$PROGRESS_FILE" << EOF
# Plan A - AG-UI State-Driven React Cards - Ralph Progress Log

## Project Context
- Building SpreadsheetValidator with AG-UI State-Driven React Cards
- Google ADK agents + ag-ui-adk FastAPI SSE + CopilotKit frontend
- 6 phases, $(jq '.stories | length' "$PRD_FILE") total stories
- TDD approach: RED -> GREEN -> REFACTOR for every story

## Completed Stories
(none yet)

## Current Phase
Phase 1: Foundation

## Learnings & Patterns
(To be updated as implementation progresses)

## Blockers & Issues
(none yet)

## Quality Gates
- pytest (all tests must pass)
- vitest (frontend tests must pass)
- Each story follows TDD: write test first, then implement
- Commit message format: feat|fix|refactor(scope): description

---

## Iteration Log

EOF
        log_success "Created progress-prd_plan_a.txt"
    fi
}

# Show current progress
show_progress() {
    echo ""
    log_info "=== Current Progress ==="

    # Show phase completion
    for phase in $(seq 1 6); do
        PHASE_TOTAL=$(jq "[.stories[] | select(.phase == $phase)] | length" "$PRD_FILE")
        PHASE_COMPLETE=$(jq "[.stories[] | select(.phase == $phase and .passes == true)] | length" "$PRD_FILE")
        PHASE_TITLE=$(jq -r ".phases[\"$phase\"].title // \"Phase $phase\"" "$PRD_FILE")

        if [ "$PHASE_COMPLETE" -eq "$PHASE_TOTAL" ]; then
            echo -e "  ${GREEN}[x]${NC} Phase $phase: $PHASE_TITLE ($PHASE_COMPLETE/$PHASE_TOTAL)"
        elif [ "$PHASE_COMPLETE" -gt 0 ]; then
            echo -e "  ${YELLOW}[~]${NC} Phase $phase: $PHASE_TITLE ($PHASE_COMPLETE/$PHASE_TOTAL)"
        else
            echo -e "  [ ] Phase $phase: $PHASE_TITLE ($PHASE_COMPLETE/$PHASE_TOTAL)"
        fi
    done
    echo ""
}

# Get next story to work on
get_next_story() {
    # Get first incomplete story (ordered by id)
    jq -r '[.stories[] | select(.passes == false)][0] | "\(.id)|\(.title)|\(.phase)|\(.spec)"' "$PRD_FILE"
}

# Main execution loop
run_ralph() {
    cd "$PROJECT_ROOT"

    log_info "Starting Ralph autonomous loop"
    log_info "Max iterations: $MAX_ITERATIONS"
    log_info "Project root: $PROJECT_ROOT"

    show_progress

    for ((i=1; i<=MAX_ITERATIONS; i++)); do
        echo ""
        echo "========================================"
        log_info "ITERATION $i of $MAX_ITERATIONS"
        echo "========================================"

        # Get next story info
        NEXT_STORY=$(get_next_story)
        if [ "$NEXT_STORY" == "null|null|null|null" ] || [ -z "$NEXT_STORY" ]; then
            log_success "All stories complete!"
            break
        fi

        STORY_ID=$(echo "$NEXT_STORY" | cut -d'|' -f1)
        STORY_TITLE=$(echo "$NEXT_STORY" | cut -d'|' -f2)
        STORY_PHASE=$(echo "$NEXT_STORY" | cut -d'|' -f3)
        STORY_SPEC=$(echo "$NEXT_STORY" | cut -d'|' -f4)

        log_info "Next story: [$STORY_ID] $STORY_TITLE"
        log_info "Phase: $STORY_PHASE | Spec: $STORY_SPEC"
        echo ""

        # Spawn Claude Code with the prompt
        cd "$PROJECT_ROOT"
        log_info "Spawning Claude Code..."

        # Build context with current story info
        CONTEXT="# Ralph Context

**Current Story:** $STORY_ID - $STORY_TITLE
**Phase:** $STORY_PHASE
**Spec File:** $STORY_SPEC
**PRD File:** prd_plan_a.json
**Progress File:** progress-prd_plan_a.txt

---

"
        OUTPUT=$(printf "%b" "$CONTEXT" | cat - "$PROMPT_FILE" | claude --dangerously-skip-permissions 2>&1 | tee /dev/tty) || true

        # Check for completion signal
        if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
            echo ""
            log_success "============================================"
            log_success "ALL STORIES COMPLETE!"
            log_success "============================================"
            log_success "Total iterations: $i"
            show_progress
            exit 0
        fi

        # Show updated progress
        REMAINING=$(jq '[.stories[] | select(.passes == false)] | length' "$PRD_FILE" 2>/dev/null || echo "?")
        log_info "Stories remaining: $REMAINING"

        # Brief pause between iterations
        if [ $i -lt $MAX_ITERATIONS ]; then
            log_info "Pausing before next iteration..."
            sleep 2
        fi
    done

    echo ""
    log_warning "============================================"
    log_warning "MAX ITERATIONS REACHED"
    log_warning "============================================"
    show_progress
    log_info "Run Ralph again to continue: ./scripts/ralph/ralph.sh $MAX_ITERATIONS"
    exit 1
}

# Main entry point
main() {
    echo ""
    echo "  ██████╗  █████╗ ██╗     ██████╗ ██╗  ██╗"
    echo "  ██╔══██╗██╔══██╗██║     ██╔══██╗██║  ██║"
    echo "  ██████╔╝███████║██║     ██████╔╝███████║"
    echo "  ██╔══██╗██╔══██║██║     ██╔═══╝ ██╔══██║"
    echo "  ██║  ██║██║  ██║███████╗██║     ██║  ██║"
    echo "  ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝"
    echo "  Autonomous AI Agent Loop - Plan A - AG-UI State-Driven"
    echo ""

    validate_setup
    init_progress
    run_ralph
}

main "$@"
