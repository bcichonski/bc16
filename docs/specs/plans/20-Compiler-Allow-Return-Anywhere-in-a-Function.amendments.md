# Amendments — 20 Compiler: allow return anywhere in a function

## A1 — 2026-11-23 — requested by owner

contradiction — replace the compile-time guard on `return` inside an inner scope with run-time unwinding of those scopes, so `return` works from anywhere also once block scopes (#24) exist — owner comment after PR #169: "return inside an inner variable scope is not possible where you claimed you can return out of everywhere"
