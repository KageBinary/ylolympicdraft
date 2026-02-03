from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings

from api.routes.auth import router as auth_router
from api.routes.me import router as me_router
from api.routes.leagues import router as leagues_router
from api.routes.events import router as events_router
from api.routes.draft import router as draft_router
from api.routes.results import router as results_router
from api.routes import entries


from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
app = FastAPI(title="YL Olympic Draft API", swagger_ui_parameters={"persistAuthorization": True})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(leagues_router)
app.include_router(events_router)
app.include_router(draft_router)
app.include_router(results_router)
app.include_router(entries.router)
@app.get("/health")
def health():
    return {"ok": True}
