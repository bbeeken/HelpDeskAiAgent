from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Truck Stop MCP Helpdesk API")
app.include_router(router)
