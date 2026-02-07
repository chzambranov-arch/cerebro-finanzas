from app.main import app
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8004))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
