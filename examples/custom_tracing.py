"""Example: Custom Trace Logging with Metadata

Demonstrates how to log custom data to the trace for debugging and analysis.
"""

import asyncio
from tinyagent import node, State, Flow


@node()
async def fetch_user(state: State) -> bool:
    """Fetch user data and log metadata."""
    user_id = await state.get("user_id", 123)
    user_data = {"id": user_id, "name": "Alice", "role": "admin"}
    
    await state.set("user", user_data)
    
    # Log with custom metadata
    state.log("fetch_user:custom", {
        "user_id": user_id,
        "cache_hit": False,
        "api_latency_ms": 45
    })
    
    return True


@node()
async def process_user(state: State) -> bool:
    """Process user and log decision metadata."""
    user = await state.get("user")
    
    decision = "approved" if user["role"] == "admin" else "pending"
    await state.set("decision", decision)
    
    # Log decision metadata
    state.log("process_user:decision", {
        "decision": decision,
        "user_role": user["role"],
        "confidence": 0.95
    })
    
    return True


async def main():
    print("=== Custom Trace Logging Example ===\n")
    
    state = State(data={"user_id": 456})
    
    await Flow().run("fetch_user >> process_user", state)
    
    print(f"Decision: {await state.get('decision')}\n")
    
    print("📊 Full Trace with Metadata:")
    for timestamp, event, metadata in state.trace:
        print(f"  {timestamp:.3f} - {event}")
        if metadata:
            print(f"    Metadata: {metadata}")


if __name__ == "__main__":
    asyncio.run(main())
