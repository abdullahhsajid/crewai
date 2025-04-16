import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
# from dotenv import load_dotenv

# load_dotenv()

# os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
# os.environ["OPENAI_MODEL_NAME"] = os.getenv("OPENAI_MODEL_NAME")

app = FastAPI(title="Crew AI Bot API", description="API to run Crew AI Bot", version="1.0.0")



# result = crew.kickoff(inputs=crew_inputs)

# print("############")
# print(result)

@app.get("/")
async def root():
    return {"message": "Crew AI Bot API is running"}

@app.post("/run-agent")
async def run_agent(inputs: dict):
    try:
        return {"result":"Test!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
