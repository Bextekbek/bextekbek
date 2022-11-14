import logging
import os

from aiohttp.web import Application
from aredis import StrictRedis


logging.basicConfig(level=logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO')))

app = Application()
db = StrictRedis(host='127.0.0.1', port=6379, db=0, decode_responses=True)

from .routes import routes
from .parser import parser_cycle
app.add_routes(routes)
app.on_startup.append(parser_cycle)
