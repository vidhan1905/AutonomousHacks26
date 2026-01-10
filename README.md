# Hospital AI Assistant System

AI-powered hospital assistant system with LangGraph MCP integration, real-time chat interface where LLM directly converses with patients, patient verification, ticket management, and appointment scheduling.

## Setup

1. **Install dependencies**: `uv sync`
2. **Configure environment variables**: 
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```
3. **Create database** (if it doesn't exist):
   ```bash
   uv run python scripts/init_db.py
   ```
4. **Run migrations**: `uv run alembic upgrade head`
5. **Generate synthetic data** (optional): `uv run python scripts/generate_dataset.py`
6. **Start backend**: `uv run uvicorn backend.src.main:app --reload --port 8000`
7. **Start frontend**: `cd frontend && npm install && npm run dev`

## Environment Variables

See `.env.example` for a sample configuration file. Copy it to `.env` and fill in your values:

- `DATABASE_URL`: PostgreSQL connection string
- `OPENAI_API_KEY`: Your OpenAI API key
- `JWT_SECRET_KEY`: A secure random string (use `openssl rand -hex 32` to generate)
- `LANGSMITH_API_KEY`: Your LangSmith API key (optional, for tracing and observability)
- `LANGSMITH_TRACING`: Set to `true` to enable LangSmith tracing (optional)
- `LANGSMITH_PROJECT`: Project name in LangSmith (optional, defaults to "hospital-ai-assistant")

## Quick Testing Guide

### Test Patient Account
- **Phone**: `001-852-326-5094x079`
- **Name**: April Maldonado
- **DOB**: 1955-02-28

### Quick Test Flow

1. **Login** as patient with phone: `001-852-326-5094x079`
2. **Start conversation** and send: `Hi`
3. **Provide info**: `My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28`
4. **Request appointment**: `I'd like to schedule an appointment for next week`
5. **Request service**: `I need a blood test done`

### Example Test Messages

**For Appointment Scheduling:**
- `I'd like to schedule an appointment for next week for my follow-up`
- `Can I book a consultation?`
- `I want to see a doctor tomorrow`

**For Service Requests:**
- `I need a blood test done. I've been feeling tired lately`
- `Can you help me get a lab test?`
- `I need an imaging scan for my headaches`

**For Emergency:**
- `I'm having severe abdominal pain. I need emergency care`

For detailed testing instructions and all test scenarios, see [TESTING.md](./TESTING.md).

## Visualizing the LangGraph Workflow

You can visualize the LangGraph conversation agent workflow using the provided script:

```bash
# Generate Mermaid diagram and HTML visualization
uv run python scripts/visualize_graph.py
```

This will create:
- `langgraph_visualization.html` - Interactive HTML file with Mermaid diagram (open in browser)
- `langgraph_visualization.mmd` - Mermaid diagram source file

For ASCII visualization (optional), install the visualization dependencies:
```bash
uv sync --extra viz
```

Then run the visualization script again to also generate `langgraph_ascii.txt`.

The visualization shows:
- **Nodes**: agent, tools, process_results, collect_info, verify_patient
- **Edges**: Flow between nodes
- **Conditional Edges**: Decision points that route based on state
- **Workflow**: Complete conversation flow from user input to response

## LangSmith Integration (Observability & Tracing)

This project includes LangSmith integration for monitoring, debugging, and analyzing LLM interactions.

### Setup LangSmith

1. **Create a LangSmith account**: Go to [https://smith.langchain.com/](https://smith.langchain.com/) and sign up
2. **Get your API key**: Navigate to Settings → API Keys and create a new API key
3. **Configure environment variables**: Add the following to your `.env` file:
   ```bash
   LANGSMITH_API_KEY=your_langsmith_api_key_here
   LANGSMITH_TRACING=true
   LANGSMITH_PROJECT=hospital-ai-assistant
   ```

### Viewing Traces

Once enabled, all LangChain operations (LLM calls, tool invocations, graph executions) are automatically traced to LangSmith. You can:

- **View traces in real-time**: Open [https://smith.langchain.com/](https://smith.langchain.com/) to see traces as they happen
- **Filter by project**: Use the `LANGSMITH_PROJECT` to organize traces
- **Debug issues**: Inspect individual LLM calls, tool executions, and graph node transitions
- **Monitor performance**: Track latency, token usage, and costs
- **Analyze conversations**: View complete conversation flows with state changes

### What Gets Traced

- **LLM Invocations**: All ChatOpenAI calls with prompts, responses, and metadata
- **Tool Executions**: Database queries, patient verification, doctor ranking, ticket creation
- **Graph Execution**: Complete LangGraph workflow with node transitions and state changes
- **Message Flow**: All messages (human, AI, tool) in conversations
- **Errors**: Exceptions and error messages for debugging

### Disabling Tracing

To disable tracing without removing the configuration, set:
```bash
LANGSMITH_TRACING=false
```

Or simply remove/comment out the `LANGSMITH_API_KEY` environment variable.
