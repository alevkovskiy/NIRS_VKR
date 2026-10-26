from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()

@app.get("/")
def main_page():
    return FileResponse("/templates/main_page.html")