# sentinel/safety/__init__.py
# Makes 'sentinel.safety' importable.
# Contains all deterministic safety controls: red-flag callback, HITL gate,
# circuit breaker. These are the "hard chokepoints" that operate outside the
# model's judgment and cannot be reasoned away.
