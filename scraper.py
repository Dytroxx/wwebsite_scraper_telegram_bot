import asyncio
import os

import aiofiles
import aiohttp
import schedule
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from bs4 import BeautifulSoup

# Private Tokens
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class ProductChecker:
    def __init__(
        self, product_name, product_url, status_file, parse_method, format_notification
    ):
        self.product_name = product_name
        self.product_url = product_url
        self.status_file = status_file
        self.parse_method = parse_method
        self.format_notification = format_notification

    async def scrape_website(self):
        """Scrape the product availability status from the website."""
        print(f"Scraping the website for {self.product_name}...")
        async with aiohttp.ClientSession() as session:
            async with session.get(self.product_url) as response:
                if response.status == 200:
                    print("Successfully fetched the webpage.")
                    text = await response.text()
                    soup = BeautifulSoup(text, "html.parser")
                    return self.parse_method(soup)
                else:
                    print(
                        f"Failed to retrieve the webpage. Status code: {response.status}"
                    )
                    return None

    async def read_previous_status(self):
        """Read the previous status from the file."""
        if os.path.exists(self.status_file):
            async with aiofiles.open(self.status_file, "r") as file:
                status = await file.read()
                print(f"Previous status for {self.product_name}: {status.strip()}")
                return status.strip()
        print(f"No previous status found for {self.product_name}.")
        return None

    async def write_current_status(self, status):
        """Write the current status to the file."""
        print(f"Writing current status for {self.product_name} to file...")
        async with aiofiles.open(self.status_file, "w") as file:
            await file.write(status)
        print(f"Current status written to file for {self.product_name}.")

    async def check_for_updates(self):
        """Check if the product availability status has changed."""
        current_status = await self.scrape_website()
        previous_status = await self.read_previous_status() if current_status else None
        if current_status and current_status != previous_status:
            await self.write_current_status(current_status)
            return True, previous_status, current_status
        return False, previous_status, current_status

    async def notify(self, message):
        """Send a Telegram notification."""
        await send_telegram_notification(message)


async def send_telegram_notification(message):
    """Send a notification message via Telegram."""
    print("Sending Telegram notification...")
    try:
        response = await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="HTML"
        )
        print(f"Notification sent. Response: {response}")
    except Exception as e:
        print(f"Failed to send notification: {e}")


def parse_darkside_tobacco(soup):
    """Parse the availability status for Darkside Tobacco."""
    availability_status = soup.find("span", id="availability_value").text.strip()
    return availability_status


def parse_tangiers_noir_tobacco(soup):
    """Parse the list of flavors for Tangiers Noir Tobacco."""
    flavor_select = soup.find("select", id="group_16")
    if flavor_select:
        flavors = [option.text.strip() for option in flavor_select.find_all("option")]
        return "\n".join(flavors)
    return None


def format_darkside_notification(
    product_name, previous_status, current_status, product_url
):
    """Format the notification message for Darkside Tobacco."""
    return (
        f"<b>{product_name} Status Update:</b>\n\n"
        f"Previous status: {previous_status}\n"
        f"Current status: {current_status}\n\n"
        f"Check it out here: {product_url}"
    )


def format_tangiers_notification(
    product_name, previous_status, current_status, product_url
):
    """Format the notification message for Tangiers Noir Tobacco."""
    previous_flavors = set(previous_status.split("\n")) if previous_status else set()
    current_flavors = set(current_status.split("\n"))
    added_flavors = current_flavors - previous_flavors
    removed_flavors = previous_flavors - current_flavors

    added_text = (
        "\n".join(f"+ {flavor}" for flavor in added_flavors)
        if added_flavors
        else "No new flavors."
    )
    removed_text = (
        "\n".join(f"- {flavor}" for flavor in removed_flavors)
        if removed_flavors
        else "No flavors removed."
    )

    return (
        f"<b>{product_name} Flavors Update:</b>\n\n"
        f"Changes:\n{added_text}\n{removed_text}\n\n"
        f"Check it out here: {product_url}"
    )


def format_tangiers_current_flavors(product_name, current_status, product_url):
    """Format the notification message for current available Tangiers flavors."""
    return (
        f"<b>Current available flavors for {product_name}:</b>\n\n"
        f"{current_status}\n\n"
        f"Check it out here: {product_url}"
    )


async def process_checker(checker):
    """Process a single ProductChecker instance."""
    updated, previous_status, current_status = await checker.check_for_updates()
    if checker.product_name == "Darkside Tobacco" and updated:
        message = format_darkside_notification(
            checker.product_name, previous_status, current_status, checker.product_url
        )
        await checker.notify(message)
    elif checker.product_name == "Tangiers Noir Tobacco" and updated:
        changes_message = format_tangiers_notification(
            checker.product_name, previous_status, current_status, checker.product_url
        )
        await checker.notify(changes_message)
        await save_current_flavors(current_status)


async def save_current_flavors(current_status):
    """Save the current flavors for Tangiers Noir Tobacco to a file."""
    async with aiofiles.open("tangiers_current_status.txt", "w") as file:
        await file.write(current_status)


async def job():
    """Check for updates for all products and send notifications if there are changes."""
    print("Starting job...")
    checkers = [
        ProductChecker(
            product_name="Darkside Tobacco",
            product_url="http://www.juicyhookah.com/darkside/322-darkside-200g.html",
            status_file="darkside_status.txt",
            parse_method=parse_darkside_tobacco,
            format_notification=format_darkside_notification,
        ),
        ProductChecker(
            product_name="Tangiers Noir Tobacco",
            product_url="https://www.juicyhookah.com/tangiers/127-tangiers-noir-shisha-250g.html",
            status_file="tangiers_noir_status.txt",
            parse_method=parse_tangiers_noir_tobacco,
            format_notification=format_tangiers_notification,
        ),
    ]

    for checker in checkers:
        await process_checker(checker)
    print("Job finished.")


@dp.message(Command(commands=["AllTangiersList"]))
async def send_tangiers_current_flavors(message: Message):
    """Send the current list of available Tangiers flavors."""
    if os.path.exists("tangiers_current_status.txt"):
        async with aiofiles.open("tangiers_current_status.txt", "r") as file:
            current_status = await file.read()
        current_flavors_message = format_tangiers_current_flavors(
            "Tangiers Noir Tobacco",
            current_status,
            "https://www.juicyhookah.com/tangiers/127-tangiers-noir-shisha-250g.html",
        )
        await message.reply(current_flavors_message, parse_mode="HTML")
    else:
        await message.reply(
            "Current flavors list is not available yet.", parse_mode="HTML"
        )


async def main():
    # Perform an initial check immediately
    print("Starting initial check...")
    await job()

    # Schedule the job to run every 10 seconds
    schedule.every(45).minutes.do(lambda: asyncio.create_task(job()))

    # Start the scheduler
    print("Scheduler started.")

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)


if __name__ == "__main__":
    # Start the Telegram bot and the main coroutine
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.create_task(dp.start_polling())
    loop.run_until_complete(main())