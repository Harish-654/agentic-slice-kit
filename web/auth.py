"""Sign-up, sign-in and the guard that keeps every other route to its owner.

    POST /api/auth/signup   make an account and sign in
    POST /api/auth/login    sign in
    POST /api/auth/logout   sign out
    GET  /api/auth/me       who is signed in (401 if nobody)

A sign-in is a random token in an HttpOnly, SameSite=Lax cookie; the database keeps only its hash
(demo/tutor/accounts.py). SameSite=Lax plus JSON-only bodies is what keeps another site from acting as the
student, so there is no separate CSRF token.

`REQUIRED` exists so tests of the tutor itself can run without signing in. It is True in the running app.
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from demo.tutor import accounts
from slice.store import Store

REQUIRED = True
COOKIE = "tutor_session"


class Limiter:
    """Slows down guessing a password. After `tries` wrong passwords for one name from one address within
    `window` seconds, sign-in is refused for `lock` seconds. In memory, so it resets when the server
    restarts and does not span several servers: enough to stop a script guessing, not a defence in depth."""

    def __init__(self, tries: int = 5, window: float = 900.0, lock: float = 60.0, clock=time.monotonic):
        self.tries, self.window, self.lock, self.clock = tries, window, lock, clock
        self._fails: dict[str, list[float]] = {}
        self._until: dict[str, float] = {}
        self._mutex = threading.Lock()

    def wait(self, key: str) -> int:
        """Seconds still to wait before this key may try again (0 if it may)."""
        with self._mutex:
            return max(0, int(self._until.get(key, 0) - self.clock() + 0.999))

    def failed(self, key: str) -> None:
        now = self.clock()
        with self._mutex:
            recent = [t for t in self._fails.get(key, []) if now - t < self.window] + [now]
            self._fails[key] = recent
            if len(recent) >= self.tries:
                self._until[key] = now + self.lock
                self._fails[key] = []

    def ok(self, key: str) -> None:
        with self._mutex:
            self._fails.pop(key, None)
            self._until.pop(key, None)


limiter = Limiter()


def _who(request: Request, store: Store) -> str | None:
    return accounts.who(store, request.cookies.get(COOKIE))


def guard(get_store):
    """The dependency every protected route hangs on. It returns the signed-in name, raises 401 when nobody
    is signed in, and returns None when login is switched off (tests only)."""

    def current_student(request: Request, store: Store = Depends(get_store)) -> str | None:
        if not REQUIRED:
            return None
        name = _who(request, store)
        if name is None:
            raise HTTPException(401, "Please sign in.")
        return name

    return current_student


class Credentials(BaseModel):
    name: str = Field(max_length=200)
    password: str = Field(max_length=accounts.MAX_PASSWORD + 50)


def _sign_in(request: Request, response: Response, store: Store, name: str) -> None:
    response.set_cookie(COOKIE, accounts.open_session(store, name), max_age=accounts.SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", secure=request.url.scheme == "https", path="/")


def build_router(get_store) -> APIRouter:
    router = APIRouter(prefix="/api/auth")

    @router.post("/signup")
    def signup(req: Credentials, request: Request, response: Response, store: Store = Depends(get_store)):
        try:
            name = accounts.create(store, req.name, req.password)
        except accounts.AccountError as e:
            raise HTTPException(422, str(e))
        _sign_in(request, response, store, name)
        return {"student": name}

    @router.post("/login")
    def login(req: Credentials, request: Request, response: Response, store: Store = Depends(get_store)):
        key = f"{accounts.name_key(' '.join(req.name.split()))}|{request.client.host if request.client else ''}"
        wait = limiter.wait(key)
        if wait:
            raise HTTPException(429, f"Too many wrong passwords. Try again in {wait} seconds.",
                                headers={"Retry-After": str(wait)})
        name = accounts.verify(store, req.name, req.password)
        if name is None:
            limiter.failed(key)
            raise HTTPException(401, "That name and password do not match.")
        limiter.ok(key)
        _sign_in(request, response, store, name)
        return {"student": name}

    @router.post("/logout")
    def logout(request: Request, response: Response, store: Store = Depends(get_store)):
        accounts.close_session(store, request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @router.get("/me")
    def me(request: Request, store: Store = Depends(get_store)):
        if not REQUIRED:
            return {"student": None, "login_required": False}
        name = _who(request, store)
        if name is None:
            raise HTTPException(401, "Please sign in.")
        return {"student": name, "login_required": True}

    return router
