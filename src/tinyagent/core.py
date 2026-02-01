"""TinyAgent: Zero-dependency async-first agent orchestration framework."""
from __future__ import annotations
import asyncio, logging, re, time
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

class State:
    """Async-safe transient state with unbounded tracing for GNN training data collection."""
    def __init__(self, data: dict[str, Any] | None = None, async_safe: bool = False, trace_id: str | None = None):
        self._data = data or {}
        self._lock: asyncio.Lock | None = asyncio.Lock() if async_safe else None
        self.trace: list[tuple[float, str, dict | None]] = []
        self.trace_id: str = trace_id or f"{time.time():.0f}-{id(self)}"

    async def get(self, key: str, default: Any = None) -> Any:
        if self._lock:
            async with self._lock: return self._data.get(key, default)
        return self._data.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        if self._lock:
            async with self._lock: self._data[key] = value
        else: self._data[key] = value

    def log(self, entry: str, metadata: dict[str, Any] | None = None) -> None:
        self.trace.append((time.time(), entry, metadata))

class Node:
    """Atomic unit of work wrapping an async callable."""
    _registry: dict[str, Node] = {}

    def __init__(self, name: str, fn: Callable[[State], Awaitable[bool]], timeout: float | None = None, retries: int = 0):
        if timeout is not None and timeout <= 0: raise ValueError(f"timeout must be > 0, got {timeout}")
        if retries < 0: raise ValueError(f"retries must be >= 0, got {retries}")
        self.name, self._fn, self._timeout, self._retries = name, fn, timeout, retries
        Node._registry[name] = self

    async def execute(self, state: State) -> bool:
        for attempt in range(self._retries + 1):
            start = time.time()
            try:
                r = await (asyncio.wait_for(self._fn(state), self._timeout) if self._timeout else self._fn(state))
                state.log(f"{self.name}:OK:{time.time()-start:.3f}s"); return bool(r)
            except asyncio.TimeoutError: state.log(f"{self.name}:TIMEOUT:{time.time()-start:.3f}s")
            except Exception as e: logger.exception(self.name); state.log(f"{self.name}:ERR({type(e).__name__}):{time.time()-start:.3f}s")
        return False

class Flow:
    """Graph-based orchestrator with compiled execution plans."""
    _P = {">>": 1, "|": 2, "?": 2, "&": 3, "<": 4}
    _RE = re.compile(r"(\(|\)|>>|&|\?|\||<\d+>|\w+)")
    
    def __init__(self):
        self._cache: dict[str, list[str]] = {}
        self._visited: set[str] = set()

    async def run(self, expr: str, state: State) -> bool:
        expr_str = str(expr)
        if expr_str not in self._cache:
            tokens = self._RE.findall(expr_str)
            self._validate(tokens)
            self._cache[expr_str] = tokens
        return await self._eval(self._cache[expr_str], state)

    def _validate(self, tokens: list[str]) -> None:
        """Validate DSL and check for missing nodes."""
        depth, nodes = 0, set()
        for t in tokens:
            if t == "(": depth += 1
            elif t == ")": depth -= 1
            elif t not in self._P and not t.startswith("<") and t not in ("(", ")"):
                nodes.add(t)
                if t not in Node._registry:
                    raise ValueError(f"Node '{t}' not found in registry. Available: {list(Node._registry.keys())}")
            if depth < 0: raise ValueError(f"Unmatched closing parenthesis in expression")
        if depth != 0: raise ValueError(f"Unmatched opening parenthesis in expression")

    async def _eval(self, tokens: list[str], s: State, start: int = 0, end: int | None = None) -> bool:
        if end is None: end = len(tokens)
        if start >= end: return False
        
        if end - start == 1:
            t = tokens[start]
            return await Node._registry[t].execute(s) if t in Node._registry else False
        
        min_prec, op_idx, depth = 999, -1, 0
        for i in range(start, end):
            if tokens[i] == "(": depth += 1
            elif tokens[i] == ")": depth -= 1
            elif depth == 0 and (tokens[i] in self._P or tokens[i].startswith("<")):
                prec = self._P.get(tokens[i], 4) if not tokens[i].startswith("<") else 4
                if prec <= min_prec: min_prec, op_idx = prec, i
        
        if op_idx == -1: return await self._eval(tokens, s, start + 1, end - 1)
        
        op = tokens[op_idx]
        
        if op.startswith("<") and op.endswith(">"):
            n, last_result = int(op[1:-1]), False
            for _ in range(n):
                left_result = await self._eval(tokens, s, start, op_idx)
                right_result = await self._eval(tokens, s, op_idx + 1, end)
                last_result = right_result
                if right_result: break
            return last_result
        
        if op == "&":
            left_coro = self._eval(tokens, s, start, op_idx)
            right_coro = self._eval(tokens, s, op_idx + 1, end)
            left_result, right_result = await asyncio.gather(left_coro, right_coro)
            return left_result and right_result
        
        left_result = await self._eval(tokens, s, start, op_idx)
        
        if op == ">>": return await self._eval(tokens, s, op_idx + 1, end)
        if op == "?": return await self._eval(tokens, s, op_idx + 1, end) if left_result else False
        if op == "|": return await self._eval(tokens, s, op_idx + 1, end) if not left_result else left_result
        return False
