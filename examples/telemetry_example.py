"""Example: Telemetry and Trace Export

Demonstrates how to use TracingFlow for observability and GNN training data collection.
"""

import asyncio
from tinyagent import Node, State, Flow
from tinyagent.telemetry import TracingFlow, save_trace, TraceLoader


async def generator(state: State) -> bool:
    """Generate content."""
    count = await state.get("count", 0)
    await state.set("count", count + 1)
    await state.set("content", f"Generated content v{count + 1}")
    return count < 2  # Fail after 2 attempts to trigger loop


async def reviewer(state: State) -> bool:
    """Review generated content."""
    count = await state.get("count")
    return count >= 2  # Approve when count reaches 2


# Register nodes
Node("generator", generator)
Node("reviewer", reviewer)


async def main():
    print("=== Telemetry Example ===\n")
    
    # Example 1: Normal Flow (no tracing)
    print("1. Normal Flow (no tracing overhead):")
    state = State()
    flow = Flow()
    await flow.run("generator >> reviewer", state)
    print(f"   Result: {await state.get('count')}")
    print(f"   No trace recorded\n")
    
    # Example 2: TracingFlow (with observability)
    print("2. TracingFlow (automatic tracing):")
    state = State()
    tracing_flow = TracingFlow(trace_id="demo-001")
    await tracing_flow.run("generator <3> reviewer", state)
    print(f"   Result: {await state.get('count')}")
    print(f"   Trace events: {len(tracing_flow.trace)}")
    print(f"   Trace ID: {tracing_flow.trace_id}\n")
    
    # Example 3: Custom trace logging
    print("3. Custom trace logging:")
    tracing_flow.log("custom_event", {"key": "value", "score": 0.95})
    print(f"   Added custom event to trace\n")
    
    # Example 4: Persist trace for GNN training
    print("4. Persisting traces for GNN training:")
    for i in range(5):
        state = State()
        flow = TracingFlow(trace_id=f"workflow-{i:03d}")
        await flow.run("generator <5> reviewer", state)
        save_trace(flow, filepath="example_traces.jsonl")
        print(f"   Workflow {i}: saved to example_traces.jsonl")
    
    print("\n📊 All traces saved to example_traces.jsonl\n")
    
    # Example 5: Load and analyze traces
    print("5. Loading traces for analysis:")
    traces = TraceLoader.load_jsonl("example_traces.jsonl")
    print(f"   Total traces loaded: {len(traces)}")
    
    for trace in traces[:2]:
        print(f"\n   Trace ID: {trace['trace_id']}")
        nodes, edges = TraceLoader.to_graph(trace)
        print(f"   Graph: {len(nodes)} nodes, {len(edges)} edges")
        print(f"   Path: {' -> '.join(nodes)}")
    
    print("\n✓ Traces ready for GNN training!")
    print("  Format: JSONL (one trace per line)")
    print("  Compatible with: PyTorch Geometric, DGL, NetworkX")


if __name__ == "__main__":
    asyncio.run(main())
