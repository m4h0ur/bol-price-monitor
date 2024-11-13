# src/price_monitor.py

import os
import json
import logging
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import threading
import random
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def format_price(price):
    """Format price in correct notation (38.99)"""
    return f"€{price:.2f}"

class PriceBot:
    def __init__(self):
        self.data_file = 'data/products.json'
        self.products = self.load_products()
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '3600'))
        self._remove_urls = {}  # Store URLs for remove functionality
        self.updater = None

    def load_products(self):
        try:
            os.makedirs('data', exist_ok=True)
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading products: {e}")
        return {}

    def save_products(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.products, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving products: {e}")

    def get_price(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
            
            session = requests.Session()
            
            # First visit the homepage
            try:
                session.get('https://www.bol.com/', headers=headers, timeout=10)
                time.sleep(random.uniform(1, 3))  # Random delay
            except Exception:
                pass

            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple selectors for the name
            name_selectors = [
                ('h1', {'data-test': 'title'}),
                ('span', {'data-test': 'title'}),
                ('h1', {'class': 'product-title'}),
                ('div', {'data-test': 'title'}),
                ('h1', None)
            ]
            
            name_element = None
            for tag, attrs in name_selectors:
                if attrs:
                    name_element = soup.find(tag, attrs)
                else:
                    name_element = soup.find(tag)
                if name_element:
                    break
            
            if not name_element:
                raise ValueError("Product name not found")
            
            product_name = name_element.text.strip()
            
            # Find price
            price_selectors = [
                'promo-price',
                'price-block__price',
                'price',
                'product-price',
                'current-price'
            ]
            
            price_element = None
            for selector in price_selectors:
                elements = soup.find_all(class_=selector)
                for element in elements:
                    if element and any(c.isdigit() for c in element.text):
                        price_element = element
                        break
                if price_element:
                    break
            
            if not price_element:
                raise ValueError("Price element not found")

            price_text = price_element.text.strip()
            # Clean up the price text
            price_text = ''.join(c for c in price_text if c.isdigit() or c in '.,')
            price_text = price_text.replace(',', '.')
            
            if price_text.count('.') > 1:
                parts = price_text.split('.')
                price_text = ''.join(parts[:-1]) + '.' + parts[-1]
            
            price = float(price_text)
            # Convert to correct format if price is too high
            if price > 1000:
                price = price / 100

            logger.info(f"Found price for {product_name}: {format_price(price)}")
            return price, product_name
                
        except Exception as e:
            logger.error(f"Error getting price for {url}: {str(e)}")
            return None, None

    def start(self, update: Update, context: CallbackContext):
        help_text = """
🤖 Welcome to Bol.com Price Monitor Bot!

Available commands:
/add <url> - Start monitoring a new product
/list - List all monitored products
/remove - Remove a product from monitoring
/help - Show this help message

Simply send me a Bol.com product URL and I'll monitor its price!
"""
        update.message.reply_text(help_text)

    def help(self, update: Update, context: CallbackContext):
        self.start(update, context)

    def add_product(self, update: Update, context: CallbackContext):
        try:
            if len(context.args) < 1:
                update.message.reply_text("Please provide a Bol.com product URL\nExample: /add https://www.bol.com/product-url")
                return

            url = context.args[0]
            if not url.startswith('https://www.bol.com'):
                update.message.reply_text("Please provide a valid Bol.com URL")
                return

            chat_id = str(update.effective_chat.id)
            if chat_id not in self.products:
                self.products[chat_id] = {}

            if url in self.products[chat_id]:
                update.message.reply_text("This product is already being monitored!")
                return

            update.message.reply_text("🔍 Fetching product information...")
            price, name = self.get_price(url)

            if price is None or not name:
                update.message.reply_text(
                    "Sorry, I couldn't fetch the product information. Please check if:\n"
                    "1. The URL is correct\n"
                    "2. The product is still available\n"
                    "3. The website is accessible\n\n"
                    "Try again in a few minutes."
                )
                return

            self.products[chat_id][url] = {
                'name': name,
                'last_price': price,
                'last_check': datetime.now().isoformat()
            }
            self.save_products()

            update.message.reply_text(
                f"✅ Added to monitoring:\n"
                f"📦 {name}\n"
                f"💰 Current price: {format_price(price)}\n"
                f"I'll notify you when the price changes!"
            )

        except Exception as e:
            logger.error(f"Error adding product: {e}")
            update.message.reply_text("Sorry, something went wrong. Please try again.")

    def list_products(self, update: Update, context: CallbackContext):
        chat_id = str(update.effective_chat.id)
        if chat_id not in self.products or not self.products[chat_id]:
            update.message.reply_text("You have no products being monitored.")
            return

        message = "📊 Your Monitored Products:\n\n"
        for url, data in self.products[chat_id].items():
            message += f"📦 {data['name']}\n"
            message += f"💰 Last price: {format_price(data['last_price'])}\n"
            message += f"🔗 {url}\n\n"

        update.message.reply_text(message)

    def remove_product(self, update: Update, context: CallbackContext):
        chat_id = str(update.effective_chat.id)
        if chat_id not in self.products or not self.products[chat_id]:
            update.message.reply_text("You have no products to remove.")
            return

        # Clear previous remove URLs
        self._remove_urls.clear()
        
        keyboard = []
        for i, (url, data) in enumerate(self.products[chat_id].items()):
            callback_data = f"rm_{i}"  # Short callback data
            self._remove_urls[callback_data] = url
            keyboard.append([InlineKeyboardButton(
                f"{data['name']} ({format_price(data['last_price'])})",
                callback_data=callback_data
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Select a product to remove:", reply_markup=reply_markup)

    def button_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()

        if query.data.startswith('rm_'):
            chat_id = str(update.effective_chat.id)
            if query.data in self._remove_urls:
                url = self._remove_urls[query.data]
                if chat_id in self.products and url in self.products[chat_id]:
                    product_name = self.products[chat_id][url]['name']
                    del self.products[chat_id][url]
                    self.save_products()
                    query.edit_message_text(f"✅ Removed {product_name} from monitoring.")
                else:
                    query.edit_message_text("❌ Error: Product not found.")
            else:
                query.edit_message_text("❌ Error: Invalid removal request.")

    def check_prices(self):
        while True:
            try:
                for chat_id in list(self.products.keys()):
                    for url, data in list(self.products[chat_id].items()):
                        logger.info(f"Checking price for {url}")
                        current_price, _ = self.get_price(url)
                        
                        if current_price is None:
                            continue

                        if current_price != data['last_price']:
                            change = current_price - data['last_price']
                            change_percent = (change / data['last_price']) * 100
                            
                            message = (
                                f"💰 Price Change Alert!\n\n"
                                f"📦 {data['name']}\n"
                                f"Old price: {format_price(data['last_price'])}\n"
                                f"New price: {format_price(current_price)}\n"
                                f"Change: {'📈' if change > 0 else '📉'} {format_price(abs(change))} ({change_percent:+.1f}%)\n\n"
                                f"🔗 {url}"
                            )
                            
                            try:
                                self.updater.bot.send_message(chat_id=int(chat_id), text=message)
                                logger.info(f"Sent price alert for {data['name']}")
                            except Exception as e:
                                logger.error(f"Failed to send message: {e}")
                            
                            self.products[chat_id][url]['last_price'] = current_price
                            self.products[chat_id][url]['last_check'] = datetime.now().isoformat()
                            self.save_products()
                
                time.sleep(self.check_interval + random.randint(30, 60))
                
            except Exception as e:
                logger.error(f"Error in price check loop: {e}")
                time.sleep(60)

    def run(self):
        try:
            logger.info("Starting bot...")
            self.updater = Updater(self.token, use_context=True)
            dp = self.updater.dispatcher

            dp.add_handler(CommandHandler("start", self.start))
            dp.add_handler(CommandHandler("help", self.help))
            dp.add_handler(CommandHandler("add", self.add_product))
            dp.add_handler(CommandHandler("list", self.list_products))
            dp.add_handler(CommandHandler("remove", self.remove_product))
            dp.add_handler(CallbackQueryHandler(self.button_callback))

            # Start price checking in a separate thread
            threading.Thread(target=self.check_prices, daemon=True).start()
            
            logger.info("Bot is running!")
            self.updater.start_polling()
            self.updater.idle()
            
        except Exception as e:
            logger.error(f"Critical error: {e}")

if __name__ == "__main__":
    try:
        bot = PriceBot()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
