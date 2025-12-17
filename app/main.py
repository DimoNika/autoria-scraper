

import asyncio
from webbrowser import BackgroundBrowser
from playwright.async_api import async_playwright, Browser

from shared.models import Car, UrlQueue


# environment variables block
from dotenv import load_dotenv
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import  insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

from math import ceil

env_path = Path(__file__).resolve().parent / "shared" / ".env"
print(env_path)
load_dotenv(env_path)


postgre_user = os.getenv("POSTGRES_USER")
postgre_password = os.getenv("POSTGRES_PASSWORD")
postgres_db = os.getenv("POSTGRES_DB")

urls_at_once = int(os.getenv("AMOUNT_OF_URLS_SRCRAPED_FROM_PAGE_AT_ONCE"))
# environment variables block



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
        
            




                
async def main():
    
    positions = await get_amount()


    pages_to_scrape = ceil(positions / urls_at_once)
    urs_scrape_sem = asyncio.Semaphore(4)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        await asyncio.gather(
            *(get_urls(urs_scrape_sem, browser, page_number, urls_at_once) for page_number in range(0, pages_to_scrape)),
            return_exceptions=True
        )
    


    

asyncio.run(main())