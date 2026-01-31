"""TinyAgent: Zero-dependency async-first agent orchestration framework."""
from __future__ import annotations
import asyncio, copy, logging, re, uuid, time
from typing import Any, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)

class State:
    """Thread-safe transient state container with timestamped tracing."""
    def __init__(self, data: Optional[dict[str, Any]] = None, deep_copy: bool = False, thread_safe: bool = False):
        self._data, self._dc, self._lock = data or {}, deep_copy, asyncio.Lock() if thread_safe else None
        self.trace: list[tuple[float, str, Optional[dict]]] = []
        self.session_id: str = str(uuid.uuid4())

    async def get(self, key: str, default: Any = None) -> Any:
        if self._lock:
            async with self._lock: v = self._data.get(key, default)
        else: v = self._data.get(key, default)
        return copy.deepcopy(v) if self._dc else v

    async def set(self, key: str, value: Any) -> None:
        v = copy.deepcopy(value) if self._dc else value
        if self._lock:
            async with self._lock: self._data[key] = v
        else: self._data[key] = v

    def log(self, entry: str, metadata: Optional[dict[str, Any]] = None) -> None: 
        self.trace.append((time.time(), entry, metadata))

class Node:
    """Atomic unit of work wrapping an async callable."""
    _registry: dict[str, Node] = {}

    def __init__(self, name: str, fn: Callable[[State], Awaitable[bool]], timeout: Optional[float] = None, retries: int = 0):
        self.name, self._fn, self._timeout, self._retries = name, fn, timeout, retries
        Node._registry[name] = self

    async def execute(self, state: State) -> bool:
        for _ in range(self._retries + 1):
            start = time.time()
            try:
                r = await (asyncio.wait_for(self._fn(state), self._timeout) if self._timeout else self._fn(state))
                state.log(f"{self.name}:OK:{time.time()-start:.3f}s"); return bool(r)
            except asyncio.TimeoutError: state.log(f"{self.name}:TIMEOUT:{time.time()-start:.3f}s")
            except Exception as e: logger.exception(self.name); state.log(f"{self.name}:ERR({type(e).__name__}):{time.time()-start:.3f}s")
        return False

    def __rshift__(self, other) -> Expr: 
        other_name = other.name if isinstance(other, Node) else str(other)
        return Expr(f"{self.name} >> {other_name}")
    
    def __and__(self, other) -> Expr: 
        other_name = other.name if isinstance(other, Node) else str(other)
        return Expr(f"{self.name} & {other_name}")
    
    def __or__(self, other) -> Expr: 
        other_name = other.name if isinstance(other, Node) else str(other)
        return Expr(f"{self.name} | {other_name}")
    
    def __xor__(self, other) -> Expr: 
        other_name = other.name if isinstance(other, Node) else str(other)
        return Expr(f"{self.name} ? {other_name}")

def node(name: Optional[str] = None, timeout: Optional[float] = None, retries: int = 0):
    """Decorator to create a Node from an async function."""
    def decorator(fn: Callable[[State], Awaitable[bool]]) -> Node:
        return Node(name or fn.__name__, fn, timeout, retries)
    return decorator

class Expr:
    """Expression builder for flow DSL."""
    def __init__(self, expr: str): self._expr = expr
    def __rshift__(self, other) -> Expr: return Expr(f"({self._expr}) >> {other.name if isinstance(other, Node) else other._expr}")
    def __and__(self, other) -> Expr: return Expr(f"({self._expr}) & {other.name if isinstance(other, Node) else other._expr}")
    def __or__(self, other) -> Expr: return Expr(f"({self._expr}) | {other.name if isinstance(other, Node) else other._expr}")
    def __xor__(self, other) -> Expr: return Expr(f"({self._expr}) ? {other.name if isinstance(other, Node) else other._expr}")
    def loop(self, n: int, other) -> Expr: return Expr(f"({self._expr}) <{n}> {other.name if isinstance(other, Node) else other._expr}")
    def __str__(self) -> str: return self._expr

class Flow:
    """Graph-based orchestrator parsing DSL expressions into async execution."""
    _P, _RE = {">>": 1, "|": 2, "?": 2, "&": 3, "<": 4}, re.compile(r"(\(|\)|>>|&|\?|\||<\d+>|\w+)")

    async def run(self, expr: str | Expr, state: State) -> bool:
        tokens = self._RE.findall(str(expr))
        return await self._eval_infix(tokens, state)

    async def _eval_infix(self, tokens: list[str], s: State, start: int = 0, end: int = None) -> bool:
        """Recursively evaluate infix expression with proper precedence."""
        if end is None: end = len(tokens)
        if start >= end: return False
        
        # Handle single token
        if end - start == 1:
            t = tokens[start]
            return await Node._registry[t].execute(s) if t in Node._registry else False
        
        # Find lowest precedence operator (rightmost for left-to-right evaluation)
        min_prec, op_idx, depth = 999, -1, 0
        for i in range(start, end):
            if tokens[i] == "(": depth += 1
            elif tokens[i] == ")": depth -= 1
            elif depth == 0 and (tokens[i] in self._P or tokens[i].startswith("<")):
                prec = self._P.get(tokens[i], 4) if not tokens[i].startswith("<") else 4
                if prec <= min_prec:
                    min_prec, op_idx = prec, i
        
        if op_idx == -1:  # Parenthesized expression
            return await self._eval_infix(tokens, s, start + 1, end - 1)
        
        op = tokens[op_idx]
        
        if op.startswith("<") and op.endswith(">"):
            n = int(op[1:-1])
            for _ in range(n):
                left_result = await self._eval_infix(tokens, s, start, op_idx)
                if not left_result: break
                right_result = await self._eval_infix(tokens, s, op_idx + 1, end)
                if right_result: break
            return True
        
        left_result = await self._eval_infix(tokens, s, start, op_idx)
        
        if op == ">>": return await self._eval_infix(tokens, s, op_idx + 1, end)
        if op == "&": return left_result and await self._eval_infix(tokens, s, op_idx + 1, end)
        if op == "?": return await self._eval_infix(tokens, s, op_idx + 1, end) if left_result else False
        if op == "|": return left_result or await self._eval_infix(tokens, s, op_idx + 1, end)
        return False
