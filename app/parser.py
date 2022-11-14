""" Parser Module """
import asyncio
import logging
import os
from asyncio import (
    create_task,
    sleep,
    # Lock,
)
from json import loads
from random import choice
from re import search
from typing import List
import random

import aiohttp
from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector
from . import db


with open('Firefox.txt') as f:
    USER_AGENTS = [l.strip() for l in f.readlines() if l.strip()]


def genproxy(): 
    proxy_auth = str(random.randint(1, 0x7fffffff)) + ":" + str(random.randint(1, 0x7fffffff)) 
    # proxies = {"http": , 
    #     "https": "socks5://{}@localhost:9050".format(proxy_auth)}
    return "socks5://{}@localhost:9050".format(proxy_auth)


THREADS_COUNT = 10
PROXY = "http://127.1.0.1:9999"
CYCLE_SLEEP = 60*60*3
# TASK_LOCK = Lock()

APP_URL = 'https://steamcommunity.com/market/listings/730/{market_hash_name}'
BUY_ORDER_URL = 'https://steamcommunity.com/market/itemordershistogram?country=UA&language=english&currency=5&item_nameid={item_id}&two_factor=0' # noqa
EXCHANGE_URL = 'https://www.cbr-xml-daily.ru/daily_json.js'

BAN_LIST = ["Stiker", "Case", "Souvenir"]


def levenshtein(s1, s2, maximum):
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min(
                    (distances[i1], distances[i1 + 1], distances_[-1])
                ))
        if all((x > maximum for x in distances_)):
            return 1000
        distances = distances_
    return distances[-1]


async def add_item(market_hash_name, page_data, order_data, rub):
    """ This function add item data to 'new_items' set in redis db

    :param market_hash_name: app name
    :param page_data: data from APP URL
    :param order_data: data from BUY ORDER URL
    :param rub: exchange Rub and Usd
    """
    # noinspection PyBroadException
    try:
        buy_order = float(search(
            r'(\d+\,\d+|\d+) pуб\.',
            order_data['buy_order_summary'],
        ).group(1).replace(',', '.'))
        buy_order_percent = buy_order + (buy_order * 0.15)

        try:
            sell_order = order_data['sell_order_graph'][0][0]
        except IndexError:
            sell_order = 0

        start_pos = page_data.rfind('var line1=')
        if start_pos != -1:
            start_pos += len('var line1=')
            end_pos = page_data.find(';', start_pos)
            histogram = loads(page_data[start_pos:end_pos])
            if len(histogram) >= 4:
                prices = histogram[-4:]
            else:
                prices = histogram

            avg_price = sum([p[1] * rub for p in prices]) / len(prices)

        # noinspection PyUnboundLocalVariable
        if start_pos == -1:
            best_price = buy_order
        elif avg_price < buy_order:
            best_price = buy_order
        elif avg_price < buy_order_percent:
            best_price = avg_price
        else:
            best_price = buy_order

        item_id = await db.hget('items_id', market_hash_name)
        price_db = await db.hget('new_price_id', item_id)
        price_low = await db.hget('new_low_price_id', item_id)

        if not price_db:
            # noinspection PyUnboundLocalVariable
            await db.hset('new_price_id', item_id, f'{best_price:.2f}')
        else:
            price_db = float(price_db)
            # noinspection PyUnboundLocalVariable
            if price_db > best_price:
                await db.hset('new_price_id', item_id, f'{best_price:.2f}')

        if not price_low:
            await db.hset('new_low_price_id', item_id, f'{sell_order:.2f}')
        else:
            price_low = float(price_low)

            if price_low > sell_order:
                await db.hset('new_low_price_id', item_id, f'{sell_order:.2f}')
        await db.hset('new_price_name', market_hash_name, best_price)
        logging.info(f"adding {market_hash_name} {best_price}")

    except Exception:
        logging.exception(f'While add_item {market_hash_name}')


async def parse_item(market_hash_name: str, rub):
    
    app_url = APP_URL.format(market_hash_name=market_hash_name)
    # https://2YGnGM:o3xUPp@212.81.36.84:9148
    connector = ProxyConnector.from_url(genproxy())
    async with ClientSession(connector=connector, headers={'User-Agent': choice(USER_AGENTS), 'Connection': 'close',
                                      'X-Forwarder-For': '{}.{}.{}.{}'.format(*[random.randrange(8) for _ in range(4)])}) as session:
        for _ in range(1):
            try:
                async with session.get(app_url, verify_ssl=False) as response:
                    if response.status != 200:
                        continue
                    page_data = await response.text()

                    item_id = search(
                        r'Market_LoadOrderSpread\( (\d+) \);',
                        page_data,
                    ).group(1)
                    buy_order_url = BUY_ORDER_URL.format(item_id=item_id)
                    break
            except aiohttp.ClientConnectionError:
                pass
            except Exception as e:
                logging.exception(f'1 {market_hash_name}')

            
        else:
            raise ConnectionError()

        for _ in range(5):
            try:
                async with session.get(buy_order_url, verify_ssl=False) as response:
                    if response.status != 200:
                        continue
                    order_data = await response.json()
                    if order_data['success'] != 1:
                        continue
                    break
            except Exception as ex:
                print(ex)
        else:
            raise ConnectionError()

    await add_item(market_hash_name, page_data, order_data, rub)


async def parse_items(rub):
    while True:
        market_hash_name = await db.spop('need_parse_items')
        for ban_word in BAN_LIST:
            if ban_word in market_hash_name:
                continue
        if not market_hash_name:
            break
        try:
            await parse_item(market_hash_name, rub)
        except ConnectionError as ex:
            pass
        except Exception:
            logging.exception(f'While parsing {market_hash_name}')


async def _group_items(items):
    for item in items:
        db_items = await db.hgetall('items_id')
        for db_item, db_item_id in db_items.items():
            if item == db_item:
                item_id = db_item_id
                break
        else:
            item_id = str(len(db_items))
        await db.hset('items_id', item, item_id)


async def _get_rub_exchange():
    async with ClientSession() as session:
        async with session.get(EXCHANGE_URL) as response:
            return (await response.json(
                        content_type='application/javascript'
                    ))['Valute']['USD']['Value']


async def check_items(items: List[str]):
    not_parsed_items: List[str] = []
    for item in items:
        if (await db.hget('new_price_name', item)) is None:
            not_parsed_items.append(item)
    return not_parsed_items


class History:
    def __init__(self):
        self._history = []

    def add(self, item):
        self._history.append(item)
        if len(self._history) > 3:
            self._history = self._history[1:]

    def check(self):
        if len(self._history) < 3:
            return False
        return self._history[0] == self._history[1] == self._history[2]


async def get_market_csgo_items():
    async with ClientSession() as session:
        async with session.get("https://market.csgo.com//api/v2/prices/USD.json") as response:
            data = await response.json()
            return [i['market_hash_name'] for i in data['items']]



async def _parser_cycle():
    while True:
        try:
            logging.info('Start parsing')
            rub = await _get_rub_exchange()
            logging.info('Gets rub exchange')
            items = set(await get_market_csgo_items())
            logging.info('Get csgo market items')
            db_items = set(await db.hkeys('items_id'))
            need_group_items = items.difference(db_items)
            create_task(_group_items(need_group_items))

            items = items | db_items

            history = History()
            while True:
                not_parsed_items = await check_items(tuple(items))
                print(len(not_parsed_items))
                history.add(not_parsed_items)
                if not not_parsed_items:
                    break
                elif history.check():
                    # If won`t parse items 3 times
                    break
                else:
                    await db.sadd('need_parse_items', *not_parsed_items)
                tasks = [parse_items(rub)
                         for i in range(THREADS_COUNT)]
                await asyncio.gather(*tasks)

            await db.rename('new_price_id', 'price_id')
            await db.rename('new_low_price_id', 'low_price_id')
            await db.delete('new_price_name')
            logging.info(f'Success end parsing, sleep {CYCLE_SLEEP} seconds')
            await sleep(CYCLE_SLEEP)
        except:
            logging.exception('Exception while parsing')


async def parser_cycle(_):
    create_task(_parser_cycle())
