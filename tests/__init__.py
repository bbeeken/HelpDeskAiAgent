import os

# Ensure Pydantic forward references work under Python 3.12
os.environ.setdefault("PYDANTIC_DISABLE_STD_TYPES_SHIM", "1")

import typing
import inspect

sig = inspect.signature(typing.ForwardRef._evaluate)
if 'recursive_guard' in sig.parameters:
    original = typing.ForwardRef._evaluate

    def _evaluate(self, globalns, localns, type_params=None, *, recursive_guard=frozenset()):
        return original(self, globalns, localns, type_params, recursive_guard=recursive_guard)

    typing.ForwardRef._evaluate = _evaluate

import httpx
if 'app' not in inspect.signature(httpx.Client.__init__).parameters:
    original_client_init = httpx.Client.__init__

    def client_init(self, *args, **kwargs):
        kwargs.pop('app', None)
        return original_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = client_init
