
from aiohttp.web import (
    RouteTableDef,
    json_response,
    HTTPForbidden,
)

from . import db
from .parser import (
    _get_rub_exchange,
    parse_item
)
from . import csmarket

SECRET_TOKEN = "18a67d8c-a71a-4587-92cd-c0da18e1e1aa"
routes = RouteTableDef()


@routes.get('/api/{APP_ID}/')
async def get_all_items(request):
    
    items = await db.hgetall('items_id')
    prices = await db.hgetall('price_id')
    data = {}
    for key, val in items.items():
        price = prices.get(val)
        if price:
            data[key] = float(price)
    return json_response(data)


@routes.get('/api/filter')
async def get_all_items(request):
    
    items = await db.hgetall('items_id')
    prices = await db.hgetall('price_id')
    steamdata = {}
    for key, val in items.items():
        price = prices.get(val)
        if price:
            steamdata[key] = float(price)

    
    csmarket_items = await csmarket.get_csgomarket_items()
    min_price = float(request.rel_url.query['min'])
    max_price = float(request.rel_url.query['max'])
    sales_per_week = int(request.rel_url.query['sales'])
    difference = float(request.rel_url.query['diff'])
    price_source = request.rel_url.query['source']
    response = csmarket.filter_items(steamdata, csmarket_items,
                        min_price, max_price, sales_per_week,
                        difference, price_source)
    return json_response(response)


@routes.get('/api/{APP_ID}/item/{market_hash_name}/')
async def get_item(request):
    
    market_hash_name = request.match_info['market_hash_name']
    rub = await _get_rub_exchange()
    await parse_item(market_hash_name, rub)
    item_id = await db.hget('items_id', market_hash_name)
    if not item_id:
        return json_response({})
    price = await db.hget('price_id', item_id)
    if not price:
        return json_response({})
    return json_response({
                             market_hash_name: float(price)
                         })
