"""
Tests for tinyagent core – covers all implemented functionality.
Run with: pytest tests/
"""
import asyncio
import pytest
from tinyagent.core import State, Node, Flow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_registry():
    """Clear global Node registry between tests."""
    Node._registry.clear()


# ---------------------------------------------------------------------------
# State tests
# ---------------------------------------------------------------------------

class TestState:
    def setup_method(self):
        fresh_registry()

    def test_get_default(self):
        state = State()
        assert asyncio.run(state.get("missing")) is None

    def test_get_custom_default(self):
        state = State()
        assert asyncio.run(state.get("missing", 42)) == 42

    def test_set_and_get(self):
        async def _run():
            state = State()
            await state.set("key", "value")
            return await state.get("key")
        assert asyncio.run(_run()) == "value"

    def test_initial_data(self):
        state = State(data={"a": 1, "b": 2})
        assert asyncio.run(state.get("a")) == 1
        assert asyncio.run(state.get("b")) == 2

    def test_update(self):
        async def _run():
            state = State(data={"counter": 0})
            await state.update("counter", lambda v: v + 1)
            await state.update("counter", lambda v: v + 1)
            return await state.get("counter")
        assert asyncio.run(_run()) == 2

    def test_update_missing_key(self):
        async def _run():
            state = State()
            await state.update("x", lambda v: (v or 0) + 5)
            return await state.get("x")
        assert asyncio.run(_run()) == 5

    def test_async_safe_mode(self):
        async def _run():
            state = State(async_safe=True)
            await state.set("n", 0)
            async def inc():
                await state.update("n", lambda v: v + 1)
            await asyncio.gather(*[inc() for _ in range(50)])
            return await state.get("n")
        assert asyncio.run(_run()) == 50

    def test_overwrite_value(self):
        async def _run():
            state = State()
            await state.set("k", 1)
            await state.set("k", 99)
            return await state.get("k")
        assert asyncio.run(_run()) == 99


# ---------------------------------------------------------------------------
# Node tests
# ---------------------------------------------------------------------------

class TestNode:
    def setup_method(self):
        fresh_registry()

    def test_requires_async_fn(self):
        def sync_fn(state): return True
        with pytest.raises(TypeError, match="async callable"):
            Node("n", sync_fn)

    def test_invalid_timeout_zero(self):
        async def fn(state): return True
        with pytest.raises(ValueError, match="timeout must be > 0"):
            Node("n", fn, timeout=0)

    def test_invalid_timeout_negative(self):
        async def fn(state): return True
        with pytest.raises(ValueError, match="timeout must be > 0"):
            Node("n", fn, timeout=-1)

    def test_invalid_retries_negative(self):
        async def fn(state): return True
        with pytest.raises(ValueError, match="retries must be >= 0"):
            Node("n", fn, retries=-1)

    def test_registered_in_registry(self):
        async def fn(state): return True
        Node("my_node", fn)
        assert "my_node" in Node._registry

    def test_execute_returns_true(self):
        async def _run():
            async def fn(state): return True
            n = Node("n", fn)
            return await n.execute(State())
        assert asyncio.run(_run()) is True

    def test_execute_returns_false(self):
        async def _run():
            async def fn(state): return False
            n = Node("n", fn)
            return await n.execute(State())
        assert asyncio.run(_run()) is False

    def test_execute_bool_casts_truthy(self):
        async def _run():
            async def fn(state): return "non-empty"
            n = Node("n", fn)
            return await n.execute(State())
        assert asyncio.run(_run()) is True

    def test_execute_bool_casts_falsy(self):
        async def _run():
            async def fn(state): return None
            n = Node("n", fn)
            return await n.execute(State())
        assert asyncio.run(_run()) is False

    def test_timeout_triggers(self):
        async def _run():
            async def slow(state):
                await asyncio.sleep(10)
                return True
            n = Node("n", slow, timeout=0.05)
            return await n.execute(State())
        assert asyncio.run(_run()) is False

    def test_timeout_with_retries(self):
        async def _run():
            calls = []
            async def slow(state):
                calls.append(1)
                await asyncio.sleep(10)
                return True
            n = Node("n", slow, timeout=0.05, retries=2)
            result = await n.execute(State())
            return result, len(calls)
        result, call_count = asyncio.run(_run())
        assert result is False
        assert call_count == 3   # initial + 2 retries

    def test_retry_on_exception(self):
        async def _run():
            attempts = []
            async def flaky(state):
                attempts.append(1)
                if len(attempts) < 3:
                    raise RuntimeError("transient")
                return True
            n = Node("n", flaky, retries=3)
            result = await n.execute(State())
            return result, len(attempts)
        result, attempts = asyncio.run(_run())
        assert result is True
        assert attempts == 3

    def test_exception_exhausts_retries(self):
        async def _run():
            async def always_fails(state): raise RuntimeError("boom")
            n = Node("n", always_fails, retries=2)
            return await n.execute(State())
        assert asyncio.run(_run()) is False

    def test_raise_errors(self):
        async def _run():
            async def fn(state): raise ValueError("oops")
            n = Node("n", fn, raise_errors=True)
            return await n.execute(State())
        with pytest.raises(ValueError, match="oops"):
            asyncio.run(_run())

    def test_retry_on_false(self):
        async def _run():
            attempts = []
            async def poll(state):
                attempts.append(1)
                return len(attempts) >= 3
            n = Node("n", poll, retries=5, retry_on_false=True)
            result = await n.execute(State())
            return result, len(attempts)
        result, attempts = asyncio.run(_run())
        assert result is True
        assert attempts == 3

    def test_retry_on_false_default_stops_immediately(self):
        """Without retry_on_false, False return stops the loop."""
        async def _run():
            attempts = []
            async def fn(state):
                attempts.append(1)
                return False
            n = Node("n", fn, retries=5)
            result = await n.execute(State())
            return result, len(attempts)
        result, attempts = asyncio.run(_run())
        assert result is False
        assert attempts == 1


# ---------------------------------------------------------------------------
# Flow tests – sequential
# ---------------------------------------------------------------------------

class TestFlowSequential:
    def setup_method(self):
        fresh_registry()

    def test_simple_sequential(self):
        async def _run():
            async def a(state): await state.set("a", 1); return True
            async def b(state): await state.set("b", 2); return True
            Node("a", a); Node("b", b)
            state = State()
            result = await Flow().run("a >> b", state)
            return result, await state.get("a"), await state.get("b")
        result, a, b = asyncio.run(_run())
        assert result is True and a == 1 and b == 2

    def test_sequential_always_runs_both(self):
        """>> pipelines both nodes unconditionally; returns the last node's result.
        Use '?' for conditional short-circuit on failure."""
        async def _run():
            async def a(state): return False   # a fails
            async def b(state): await state.set("b_ran", True); return True
            Node("a", a); Node("b", b)
            state = State()
            result = await Flow().run("a >> b", state)
            return result, await state.get("b_ran")
        result, b_ran = asyncio.run(_run())
        assert result is True      # returns b's result
        assert b_ran is True       # b ran even though a returned False

    def test_multi_step_sequential(self):
        async def _run():
            order = []
            async def n1(state): order.append(1); return True
            async def n2(state): order.append(2); return True
            async def n3(state): order.append(3); return True
            Node("n1", n1); Node("n2", n2); Node("n3", n3)
            await Flow().run("n1 >> n2 >> n3", State())
            return order
        assert asyncio.run(_run()) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Flow tests – parallel
# ---------------------------------------------------------------------------

class TestFlowParallel:
    def setup_method(self):
        fresh_registry()

    def test_parallel_both_true(self):
        async def _run():
            async def a(state): await state.set("a", True); return True
            async def b(state): await state.set("b", True); return True
            Node("a", a); Node("b", b)
            state = State()
            result = await Flow().run("a & b", state)
            return result, await state.get("a"), await state.get("b")
        result, a, b = asyncio.run(_run())
        assert result is True and a is True and b is True

    def test_parallel_one_false_returns_false(self):
        async def _run():
            async def a(state): return True
            async def b(state): return False
            Node("a", a); Node("b", b)
            return await Flow().run("a & b", State())
        assert asyncio.run(_run()) is False

    def test_parallel_is_concurrent(self):
        async def _run():
            async def slow(state): await asyncio.sleep(0.2); return True
            async def also_slow(state): await asyncio.sleep(0.2); return True
            Node("slow1", slow); Node("slow2", also_slow)
            import time
            start = time.time()
            await Flow().run("slow1 & slow2", State())
            return time.time() - start
        elapsed = asyncio.run(_run())
        assert elapsed < 0.35   # parallel ~0.2s, not sequential 0.4s


# ---------------------------------------------------------------------------
# Flow tests – conditional operators
# ---------------------------------------------------------------------------

class TestFlowConditional:
    def setup_method(self):
        fresh_registry()

    def test_conditional_success_runs_next(self):
        async def _run():
            async def ok(state): return True
            async def next_n(state): await state.set("ran", True); return True
            Node("ok", ok); Node("next_n", next_n)
            state = State()
            result = await Flow().run("ok ? next_n", state)
            return result, await state.get("ran")
        result, ran = asyncio.run(_run())
        assert result is True and ran is True

    def test_conditional_success_skips_on_false(self):
        async def _run():
            async def fail(state): return False
            async def skip(state): await state.set("ran", True); return True
            Node("fail", fail); Node("skip", skip)
            state = State()
            result = await Flow().run("fail ? skip", state)
            return result, await state.get("ran")
        result, ran = asyncio.run(_run())
        assert result is False and ran is None

    def test_conditional_failure_runs_fallback(self):
        async def _run():
            async def main_n(state): return False
            async def fallback(state): await state.set("fb", True); return True
            Node("main_n", main_n); Node("fallback", fallback)
            state = State()
            result = await Flow().run("main_n | fallback", state)
            return result, await state.get("fb")
        result, fb = asyncio.run(_run())
        assert result is True and fb is True

    def test_conditional_failure_skips_fallback_on_success(self):
        async def _run():
            async def main_n(state): return True
            async def fallback(state): await state.set("fb", True); return True
            Node("main_n", main_n); Node("fallback", fallback)
            state = State()
            result = await Flow().run("main_n | fallback", state)
            return result, await state.get("fb")
        result, fb = asyncio.run(_run())
        assert result is True and fb is None

    def test_combined_conditional(self):
        """validate ? process | handle_error"""
        async def _run():
            async def validate(state): return True
            async def process(state): await state.set("processed", True); return True
            async def handle_error(state): await state.set("error", True); return True
            Node("validate", validate); Node("process", process); Node("handle_error", handle_error)
            state = State()
            result = await Flow().run("validate ? process | handle_error", state)
            return result, await state.get("processed"), await state.get("error")
        result, processed, err = asyncio.run(_run())
        assert result is True and processed is True and err is None


# ---------------------------------------------------------------------------
# Flow tests – loop operator
# ---------------------------------------------------------------------------

class TestFlowLoop:
    def setup_method(self):
        fresh_registry()

    def test_loop_exits_on_success(self):
        async def _run():
            attempts = []
            async def gen(state): return True
            async def rev(state):
                attempts.append(1)
                return len(attempts) >= 2
            Node("gen", gen); Node("rev", rev)
            result = await Flow().run("gen <5> rev", State())
            return result, len(attempts)
        result, attempts = asyncio.run(_run())
        assert result is True and attempts == 2

    def test_loop_exhausts_max(self):
        async def _run():
            runs = []
            async def gen(state): return True
            async def rev(state): runs.append(1); return False
            Node("gen", gen); Node("rev", rev)
            result = await Flow().run("gen <3> rev", State())
            return result, len(runs)
        result, runs = asyncio.run(_run())
        assert result is False and runs == 3

    def test_loop_count_must_be_positive(self):
        async def fn(state): return True
        Node("x", fn)
        with pytest.raises(ValueError, match="Loop count"):
            asyncio.run(Flow().run("x <0> x", State()))


# ---------------------------------------------------------------------------
# Flow tests – grouping and precedence
# ---------------------------------------------------------------------------

class TestFlowGrouping:
    def setup_method(self):
        fresh_registry()

    def test_grouping_changes_precedence(self):
        async def _run():
            ran = []
            async def a(state): ran.append("a"); return True
            async def b(state): ran.append("b"); return False
            async def c(state): ran.append("c"); return True
            Node("a", a); Node("b", b); Node("c", c)
            # a >> (b | c) — b fails, so c runs
            state = State()
            result = await Flow().run("a >> (b | c)", state)
            return result, ran
        result, ran = asyncio.run(_run())
        assert result is True and ran == ["a", "b", "c"]

    def test_nested_grouping(self):
        async def _run():
            ran = []
            async def a(state): ran.append("a"); return True
            async def b(state): ran.append("b"); return True
            async def c(state): ran.append("c"); return True
            Node("a", a); Node("b", b); Node("c", c)
            await Flow().run("(a >> b) >> c", State())
            return ran
        assert asyncio.run(_run()) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Flow tests – expression caching
# ---------------------------------------------------------------------------

class TestFlowCaching:
    def setup_method(self):
        fresh_registry()

    def test_expression_is_cached(self):
        async def _run():
            async def a(state): return True
            Node("a", a)
            flow = Flow()
            await flow.run("a", State())
            await flow.run("a", State())
            return "a" in flow._cache
        assert asyncio.run(_run()) is True


# ---------------------------------------------------------------------------
# Flow tests – error handling
# ---------------------------------------------------------------------------

class TestFlowErrors:
    def setup_method(self):
        fresh_registry()

    def test_missing_node(self):
        async def fn(state): return True
        Node("real", fn)
        with pytest.raises(ValueError, match="not found in registry"):
            asyncio.run(Flow().run("nonexistent", State()))

    def test_unmatched_open_paren(self):
        async def fn(state): return True
        Node("n", fn)
        with pytest.raises(ValueError, match="parenthesis"):
            asyncio.run(Flow().run("((n", State()))

    def test_unmatched_close_paren(self):
        async def fn(state): return True
        Node("n", fn)
        with pytest.raises(ValueError, match="parenthesis"):
            asyncio.run(Flow().run("n))", State()))

    def test_empty_expression(self):
        with pytest.raises(ValueError, match="empty"):
            asyncio.run(Flow().run("", State()))

    def test_non_string_expr(self):
        with pytest.raises(TypeError, match="expr must be str"):
            asyncio.run(Flow().run(42, State()))

    def test_cycle_detection(self):
        async def _run():
            async def a(state): return True
            async def b(state): return True
            Node("a", a); Node("b", b)
            # Not a real cycle (DSL is a DAG), but re-use of same node in sequence
            # Cycle detection fires when a node appears in its own ancestor path
            flow = Flow()
            # a >> a is a direct self-cycle
            try:
                await flow.run("a >> a", State())
                return "no_error"
            except RuntimeError as e:
                return str(e)
        result = asyncio.run(_run())
        assert "Cycle detected" in result


# ---------------------------------------------------------------------------
# Integration – realistic pipeline
# ---------------------------------------------------------------------------

class TestIntegration:
    def setup_method(self):
        fresh_registry()

    def test_rag_pipeline(self):
        """embed >> retrieve >> rerank >> generate"""
        async def _run():
            async def embed(state): await state.set("query_vec", [0.1, 0.2]); return True
            async def retrieve(state): await state.set("docs", ["doc1", "doc2"]); return True
            async def rerank(state): await state.set("top_doc", "doc1"); return True
            async def generate(state): await state.set("answer", "42"); return True
            Node("embed", embed); Node("retrieve", retrieve)
            Node("rerank", rerank); Node("generate", generate)
            state = State()
            result = await Flow().run("embed >> retrieve >> rerank >> generate", state)
            return result, await state.get("answer")
        result, answer = asyncio.run(_run())
        assert result is True and answer == "42"

    def test_fan_out_fan_in(self):
        """(a & b & c) >> combine"""
        async def _run():
            async def a(state): await state.set("a", 1); return True
            async def b(state): await state.set("b", 2); return True
            async def c(state): await state.set("c", 3); return True
            async def combine(state):
                vals = [await state.get("a"), await state.get("b"), await state.get("c")]
                await state.set("total", sum(vals))
                return True
            Node("a", a); Node("b", b); Node("c", c); Node("combine", combine)
            state = State()
            result = await Flow().run("(a & b & c) >> combine", state)
            return result, await state.get("total")
        result, total = asyncio.run(_run())
        assert result is True and total == 6

    def test_self_correction_loop(self):
        """generator <N> validator"""
        async def _run():
            gen_calls, val_calls = [], []
            async def generator(state):
                gen_calls.append(1)
                await state.set("draft", len(gen_calls))
                return True
            async def validator(state):
                val_calls.append(1)
                return len(val_calls) >= 2   # passes on second validation
            Node("generator", generator); Node("validator", validator)
            state = State()
            result = await Flow().run("generator <5> validator", state)
            return result, len(gen_calls), len(val_calls), await state.get("draft")
        result, gens, vals, draft = asyncio.run(_run())
        assert result is True and gens == 2 and vals == 2 and draft == 2
