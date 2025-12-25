from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Mock MCP", version="1.0.0")


@app.get("/openapi.json")
async def openapi() -> dict:
    return app.openapi()


@app.post("/echo", operation_id="echoMessage")
async def echo_message(payload: dict) -> dict:
    return {"echo": payload}


@app.post("/contacts", operation_id="fetchContacts")
async def fetch_contacts(payload: dict) -> dict:
    if payload.get("fail"):
        raise HTTPException(status_code=400, detail="bad request")
    return {"contacts": payload.get("ids", []) or ["a", "b"]}


@app.get("/files/{name}", operation_id="readContacts")
async def read_contacts(name: str) -> dict:
    if name == "missing.txt":
        raise HTTPException(status_code=404, detail="not found")
    return {"name": name, "content": "mock"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
