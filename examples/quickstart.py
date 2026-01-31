"""TinyAgent Quick Start Example

This example demonstrates the core features of TinyAgent:
- Creating nodes with the @node decorator
- Using operator-based flow definition
- Timestamped tracing
"""

import asyncio
from tinyagent import node, State, Flow


@node()
async def fetch_data(state: State) -> bool:
    """Simulate fetching data from an API."""
    print("📥 Fetching data...")
    await asyncio.sleep(0.1)  # Simulate network delay
    await state.set("data", {"temperature": 72, "humidity": 65})
    return True


@node()
async def validate_data(state: State) -> bool:
    """Validate the fetched data."""
    print("✓ Validating data...")
    data = await state.get("data")
    is_valid = data.get("temperature") is not None
    if is_valid:
        print(f"  Data valid: {data}")
    return is_valid


@node()
async def process_data(state: State) -> bool:
    """Process the validated data."""
    print("⚙️  Processing data...")
    data = await state.get("data")
    # Convert to Celsius
    celsius = (data["temperature"] - 32) * 5/9
    await state.set("result", {
        "temp_celsius": round(celsius, 1),
        "humidity": data["humidity"]
    })
    return True


@node()
async def handle_error(state: State) -> bool:
    """Handle validation errors."""
    print("❌ Data validation failed!")
    await state.set("result", {"error": "Invalid data"})
    return True


async def main():
    print("=== TinyAgent Quick Start ===\n")
    
    # Create state
    state = State()
    
    # Define flow using string DSL (simpler for complex expressions)
    # Translation: fetch, then validate, if success process, else handle_error
    flow_expr = "fetch_data >> (validate_data ? process_data | handle_error)"
    
    # Run the flow
    print(f"Running flow: {flow_expr}\n")
    success = await Flow().run(flow_expr, state)
    
    # Display results
    print(f"\n✓ Flow completed: {success}")
    result = await state.get("result")
    print(f"Result: {result}")
    
    # Show trace with timestamps
    print(f"\n📊 Execution Trace (Session: {state.session_id[:8]}):")
    start_time = state.trace[0][0] if state.trace else 0
    for timestamp, event, metadata in state.trace:
        elapsed = (timestamp - start_time) * 1000  # Convert to ms
        print(f"  +{elapsed:6.1f}ms - {event}")
        if metadata:
            print(f"    Metadata: {metadata}")


if __name__ == "__main__":
    asyncio.run(main())
