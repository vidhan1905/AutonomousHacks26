# LangGraph Routing Explanation

## Current Graph Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    Entry Point: "agent"                     │
└────────────────────────────┬────────────────────────────────┘
                             ↓
                    ┌─────────────────┐
                    │  [agent] node   │
                    │  (call_model)   │
                    │                 │
                    │  - Processes    │
                    │    messages     │
                    │  - Decides to   │
                    │    call tools   │
                    └────────┬────────┘
                             ↓
        ┌────────────────────────────────────────────┐
        │     should_continue() - Conditional        │
        │           Routing Function                 │
        └─────────────┬──────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ↓             ↓             ↓
   ┌──────┐    ┌──────────┐    ┌─────┐
   │tools │    │verify_   │    │ end │
   │      │    │patient   │    │     │
   └──┬───┘    └────┬─────┘    └─────┘
      │             │
      ↓             ↓
┌──────────┐  ┌──────────┐
│ [tools]  │  │[verify_  │
│ node     │  │ patient] │
└────┬─────┘  └────┬─────┘
     │             │
     ↓             │
┌─────────────┐   │
│[process_    │   │
│ results]    │   │
└──────┬──────┘   │
       │          │
       └──────┬───┘
              ↓
       ┌──────────┐
       │ [agent]  │  ← Loop back
       └──────────┘
```

## Routing Flow Explained

### 1. **Entry Point: `agent` node**
   - `call_model()` is called
   - LLM processes messages and decides to:
     - Call a tool (tool_calls)
     - Return a response (content)
     - Both

### 2. **Conditional Edge: `should_continue()`**
   This function decides where to route based on state:

   **If LLM has tool_calls:**
   - Check if tools are allowed (based on patient_verified)
   - Route to `"tools"` if allowed
   - Route to `"end"` if forbidden (with error message)

   **If no tool_calls:**
   - If patient not verified and all info collected → `"verify_patient"`
   - If patient verified and ToolMessage → `"agent"` (continue)
   - Otherwise → `"end"` (wait for user)

### 3. **Tool Execution Flow:**
   ```
   [agent] → [tools] → [process_results] → [agent]
   ```
   - `tools`: Executes tool calls (extract_patient_info, verify_patient, etc.)
   - `process_results`: Updates state from tool results
   - Back to `agent`: LLM can continue processing

## The "Two Functions" Issue

### Problem:
There are TWO places where info collection happens:

1. **`collect_info_node`** (lines 214-227) - NOT USED
   - This function was designed to ask for missing info
   - It's NOT in the graph anymore (removed)
   - Still exists in code (dead code)

2. **`call_model` + `extract_patient_info` tool** - ACTUALLY USED
   - LLM in `call_model` calls `extract_patient_info` tool
   - Tool extracts info from user message
   - `process_tool_results` updates state
   - LLM then asks for remaining info via system prompt

### Root Cause:
The `collect_info_node` was meant to be a separate node that validates and asks for info, but:
- It creates duplicate logic (asking for info)
- It prevents the LLM from extracting info first
- LangGraph's natural flow is: agent → tools → process → agent (loop)

## Proper LangGraph Flow

LangGraph works best with this pattern:
```
User Message
    ↓
[agent] - LLM decides to call extract_patient_info tool
    ↓
[tools] - Tool executes and extracts info
    ↓
[process_results] - State updated with extracted info
    ↓
[agent] - LLM sees updated state, asks for remaining info
    ↓
END (wait for user)
```

## Solution

Remove `collect_info_node` entirely - it's not needed because:
1. LLM naturally extracts info via tools
2. `process_tool_results` updates state
3. System prompt in `call_model` already handles asking for missing info
4. No need for separate "collect_info" node
