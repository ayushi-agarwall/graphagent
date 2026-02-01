"""Example: Parallel Execution with & Operator

Demonstrates true parallel execution using asyncio.gather.
"""

import asyncio
import time
from tinyagent import Node, State, Flow


async def fetch_user_data(state: State) -> bool:
    """Simulate fetching user data from API."""
    print(f"[{time.time():.3f}] Fetching user data...")
    await asyncio.sleep(0.3)
    await state.set("user", {"id": 123, "name": "Alice"})
    print(f"[{time.time():.3f}] User data fetched")
    return True


async def fetch_product_data(state: State) -> bool:
    """Simulate fetching product data from API."""
    print(f"[{time.time():.3f}] Fetching product data...")
    await asyncio.sleep(0.3)
    await state.set("products", [{"id": 1, "name": "Widget"}])
    print(f"[{time.time():.3f}] Product data fetched")
    return True


async def combine_results(state: State) -> bool:
    """Combine the parallel results."""
    user = await state.get("user")
    products = await state.get("products")
    
    result = {
        "user": user,
        "products": products,
        "timestamp": time.time()
    }
    
    await state.set("result", result)
    return True


# Register nodes
Node("fetch_user_data", fetch_user_data)
Node("fetch_product_data", fetch_product_data)
Node("combine_results", combine_results)


async def main():
    print("=== Parallel Execution Demo ===\n")
    
    state = State(trace_id="parallel-demo")
    
    # Run two API calls in parallel, then combine
    print("Running: (fetch_user_data & fetch_product_data) >> combine_results\n")
    
    start = time.time()
    flow = Flow()
    await flow.run("(fetch_user_data & fetch_product_data) >> combine_results", state)
    elapsed = time.time() - start
    
    result = await state.get("result")
    
    print(f"\n✓ Completed in {elapsed:.3f}s")
    print(f"  Parallel execution: ~0.3s (both APIs called simultaneously)")
    print(f"  Sequential would be: ~0.6s (one after another)")
    print(f"\nResult: {result}")
    
    print(f"\n📊 Trace:")
    for timestamp, event, metadata in state.trace:
        print(f"  {event}")


if __name__ == "__main__":
    asyncio.run(main())
