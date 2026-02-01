"""TinyAgent Telemetry: OpenTelemetry-compatible trace export and persistence.

This module provides trace collection and export functionality compatible with
OpenTelemetry standards. Install separately: pip install tinyagent[telemetry]
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

try:
    from tinyagent import State
except ImportError:
    from .core import State


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
    
    def export(self, state: State, clear: bool = True) -> None:
        """
        Export state trace to file and optionally clear it.
        
        Args:
            state: State object with trace data
            clear: If True, clear state.trace after export (default: True)
        """
        if self.format == "jsonl":
            self._export_jsonl(state)
        elif self.format == "otel":
            self._export_otel(state)
        else:
            raise ValueError(f"Unknown format: {self.format}")
        
        if clear:
            state.trace.clear()
    
    def _export_jsonl(self, state: State) -> None:
        """Export as JSONL (one trace per line)."""
        trace_data = {
            "trace_id": state.trace_id,
            "timestamp": time.time(),
            "events": [
                {
                    "ts": ts,
                    "event": event,
                    "metadata": metadata
                }
                for ts, event, metadata in state.trace
            ]
        }
        
        with open(self.filepath, "a") as f:
            f.write(json.dumps(trace_data) + "\n")
    
    def _export_otel(self, state: State) -> None:
        """Export in OpenTelemetry JSON format."""
        # Convert to OpenTelemetry span format
        spans = []
        for i, (ts, event, metadata) in enumerate(state.trace):
            # Parse event: "node_name:STATUS:duration"
            parts = event.split(":")
            name = parts[0]
            status = parts[1] if len(parts) > 1 else "UNKNOWN"
            duration_str = parts[2] if len(parts) > 2 else "0s"
            duration_ms = float(duration_str.rstrip("s")) * 1000
            
            span = {
                "traceId": state.trace_id,
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
                        "trace.id": state.trace_id
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
def save_trace(state: State, filepath: str = "traces.jsonl", clear: bool = True) -> None:
    """
    Convenience function to export trace to JSONL file.
    
    Args:
        state: State object with trace data
        filepath: Path to output file (default: traces.jsonl)
        clear: If True, clear state.trace after export (default: True)
    
    Example:
        >>> from tinyagent import State, Flow
        >>> from tinyagent.telemetry import save_trace
        >>> 
        >>> state = State(trace_id="run-001")
        >>> await flow.run("A >> B >> C", state)
        >>> save_trace(state)  # Appends to traces.jsonl, clears memory
    """
    exporter = TraceExporter(filepath, format="jsonl")
    exporter.export(state, clear=clear)
