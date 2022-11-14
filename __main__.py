from aiohttp.web import run_app

from app import app


if __name__ == "__main__":
    run_app(app, port=8090)
