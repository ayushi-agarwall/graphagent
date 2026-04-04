"""TinyAgent Quick Start Example

Demonstrates the core features of TinyAgent v0.2.0.
"""

import asyncio
from tinyagent import Node, State, Flow


async def fetch_data(state: State) -> bool:
    """Simulate fetching data from an API."""
    print("📥 Fetching data...")
    await asyncio.sleep(0.1)
    await state.set("data", {"temperature": 72, "humidity": 65})
    return True


async def validate_data(state: State) -> bool:
    """Validate the fetched data."""
    print("✓ Validating data...")
    data = await state.get("data")
    is_valid = data.get("temperature") is not None
    if is_valid:
        print(f"  Data valid: {data}")
    return is_valid


async def process_data(state: State) -> bool:
    """Process the validated data."""
    print("⚙️  Processing data...")
    data = await state.get("data")
    celsius = (data["temperature"] - 32) * 5/9
    await state.set("result", {
        "temp_celsius": round(celsius, 1),
        "humidity": data["humidity"]
    })
    return True


async def handle_error(state: State) -> bool:
    """Handle validation errors."""
    print("❌ Data validation failed!")
    await state.set("result", {"error": "Invalid data"})
    return True


# Register nodes
fetch = Node("fetch_data", fetch_data)
validate = Node("validate_data", validate_data)
process = Node("process_data", process_data)
error_handler = Node("handle_error", handle_error)


async def main():
    print("=== TinyAgent Quick Start ===\n")
    
    # Create state (pure data container)
    state = State()
    
    # Define flow using string DSL
    flow_expr = "fetch_data >> (validate_data ? process_data | handle_error)"
    
    # Run the flow
    print(f"Running flow: {flow_expr}\n")
    flow = Flow()
    success = await flow.run(flow_expr, state)
    
    # Display results
    print(f"\n✓ Flow completed: {success}")
    result = await state.get("result")
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
