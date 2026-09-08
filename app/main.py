from fastapi import FastAPI

app = FastAPI(
    title="Codebase Navigator AI",
    description="AI-powered codebase understanding and navigation system",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "Codebase Navigator AI is running!"
    }