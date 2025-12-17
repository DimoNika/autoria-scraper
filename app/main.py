

import asyncio
from webbrowser import BackgroundBrowser
from playwright.async_api import async_playwright, Browser

from shared.models import Car, UrlQueue

from sqlalchemy import create_engine, delete
from sqlalchemy.dialects.postgresql import  insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

from math import ceil

from product_processor import proccess

# environment variables block
from dotenv import load_dotenv
import os
from pathlib import Path

from datetime import datetime, time as dt_time, timedelta
import subprocess


env_path = Path(__file__).resolve().parent / "shared" / ".env"
load_dotenv(env_path)


postgre_user = os.getenv("POSTGRES_USER")
postgre_password = os.getenv("POSTGRES_PASSWORD")
postgres_db = os.getenv("POSTGRES_DB")

urls_at_once = int(os.getenv("AMOUNT_OF_URLS_SRCRAPED_FROM_PAGE_AT_ONCE"))




engine = create_engine(f"postgresql+psycopg2://{postgre_user}:{postgre_password}@db/{postgres_db}", echo=True)

print("STARTED")

# Function adds list of urls to db
def create_url(url_list):
    with Session(engine) as session:
        session.execute(
            insert(UrlQueue)
            .values(url_list)
            .on_conflict_do_nothing()
        )
        session.commit()

# Function scrapes site for total amount of positions
async def get_amount():

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://auto.ria.com/uk/search/?search_type=2&abroad=0&customs_cleared=1&page=0&limit=1")
        element = page.locator('xpath=//*[@id="SortButtonContentCount"]/span')

        number = ""
        for i in await element.inner_text():
            i: str
            if i.isdigit():
                number += i

    return int(number)

# Blocker that blokes unnecessary resources, makes work faster
async def block_resources(page):
    async def handle_route(route, request):
        if request.resource_type in ["image", "stylesheet", "font"]:

            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", handle_route)


# Function scrapes for urls of positions
async def get_urls(sem: asyncio.Semaphore, browser: Browser, page_number: int, positions_at_once: int):
    
    async with sem:
            
        
        page = await browser.new_page()

        url_list = []

        await block_resources(page)

        await page.goto(f"https://auto.ria.com/uk/search/?search_type=2&abroad=0&customs_cleared=1&page={page_number}&limit={positions_at_once}")
        elements = page.locator(".link.product-card.horizontal")
        
        print(f"https://auto.ria.com/uk/search/?search_type=2&abroad=0&customs_cleared=1&page={page_number}&limit={positions_at_once}")
        print(await elements.count())
        

        for i in range(await elements.count()):
            el = elements.nth(i)
            url = await el.get_attribute("href")
            url_list.append({"url": url, "is_processed": False})
        
        await asyncio.to_thread(create_url, url_list)
        await page.close()
        
            



# Functio starter of position scraping with delay, so urls have time to be found
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
    


    
    async with async_playwright() as p:
        browser = await p.chromium.launch()


        task1 = asyncio.gather(
            *(get_urls(urls_scrape_sem, browser, page_number, urls_at_once) for page_number in range(pages_to_scrape)),
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

    with Session(engine) as session:
        session.execute(delete(UrlQueue))
        session.execute(delete(Car))
        session.commit()
    
    print("Iteration finished")
        


# Function counts time to next execution
async def wait_until(target_time: dt_time):
    now = datetime.now()
    run_time = datetime.combine(now.date(), target_time)
    if run_time < now:
        run_time += timedelta(days=1)
    wait_seconds = (run_time - now).total_seconds()
    await asyncio.sleep(wait_seconds)


# Function that waits time than lounches main
async def daily_task(target_time: dt_time, coro):
    while True:
        await wait_until(target_time)
        try:
            print(f"Starting daily task at {datetime.now()}", flush=True)
            await coro()
            print(f"Task finished at {datetime.now()}", flush=True)
        except Exception as e:
            print(f"Error during daily task: {e}", flush=True)

async def scheduler():
    hours_to_scrap = int(os.getenv("TIME_HOURS_TO_SCRAP"))
    minutes_to_scrap = int(os.getenv("TIME_MINUTES_TO_SCRAP"))
    
    target = dt_time(hour=hours_to_scrap, minute=minutes_to_scrap)
    await daily_task(target, main)

if __name__ == "__main__":
    print(datetime.now())
    asyncio.run(scheduler())

