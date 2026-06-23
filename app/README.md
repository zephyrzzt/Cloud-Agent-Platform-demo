# App

`app.main:create_app()` builds the FastAPI application and registers the MVP routers.

Run locally with:

```bash
uvicorn app.main:app --reload
```

The current app uses an in-memory container, a background worker, and a scripted `MockProvider`, so it is meant for validating the platform flow rather than production persistence.
