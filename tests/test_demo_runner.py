import pytest
from test_aiops import SimpleAIOpsDemo

def test_aiops_demo_runs_without_crashing():
    """Basic smoke test to ensure demo runs end-to-end"""
    demo = SimpleAIOpsDemo()
    try:
        demo.run_complete_demo()
    except Exception as e:
        pytest.fail(f"Demo raised an exception: {e}")
