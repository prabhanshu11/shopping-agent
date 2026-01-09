"""Claude Agent SDK integration for adaptive shopping navigation.

This module provides AI-powered navigation that can:
- Self-heal when encountering unexpected UI states
- Adaptively try alternative approaches
- Log learnings for continuous improvement
"""

from app.agent.shopping_agent import ShoppingAgent, ShoppingAgentConfig

__all__ = [
    "ShoppingAgent",
    "ShoppingAgentConfig",
]
