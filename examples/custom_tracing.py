"""Example: Custom Logging with TracingFlow

Demonstrates how to add custom metadata to traces for debugging.
"""

import asyncio
from tinyagent import Node, State
from tinyagent.telemetry import TracingFlow


async def fetch_user(state: State) -> bool:
    """Fetch user data."""
    user_id = await state.get("user_id", 123)
    user_data = {"id": user_id, "name": "Alice", "role": "admin"}
    await state.set("user", user_data)
    return True


async def process_user(state: State) -> bool:
    """Process user."""
    user = await state.get("user")
    decision = "approved" if user["role"] == "admin" else "pending"
    await state.set("decision", decision)
    return True


# Register nodes
Node("fetch_user", fetch_user)
Node("process_user", process_user)


async def main():
    print("=== Custom Trace Logging Example ===\n")
    
    state = State(data={"user_id": 456})
    flow = TracingFlow(trace_id="custom-trace-demo")
    
    await flow.run("fetch_user >> process_user", state)
    
    # Add custom metadata to trace
    flow.log("custom_decision", {
        "user_id": 456,
        "decision": await state.get("decision"),
        "confidence": 0.95
    })
    
    print(f"Decision: {await state.get('decision')}\n")
    
    print("📊 Full Trace with Metadata:")
    for timestamp, event, metadata in flow.trace:
        print(f"  {timestamp:.3f} - {event}")
        if metadata:
            print(f"    Metadata: {metadata}")


if __name__ == "__main__":
    asyncio.run(main())
