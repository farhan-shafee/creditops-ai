"""Offline tests must not consume locally configured provider credentials."""

import httpx
import httpx2
import pytest
from creditops.settings import Settings


@pytest.fixture(autouse=True)
def offline_provider_boundary(monkeypatch):
    # Tests configure synthetic keys explicitly. Never read the owner's .env.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    def check(request):
        if request.url.host not in {"127.0.0.1", "localhost", "::1"}:
            raise AssertionError("Offline tests forbid external HTTP transport")

    def protect(library):
        sync_request = library.HTTPTransport.handle_request
        async_request = library.AsyncHTTPTransport.handle_async_request

        def guarded_sync(self, request):
            check(request)
            return sync_request(self, request)

        async def guarded_async(self, request):
            check(request)
            return await async_request(self, request)

        monkeypatch.setattr(library.HTTPTransport, "handle_request", guarded_sync)
        monkeypatch.setattr(library.AsyncHTTPTransport, "handle_async_request", guarded_async)

    # The installed Anthropic SDK uses httpx2; OpenAI uses httpx.
    protect(httpx)
    protect(httpx2)
