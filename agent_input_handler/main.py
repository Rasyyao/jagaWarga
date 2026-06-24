from fastapi import FastAPI
from agent_input_handler.api.webhook import router as webhook_router

app = FastAPI(title="JagaWarga Agent Input Handler")

app.include_router(webhook_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}