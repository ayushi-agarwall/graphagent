"""TinyAgent: Zero-dependency async-first agent orchestration framework."""
from __future__ import annotations
import asyncio, re
from typing import Any, Callable, Awaitable

class State:
    """Async-safe transient state container for agent data."""
    def __init__(self, data: dict[str, Any] | None = None, async_safe: bool = False):
        self._data = data or {}
        self._lock: asyncio.Lock | None = asyncio.Lock() if async_safe else None

    async def get(self, key: str, default: Any = None) -> Any:
        if self._lock:
            async with self._lock: return self._data.get(key, default)
        return self._data.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        if self._lock:
            async with self._lock: self._data[key] = value
        else: self._data[key] = value
    
    async def update(self, key: str, fn: Callable[[Any], Any]) -> None:
        """Atomically update a value using a function."""
        if self._lock:
            async with self._lock: self._data[key] = fn(self._data.get(key))
        else: self._data[key] = fn(self._data.get(key))

class Node:
    """Atomic unit of work wrapping an async callable."""
    _registry: dict[str, Node] = {}

    def __init__(self, name: str, fn: Callable[[State], Awaitable[bool]], timeout: float | None = None, retries: int = 0, raise_errors: bool = False):
        if timeout is not None and timeout <= 0: raise ValueError(f"timeout must be > 0, got {timeout}")
        if retries < 0: raise ValueError(f"retries must be >= 0, got {retries}")
        self.name, self._fn, self._timeout, self._retries, self._raise = name, fn, timeout, retries, raise_errors
        Node._registry[name] = self

    async def execute(self, state: State) -> bool:
        for _ in range(self._retries + 1):
            try:
                r = await (asyncio.wait_for(self._fn(state), self._timeout) if self._timeout else self._fn(state))
                return bool(r)
            except asyncio.TimeoutError:
                continue
            except KeyboardInterrupt:
                raise
            except Exception as e:
                if self._raise: raise
                continue
        return False

class Flow:
    """Graph-based orchestrator with compiled execution plans."""
    _P = {">>": 1, "|": 2, "?": 2, "&": 3, "<": 4}
    _RE = re.compile(r'(\(|\)|>>|&|\?|\||<\d+>|[^\s()&|?<>]+)')
    
    def __init__(self):
        self._cache: dict[str, list[str]] = {}

    async def run(self, expr: str, state: State) -> bool:
        if not isinstance(expr, str):
            raise TypeError(f"expr must be str, got {type(expr).__name__}")
        if not expr or not expr.strip():
            raise ValueError("expr cannot be empty")
        
        # Remove whitespace and tokenize
        expr_clean = re.sub(r'\s+', '', expr)
        
        if expr_clean not in self._cache:
            tokens = self._RE.findall(expr_clean)
            self._validate(tokens)
            self._cache[expr_clean] = tokens
        
        return await self._eval(self._cache[expr_clean], state)

    def _validate(self, tokens: list[str]) -> None:
        """Validate DSL and check for missing nodes."""
        depth = 0
        for t in tokens:
            if t == "(": depth += 1
            elif t == ")": depth -= 1
            elif t not in self._P and not t.startswith("<") and t not in ("(", ")"):
                if t not in Node._registry:
                    raise ValueError(f"Node '{t}' not found in registry. Available: {list(Node._registry.keys())}")
            if depth < 0: raise ValueError("Unmatched closing parenthesis")
        if depth != 0: raise ValueError("Unmatched opening parenthesis")

    async def _eval(self, tokens: list[str], s: State, start: int = 0, end: int | None = None, path: tuple[str, ...] = ()) -> bool:
        if end is None: end = len(tokens)
        if start >= end: return False
        
        # Single node - check for cycles in sequential path
        if end - start == 1:
            t = tokens[start]
            if t in Node._registry:
                if t in path:
                    raise RuntimeError(f"Cycle detected: {' >> '.join(path + (t,))}")
                return await Node._registry[t].execute(s)
            return False
        
        min_prec, op_idx, depth = 999, -1, 0
        for i in range(start, end):
            if tokens[i] == "(": depth += 1
            elif tokens[i] == ")": depth -= 1
            elif depth == 0 and (tokens[i] in self._P or tokens[i].startswith("<")):
                prec = self._P.get(tokens[i], 4) if not tokens[i].startswith("<") else 4
                if prec <= min_prec: min_prec, op_idx = prec, i
        
        if op_idx == -1: return await self._eval(tokens, s, start + 1, end - 1, path)
        
        op = tokens[op_idx]
        
        if op.startswith("<") and op.endswith(">"):
            n, last_result = int(op[1:-1]), False
            for _ in range(n):
                left_result = await self._eval(tokens, s, start, op_idx, path)
                right_result = await self._eval(tokens, s, op_idx + 1, end, path)
                last_result = right_result
                if right_result: break
            return last_result
        
        if op == "&":
            left_coro = self._eval(tokens, s, start, op_idx, path)
            right_coro = self._eval(tokens, s, op_idx + 1, end, path)
            left_result, right_result = await asyncio.gather(left_coro, right_coro)
            return left_result and right_result
        
        # For >> operator, extend path to detect cycles
        if op == ">>":
            # Get left node name if it's a single token
            if op_idx - start == 1 and tokens[start] in Node._registry:
                new_path = path + (tokens[start],)
            else:
                new_path = path
            
            left_result = await self._eval(tokens, s, start, op_idx, path)
            return await self._eval(tokens, s, op_idx + 1, end, new_path)
        
        left_result = await self._eval(tokens, s, start, op_idx, path)
        
        if op == "?": return await self._eval(tokens, s, op_idx + 1, end, path) if left_result else False
        if op == "|": return await self._eval(tokens, s, op_idx + 1, end, path) if not left_result else left_result
        return False
