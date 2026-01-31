# TinyAgent

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/ayushi-agarwall/tinyagent/releases)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Size](https://img.shields.io/badge/code%20size-6.4%20KB-green.svg)](./src/tinyagent/core.py)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](./pyproject.toml)

A zero-dependency, async-first agent orchestration framework built on graph theory.

![TinyAgent Architecture](./assets/tinyagent_architecture.png)

## Overview

TinyAgent is a minimal, production-ready framework for building AI agents and complex multi-agent orchestrations. The entire core is under 100 lines of Python using only the standard library.

| Framework | Core Lines | Dependencies | Vendor Lock-in |
|-----------|------------|--------------|----------------|
| LangGraph | ~15,000+ | 20+ | LangChain ecosystem |
| CrewAI | ~8,000+ | 30+ | CrewAI platform |
| Pydantic AI | ~5,000+ | 15+ | Pydantic ecosystem |
| AutoGen | ~20,000+ | 40+ | Microsoft Azure |
| TinyAgent | ~100 | 0 | None |

## Design Philosophy

- **Zero bloat**: No unnecessary abstractions
- **Zero dependencies**: Python standard library only
- **Zero vendor lock-in**: Integrate with any LLM, tool, or service
- **Rapid prototyping**: Build agents in minutes
- **Production extensible**: Scale without rewriting

## Core Concepts

TinyAgent is built on three primitives:

| Component | Purpose |
|-----------|---------|
| `Node` | Atomic unit of work (agent) |
| `State` | Thread-safe, transient data container with timestamped tracing |
| `Flow` | Graph orchestrator with DSL parser |

### Edge Operators

```
>>    Sequential: Run A then B
&     Parallel: Run A and B concurrently
?     Conditional Success: Run B only if A succeeds
|     Conditional Failure: Run B only if A fails
<N>   Loop: Alternate between A and B up to N times
()    Grouping: Isolate precedence
```

## Installation

### Option 1: Install from Source (Recommended for now)

```bash
git clone https://github.com/ayushi-agarwall/tinyagent.git
cd tinyagent
pip install -e .
```

### Option 2: Copy-Paste (Zero Install)

Just copy [`src/tinyagent/core.py`](./src/tinyagent/core.py) into your project:

```bash
curl -O https://raw.githubusercontent.com/ayushi-agarwall/tinyagent/main/src/tinyagent/core.py
```

### Option 3: PyPI (Coming Soon)

```bash
pip install tinyagent
```

## Quick Start

```python
import asyncio
from tinyagent import node, State, Flow

@node()
async def fetch(state: State) -> bool:
    await state.set("data", {"value": 42})
    return True

@node()
async def process(state: State) -> bool:
    data = await state.get("data")
    await state.set("result", data["value"] * 2)
    return True

async def main():
    state = State()
    
    # Option 1: Operator-based flow definition
    await Flow().run(fetch >> process, state)
    
    # Option 2: String DSL
    await Flow().run("fetch >> process", state)
    
    print(await state.get("result"))  # 84
    print(state.trace)  # [(1706745600.123, 'fetch:OK'), (1706745600.456, 'process:OK')]

asyncio.run(main())
```

## Supported Architectures

TinyAgent provides Turing-complete orchestration. The following patterns are natively supported through edge operators:

### Multi-Agent Systems
Parallel execution with fan-out and fan-in. Multiple specialized agents work concurrently on subtasks, with results aggregated by a coordinator.

### Workflow Automation
Sequential pipelines with conditional branching. Tasks execute in order with success/failure routing to handle edge cases.

### RAG Pipelines
Retrieval-augmented generation through sequential node composition: embedding, retrieval, reranking, and generation stages.

### Graph of Thoughts (GoT)
Parallel reasoning branches that explore multiple solution paths simultaneously, then aggregate insights.

### Mixture of Experts (MoE)
Router nodes that dispatch to specialized expert nodes running in parallel, with a combiner for final output.

### Self-Correction Loop (Reflexion)
Bidirectional loops using the `<N>` operator. A generator produces output, a validator checks it, and the loop continues until success or max iterations.

### Hierarchical Multi-Agent
Nested flows where orchestrator nodes invoke sub-flows, enabling tree-structured agent hierarchies.

### Consensus Mechanisms
Parallel agents with voting aggregation for ensemble decision-making.

## Inherent Tracing

Every request generates a timestamped trace log with execution duration automatically. Timestamps and durations enable temporal modeling and performance analysis.

```python
state = State()
await Flow().run("A >> B ? C | D", state)
print(state.trace)
# [
#   (1706745600.001, 'A:OK:0.150s', None),
#   (1706745600.151, 'B:ERR(ValueError):0.023s', None),
#   (1706745600.174, 'D:OK:0.005s', None)
# ]
```

Trace format: `(timestamp, "{NodeName}:{Status}:{Duration}", metadata)`

**Status values:**
- `OK` - Successful execution
- `TIMEOUT` - Execution exceeded timeout
- `ERR({ExceptionType})` - Exception occurred

**Duration** - Time in seconds (3 decimal precision) the node took to execute

### Custom Trace Logging

Users can log custom data with metadata for debugging and analysis:

```python
@node()
async def my_agent(state: State) -> bool:
    # Your logic here
    result = {"score": 0.95, "category": "approved"}
    
    # Log custom event with metadata
    state.log("my_agent:decision", {
        "score": result["score"],
        "category": result["category"],
        "confidence": 0.95
    })
    
    return True

# Trace will include:
# (timestamp, 'my_agent:decision', {'score': 0.95, 'category': 'approved', 'confidence': 0.95})
# (timestamp, 'my_agent:OK:0.023s', None)
```

## API Reference

### State

```python
State(
    data: dict = None,       # Initial state data
    deep_copy: bool = False, # Enable deep copying on get/set
    thread_safe: bool = False # Enable async lock
)
```

Methods:
- `await state.get(key, default=None)` - Retrieve value
- `await state.set(key, value)` - Store value
- `state.log(entry, metadata=None)` - Add custom trace entry with optional metadata dict
- `state.trace` - List of (timestamp, event, metadata) tuples
- `state.session_id` - Unique session identifier

### Node

```python
# Via decorator
@node(name="optional_name", timeout=30.0, retries=3)
async def my_node(state: State) -> bool:
    ...

# Via constructor
Node(
    name: str,
    fn: Callable[[State], Awaitable[bool]],
    timeout: float = None,
    retries: int = 0
)
```

Nodes support operator chaining:
```python
flow_expr = fetch >> process >> output
flow_expr = step_a & step_b  # parallel
flow_expr = validate ^ fallback  # conditional
```

### Flow

```python
Flow()
```

Methods:
- `await flow.run(expr, state)` - Execute DSL expression (string or Expr object)

## Loop Operator

The `<N>` operator alternates execution between two nodes:

```python
# generator produces, reviewer validates, loops up to 3 times
await flow.run("generator <3> reviewer", state)
```

Execution:
1. Run generator
2. Run reviewer
3. If reviewer returns False, repeat (up to N times)
4. Exit on reviewer success or max iterations

## Extensibility

TinyAgent integrates with external libraries without lock-in:

```python
from tinyagent import node, State

# With any LLM client
@node()
async def llm_node(state: State) -> bool:
    response = await openai_client.chat(await state.get("prompt"))
    await state.set("response", response)
    return True

# With any HTTP client
@node()
async def api_node(state: State) -> bool:
    async with aiohttp.ClientSession() as session:
        async with session.get(await state.get("url")) as resp:
            await state.set("data", await resp.json())
    return True
```

## Future Roadmap

### GNN-Powered Self-Optimization

TinyAgent trace logs are architected as timestamped graph data specifically designed to serve as training data for Graph Neural Networks (GNNs/GCNs) and temporal graph models. This enables:

1. **Execution Pattern Learning**: GNNs learn optimal execution paths from historical traces
2. **Temporal Modeling**: Timestamps enable State Space Models on temporal graphs
3. **Predictive Routing**: Dynamic edge weight optimization based on node performance
4. **Anomaly Detection**: Identification of suboptimal or failing flow patterns
5. **Self-Healing Flows**: Automatic rerouting around predicted failure points

The trace format `[(t1, "A:OK"), (t2, "B:ERR"), (t3, "C:OK")]` directly maps to temporal graph representations suitable for GNN/SSM training.

### Planned Features

- Pub/sub event system
- Workflow validation (cycle detection)
- Mermaid diagram visualization

## License

MIT License. See [LICENSE](./LICENSE) for details.
