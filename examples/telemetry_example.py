"""Example: Telemetry and Trace Export

Demonstrates how to use the telemetry module to persist traces for GNN training.
"""

import asyncio
from tinyagent import Node, State, Flow
from tinyagent.telemetry import save_trace, TraceLoader


async def generator(state: State) -> bool:
    """Generate content."""
    count = await state.get("count", 0)
    await state.set("count", count + 1)
    await state.set("content", f"Generated content v{count + 1}")
    return count < 2  # Fail after 2 attempts to trigger loop


async def reviewer(state: State) -> bool:
    """Review generated content."""
    count = await state.get("count")
    content = await state.get("content")
    
    # Log custom metadata
    state.log("reviewer:decision", {
        "count": count,
        "content_length": len(content),
        "approved": count >= 2
    })
    
    return count >= 2  # Approve when count reaches 2


# Register nodes
Node("generator", generator)
Node("reviewer", reviewer)


async def main():
    print("=== Telemetry Example ===\n")
    
    # Simulate multiple workflow runs
    print("Running 5 workflows with self-correction loops...\n")
    
    for i in range(5):
        state = State(trace_id=f"workflow-{i:03d}")
        flow = Flow()
        
        # Self-correction loop
        result = await flow.run("generator <5> reviewer", state)
        
        print(f"Workflow {i}: {'✓ Success' if result else '✗ Failed'}")
        print(f"  Events: {len(state.trace)}")
        print(f"  Trace ID: {state.trace_id}")
        
        # Export trace to file and clear memory
        save_trace(state, filepath="example_traces.jsonl")
    
    print("\n📊 All traces saved to example_traces.jsonl\n")
    
    # Load and analyze traces
    print("=== Analyzing Traces ===\n")
    traces = TraceLoader.load_jsonl("example_traces.jsonl")
    
    print(f"Total traces loaded: {len(traces)}")
    
    for trace in traces[:2]:  # Show first 2
        print(f"\nTrace ID: {trace['trace_id']}")
        print(f"Events: {len(trace['events'])}")
        
        # Convert to graph
        nodes, edges = TraceLoader.to_graph(trace)
        print(f"Graph: {len(nodes)} nodes, {len(edges)} edges")
        print(f"Execution path: {' -> '.join(nodes)}")
    
    print("\n✓ Traces ready for GNN training!")
    print("  Format: JSONL (one trace per line)")
    print("  Compatible with: PyTorch Geometric, DGL, NetworkX")


if __name__ == "__main__":
    asyncio.run(main())
