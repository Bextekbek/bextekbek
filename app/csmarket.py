import asyncio
import aiohttp

import time
import json



async def get_csgomarket_items():
    url = "https://market.csgo.com/api/v2/prices/class_instance/RUB.json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return (await response.json())["items"]



async def get_steam_items():
    url = "http://195.133.147.166:8090/api/730/"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()


def filter_items(steam_items, csgo_market_items,
                    min_price, max_price, sale_per_week,
                    steam_difference, price_source):
    filtered_items = []
    for csgomarket_item in csgo_market_items:
        market_hash_name = csgo_market_items[csgomarket_item]["market_hash_name"]
        
        if not market_hash_name in steam_items:
            continue

        popularity_7d = csgo_market_items[csgomarket_item]["popularity_7d"]

        if not popularity_7d:
            continue
        
        popularity_7d = int(popularity_7d)

        if popularity_7d <= sale_per_week:
            continue

        csgo_item_price = csgo_market_items[csgomarket_item][price_source]

        if not csgo_item_price:
            continue
        
        csgo_item_price = float(csgo_item_price)
        csgo_item_price = csgo_item_price - csgo_item_price/100*5
        steam_price = steam_items[market_hash_name]

        if steam_price <= min_price or steam_price >= max_price:
            continue
        
        price_difference = ((steam_price - csgo_item_price)/steam_price) * 100

        if price_difference >= steam_difference:
            continue

        filtered_items.append(market_hash_name)
    return filtered_items 

if __name__ == "__main__":
    a = ["1","a", "4"]
    if any(a) in "1njc":
        print(a)