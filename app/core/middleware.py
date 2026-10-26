import gzip
import zlib
from starlette.types import ASGIApp, Receive, Scope, Send


class GzipDecompressionMiddleware:
    """
    ASGI middleware that decompresses incoming gzip/deflate request bodies.
    Allows clients to send large payloads with 'Content-Encoding: gzip',
    reducing payload size by up to 90% and passing through WAF filters safely.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            encoding = headers.get(b"content-encoding", b"").decode("latin-1").lower()
            if "gzip" in encoding or "deflate" in encoding:
                body = bytearray()
                while True:
                    message = await receive()
                    body.extend(message.get("body", b""))
                    if not message.get("more_body", False):
                        break

                try:
                    if "gzip" in encoding:
                        decompressed = gzip.decompress(bytes(body))
                    else:
                        decompressed = zlib.decompress(bytes(body))
                except Exception:
                    decompressed = bytes(body)

                new_headers = [
                    (k, v) for k, v in scope["headers"]
                    if k.lower() not in (b"content-encoding", b"content-length")
                ]
                new_headers.append((b"content-length", str(len(decompressed)).encode("latin-1")))
                scope["headers"] = new_headers

                has_sent = False

                async def custom_receive():
                    nonlocal has_sent
                    if not has_sent:
                        has_sent = True
                        return {"type": "http.request", "body": decompressed, "more_body": False}
                    return {"type": "http.request", "body": b"", "more_body": False}

                await self.app(scope, custom_receive, send)
                return

        await self.app(scope, receive, send)
