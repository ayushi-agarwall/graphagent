"""TinyAgent Telemetry: OpenTelemetry-compatible trace export and persistence.

This module provides tracing capabilities separate from the core framework.
Use TracingFlow instead of Flow to enable automatic execution tracing.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any
import asyncio

try:
    from tinyagent import State, Flow, Node
except ImportError:
    from .core import State, Flow, Node


class TracingFlow(Flow):
    """Flow wrapper that automatically traces execution for debugging and GNN training."""
    
    def __init__(self, trace_id: str | None = None):
        """
        Initialize tracing flow.
        
        Args:
            trace_id: Custom trace identifier (default: auto-generated)
        """
        super().__init__()
        self.trace_id = trace_id or f"{time.time():.0f}-{id(self)}"
        self.trace: list[tuple[float, str, dict | None]] = []
    
    async def run(self, expr: str, state: State) -> bool:
        """Run flow with automatic tracing."""
        # Parse and validate expression
        expr_str = str(expr)
        if expr_str not in self._cache:
            tokens = self._RE.findall(expr_str)
            self._validate(tokens)
            self._cache[expr_str] = tokens
        
        # Run with tracing
        return await self._eval_traced(self._cache[expr_str], state)
    
    async def _eval_traced(self, tokens: list[str], s: State, start: int = 0, end: int | None = None) -> bool:
        """Evaluate with tracing - wraps parent _eval method."""
        if end is None: end = len(tokens)
        if start >= end: return False
        
        # Single node - trace it
        if end - start == 1:
            t = tokens[start]
            if t in Node._registry:
                node = Node._registry[t]
                return await self._execute_traced(node, s)
            return False
        
        # Find operator (same logic as parent)
        min_prec, op_idx, depth = 999, -1, 0
        for i in range(start, end):
            if tokens[i] == "(": depth += 1
            elif tokens[i] == ")": depth -= 1
            elif depth == 0 and (tokens[i] in self._P or tokens[i].startswith("<")):
                prec = self._P.get(tokens[i], 4) if not tokens[i].startswith("<") else 4
                if prec <= min_prec: min_prec, op_idx = prec, i
        
        if op_idx == -1: return await self._eval_traced(tokens, s, start + 1, end - 1)
        
        op = tokens[op_idx]
        
        # Loop operator
        if op.startswith("<") and op.endswith(">"):
            n, last_result = int(op[1:-1]), False
            for _ in range(n):
                left_result = await self._eval_traced(tokens, s, start, op_idx)
                right_result = await self._eval_traced(tokens, s, op_idx + 1, end)
                last_result = right_result
                if right_result: break
            return last_result
        
        # Parallel operator
        if op == "&":
            left_coro = self._eval_traced(tokens, s, start, op_idx)
            right_coro = self._eval_traced(tokens, s, op_idx + 1, end)
            left_result, right_result = await asyncio.gather(left_coro, right_coro)
            return left_result and right_result
        
        # Sequential operators
        left_result = await self._eval_traced(tokens, s, start, op_idx)
        
        if op == ">>": return await self._eval_traced(tokens, s, op_idx + 1, end)
        if op == "?": return await self._eval_traced(tokens, s, op_idx + 1, end) if left_result else False
        if op == "|": return await self._eval_traced(tokens, s, op_idx + 1, end) if not left_result else left_result
        return False
    
    async def _execute_traced(self, node: Node, state: State) -> bool:
        """Execute node and record trace."""
        start_time = time.time()
        
        for attempt in range(node._retries + 1):
            try:
                r = await (asyncio.wait_for(node._fn(state), node._timeout) if node._timeout else node._fn(state))
                duration = time.time() - start_time
                self.trace.append((time.time(), f"{node.name}:OK:{duration:.3f}s", None))
                return bool(r)
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                self.trace.append((time.time(), f"{node.name}:TIMEOUT:{duration:.3f}s", None))
            except Exception as e:
                duration = time.time() - start_time
                self.trace.append((time.time(), f"{node.name}:ERR({type(e).__name__}):{duration:.3f}s", None))
        
        return False
    
    def log(self, entry: str, metadata: dict[str, Any] | None = None) -> None:
        """Add custom trace entry."""
        self.trace.append((time.time(), entry, metadata))


class TraceExporter:
    """Export traces to various backends in OpenTelemetry-compatible format."""
    
    def __init__(self, filepath: str = "traces.jsonl", format: str = "jsonl"):
        """
        Initialize trace exporter.
        
        Args:
            filepath: Path to output file
            format: Export format - 'jsonl' (default) or 'otel' (OpenTelemetry JSON)
        """
        self.filepath = Path(filepath)
        self.format = format
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
    
    def export(self, flow: TracingFlow, clear: bool = True) -> None:
        """
        Export flow trace to file and optionally clear it.
        
        Args:
            flow: TracingFlow object with trace data
            clear: If True, clear flow.trace after export (default: True)
        """
        if self.format == "jsonl":
            self._export_jsonl(flow)
        elif self.format == "otel":
            self._export_otel(flow)
        else:
            raise ValueError(f"Unknown format: {self.format}")
        
        if clear:
            flow.trace.clear()
    
    def _export_jsonl(self, flow: TracingFlow) -> None:
        """Export as JSONL (one trace per line)."""
        trace_data = {
            "trace_id": flow.trace_id,
            "timestamp": time.time(),
            "events": [
                {
                    "ts": ts,
                    "event": event,
                    "metadata": metadata
                }
                for ts, event, metadata in flow.trace
            ]
        }
        
        with open(self.filepath, "a") as f:
            f.write(json.dumps(trace_data) + "\n")
    
    def _export_otel(self, flow: TracingFlow) -> None:
        """Export in OpenTelemetry JSON format."""
        spans = []
        for i, (ts, event, metadata) in enumerate(flow.trace):
            parts = event.split(":")
            name = parts[0]
            status = parts[1] if len(parts) > 1 else "UNKNOWN"
            duration_str = parts[2] if len(parts) > 2 else "0s"
            duration_ms = float(duration_str.rstrip("s")) * 1000
            
            span = {
                "traceId": flow.trace_id,
                "spanId": f"{i:016x}",
                "parentSpanId": f"{i-1:016x}" if i > 0 else None,
                "name": name,
                "kind": "INTERNAL",
                "startTimeUnixNano": int(ts * 1e9),
                "endTimeUnixNano": int((ts + duration_ms/1000) * 1e9),
                "attributes": metadata or {},
                "status": {
                    "code": "OK" if status == "OK" else "ERROR",
                    "message": status
                }
            }
            spans.append(span)
        
        otel_data = {
            "resourceSpans": [{
                "resource": {
                    "attributes": {
                        "service.name": "tinyagent",
                        "trace.id": flow.trace_id
                    }
                },
                "scopeSpans": [{
                    "scope": {"name": "tinyagent"},
                    "spans": spans
                }]
            }]
        }
        
        with open(self.filepath, "a") as f:
            f.write(json.dumps(otel_data) + "\n")


class TraceLoader:
    """Load and parse exported traces for analysis or GNN training."""
    
    @staticmethod
    def load_jsonl(filepath: str) -> list[dict[str, Any]]:
        """Load traces from JSONL file."""
        traces = []
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    traces.append(json.loads(line))
        return traces
    
    @staticmethod
    def to_graph(trace_data: dict) -> tuple[list[str], list[tuple[str, str]]]:
        """
        Convert trace to graph representation (nodes, edges).
        
        Returns:
            (nodes, edges) where nodes is list of event names,
            edges is list of (source, target) tuples
        """
        nodes = []
        edges = []
        
        for i, event in enumerate(trace_data["events"]):
            node_name = event["event"].split(":")[0]
            nodes.append(node_name)
            
            if i > 0:
                prev_node = nodes[i-1]
                edges.append((prev_node, node_name))
        
        return nodes, edges


# Convenience function
def save_trace(flow: TracingFlow, filepath: str = "traces.jsonl", clear: bool = True) -> None:
    """
    Convenience function to export trace to JSONL file.
    
    Args:
        flow: TracingFlow object with trace data
        filepath: Path to output file (default: traces.jsonl)
        clear: If True, clear flow.trace after export (default: True)
    
    Example:
        >>> from tinyagent import State
        >>> from tinyagent.telemetry import TracingFlow, save_trace
        >>> 
        >>> flow = TracingFlow(trace_id="run-001")
        >>> state = State()
        >>> await flow.run("A >> B >> C", state)
        >>> save_trace(flow)  # Appends to traces.jsonl, clears memory
    """
    exporter = TraceExporter(filepath, format="jsonl")
    exporter.export(flow, clear=clear)
