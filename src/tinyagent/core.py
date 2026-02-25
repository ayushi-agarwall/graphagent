import asyncio, inspect, re
class State:
    def __init__(self, data=None, async_safe: bool = False):
        self._data, self._lock = data or {}, (asyncio.Lock() if async_safe else None)
    async def _do(self, fn):
        if self._lock:
            async with self._lock: return fn()
        return fn()
    async def get(self, key: str, default=None):
        return await self._do(lambda: self._data.get(key, default))
    async def set(self, key: str, value) -> None:
        await self._do(lambda: self._data.__setitem__(key, value))
    async def update(self, key: str, fn) -> None:
        await self._do(lambda: self._data.__setitem__(key, fn(self._data.get(key))))
class Node:
    _registry: dict[str, "Node"] = {}
    def __init__(self, name: str, fn, timeout=None, retries: int = 0, raise_errors: bool = False):
        call = getattr(fn, "__call__", None)
        if not (inspect.iscoroutinefunction(fn) or (call and inspect.iscoroutinefunction(call))): raise TypeError(f"fn for node '{name}' must be an async callable")
        if timeout is not None and timeout <= 0: raise ValueError(f"timeout must be > 0, got {timeout}")
        if retries < 0: raise ValueError(f"retries must be >= 0, got {retries}")
        self.name, self._fn, self._timeout, self._retries, self._raise = name, fn, timeout, retries, raise_errors; Node._registry[name] = self
    async def execute(self, state) -> bool:
        for _ in range(self._retries + 1):
            try: return bool(await (asyncio.wait_for(self._fn(state), self._timeout) if self._timeout else self._fn(state)))
            except asyncio.TimeoutError: pass
            except KeyboardInterrupt: raise
            except Exception:
                if self._raise: raise
        return False
class Flow:
    _P, _RE = {">>": 1, "|": 2, "?": 2, "&": 3, "<": 4}, re.compile(r"(\(|\)|>>|&|\?|\||<\d+>|[^\s()&|?<>]+)")
    def __init__(self): self._cache: dict[str, list[str]] = {}
    async def run(self, expr: str, state) -> bool:
        if not isinstance(expr, str): raise TypeError(f"expr must be str, got {type(expr).__name__}")
        c = re.sub(r"\s+", "", expr or "")
        if not c: raise ValueError("expr cannot be empty")
        if c not in self._cache:
            t = self._RE.findall(c)
            if "".join(t) != c: raise ValueError(f"Invalid syntax in expression: {expr}")
            self._validate(t); self._cache[c] = t
        return (await self._eval(self._cache[c], state))[0]
    def _validate(self, t: list[str]) -> None:
        exp, d = True, 0
        for x in t:
            op = x in self._P or (x.startswith("<") and x.endswith(">"))
            if exp:
                if x == "(": d += 1; continue
                if x == ")" or op: raise ValueError(f"Expected node or '(', got '{x}'")
                if x not in Node._registry: raise ValueError(f"Node '{x}' not found in registry. Available: {list(Node._registry.keys())}")
                exp = False; continue
            if x == ")":
                d -= 1
                if d < 0: raise ValueError("Unmatched closing parenthesis")
                continue
            if op:
                if x.startswith("<") and int(x[1:-1]) <= 0: raise ValueError(f"Loop count must be > 0, got {int(x[1:-1])}")
                exp = True; continue
            raise ValueError(f"Expected operator or ')', got '{x}'")
        if d != 0: raise ValueError("Unmatched opening parenthesis")
        if exp: raise ValueError("Expression cannot end with an operator")
    @staticmethod
    def _m(a, b): o = list(a); [o.append(n) for n in b if n not in o]; return tuple(o)
    async def _eval(self, t: list[str], s, i: int = 0, j=None, p=()):
        j = len(t) if j is None else j
        if i >= j: return False, ()
        if j - i == 1:
            n = t[i]
            if n in Node._registry and n in p: raise RuntimeError(f"Cycle detected: {' >> '.join(p + (n,))}")
            if n in Node._registry: return await Node._registry[n].execute(s), (n,)
            return False, ()
        m, k, d = 999, -1, 0
        for x in range(i, j):
            if t[x] == "(": d += 1
            elif t[x] == ")": d -= 1
            elif d == 0 and (t[x] in self._P or t[x].startswith("<")):
                pr = 4 if t[x].startswith("<") else self._P[t[x]]
                if pr <= m: m, k = pr, x
        if k == -1: return await self._eval(t, s, i + 1, j - 1, p)
        op = t[k]
        if op.startswith("<"):
            n, last, seen = int(op[1:-1]), False, ()
            for _ in range(n):
                _, ln = await self._eval(t, s, i, k, p); r, rn = await self._eval(t, s, k + 1, j, self._m(p, ln))
                last, seen = r, self._m(seen, self._m(ln, rn))
                if r: break
            return last, seen
        if op == "&":
            (lr, ln), (rr, rn) = await asyncio.gather(self._eval(t, s, i, k, p), self._eval(t, s, k + 1, j, p))
            return lr and rr, self._m(ln, rn)
        lr, ln = await self._eval(t, s, i, k, p)
        if op == ">>":
            if not lr: return False, ln
            rr, rn = await self._eval(t, s, k + 1, j, self._m(p, ln)); return rr, self._m(ln, rn)
        if op == "?":
            if not lr: return False, ln
            rr, rn = await self._eval(t, s, k + 1, j, self._m(p, ln)); return rr, self._m(ln, rn)
        if op == "|":
            if lr: return lr, ln
            rr, rn = await self._eval(t, s, k + 1, j, self._m(p, ln)); return rr, self._m(ln, rn)
        return False, ln
