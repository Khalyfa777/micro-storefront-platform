from collections.abc import Awaitable, Callable

from starlette.responses import JSONResponse
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int,
    ) -> None:
        self.app = app
        self.max_body_bytes = (
            max_body_bytes
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(
                scope,
                receive,
                send,
            )
            return

        for key, value in scope.get(
            "headers",
            [],
        ):
            if key.lower() != b"content-length":
                continue

            try:
                content_length = int(
                    value.decode("ascii")
                )
            except (
                UnicodeDecodeError,
                ValueError,
            ):
                break

            if (
                content_length
                > self.max_body_bytes
            ):
                await self._send_too_large(
                    scope,
                    receive,
                    send,
                )
                return

            break

        received_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes

            message = await receive()

            if (
                message["type"]
                == "http.request"
            ):
                received_bytes += len(
                    message.get(
                        "body",
                        b"",
                    )
                )

                if (
                    received_bytes
                    > self.max_body_bytes
                ):
                    raise (
                        _RequestBodyTooLarge
                    )

            return message

        async def tracked_send(
            message: Message,
        ) -> None:
            nonlocal response_started

            if (
                message["type"]
                == "http.response.start"
            ):
                response_started = True

            await send(message)

        try:
            await self.app(
                scope,
                limited_receive,
                tracked_send,
            )
        except _RequestBodyTooLarge:
            if response_started:
                raise

            await self._send_too_large(
                scope,
                receive,
                send,
            )

    @staticmethod
    async def _send_too_large(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": (
                    "Request body is too large."
                ),
            },
        )

        await response(
            scope,
            receive,
            send,
        )
