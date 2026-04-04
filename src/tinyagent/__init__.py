"""TinyAgent: Zero-dependency async-first agent orchestration framework.

A minimal framework for building AI agents and multi-agent orchestrations.
Built on graph theory with zero external dependencies.
"""

from .core import Node, State, Flow

__version__ = "0.2.0"
__all__ = ["Node", "State", "Flow"]
