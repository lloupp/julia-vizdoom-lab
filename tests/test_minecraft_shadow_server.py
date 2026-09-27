import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from minecraft_shadow import ShadowDecision
from minecraft_shadow_server import Handler


class StableShadow:
    def invariance_check(self, state, available):
        decision = ShadowDecision("gather", 0.9, {"gather": 0.9}, 1.0, True)
        return {"stable": True, "forward": decision, "reverse": decision, "actions": tuple(available)}


class UnstableShadow:
    def invariance_check(self, state, available):
        forward = ShadowDecision("gather", 0.99, {"gather": 0.99}, 1.0, True)
        reverse = ShadowDecision("wait", 0.98, {"wait": 0.98}, 1.0, True)
        return {"stable": False, "forward": forward, "reverse": reverse, "actions": tuple(available)}


def call(shadow):
    Handler.shadow = shadow
    Handler.threshold = 0.75
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps({"state": {"health": 20}, "available_actions": ["gather", "wait"]}).encode()
        request = Request(
            f"http://127.0.0.1:{server.server_port}/v1/minecraft/decision",
            data=body,
            headers={"content-type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            return json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()


def test_shadow_server_never_grants_execution_trust():
    result = call(StableShadow())
    assert result["eligible"] is True
    assert result["trusted"] is False
    assert result["shadow"] is True


def test_shadow_server_flags_option_order_instability():
    result = call(UnstableShadow())
    assert result["stable"] is False
    assert result["eligible"] is False
    assert result["trusted"] is False
