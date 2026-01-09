import sys
import os
import tools

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestModel(BaseModel):
    topic: str

@app.post("/api/run")
def run_agent(request: RequestModel):
    print(f"📥 [Process Start] Topic: {request.topic}")
    
    try:
        result = tools.consult_experts_team.invoke(request.topic)
        return {"status": "success", "result": result}
    except Exception as e:
        print(f"🔥 [Exception]: {str(e)}")
        return {"status": "error", "result": f"Internal Server Error: {str(e)}"}

if __name__ == "__main__":
    print(f"🚀 Server initializing at {current_dir}")
    uvicorn.run(app, host="0.0.0.0", port=8000)