"""
Adapter factory (Round 1 placeholder).

后续轮次会在此扩展：
- openai_adapter
- generic_http_adapter
- local_stub_adapter
"""
from .echo_adapter import EchoAdapter

def make_adapter(name: str, config: dict):
    """Return an adapter instance based on its name.

    Parameters
    ----------
    name:
        Adapter identifier from configuration. Round 1 ignores this value and
        always returns :class:`EchoAdapter`.
    config:
        Adapter-specific configuration mapping. The placeholder adapter simply
        stores it for later use.
    """
    # Round 1: 占位返回 EchoAdapter；下一轮才接主流程
    return EchoAdapter(config or {})
