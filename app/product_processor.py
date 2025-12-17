import asyncio
import re
from playwright.async_api import async_playwright, Browser, TimeoutError, Error
from shared.models import UrlQueue, Car
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from sqlalchemy import create_engine


# environment variables block
from dotenv import load_dotenv
import os
from pathlib import Path


env_path = Path(__file__).resolve().parent / "shared" / ".env"
load_dotenv(env_path)


postgre_user = os.getenv("POSTGRES_USER")
postgre_password = os.getenv("POSTGRES_PASSWORD")
postgres_db = os.getenv("POSTGRES_DB")

urls_at_once = int(os.getenv("AMOUNT_OF_URLS_SRCRAPED_FROM_PAGE_AT_ONCE"))


engine = create_engine(f"postgresql+psycopg2://{postgre_user}:{postgre_password}@db/{postgres_db}", echo=True)

# Blocker that blokes unnecessary resources, makes work faster
async def block_resources(page):
    async def handle_route(route, request):
        if request.resource_type in ["image", "font"]:
            # не загружаем картинки, CSS и шрифты
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", handle_route)


# Function converts odometer value
def odometer_to_int(odometer: str):
    
    if odometer == "Без пробігу":
        return 0
    
    return int(re.sub(r"\D", "", odometer)) * 1000

# Function gets url to process from db
def get_next_url():
    with Session(engine) as session:

        url = session.execute(
            select(UrlQueue)
            .where(UrlQueue.is_processed==False)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).scalars().first()

        if url is None:
            return None

        # Mark as processed immediately to avoid multiple workers
        # selecting the same row after the lock is released.
        url.is_processed = True

        session.commit()

        print("end of get_next_url", flush=True)

        return url.url

# def update_url_as_processed(url):
#     with Session(engine) as session:

#         url_obj: UrlQueue = session.query(UrlQueue).filter_by(url=url).first()
#         # url_obj:UrlQueue = select(UrlQueue).where(UrlQueue.url == url).first()
#         url_obj.is_processed = True
        
#         session.commit()

    

def create_car(car: Car):
    try:
        with Session(engine) as session:
            session.add(car)
            session.commit()
    except Exception as e:
        print(f"TimeoutError. Car can not be added.")
    

async def proccess(browser: Browser):
    # url (рядок)
    # title (рядок)
    # price_usd (число)
    # odometer (число, потрібно перевести 95 тис. у 95000 і записати як число)
    # username (рядок)
    # phone_number (число, приклад структури: 38063……..)
    # image_url (рядок)
    # images_count (число)
    # car_number (рядок)
    # car_vin (рядок)
    # datetime_found (дата збереження в базу)
    while True:
        try:    

            url_raw = await asyncio.to_thread(get_next_url)

            if url_raw is None:
                break

            # get_next_url now returns the raw path string (e.g. "/some/path")
            url = "https://auto.ria.com" + url_raw


            
            page = await browser.new_page()

            await block_resources(page)

            await page.goto(url)

            # title
            try:
                title = await page.locator("#sideTitleTitle").inner_text(timeout=5000)
            except TimeoutError:
                print(f"TimeoutError. Error at title. {url}")
                title = " "

            # price_usd
            try:
                price_usd_str = await page.locator('xpath=//*[@id="sidePrice"]/*[1]').inner_text(timeout=5000)
                price_usd = int(re.sub(r"\D", "", price_usd_str))
            except TimeoutError:
                print(f"TimeoutError. Error at price. {url}")
                price_usd = 0

            # odometer
            try:
                odometer_str = await page.locator('#basicInfoTableMainInfo0').inner_text(timeout=5000)
                odometer = odometer_to_int(odometer_str)
            except TimeoutError:
                print(f"TimeoutError. Error at odometer. {url}")
                odometer = 0

            # username
            try:
                username = await page.locator('#sellerInfoUserName').inner_text(timeout=5000)
            except TimeoutError:
                print(f"TimeoutError. Error at username. {url}")
                username = " "

            # image_url
            try:
                image_url = await page.locator('xpath=//*[@id="v-4-1-0-0-0"]/span/picture/img').get_attribute("data-src", timeout=5000)
            except TimeoutError:
                print(f"TimeoutError. Error at image_url. {url}")
                image_url = " "

            # images_count
            try:
                images_count = int(await page.locator('xpath=//*[@id="photoSlider"]/span/span[2]').inner_text(timeout=5000))
            except TimeoutError:
                print(f"TimeoutError. Error at images_count. {url}")
                images_count = 0


            
            # car_number
            try:
                 car_number = await page.locator('xpath=//*[@id="badges"]/div[1]/span').inner_text(timeout=5000)
            except TimeoutError:
                print(f"TimeoutError. Error at car_number. {url}")
                car_number = " "


            # car_vin
            try:
                vin_locator = page.locator(
                    "span",
                    has_text=re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
                )
                car_vin = await vin_locator.first.inner_text()
            except TimeoutError:
                print(f"TimeoutError. Error at car_vin. {url}")
                car_vin = " "
            

            # phone_number
            try:
                await page.locator('span', has_text="XXX XX XX").first.click(timeout=5000)
                
                
                phone_number = await page.locator('a[href*="tel:"]').get_attribute("href", timeout=5000)
                phone_number = int("38" + re.sub(r"\D", "", phone_number))
                print(phone_number)
            except TimeoutError:
                print(f"Error: TimeoutError. No phone number acquired.")
                phone_number = 0
            
            
            try:
                new_car = Car(url, title, price_usd, odometer, username, phone_number, image_url, images_count, car_vin, car_number)
            except:
                print("Error at car creation")

            await asyncio.to_thread(create_car, new_car)

            
            

            print((
                f"url: {url}\n"
                f"title: {title}\n"
                f"price_usd: {price_usd}\n"
                f"odometer: {odometer}\n"
                f"username: {username}\n"

                f"phone_number: {phone_number}\n"
                f"image_url: {image_url}\n"
                f"images_count: {images_count}\n"
                f"car_number: {car_number}\n"
                f"car_vin: {car_vin}\n"
                ))
            await page.close()

        except Exception as e:
            continue
            




