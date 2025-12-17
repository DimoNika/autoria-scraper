

import asyncio
from webbrowser import BackgroundBrowser
from playwright.async_api import async_playwright, Browser

from shared.models import Car, UrlQueue

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import  insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

from math import ceil

from product_processor import proccess

# environment variables block
from dotenv import load_dotenv
import os
from pathlib import Path

import schedule
from datetime import datetime, time as dt_time, timedelta
import subprocess
from time import sleep

env_path = Path(__file__).resolve().parent / "shared" / ".env"
print(env_path)
load_dotenv(env_path)


postgre_user = os.getenv("POSTGRES_USER")
postgre_password = os.getenv("POSTGRES_PASSWORD")
postgres_db = os.getenv("POSTGRES_DB")

urls_at_once = int(os.getenv("AMOUNT_OF_URLS_SRCRAPED_FROM_PAGE_AT_ONCE"))




engine = create_engine(f"postgresql+psycopg2://{postgre_user}:{postgre_password}@db/{postgres_db}", echo=True)

print("STARTED")


def create_url(url_list):
    with Session(engine) as session:
        session.execute(
            insert(UrlQueue)
            .values(url_list)
            .on_conflict_do_nothing()
        )
        session.commit()

async def get_amount():

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://auto.ria.com/uk/search/?search_type=2&abroad=0&customs_cleared=1&page=0&limit=1")
        # element = page.locator(".vertical-center.horizontal-between.grid-template.full")
        element = page.locator('xpath=//*[@id="SortButtonContentCount"]/span')

        number = ""
        for i in await element.inner_text():
            i: str
            if i.isdigit():
                number += i


        
        print(int(number))
    return int(number)


async def block_resources(page):
    async def handle_route(route, request):
        if request.resource_type in ["image", "stylesheet", "font"]:

            await route.abort()
        else:
            await route.continue_()

    # перехватываем все запросы
    await page.route("**/*", handle_route)

async def get_urls(sem: asyncio.Semaphore, browser: Browser, page_number: int, positions_at_once: int):
    
    async with sem:
            
        
        page = await browser.new_page()

        url_list = []

        await block_resources(page)

        await page.goto(f"https://auto.ria.com/uk/search/?search_type=2&abroad=0&customs_cleared=1&page={page_number}&limit={positions_at_once}")
        elements = page.locator(".link.product-card.horizontal")
        
        print("Func launched")
        print(f"https://auto.ria.com/uk/search/?search_type=2&abroad=0&customs_cleared=1&page={page_number}&limit={positions_at_once}")
        print(await elements.count())
        

        for i in range(await elements.count()):
            el = elements.nth(i)
            url = await el.get_attribute("href")
            # print(url)
            url_list.append({"url": url, "is_processed": False})
        
        await asyncio.to_thread(create_url, url_list)
        await page.close()
        
            




async def delayed_process_start(delay, browser, workers):
    await asyncio.sleep(delay)
    await asyncio.gather(
        *(proccess(browser) for _ in range(workers)),
        return_exceptions=True
    )

async def main():
    print("Main started", flush=True)
    
    positions = await get_amount()


    pages_to_scrape = ceil(positions / urls_at_once)
    urls_scrape_sem = asyncio.Semaphore(2)
    proccess_workers = 3
    process_sem = asyncio.Semaphore(proccess_workers)


    
    async with async_playwright() as p:
        browser = await p.chromium.launch()


        task1 = asyncio.gather(
            *(get_urls(urls_scrape_sem, browser, page_number, urls_at_once) for page_number in range(4)),
            return_exceptions=True
        )

        task2 = asyncio.create_task(
            delayed_process_start(
                30,
                browser,
                proccess_workers
            )
        )
        await asyncio.gather(task1, task2)
    
        output_file = "dumps/" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".dump"
        env = os.environ.copy()
        env["PGPASSWORD"] = postgre_password


        command = [
            "pg_dump",
            "-h", "db",
            "-p", "5432",
            "-U", postgre_user,
            "-F", 'c',
            "-Z", "6", # COMPRESSION_LEVEL
            "-f", output_file,
            postgres_db
    ]
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)



async def wait_until(target_time: dt_time):
    """Ждём до указанного времени (сегодня или завтра)"""
    now = datetime.now()
    run_time = datetime.combine(now.date(), target_time)
    if run_time < now:
        run_time += timedelta(days=1)
    wait_seconds = (run_time - now).total_seconds()
    await asyncio.sleep(wait_seconds)

async def daily_task(target_time: dt_time, coro):
    """Запускает асинхронную задачу каждый день в target_time"""
    while True:
        await wait_until(target_time)
        try:
            print(f"Starting daily task at {datetime.now()}", flush=True)
            await coro()
            print(f"Task finished at {datetime.now()}", flush=True)
        except Exception as e:
            print(f"Error during daily task: {e}", flush=True)

async def scheduler():
    target = dt_time(hour=5, minute=34)
    await daily_task(target, main)  # main — твоя асинхронная функция

if __name__ == "__main__":
    print(datetime.now())
    asyncio.run(scheduler())

# time_to_scrap = os.getenv("TIME_TO_SCRAP")
# def test():
#     print("hello world", flush=True)
#     print(datetime.datetime.now())
    
# # schedule.every().second.do(test)
# schedule.every().day.at(time_to_scrap).do(lambda: asyncio.run(main()))

# while True:
#     schedule.run_pending()
#     sleep(1)
# # asyncio.run(main())