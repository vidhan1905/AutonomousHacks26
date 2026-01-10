#!/usr/bin/env python3
"""
Script to visualize the LangGraph workflow.
Generates Mermaid diagrams and ASCII visualizations of the conversation agent graph.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.src.agents.conversation_agent import create_graph


def visualize_graph():
    """Generate visualizations of the LangGraph workflow."""
    print("Creating LangGraph visualization...")
    
    # Create the graph
    graph = create_graph()
    
    # Get the compiled graph
    compiled_graph = graph.get_graph()
    
    # Generate Mermaid diagram
    print("\n" + "="*80)
    print("MERMAID DIAGRAM")
    print("="*80)
    mermaid_diagram = compiled_graph.draw_mermaid()
    print(mermaid_diagram)
    
    # Generate ASCII diagram (optional, requires grandalf)
    ascii_diagram = None
    try:
        print("\n" + "="*80)
        print("ASCII DIAGRAM")
        print("="*80)
        ascii_diagram = compiled_graph.draw_ascii()
        print(ascii_diagram)
    except ImportError as e:
        print(f"⚠ ASCII diagram requires 'grandalf' package. Install with: uv add grandalf")
        print("Mermaid diagram is still available.")
    except Exception as e:
        print(f"⚠ Could not generate ASCII diagram: {e}")
        print("Mermaid diagram is still available.")
    
    # Save Mermaid diagram to file
    mermaid_file = project_root / "langgraph_visualization.mmd"
    with open(mermaid_file, "w") as f:
        f.write(mermaid_diagram)
    print(f"\n✓ Mermaid diagram saved to: {mermaid_file}")
    
    # Create HTML file with Mermaid diagram
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LangGraph Workflow Visualization</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }}
        .mermaid {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border: 2px solid #e9ecef;
            margin: 20px 0;
        }}
        .info {{
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info h3 {{
            margin-top: 0;
            color: #1976D2;
        }}
        .info ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .info li {{
            margin: 5px 0;
        }}
        .node-info {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }}
        .node-info h4 {{
            margin-top: 0;
            color: #667eea;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 LangGraph Workflow Visualization</h1>
        <p class="subtitle">Hospital AI Assistant - Conversation Agent Graph</p>
        
        <div class="info">
            <h3>📊 Graph Overview</h3>
            <p>This diagram shows the complete workflow of the LangGraph conversation agent, including:</p>
            <ul>
                <li><strong>Nodes:</strong> Different processing stages (agent, tools, process_results, etc.)</li>
                <li><strong>Edges:</strong> Flow of execution between nodes</li>
                <li><strong>Conditional Edges:</strong> Decision points that route to different nodes based on state</li>
            </ul>
        </div>
        
        <div class="mermaid">
{mermaid_diagram}
        </div>
        
        <div class="node-info">
            <h4>🔵 Node Descriptions</h4>
            <ul>
                <li><strong>agent:</strong> Main LLM node that processes user messages and decides on actions</li>
                <li><strong>tools:</strong> Executes tool calls (verify_patient, get_patient_history, create_ticket, etc.)</li>
                <li><strong>process_results:</strong> Processes tool results and updates conversation state</li>
                <li><strong>collect_info:</strong> Collects missing patient information (name, phone, DOB)</li>
                <li><strong>verify_patient:</strong> Verifies patient identity against database</li>
            </ul>
        </div>
        
        <div class="node-info">
            <h4>🔄 Workflow Flow</h4>
            <ol>
                <li>User message enters through <code>agent</code> node</li>
                <li>Agent decides next action via <code>should_continue</code> conditional function</li>
                <li>Routes to:
                    <ul>
                        <li><code>tools</code> → if tool calls needed</li>
                        <li><code>collect_info</code> → if patient info missing</li>
                        <li><code>verify_patient</code> → if verification needed</li>
                        <li><code>end</code> → if response ready</li>
                    </ul>
                </li>
                <li>After tools execute, flows to <code>process_results</code></li>
                <li><code>process_results</code> updates state and returns to <code>agent</code></li>
                <li>Process repeats until <code>end</code> is reached</li>
            </ol>
        </div>
        
        <div class="info">
            <h3>🛠️ Tools Available</h3>
            <ul>
                <li><code>extract_patient_info</code> - Extracts name, phone, DOB from user message</li>
                <li><code>verify_patient</code> - Verifies patient exists in database</li>
                <li><code>create_patient</code> - Creates new patient record</li>
                <li><code>get_patient_history</code> - Retrieves patient's medical history</li>
                <li><code>get_service_persons_by_type</code> - Gets doctors by service type</li>
                <li><code>rank_doctors_with_llm</code> - Ranks doctors using LLM analysis</li>
                <li><code>create_multiple_tickets</code> - Creates tickets for multiple doctors</li>
                <li><code>create_ticket</code> - Creates a service ticket</li>
                <li><code>schedule_appointment</code> - Schedules an appointment</li>
            </ul>
        </div>
    </div>
    
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            themeVariables: {{
                primaryColor: '#667eea',
                primaryTextColor: '#fff',
                primaryBorderColor: '#4a5568',
                lineColor: '#667eea',
                secondaryColor: '#f3e5f5',
                tertiaryColor: '#fff3e0',
                noteBkgColor: '#fff3cd',
                noteTextColor: '#856404',
                noteBorderColor: '#ffc107'
            }},
            flowchart: {{
                useMaxWidth: true,
                htmlLabels: true,
                curve: 'basis',
                padding: 20
            }}
        }});
    </script>
</body>
</html>
"""
    
    html_file = project_root / "langgraph_visualization.html"
    with open(html_file, "w") as f:
        f.write(html_content)
    print(f"✓ HTML visualization saved to: {html_file}")
    
    # Save ASCII diagram to file (if available)
    if ascii_diagram:
        ascii_file = project_root / "langgraph_ascii.txt"
        with open(ascii_file, "w") as f:
            f.write(ascii_diagram)
        print(f"✓ ASCII diagram saved to: {ascii_file}")
    
    print("\n" + "="*80)
    print("Visualization complete! Open langgraph_visualization.html in a browser to view.")
    print("="*80)


if __name__ == "__main__":
    try:
        visualize_graph()
    except Exception as e:
        print(f"Error generating visualization: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
