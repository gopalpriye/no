import requests
import asyncio
import aiohttp
import json
import zipfile
import os
import random
import re
import logging
import time
from pyrogram.types import CallbackQuery
from typing import Dict, List, Any, Tuple
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyromod.exceptions.listener_timeout import ListenerTimeout
from concurrent.futures import ThreadPoolExecutor
from flask import Flask
import threading
import sqlite3
from config import api_id, api_hash, bot_token, chat_id, log_channel_id

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)

# Thread pool for async tasks
THREADPOOL = ThreadPoolExecutor(max_workers=50)

# Image list for welcome message
image_list = [
    "https://te.legra.ph/file/11366447de3410810a383-d29ae883f7add39f2a.jpg",
]

# Default thumbnail for fallback
DEFAULT_THUMBNAIL = "https://te.legra.ph/file/11366447de3410810a383-d29ae883f7add39f2a.jpg"

# Initialize bot
bot = Client(
    "bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

# Flask app for Render/Koyeb
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# SQLite Database Setup
def init_db():
    conn = sqlite3.connect('auth_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS auth_users (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def add_auth_user(user_id: int):
    conn = sqlite3.connect('auth_users.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO auth_users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_auth_user(user_id: int):
    conn = sqlite3.connect('auth_users.db')
    c = conn.cursor()
    c.execute("DELETE FROM auth_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_auth_users() -> List[int]:
    conn = sqlite3.connect('auth_users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM auth_users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# Initialize database
init_db()

# MODIFIED: Enhanced welcome message with emojis and formatting
WELCOME_MESSAGE = """
🌟 **Welcome to the Ultimate Course Extractor Bot!** 🌟

Unlock premium educational content effortlessly! 📚 Extract courses from 📍 **Classplus** and 🔖 **Physics Wallah** with ease. Choose an option to begin:

🔹 **Classplus Extractor** 📖: Access Classplus courses without purchase.
🔹 **Physics Wallah Extractor** 🚀: Retrieve Physics Wallah content seamlessly.
🔹 **Premium Features** 💎: Unlock faster extraction and priority support.
🔹 **Developer Support** 🛠️: Join our support group for assistance.

⚠️ *Note*: Ensure you have permission to access the content.

**Let’s dive into learning!  🎉 Owner : @SEM2JOB_SERVICE_BOT**
"""

# --- Utility Functions ---
def clean_filename(name: str) -> str:
    """Clean filename by replacing invalid characters."""
    return re.sub(r'[\/:*?"<>|]', '-', name)

def shorten_caption(caption: str, max_length: int = 1024) -> str:
    """Shorten caption to fit Telegram's limit."""
    if len(caption) <= max_length:
        return caption
    return caption[:max_length - 10] + "... *truncated*"

async def is_valid_url(session: aiohttp.ClientSession, url: str) -> bool:
    """Check if a URL is accessible with robust error handling."""
    if not url or not url.startswith(('http://', 'https://')):
        return False
    try:
        async with session.head(url, allow_redirects=True, timeout=5) as response:
            if response.status in (200, 301, 302):
                return True
            logging.warning(f"URL {url} returned status {response.status}")
            return False
    except aiohttp.ClientError as e:
        logging.warning(f"URL validation failed for {url}: {e}")
        return False
    except asyncio.TimeoutError:
        logging.warning(f"URL validation timed out for {url}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error validating URL {url}: {e}")
        return False

async def send_to_log_channel(bot: Client, user_id: int, username: str, content: str, file_path: str = None):
    """Send extracted content to log channel with username."""
    caption = f"📤 **Extracted by User**\n👤 User ID: `{user_id}`\n📛 Username: @{username}\n\n{content}"
    try:
        if file_path:
            with open(file_path, 'rb') as f:
                await bot.send_document(
                    chat_id=log_channel_id,
                    document=f,
                    caption=shorten_caption(caption)
                )
        else:
            await bot.send_message(
                chat_id=log_channel_id,
                text=shorten_caption(caption)
            )
    except Exception as e:
        logging.error(f"Error sending to log channel: {e}")

# --- Authorization Commands ---
@bot.on_message(filters.command(["auth_user"]) & filters.user(7836088695))  # Replace 7836088695 with your Telegram ID
async def auth_user(bot: Client, message: Message):
    try:
        user_id = int(message.text.split()[1])
        add_auth_user(user_id)
        await message.reply_text(f"✅ User `{user_id}` authorized successfully!")
    except (IndexError, ValueError):
        await message.reply_text("❌ Usage: /auth_user <user_id>")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.command(["deauth_user"]) & filters.user(7836088695))  # Replace 7836088695 with your Telegram ID
async def deauth_user(bot: Client, message: Message):
    try:
        user_id = int(message.text.split()[1])
        remove_auth_user(user_id)
        await message.reply_text(f"✅ User `{user_id}` deauthorized successfully!")
    except (IndexError, ValueError):
        await message.reply_text("❌ Usage: /deauth_user <user_id>")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.command(["myplan"]))
async def my_plan(bot: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    is_premium = user_id in get_auth_users()
    plan_status = "Premium 🎖️" if is_premium else "Free 🆓"
    keyboard = [
        [InlineKeyboardButton("💎 Upgrade to Premium", url="https://t.me/SEM2JOB")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        f"📋 **Your Plan Details** 📚\n\n"
        f"👤 **User ID**: `{user_id}`\n"
        f"📛 **Username**: @{username}\n"
        f"📊 **Plan**: {plan_status}\n\n"
        f"{'✅ Full access to all features including .txt files.' if is_premium else '❌ Limited access. Upgrade to Premium for .txt files and more!'}",
        reply_markup=reply_markup
    )

# --- Classplus Functions ---
async def fetch_cpwp_signed_url(url_val: str, name: str, session: aiohttp.ClientSession, headers: Dict[str, str]) -> str | None:
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        params = {"url": url_val}
        try:
            async with session.get("https://api.classplusapp.com/cams/uploader/video/jw-signed-url", params=params, headers=headers) as response:
                response.raise_for_status()
                response_json = await response.json()
                signed_url = response_json.get("url") or response_json.get('drmUrls', {}).get('manifestUrl')
                return signed_url
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed for {name}: {e}")
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(2 ** attempt)
    logging.error(f"Failed to fetch signed URL for {name} after {MAX_RETRIES} attempts.")
    return None

async def process_cpwp_url(url_val: str, name: str, content_type: str, thumbnail: str, session: aiohttp.ClientSession, headers: Dict[str, str]) -> Dict | None:
    try:
        signed_url = await fetch_cpwp_signed_url(url_val, name, session, headers)
        if not signed_url:
            logging.warning(f"Failed to obtain signed URL for {name}: {url_val}")
            return None
        if "testbook.com" in url_val or "classplusapp.com/drm" in url_val or "media-cdn.classplusapp.com/drm" in url_val:
            return {"name": name, "url": url_val, "type": content_type, "thumbnail": thumbnail}
        async with session.get(signed_url) as response:
            response.raise_for_status()
        return {"name": name, "url": url_val, "type": content_type, "thumbnail": thumbnail}
    except Exception as e:
        logging.exception(f"Unexpected error processing {name}: {e}")
        return None

async def get_cpwp_course_content(session: aiohttp.ClientSession, headers: Dict[str, str], batch_token: str, folder_id: int = 0, limit: int = 9999999999, retry_count: int = 0, folder_path: str = "", subfolder_name: str = "") -> Tuple[List[Dict], int, int, int, str]:
    MAX_RETRIES = 3
    fetched_urls: set[str] = set()
    results: List[Dict] = []
    video_count = 0
    pdf_count = 0
    image_count = 0
    batch_thumbnail = ""
    content_tasks: List[Tuple[int, asyncio.Task[Dict | None]]] = []
    folder_tasks: List[Tuple[int, asyncio.Task[Tuple[List[Dict], int, int, int, str]]]] = []

    try:
        content_api = f'https://api.classplusapp.com/v2/course/preview/content/list/{batch_token}'
        params = {'folderId': folder_id, 'limit': limit}
        async with session.get(content_api, params=params, headers=headers) as res:
            res.raise_for_status()
            res_json = await res.json()
            contents: List[Dict[str, Any]] = res_json.get('data', [])
            if not contents:
                logging.warning(f"No content found for Batch_Token: {batch_token}, folder_id: {folder_id}")
                return [], 0, 0, 0, ""

            for content in contents:
                if content.get('contentType') == 1:  # Folder
                    folder_name = content.get('name', 'Unknown Folder')
                    folder_task = asyncio.create_task(get_cpwp_course_content(session, headers, batch_token, content['id'], limit, retry_count=0, folder_path=f"{folder_path}/{folder_name}" if folder_path else folder_name, subfolder_name=folder_name))
                    folder_tasks.append((content['id'], folder_task))
                else:
                    name: str = content.get('name', 'Unknown')
                    url_val: str | None = content.get('url') or content.get('thumbnailUrl')
                    thumbnail: str | None = content.get('thumbnailUrl', '')
                    if not batch_thumbnail and thumbnail:
                        batch_thumbnail = thumbnail
                    content_type = 'video' if url_val and (url_val.endswith('m3u8') or 'video' in url_val.lower()) else 'pdf' if url_val and url_val.endswith('.pdf') else 'image'
                    if not url_val:
                        logging.warning(f"No URL found for content: {name}")
                        continue
                    if "media-cdn.classplusapp.com/tencent/" in url_val:
                        url_val = url_val.rsplit('/', 1)[0] + "/master.m3u8"
                    elif "media-cdn.classplusapp.com" in url_val and url_val.endswith('.jpg'):
                        identifier = url_val.split('/')[-3]
                        url_val = f'https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/{identifier}/master.m3u8'
                    elif "tencdn.classplusapp.com" in url_val and url_val.endswith('.jpg'):
                        identifier = url_val.split('/')[-2]
                        url_val = f'https://media-cdn.classplusapp.com/tencent/{identifier}/master.m3u8'
                    elif "4b06bf8d61c41f8310af9b2624459378203740932b456b07fcf817b737fbae27" in url_val and url_val.endswith('.jpeg'):
                        url_val = f"https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/b08bad9ff8d969639b2e43d5769342cc62b510c4345d2f7f153bec53be84fe35/{url_val.split('/')[-1].split('.')[0]}/master.m3u8"
                    elif "cpvideocdn.testbook.com" in url_val and url_val.endswith('.png'):
                        match = re.search(r'/streams/([a-f0-9]{24})/', url_val)
                        video_id = match.group(1) if match else url_val.split('/')[-2]
                        url_val = f'https://cpvod.testbook.com/{video_id}/playlist.m3u8'
                    elif "media-cdn.classplusapp.com/drm/" in url_val and url_val.endswith('.png'):
                        video_id = url_val.split('/')[-3]
                        url_val = f'https://media-cdn.classplusapp.com/drm/{video_id}/playlist.m3u8'
                    elif "https://media-cdn.classplusapp.com" in url_val and ("cc/" in url_val or "lc/" in url_val or "uc/" in url_val or "dy/" in url_val) and url_val.endswith('.png'):
                        url_val = url_val.replace('thumbnail.png', 'master.m3u8')
                    elif "https://tb-video.classplusapp.com" in url_val and url_val.endswith('.jpg'):
                        video_id = url_val.split('/')[-1].split('.')[0]
                        url_val = f'https://tb-video.classplusapp.com/{video_id}/master.m3u8'
                    if url_val.endswith(("master.m3u8", "playlist.m3u8")) and url_val not in fetched_urls:
                        fetched_urls.add(url_val)
                        headers2 = {'x-access-token': 'eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9'}
                        task = asyncio.create_task(process_cpwp_url(url_val, name, content_type, thumbnail, session, headers2))
                        content_tasks.append((content['id'], task))
                    else:
                        if url_val and url_val not in fetched_urls:
                            fetched_urls.add(url_val)
                            results.append({
                                "name": name,
                                "url": url_val,
                                "type": content_type,
                                "thumbnail": thumbnail,
                                "folder_path": folder_path,
                                "subfolder_name": subfolder_name
                            })
                            if content_type == 'pdf':
                                pdf_count += 1
                            elif content_type == 'image':
                                image_count += 1
    except Exception as e:
        logging.exception(f"Unexpected error in get_cpwp_course_content: {e}")
        if retry_count < MAX_RETRIES:
            logging.info(f"Retrying folder {folder_id} (Attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(2 ** retry_count)
            return await get_cpwp_course_content(session, headers, batch_token, folder_id, limit, retry_count + 1, folder_path, subfolder_name)
        else:
            logging.error(f"Failed to retrieve folder {folder_id} after {MAX_RETRIES} retries.")
            return [], 0, 0, 0, ""
    content_results = await asyncio.gather(*(task for _, task in content_tasks), return_exceptions=True)
    folder_results = await asyncio.gather(*(task for _, task in folder_tasks), return_exceptions=True)
    for _, result in zip(content_tasks, content_results):
        if isinstance(result, Exception):
            logging.error(f"Task failed with exception: {result}")
        elif result:
            results.append({
                "name": result["name"],
                "url": result["url"],
                "type": result["type"],
                "thumbnail": result["thumbnail"],
                "folder_path": folder_path,
                "subfolder_name": subfolder_name
            })
            video_count += 1
    for folder_id, folder_result in folder_tasks:
        try:
            nested_results, nested_video_count, nested_pdf_count, nested_image_count, nested_thumbnail = await folder_result
            if nested_results:
                results.extend(nested_results)
            video_count += nested_video_count
            pdf_count += nested_pdf_count
            image_count += nested_image_count
            if nested_thumbnail and not batch_thumbnail:
                batch_thumbnail = nested_thumbnail
        except Exception as e:
            logging.error(f"Error processing folder {folder_id}: {e}")
    return results, video_count, pdf_count, image_count, batch_thumbnail

async def process_cpwp(bot: Client, m: Message, user_id: int):
    headers = {
        'accept-encoding': 'gzip',
        'accept-language': 'EN',
        'api-version': '35',
        'app-version': '1.4.73.2',
        'build-number': '35',
        'connection': 'Keep-Alive',
        'content-type': 'application/json',
        'device-details': 'Xiaomi_Redmi 7_SDK-32',
        'device-id': 'c28d3cb16bbdac01',
        'host': 'api.classplusapp.com',
        'region': 'IN',
        'user-agent': 'Mobile-Android',
        'webengage-luid': '00000187-6fe4-5d41-a530-26186858be4c'
    }
    loop = asyncio.get_event_loop()
    CONNECTOR = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=CONNECTOR, loop=loop) as session:
        try:
            editable = await m.reply_text("📥 **Enter ORG Code of Your Classplus App** 🔑")
            try:
                input1 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                org_code = input1.text.lower().strip()
                if not org_code or not re.match(r'^[a-zA-Z0-9]+$', org_code):
                    raise ValueError("Invalid ORG Code. Please enter a valid alphanumeric code.")
                await input1.delete(True)
            except ListenerTimeout:
                await editable.edit("⏰ *Timeout! You took too long to respond.*")
                return
            except ValueError as ve:
                await editable.edit(f"❌ *Error: {ve}*")
                return
            except Exception as e:
                logging.exception(f"Error during input1 listening: {e}")
                await editable.edit(f"❌ *Error: {e}*")
                return
            hash_headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://qsvfn.courses.store/?mainCategory=0&subCatList=[130504,62442]',
                'Sec-CH-UA': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
            }
            async with session.get(f"https://{org_code}.courses.store", headers=hash_headers) as response:
                html_text = await response.text()
                hash_match = re.search(r'"hash":"(.*?)"', html_text)
                if hash_match:
                    token = hash_match.group(1)
                    async with session.get(f"https://api.classplusapp.com/v2/course/preview/similar/{token}?limit=999999", headers=headers) as response:
                        if response.status == 200:
                            res_json = await response.json()
                            courses = res_json.get('data', {}).get('coursesData', [])
                            logging.info(f"API response for courses: {json.dumps(res_json, indent=2)}")
                            if courses:
                                courses_file = f"@SEM2JOB_{org_code}_courses_list.txt"
                                with open(courses_file, 'w', encoding='utf-8') as f:
                                    f.write("List of Courses 📑\n")
                                    f.write("====== BY : @SEM2JOB_SERVICE_BOT ===== \n\n")
                                    for cnt, course in enumerate(courses, 1):
                                        name = course.get('name', 'Unknown Course')
                                        course_id = course.get('id', 'N/A')
                                        price = course.get('finalPrice', 'N/A')
                                        description = course.get('description', 'No description available')
                                        f.write(f"{cnt}. 🌟 Name: {name}\n")
                                        f.write(f"🆔️ ID: {course_id}\n")
                                        f.write(f"💵 Price: ₹{price}\n")
                                        f.write(f"📝 Description: {description}\n")
                                        f.write("╾──• 🛍 Fᴏʀ Pᴜʀᴄʜᴀꜱᴇ Mꜱɢ Mᴇ: https://t.me/SEM2JOB •──╼\n")
                                await m.reply_document(
                                    document=courses_file,
                                    caption="📄 **List of all available courses** Extracted By : 〽️ @SEM2JOB",
                                    file_name=f"@SEM2JOB_{org_code}_courses_list.txt"
                                )
                                await send_to_log_channel(bot, user_id, m.from_user.username or "Unknown", "Courses list extracted.", courses_file)
                                os.remove(courses_file)
                                text = "📋 **Select a Course (Enter Index Number)**\n\n*Check the .txt file for course list.**\n\n**If your batch is not listed, enter the batch name.** any problem contact @SEM2JOB"
                                keyboard = [
                                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                                     InlineKeyboardButton("🔙 Back", callback_data="classplus_menu")]
                                ]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await editable.edit(text, reply_markup=reply_markup)
                                try:
                                    input2 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                                    raw_text2 = input2.text.strip()
                                    await input2.delete(True)
                                except ListenerTimeout:
                                    await editable.edit("⏰ *Timeout! You took too long to respond.*")
                                    return
                                except Exception as e:
                                    logging.exception(f"Error during input2 listening: {e}")
                                    await editable.edit(f"❌ *Error: {e}*")
                                    return
                                if raw_text2.isdigit() and 1 <= int(raw_text2) <= len(courses):
                                    selected_course_index = int(raw_text2)
                                    course = courses[selected_course_index - 1]
                                    selected_batch_id = course.get('id', 'N/A')
                                    selected_batch_name = course.get('name', 'Unknown Course')
                                    price = course.get('finalPrice', 'N/A')
                                    description = course.get('description', 'No description available')
                                    batch_thumbnail = course.get('imageUrl', DEFAULT_THUMBNAIL)
                                    clean_batch_name = clean_filename(selected_batch_name)
                                    clean_file_name = f"@SEM2JOB_{clean_batch_name}"
                                else:
                                    search_url = f"https://api.classplusapp.com/v2/course/preview/similar/{token}?search={raw_text2}"
                                    async with session.get(search_url, headers=headers) as response:
                                        if response.status == 200:
                                            res_json = await response.json()
                                            courses = res_json.get("data", {}).get("coursesData", [])
                                            logging.info(f"Search API response: {json.dumps(res_json, indent=2)}")
                                            if courses:
                                                text = '📋 **Select a Course (Enter Index Number)**\n\n'
                                                for cnt, course in enumerate(courses, 1):
                                                    name = course.get('name', 'Unknown Course')
                                                    course_id = course.get('id', 'N/A')
                                                    price = course.get('finalPrice', 'N/A')
                                                    if name == 'Unknown Course' or course_id == 'N/A':
                                                        logging.warning(f"Incomplete course data in search: {course}")
                                                    text += f"{cnt}. 🌟 `{name}` (🆔️ID: {course_id}, 💵₹{price})\n"
                                                keyboard = [
                                                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                                                     InlineKeyboardButton("🔙 Back", callback_data="classplus_menu")]
                                                ]
                                                reply_markup = InlineKeyboardMarkup(keyboard)
                                                text = shorten_caption(text, max_length=4096)
                                                await editable.edit(text, reply_markup=reply_markup)
                                                try:
                                                    input3 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                                                    raw_text3 = input3.text.strip()
                                                    await input3.delete(True)
                                                except ListenerTimeout:
                                                    await editable.edit("⏰ *Timeout! You took too long to respond.*")
                                                    return
                                                except Exception as e:
                                                    logging.exception(f"Error during input3 listening: {e}")
                                                    await editable.edit(f"❌ *Error: {e}*")
                                                    return
                                                if raw_text3.isdigit() and 1 <= int(raw_text3) <= len(courses):
                                                    selected_course_index = int(raw_text3)
                                                    course = courses[selected_course_index - 1]
                                                    selected_batch_id = course.get('id', 'N/A')
                                                    selected_batch_name = course.get('name', 'Unknown Course')
                                                    price = course.get('finalPrice', 'N/A')
                                                    description = course.get('description', 'No description available')
                                                    batch_thumbnail = course.get('imageUrl', DEFAULT_THUMBNAIL)
                                                    clean_batch_name = clean_filename(selected_batch_name)
                                                    clean_file_name = f"@SEM2JOB_{clean_batch_name}"
                                                else:
                                                    raise Exception("Wrong Index Number")
                                            else:
                                                raise Exception("Didn't Find Any Course Matching The Search Term")
                                        else:
                                            raise Exception(f"API Error: {response.text}")
                                batch_headers = {
                                    'Accept': 'application/json, text/plain, */*',
                                    'region': 'IN',
                                    'accept-language': 'EN',
                                    'Api-Version': '22',
                                    'tutorWebsiteDomain': f'https://{org_code}.courses.store'
                                }
                                params = {'courseId': f'{selected_batch_id}'}
                                async with session.get(f"https://api.classplusapp.com/v2/course/preview/org/info", params=params, headers=batch_headers) as response:
                                    if response.status == 200:
                                        res_json = await response.json()
                                        logging.info(f"Org info API response: {json.dumps(res_json, indent=2)}")
                                        Batch_Token = res_json.get('data', {}).get('hash', '')
                                        App_Name = res_json.get('data', {}).get('name', 'Polytechnic Academy')
                                        if not Batch_Token or not App_Name:
                                            logging.error(f"Missing Batch_Token or App_Name: {res_json}")
                                            raise Exception("Failed to retrieve Batch Token or App Name")
                                        await editable.edit(f"⚙️ **Extracting course:** 📤 `{selected_batch_name}` ...")
                                        start_time = time.time()
                                        course_content, video_count, pdf_count, image_count, _ = await get_cpwp_course_content(session, headers, Batch_Token)
                                        if course_content:
                                            file = f"{clean_file_name}.txt"
                                            with open(file, 'w', encoding='utf-8') as f:
                                                for item in course_content:
                                                    folder_path = item['folder_path']
                                                    subfolder_name = item['subfolder_name']
                                                    path = f"{folder_path} > " if folder_path and subfolder_name else folder_path or subfolder_name
                                                    f.write(f"[@SEM2JOB] > {path} > {item['name']}: {item['url']}\n")
                                            end_time = time.time()
                                            response_time = end_time - start_time
                                            minutes = int(response_time // 60)
                                            seconds = int(response_time % 60)
                                            formatted_time = f"{minutes} minutes {seconds} seconds" if minutes > 0 else f"{seconds} seconds"
                                            await editable.delete(True)
                                            caption = shorten_caption(
                                                f"**╾──• ✅ FULL COURSE AVAILABLE ✅️ •──╼**\n\n"
                                                f"**📲 APP NAME**: {App_Name}** ( `{org_code}` )\n\n ======= 🪪 BATCH DETAILS 🪪 =======\n\n"
                                                f"**📩 BATCH NAME**: `{selected_batch_name}`\n"
                                                f"**🆔️ BATCH ID**: `{selected_batch_id}`\n"
                                                f"**💵 PRICE**: ₹{price}\n\n"
                                                f"**📝 DESCRIPTION**: _{description}_\n\n╭━ ===📁 TOTAL CONTENT ⤵️\n"
                                                f"┠  ├🎬 VIDEO : {video_count}\n"
                                                f"┠  ├ 📕PDF :  {pdf_count}\n"
                                                f"┠ -dotenv"
                                                f"╰┈➤ 〽️Owner:  @SEM2JOB_SERVICE_BOT\n\n **╾──• 🛍 Fᴏʀ Pᴜʀᴄʜᴀꜱᴇ Mꜱɢ Mᴇ: @SEM2JOB •──╼**"
                                            )
                                            course_list_text = (
                                                f"📋 **Course Details Provided By 🪪 @SEM2JOB** 📚\n\n"
                                                f"** 📲 App Name**: `{App_Name}` ({org_code})\n"
                                                f"** 📩 Batch Name**: `{selected_batch_name}`\n"
                                                f"** 🆔️ Batch ID**: `{selected_batch_id}`\n"
                                                f"** 💵 Price**: ₹{price}\n"
                                                f"** 📝 Description**: _{description}_\n"
                                                f"** 🎬 Videos**: {video_count}\n"
                                                f"** 📕 PDFs:** {pdf_count}\n"
                                                f"** 🖼️ Images :** {image_count}\n"
                                                f"⏱️ *Time Taken*: {formatted_time}"
                                            )
                                            is_premium = user_id in get_auth_users()
                                            if batch_thumbnail and await is_valid_url(session, batch_thumbnail):
                                                await m.reply_photo(
                                                    photo=batch_thumbnail,
                                                    caption=caption
                                                )
                                            else:
                                                logging.warning(f"Using default thumbnail for {selected_batch_name}")
                                                await m.reply_photo(
                                                    photo=DEFAULT_THUMBNAIL,
                                                    caption=caption
                                                )
                                            await m.reply_text(course_list_text)
                                            await send_to_log_channel(bot, user_id, m.from_user.username or "Unknown", caption, file if is_premium else file)
                                            if is_premium:
                                                txt_caption = shorten_caption(
                                                    f"✅ **YOUR TXT EXTRACTED SUCCESSFULLY**\n\n"
                                                    f"**📲 App Name**: `{App_Name}` ({org_code})\n"
                                                    f"**📩 Batch Name**: `{selected_batch_name}`\n"
                                                    f"**🆔️ Batch ID**: `{selected_batch_id}`\n"
                                                    f"**🎬 Videos : ** {video_count}\n"
                                                    f"**📕 PDFs :** {pdf_count}\n"
                                                    f"**🖼️ Images :** {image_count}\n"
                                                    f"**👨‍💻Extracted By : @SEM2JOB_SERVICE_BOT** "
                                                )
                                                with open(file, 'rb') as f:
                                                    await m.reply_document(
                                                        document=f,
                                                        caption=txt_caption,
                                                        file_name=f"@SEM2JOB_{clean_batch_name}.txt"
                                                    )
                                            else:
                                                await m.reply_text(
                                                    "❌ **Limited Access**\nYou are a free user. To download .txt files, upgrade to Premium!\nContact: @SEM2JOB",
                                                    reply_markup=InlineKeyboardMarkup([
                                                        [InlineKeyboardButton("💎 Upgrade to Premium", url="https://t.me/SEM2JOB")]
                                                    ])
                                                )
                                            os.remove(file)
                                        else:
                                            raise Exception(f"No content found for course Sorry brother 😒: {selected_batch_name}")
                                    else:
                                        raise Exception(f"API Error: {response.text}")
                        else:
                            raise Exception("Didn't Find Any Course")
                else:
                    raise Exception("Invalid ORG Code")
        except Exception as e:
            keyboard = [
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                 InlineKeyboardButton("🔙 Back", callback_data="classplus_menu")]
            ]
            await editable.edit(f"❌ *Error: {e}*", reply_markup=InlineKeyboardMarkup(keyboard))
        finally:
            await session.close()
            await CONNECTOR.close()

async def process_extract_all(bot: Client, m: Message, user_id: int):
    headers = {
        'accept-encoding': 'gzip',
        'accept-language': 'EN',
        'api-version': '35',
        'app-version': '1.4.73.2',
        'build-number': '35',
        'connection': 'Keep-Alive',
        'content-type': 'application/json',
        'device-details': 'Xiaomi_Redmi 7_SDK-32',
        'device-id': 'c28d3cb16bbdac01',
        'host': 'api.classplusapp.com',
        'region': 'IN',
        'user-agent': 'Mobile-Android',
        'webengage-luid': '00000187-6fe4-5d41-a530-26186858be4c'
    }
    loop = asyncio.get_event_loop()
    CONNECTOR = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=CONNECTOR, loop=loop) as session:
        try:
            editable = await m.reply_text("📥 **Enter ORG Code of Your Classplus App** 🔑")
            try:
                input1 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                org_code = input1.text.lower().strip()
                if not org_code or not re.match(r'^[a-zA-Z0-9]+$', org_code):
                    raise ValueError("Invalid ORG Code. Please enter a valid alphanumeric code.")
                await input1.delete(True)
            except ListenerTimeout:
                await editable.edit("⏰ *Timeout! You took too long to respond.*")
                return
            except ValueError as ve:
                await editable.edit(f"❌ *Error: {ve}*")
                return
            except Exception as e:
                logging.exception(f"Error during input1 listening: {e}")
                await editable.edit(f"❌ *Error: {e}*")
                return
            hash_headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://qsvfn.courses.store/?mainCategory=0&subCatList=[130504,62442]',
                'Sec-CH-UA': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
            }
            async with session.get(f"https://{org_code}.courses.store", headers=hash_headers) as response:
                html_text = await response.text()
                hash_match = re.search(r'"hash":"(.*?)"', html_text)
                if hash_match:
                    token = hash_match.group(1)
                    await editable.edit("🔄 **Fetching all courses ...plz wait brother 😊**")
                    async with session.get(f"https://api.classplusapp.com/v2/course/preview/similar/{token}?limit=999999", headers=headers) as response:
                        if response.status == 200:
                            res_json = await response.json()
                            courses = res_json.get('data', {}).get('coursesData', [])
                            logging.info(f"All courses API response: {json.dumps(res_json, indent=2)}")
                            if courses:
                                courses_file = f"@SEM2JOB_{org_code}_all_courses.txt"
                                with open(courses_file, 'w', encoding='utf-8') as f:
                                    f.write("📚 List of All Courses \n")
                                    f.write("======== Extracted By : @SEM2JOB======\n\n")
                                    for idx, course in enumerate(courses, 1):
                                        name = course.get('name', 'Unknown Course')
                                        course_id = course.get('id', 'N/A')
                                        price = course.get('finalPrice', 'N/A')
                                        description = course.get('description', 'No description available')
                                        f.write(f"{idx}. Name: {name}\n")
                                        f.write(f"ID: {course_id}\n")
                                        f.write(f"Price: ₹{price}\n")
                                        f.write(f"Description: {description}\n")
                                        f.write("╾──• 🛍 Fᴏʀ Pᴜʀᴄʜᴀꜱᴇ Mꜱɢ Mᴇ: https://t.me/SEM2JOB •──╼\n")
                                await m.reply_document(
                                    document=courses_file,
                                    caption="📄 *List of all courses with their Batch IDs and Details/n\n Provided By: @SEM2JOB*",
                                    file_name=f"@SEM2JOB_{org_code}_all_courses.txt"
                                )
                                await send_to_log_channel(bot, user_id, m.from_user.username or "Unknown", "All courses list extracted.", courses_file)
                                os.remove(courses_file)
                                await editable.edit("⚙️ **Extracting content for all courses, this may take a while..smjhe boss 😊.**")
                                is_premium = user_id in get_auth_users()
                                for course in courses:
                                    try:
                                        selected_batch_id = course.get('id', 'N/A')
                                        selected_batch_name = course.get('name', 'Unknown Course')
                                        price = course.get('finalPrice', 'N/A')
                                        description = course.get('description', 'No description available')
                                        batch_thumbnail = course.get('imageUrl', DEFAULT_THUMBNAIL)
                                        clean_batch_name = clean_filename(selected_batch_name)
                                        clean_file_name = f"@SEM2JOB_{clean_batch_name}"
                                        batch_headers = {
                                            'Accept': 'application/json, text/plain, */*',
                                            'region': 'IN',
                                            'accept-language': 'EN',
                                            'Api-Version': '22',
                                            'tutorWebsiteDomain': f'https://{org_code}.courses.store'
                                        }
                                        params = {'courseId': f'{selected_batch_id}'}
                                        async with session.get(f"https://api.classplusapp.com/v2/course/preview/org/info", params=params, headers=batch_headers) as batch_response:
                                            if batch_response.status == 200:
                                                batch_json = await batch_response.json()
                                                logging.info(f"Batch info API response for {selected_batch_name}: {json.dumps(batch_json, indent=2)}")
                                                Batch_Token = batch_json.get('data', {}).get('hash', '')
                                                App_Name = batch_json.get('data', {}).get('name', 'Polytechnic Academy')
                                                if not Batch_Token:
                                                    logging.error(f"No Batch Token for {selected_batch_name}")
                                                    continue
                                                await editable.edit(f"**⚙️Extracting: 📤** `{selected_batch_name}`")
                                                start_time = time.time()
                                                course_content, video_count, pdf_count, image_count, _ = await get_cpwp_course_content(session, headers, Batch_Token)
                                                if course_content:
                                                    file = f"@SEM2JOB_{clean_file_name}.txt"
                                                    with open(file, 'w', encoding='utf-8') as f:
                                                        for item in course_content:
                                                            folder_path = item['folder_path']
                                                            subfolder_name = item['subfolder_name']
                                                            path = f"{folder_path} > {subfolder_name}" if folder_path and subfolder_name else folder_path or subfolder_name
                                                            f.write(f"[@SEM2JOB] > {path} > {item['name']}: {item['url']}\n")
                                                    end_time = time.time()
                                                    response_time = end_time - start_time
                                                    minutes = int(response_time // 60)
                                                    seconds = int(response_time % 60)
                                                    formatted_time = f"{minutes} minutes {seconds} seconds" if minutes > 0 else f"{seconds} seconds"
                                                    caption = shorten_caption(
                                                        f"**╾──• ✅ FULL COURSE AVAILABLE ✅️ •──╼**\n\n"
                                                        f"**📲 APP NAME**: {App_Name}** ( `{org_code}` )\n\n ======= 🪪 BATCH DETAILS 🪪 =======\n\n"
                                                        f"**📩 BATCH NAME**: `{selected_batch_name}`\n"
                                                        f"**🆔️ BATCH ID**: `{selected_batch_id}`\n"
                                                        f"**💵 PRICE**: ₹{price}\n\n"
                                                        f"**📝 DESCRIPTION**: __{description}__\n\n╭━ ===📁 TOTAL CONTENT ⤵️\n"
                                                        f"┠  ├🎬 VIDEO : {video_count}\n"
                                                        f"┠  ├ 📕PDF :  {pdf_count}\n"
                                                        f"┠  └🖼 IMAGE : {image_count}\n"
                                                        f"╰┈➤ 〽️Owner:  @SEM2JOB_SERVICE_BOT\n\n**╾──• 🛍 Fᴏʀ Pᴜʀᴄʜᴀꜱᴇ Mꜱɢ Mᴇ: @SEM2JOB •──╼**"
                                                    )
                                                    course_list_text = (
                                                        f"📋 **Course Details Provided By 🪪 @SEM2JOB** 📚\n\n"
                                                        f"** 📲 App Name**: `{App_Name}` ({org_code})\n"
                                                        f"** 📩 Batch Name**: `{selected_batch_name}`\n"
                                                        f"** 🆔️ Batch ID**: `{selected_batch_id}`\n"
                                                        f"** 💵 Price**: ₹{price}\n"
                                                        f"** 📝 Description**: _{description}_\n"
                                                        f"** 🎬 Videos**: {video_count}\n"
                                                        f"** 📕 PDFs:** {pdf_count}\n"
                                                        f"** 🖼️ Images :** {image_count}\n"
                                                        f"⏱️ *Time Taken*: {formatted_time}"
                                                    )
                                                    if batch_thumbnail and await is_valid_url(session, batch_thumbnail):
                                                        await m.reply_photo(
                                                            photo=batch_thumbnail,
                                                            caption=caption
                                                        )
                                                    else:
                                                        logging.warning(f"Using default thumbnail for {selected_batch_name}")
                                                        await m.reply_photo(
                                                            photo=DEFAULT_THUMBNAIL,
                                                            caption=caption
                                                        )
                                                    await m.reply_text(course_list_text)
                                                    await send_to_log_channel(bot, user_id, m.from_user.username or "Unknown", caption, file if is_premium else file)
                                                    if is_premium:
                                                        txt_caption = shorten_caption(
                                                            f"✅ **YOUR TXT EXTRACTED SUCCESSFULLY**\n\n"
                                                            f"**📲 App Name**: `{App_Name}` ({org_code})\n"
                                                            f"**📩 Batch Name**: `{selected_batch_name}`\n"
                                                            f"**🆔️ Batch ID**: `{selected_batch_id}`\n"
                                                            f"**🎬 Videos : ** {video_count}\n"
                                                            f"**📕 PDFs :** {pdf_count}\n"
                                                            f"**🖼️ Images :** {image_count}\n"
                                                            f"**👨‍💻Extracted By : @SEM2JOB_SERVICE_BOT** "
                                                        )
                                                        with open(file, 'rb') as f:
                                                            await m.reply_document(
                                                                document=f,
                                                                caption=txt_caption,
                                                                file_name=f"@SEM2JOB_{clean_batch_name}.txt"
                                                            )
                                                    else:
                                                        await m.reply_text(
                                                            "❌ **Limited Access**\nYou are a free user. To download .txt files, upgrade to Premium!\nContact: @SEM2JOB",
                                                            reply_markup=InlineKeyboardMarkup([
                                                                [InlineKeyboardButton("💎 Upgrade to Premium", url="https://t.me/SEM2JOB")]
                                                            ])
                                                        )
                                                    os.remove(file)
                                                else:
                                                    await m.reply_text(f"❌ *No content found for course: `{selected_batch_name}`*")
                                            else:
                                                await m.reply_text(f"❌ *Failed to fetch Batch Token for course: `{selected_batch_name}`*")
                                    except Exception as e:
                                        logging.error(f"Error processing course {selected_batch_name}: {e}")
                                        await m.reply_text(f"❌ *Error processing `{selected_batch_name}`: {e}*")
                                        continue
                            else:
                                await editable.edit("❌ *No courses found*")
                        else:
                            await editable.edit(f"❌ *Error fetching courses: {response.text}*")
                else:
                    await editable.edit("❌ *No App Found for ORG Code*")
        except Exception as e:
            keyboard = [
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                 InlineKeyboardButton("🔙 Back", callback_data="classplus_menu")]
            ]
            await editable.edit(f"❌ *Error: {e}*", reply_markup=InlineKeyboardMarkup(keyboard))
        finally:
            await session.close()
            await CONNECT.close()

# --- Physics Wallah Functions ---
async def fetch_pwwp_data(session: aiohttp.ClientSession, url: str, headers: Dict = None, params: Dict = None, data: Dict = None, method: str = 'GET') -> Any:
    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with session.request(method, url, headers=headers, params=params, json=data) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"Attempt {attempt + 1} failed: aiohttp error fetching {url}: {e}")
        except Exception as e:
            logging.exception(f"Attempt {attempt + 1} failed: Unexpected error fetching {url}: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
    logging.error(f"Failed to fetch {url} after {max_retries} attempts.")
    return None

async def process_pwwp_chapter_content(session: aiohttp.ClientSession, chapter_id, selected_batch_id, subject_id, schedule_id, content_type, headers: Dict, batch_thumbnail: str) -> Dict:
    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers=headers)
    content = []
    if data and data.get("success") and data.get("data"):
        data_item = data["data"]
        if content_type in ("videos", "DppVideos"):
            video_details = data_item.get('videoDetails', {})
            if video_details:
                name = data_item.get('topic', '')
                video_url = video_details.get('videoUrl') or video_details.get('embedCode') or ""
                thumbnail = video_details.get('image', '') or batch_thumbnail
                if video_url:
                    content.append({"name": name, "url": video_url, "type": content_type, "thumbnail": thumbnail})
        elif content_type in ("notes", "DppNotes"):
            homework_ids = data_item.get('homeworkIds', [])
            for homework in homework_ids:
                attachment_ids = homework.get('attachmentIds', [])
                name = homework.get('topic', '')
                for attachment in attachment_ids:
                    url = attachment.get('baseUrl', '') + attachment.get('key', '')
                    if url:
                        content.append({"name": name, "url": url, "type": content_type, "thumbnail": batch_thumbnail})
        return {content_type: content} if content else {}
    else:
        logging.warning(f"No Data Found For Id - {schedule_id}")
        return {}

async def fetch_pwwp_all_schedule(session: aiohttp.ClientSession, chapter_id, selected_batch_id, subject_id, content_type, headers: Dict) -> List[Dict]:
    all_schedule = []
    page = 1
    while True:
        params = {
            'tag': chapter_id,
            'contentType': content_type,
            'page': page
        }
        url = f"https://api.penpencil.co/v2/batches/{selected_batch_id}/subject/{subject_id}/contents"
        data = await fetch_pwwp_data(session, url, headers=headers, params=params)
        if data and data.get("success") and data.get("data"):
            for item in data["data"]:
                item['content_type'] = content_type
                all_schedule.append(item)
            page += 1
        else:
            break
    return all_schedule

async def process_pwwp_chapters(session: aiohttp.ClientSession, chapter_id, selected_batch_id, subject_id, headers: Dict, batch_thumbnail: str):
    content_types = ['videos', 'notes', 'DppNotes', 'DppVideos']
    all_schedule_tasks = [fetch_pwwp_all_schedule(session, chapter_id, selected_batch_id, subject_id, content_type, headers) for content_type in content_types]
    all_schedules = await asyncio.gather(*all_schedule_tasks)
    all_schedule = []
    for schedule in all_schedules:
        all_schedule.extend(schedule)
    content_tasks = [
        process_pwwp_chapter_content(session, chapter_id, selected_batch_id, subject_id, item["_id"], item['content_type'], headers, batch_thumbnail)
        for item in all_schedule
    ]
    content_results = await asyncio.gather(*content_tasks)
    combined_content = {}
    for result in content_results:
        if result:
            for content_type, content_list in result.items():
                if content_type not in combined_content:
                    combined_content[content_type] = []
                combined_content[content_type].extend(content_list)
    return combined_content

async def get_pwwp_all_chapters(session: aiohttp.ClientSession, selected_batch_id, subject_id, headers: Dict):
    all_chapters = []
    page = 1
    while True:
        url = f"https://api.penpencil.co/v2/batches/{selected_batch_id}/subject/{subject_id}/topics?page={page}"
        data = await fetch_pwwp_data(session, url, headers=headers)
        if data and data.get("data"):
            chapters = data["data"]
            all_chapters.extend(chapters)
            page += 1
        else:
            break
    return all_chapters

async def process_pwwp_subject(session: aiohttp.ClientSession, subject: Dict, selected_batch_id: str, selected_batch_name: str, zipf: zipfile.ZipFile, json_data: Dict, all_subject_urls: Dict[str, List[Dict]], headers: Dict, batch_thumbnail: str):
    subject_name = subject.get("subject", "Unknown Subject").replace("/", "-")
    subject_id = subject.get("_id")
    json_data[selected_batch_name][subject_name] = {}
    zipf.writestr(f"{subject_name}/", "")
    chapters = await get_pwwp_all_chapters(session, selected_batch_id, subject_id, headers)
    chapter_tasks = []
    for chapter in chapters:
        chapter_name = chapter.get("name", "Unknown Chapter").replace("/", "-")
        zipf.writestr(f"{subject_name}/{chapter_name}/", "")
        json_data[selected_batch_name][subject_name][chapter_name] = {}
        chapter_tasks.append(process_pwwp_chapters(session, chapter["_id"], selected_batch_id, subject_id, headers, batch_thumbnail))
    chapter_results = await asyncio.gather(*chapter_tasks)
    all_urls = []
    for chapter, chapter_content in zip(chapters, chapter_results):
        chapter_name = chapter.get("name", "Unknown Chapter").replace("/", "-")
        for content_type in ['videos', 'notes', 'DppNotes', 'DppVideos']:
            if chapter_content.get(content_type):
                content = chapter_content[content_type]
                content.reverse()
                content_string = ""
                for item in content:
                    content_string += f"[@SEM2JOB/{subject_name}/{chapter_name}] {content_type.capitalize()} > {item['name']}: {item['url']}\n"
                zipf.writestr(f"{subject_name}/{chapter_name}/{content_type}.txt", content_string.encode('utf-8'))
                json_data[selected_batch_name][subject_name][chapter_name][content_type] = content
                all_urls.extend(content)
    all_subject_urls[subject_name] = all_urls

def find_pw_old_batch(batch_search):
    try:
        response = requests.get(f"https://abhiguru143.github.io/AS-MULTIVERSE-PW/batch/batch.json")
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data: {e}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {e}")
        return []
    matching_batches = []
    for batch in data:
        if batch_search.lower() in batch['batch_name'].lower():
            matching_batches.append(batch)
    return matching_batches

async def get_pwwp_todays_schedule_content_details(session: aiohttp.ClientSession, selected_batch_id, subject_id, schedule_id, headers: Dict, batch_thumbnail: str) -> List[Dict]:
    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers)
    content = []
    if data and data.get("success") and data.get("data"):
        data_item = data["data"]
        video_details = data_item.get('videoDetails', {})
        if video_details:
            name = data_item.get('topic')
            video_url = video_details.get('videoUrl') or video_details.get('embedCode')
            thumbnail = video_details.get('image', '') or batch_thumbnail
            if video_url:
                content.append({"name": name, "url": video_url, "type": "video", "thumbnail": thumbnail})
        homework_ids = data_item.get('homeworkIds', [])
        for homework in homework_ids:
            attachment_ids = homework.get('attachmentIds', [])
            name = homework.get('topic')
            for attachment in attachment_ids:
                url = attachment.get('baseUrl', '') + attachment.get('key', '')
                if url:
                    content.append({"name": name, "url": url, "type": "notes", "thumbnail": batch_thumbnail})
        dpp = data_item.get('dpp')
        if dpp:
            dpp_homework_ids = dpp.get('homeworkIds', [])
            for homework in dpp_homework_ids:
                attachment_ids = homework.get('attachmentIds', [])
                name = homework.get('topic')
                for attachment in attachment_ids:
                    url = attachment.get('baseUrl', '') + attachment.get('key', '')
                    if url:
                        content.append({"name": name, "url": url, "type": "DppNotes", "thumbnail": batch_thumbnail})
    else:
        logging.warning(f"No Data Found For Id - {schedule_id}")
    return content

async def get_pwwp_all_todays_schedule_content(session: aiohttp.ClientSession, selected_batch_id: str, headers: Dict, batch_thumbnail: str) -> List[Dict]:
    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/todays-schedule"
    todays_schedule_details = await fetch_pwwp_data(session, url, headers)
    all_content = []
    if todays_schedule_details and todays_schedule_details.get("success") and todays_schedule_details.get("data"):
        tasks = []
        for item in todays_schedule_details['data']:
            schedule_id = item.get('_id')
            subject_id = item.get('batchSubjectId')
            task = asyncio.create_task(get_pwwp_todays_schedule_content_details(session, selected_batch_id, subject_id, schedule_id, headers, batch_thumbnail))
            tasks.append(task)
        results = await asyncio.gather(*tasks)
        for result in results:
            all_content.extend(result)
    else:
        logging.warning("No today's schedule data found.")
    return all_content

async def send_to_log_channel(bot: Client, user_id: int, username: str, message: str, file_path: str = None):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Try to establish interaction with the channel by sending a test message
            if attempt == 0:
                try:
                    await bot.send_message(
                        chat_id=log_channel_id,
                        text="Initializing log channel interaction..."
                    )
                except Exception as init_error:
                    logging.warning(f"Failed to initialize log channel: {init_error}")
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    await bot.send_document(
                        chat_id=log_channel_id,
                        document=f,
                        caption=message
                    )
            else:
                await bot.send_message(
                    chat_id=log_channel_id,
                    text=message
                )
            return True
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed to send to log channel: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    logging.error(f"Failed to send to log channel after {max_retries} attempts.")
    return False

async def process_pwwp(bot: Client, m: Message, user_id: int):
    editable = await m.reply_text("🔑 **Enter Working Access Token** 🔐\n\n*OR*\n\n📱 **Enter Phone Number (10 digits)\n\n Any Problem contact ☎️ @SEM2JOB**")
    try:
        input1 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
        raw_text1 = input1.text.strip()
        await input1.delete(True)
    except ListenerTimeout:
        await editable.edit("⏰ *Timeout! You took too long to respond.*")
        return
    headers = {
        'Host': 'api.penpencil.co',
        'client-id': '5eb393ee95fab7468a79d189',
        'client-version': '1910',
        'user-agent': 'Mozilla/5.0 (Linux; Android 12; M2101K6P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36',
        'randomid': '72012511-256c-4e1c-b4c7-29d67136af37',
        'client-type': 'WEB',
        'content-type': 'application/json; charset=utf-8',
    }
    loop = asyncio.get_event_loop()
    CONNECTOR = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=CONNECTOR, loop=loop) as session:
        try:
            user_phone = ""
            user_name = ""
            if raw_text1.isdigit() and len(raw_text1) == 10:
                user_phone = raw_text1
                data = {
                    "username": user_phone,
                    "countryCode": "+91",
                    "organizationId": "5eb393ee95fab7468a79d189"
                }
                try:
                    async with session.post(f"https://api.penpencil.co/v1/users/get-otp?smsType=0", json=data, headers=headers) as response:
                        await response.read()
                except Exception as e:
                    await editable.edit(f"❌ *Error: {e}*")
                    return
                editable = await editable.edit("🔐 **Enter OTP You Received** 🔢")
                try:
                    input2 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    otp = input2.text.strip()
                    if not otp.isdigit() or len(otp) != 6:
                        raise ValueError("Invalid OTP. Please enter a 6-digit OTP.")
                    await input2.delete(True)
                except ListenerTimeout:
                    await editable.edit("⏰ *Timeout! You took too long to respond.*")
                    return
                except ValueError as ve:
                    await editable.edit(f"❌ *Error: {ve}*")
                    return
                payload = {
                    "username": user_phone,
                    "otp": otp,
                    "client_id": "system-admin",
                    "client_secret": "KjPXuAVfC5xbmgreETNMaL7z",
                    "grant_type": "password",
                    "organizationId": "5eb393ee95fab7468a79d189",
                    "latitude": 0,
                    "longitude": 0
                }
                try:
                    async with session.post(f"https://api.penpencil.co/v3/oauth/token", json=payload, headers=headers) as response:
                        res_json = await response.json()
                        access_token = res_json["data"]["access_token"]
                        user_name = res_json["data"].get("firstName", "") + " " + res_json["data"].get("lastName", "")
                        user_name = user_name.strip() or "Unknown"
                        login_caption = (
                            f"✅ **Physics Wallah Login Successful!** 🎉\n\n"
                            f"📱 **Mobile**: {user_phone}\n"
                            f"👤 **Name**: {user_name}\n"
                            f"*Save this Login Token for future use*:\n```\n{access_token}\n```"
                        )
                        await editable.edit(login_caption)
                        # Send login details to log channel
                        await send_to_log_channel(
                            bot,
                            user_id,
                            m.from_user.username or "Unknown",
                            login_caption
                        )
                        editable = await m.reply_text("📋 *Getting Batches In Your ID*")
                except Exception as e:
                    await editable.edit(f"❌ *Error: {e}*")
                    return
            else:
                access_token = raw_text1
            headers['authorization'] = f"Bearer {access_token}"
            params = {
                'mode': '1',
                'page': '1',
            }
            try:
                async with session.get(f"https://api.penpencil.co/v3/batches/all-purchased-batches", headers=headers, params=params) as response:
                    response.raise_for_status()
                    batches = (await response.json()).get("data", [])
            except Exception as e:
                await editable.edit("❌ *Login Failed! Token Expired*\nPlease enter a working token or login with phone number If any problem contact ☎️ @SEM2JOB.")
                return
            await editable.edit("📚 **Enter Your Batch Name (First see in official app) thanks @SEM2JOB**")
            try:
                input3 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                batch_search = input3.text.strip()
                if not batch_search:
                    raise ValueError("Batch name cannot be empty.")
                await input3.delete(True)
            except ListenerTimeout:
                await editable.edit("⏰ *Timeout! You took too long to respond.*")
                return
            except ValueError as ve:
                await editable.edit(f"❌ *Error: {ve}*")
                return
            url = f"https://api.penpencil.co/v3/batches/search?name={batch_search}"
            courses = await fetch_pwwp_data(session, url, headers)
            courses = courses.get("data", []) if courses else []
            selected_batches = []
            if courses:
                text = '📋 **Select a Course (Enter Index Number)**\n\n'
                for cnt, course in enumerate(courses, 1):
                    name = course['name']
                    text += f"{cnt}. 🌟 `{name}`\n"
                text += '\n*If your batch is not listed, enter "No"*\n\n'
                text += '✅️To download a specific course, send its index number or\n'
                text += '📇 To download multiple courses, send indices like this: 2&5&7\n'
                text += '〽️ To download all courses, send "all"'
                await editable.edit(text)
                try:
                    input4 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    raw_text4 = input4.text.strip()
                    await input4.delete(True)
                except ListenerTimeout:
                    await editable.edit("⏰ *Timeout! You took too long to respond.*")
                    return
                if raw_text4.lower() == "all":
                    selected_batches = courses
                elif "&" in raw_text4:
                    indices = []
                    for i in raw_text4.split("&"):
                        if i.isdigit() and 1 <= int(i) <= len(courses):
                            indices.append(int(i))
                    selected_batches = [courses[i - 1] for i in indices if i - 1 < len(courses)]
                elif raw_text4.isdigit() and 1 <= int(raw_text4) <= len(courses):
                    selected_batches = [courses[int(raw_text4) - 1]]
                elif raw_text4.lower() == "no":
                    courses = find_pw_old_batch(batch_search)
                    if courses:
                        text = '📋 **Select a Course (Enter Index Number)**\n\n'
                        for cnt, course in enumerate(courses, 1):
                            name = course['batch_name']
                            text += f"{cnt}. 🗂 `{name}`\n"
                        await editable.edit(text)
                        try:
                            input5 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                            raw_text5 = input5.text.strip()
                            await input5.delete(True)
                        except ListenerTimeout:
                            await editable.edit("⏰ *Timeout! You took too long to respond.*")
                            return
                        if raw_text5.isdigit() and 1 <= int(raw_text5) <= len(courses):
                            selected_batches = [courses[int(raw_text5) - 1]]
                        else:
                            raise Exception("Invalid batch index.")
                    else:
                        raise Exception("No old batches found.")
                else:
                    raise Exception("Invalid input. Please enter a valid index, indices (e.g., 2&5&7), 'all', or 'No'.")
                await editable.edit("📋 **Select an Option**\n\n1. `🎯 Full Batch`\n2. `📆 Today's Class`\n3. `💼 Khazana`")
                try:
                    input6 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    raw_text6 = input6.text.strip()
                    await input6.delete(True)
                except ListenerTimeout:
                    await editable.edit("⏰ *Timeout! You took too long to respond.*")
                    return
                is_premium = user_id in get_auth_users()
                for course in selected_batches:
                    try:
                        selected_batch_id = course.get('_id', course.get('batch_id'))
                        selected_batch_name = course.get('name', course.get('batch_name', 'Unknown Batch'))
                        clean_batch_name = clean_filename(selected_batch_name)
                        clean_file_name = f"@SEM2JOB_{clean_batch_name}"
                        # Create new editable message for each batch
                        editable = await m.reply_text(f"⚙️ **Extracting course:** `{selected_batch_name}` ...")
                        await asyncio.sleep(0.5)  # Delay to avoid API rate limiting
                        start_time = time.time()
                        content_list = []
                        video_count = 0
                        pdf_count = 0
                        image_count = 0
                        batch_thumbnail = ""
                        if raw_text6 == '1':
                            url = f"https://api.penpencil.co/v3/batches/{selected_batch_id}/details"
                            batch_details = await fetch_pwwp_data(session, url, headers=headers)
                            if batch_details and batch_details.get("success"):
                                subjects = batch_details.get("data", {}).get("subjects", [])
                                batch_thumbnail = batch_details.get("data", {}).get("thumbnail", "") or DEFAULT_THUMBNAIL
                                logging.info(f"Thumbnail for {selected_batch_name}: {batch_thumbnail}")
                                json_data = {selected_batch_name: {}}
                                all_subject_urls = {}
                                with zipfile.ZipFile(f"{clean_file_name}.zip", 'w') as zipf:
                                    subject_tasks = [process_pwwp_subject(session, subject, selected_batch_id, selected_batch_name, zipf, json_data, all_subject_urls, headers, batch_thumbnail) for subject in subjects]
                                    await asyncio.gather(*subject_tasks)
                                with open(f"@SEM2JOB_{clean_file_name}.json", 'w', encoding='utf-8') as f:
                                    json.dump(json_data, f, indent=4)
                                with open(f"@SEM2JOB_{clean_file_name}.txt", 'w', encoding='utf-8') as f:
                                    for subject in subjects:
                                        subject_name = subject.get("subject", "Unknown Subject").replace("/", "-")
                                        if subject_name in all_subject_urls:
                                            for item in all_subject_urls[subject_name]:
                                                f.write(f"[@SEM2JOB/{subject_name}] {item['type'].capitalize()} > {item['name']}: {item['url']}\n")
                                                content_list.append(item)
                                                if item['type'] in ('videos', 'DppVideos'):
                                                    video_count += 1
                                                elif item['type'] in ('notes', 'DppNotes'):
                                                    pdf_count += 1
                                                elif item['type'] == 'image':
                                                    image_count += 1
                            else:
                                logging.error(f"Failed to fetch batch details for {selected_batch_name}: {batch_details.get('message')}")
                                await editable.edit(f"❌ *Failed to fetch details for `{selected_batch_name}`*")
                                continue
                        elif raw_text6 == '2':
                            selected_batch_name = f"{selected_batch_name} - Today's Class"
                            content_list = await get_pwwp_all_todays_schedule_content(session, selected_batch_id, headers, batch_thumbnail)
                            if content_list:
                                with open(f"@SEM2JOB_{clean_file_name}.txt", "w", encoding="utf-8") as f:
                                    for item in content_list:
                                        f.write(f"[@SEM2JOB] {item['type'].capitalize()} > {item['name']}: {item['url']}\n")
                                        if item['type'] == 'video':
                                            video_count += 1
                                        elif item['type'] in ('notes', 'DppNotes'):
                                            pdf_count += 1
                                        elif item['type'] == 'image':
                                            image_count += 1
                            else:
                                logging.error(f"No classes found today for {selected_batch_name}")
                                await editable.edit(f"❌ *No classes found today for `{selected_batch_name}`*")
                                continue
                        elif raw_text6 == '3':
                            raise Exception("Khazana: Work In Progress")
                        else:
                            raise Exception("Invalid index.")
                        end_time = time.time()
                        response_time = end_time - start_time
                        minutes = int(response_time // 60)
                        seconds = int(response_time % 60)
                        formatted_time = f"{minutes} minutes {seconds} seconds" if minutes > 0 else f"{seconds} seconds"
                        caption = shorten_caption(
                            f"✅ **Extraction Complete!** 🎉\n\n"
                            f"**📲 App Name**: Physics Wallah\n"
                            f"**📩 Batch Name**: `{selected_batch_name}`\n"
                            f"**🆔️ Batch ID**: `{selected_batch_id}`\n"
                            f"**🎬 Videos**: {video_count}\n"
                            f"**📄 PDFs**: {pdf_count}\n"
                            f"**🖼️ Images**: {image_count}\n"
                            f"**🛍 Full course purchase**: @SEM2JOB\n"
                            f"**👨‍💻 Extracted By**: @SEM2JOB_SERVICE_BOT"
                        )
                        course_list_text = (
                            f"📋 **Course Details** 📚\n\n"
                            f"**📲 App Name**: Physics Wallah\n"
                            f"**📩 Batch Name**: `{selected_batch_name}`\n"
                            f"**🆔️ Batch ID**: `{selected_batch_id}`\n"
                            f"**🎬 Videos**: {video_count}\n"
                            f"**📄 PDFs**: {pdf_count}\n"
                            f"**🖼️ Images**: {image_count}\n"
                            f"**⏱️ Time Taken**: {formatted_time}\n"
                            f"**👨‍💻 Extracted By**: @SEM2JOB_SERVICE_BOT"
                        )
                        # Simplified thumbnail validation
                        thumbnail_valid = False
                        if batch_thumbnail:
                            try:
                                async with session.get(batch_thumbnail) as resp:
                                    if resp.status == 200:
                                        thumbnail_valid = True
                                    else:
                                        logging.warning(f"Invalid thumbnail URL {batch_thumbnail}: Status {resp.status}")
                            except Exception as e:
                                logging.warning(f"Failed to validate thumbnail {batch_thumbnail}: {e}")
                        if thumbnail_valid:
                            await m.reply_photo(
                                photo=batch_thumbnail,
                                caption=caption
                            )
                        else:
                            logging.warning(f"Using default thumbnail for {selected_batch_name}")
                            await m.reply_photo(
                                photo=DEFAULT_THUMBNAIL,
                                caption=caption
                            )
                        await m.reply_text(course_list_text)
                        files = [f"@SEM2JOB_{clean_file_name}.{ext}" for ext in ["txt", "zip", "json"]]
                        # Send files to log channel with delay
                        for file in files:
                            if os.path.exists(file):
                                log_caption = shorten_caption(
                                    f"📤 **Extracted by User**\n"
                                    f"👤 User ID: `{user_id}`\n"
                                    f"📛 Username: @{m.from_user.username or 'Unknown'}\n"
                                    f"📲 App Name: Physics Wallah\n"
                                    f"📩 Batch Name: `{selected_batch_name}`\n"
                                    f"🆔️ Batch ID: `{selected_batch_id}`\n"
                                    f"🎬 Videos: {video_count}\n"
                                    f"📄 PDFs: {pdf_count}\n"
                                    f"🖼️ Images: {image_count}\n"
                                    f"👨‍💻 Extracted By: @SEM2JOB_SERVICE_BOT"
                                )
                                await send_to_log_channel(
                                    bot,
                                    user_id,
                                    m.from_user.username or "Unknown",
                                    log_caption,
                                    file
                                )
                                await asyncio.sleep(2)  # Increased delay to avoid flood control
                        if is_premium:
                            for file in files:
                                if os.path.exists(file):
                                    file_ext = os.path.splitext(file)[1][1:]
                                    try:
                                        with open(file, 'rb') as f:
                                            await m.reply_document(
                                                document=f,
                                                caption=shorten_caption(
                                                    f"✅ **{file_ext.upper()} File Extracted Successfully** 🎉\n\n"
                                                    f"**📲 App Name**: Physics Wallah\n"
                                                    f"**📩 Batch Name**: `{selected_batch_name}`\n"
                                                    f"**🆔️ Batch ID**: `{selected_batch_id}`\n"
                                                    f"**🎬 Videos**: {video_count}\n"
                                                    f"**📄 PDFs**: {pdf_count}\n"
                                                    f"**🖼️ Images**: {image_count}\n"
                                                    f"**👨‍💻 Extracted By**: @SEM2JOB_SERVICE_BOT"
                                                )
                                            )
                                    except Exception as e:
                                        logging.error(f"Error sending {file_ext} file: {e}")
                                        await m.reply_text(f"❌ *Error sending {file_ext.upper()} file: {e}*")
                        else:
                            await m.reply_text(
                                "❌ **Limited Access**\nYou are a free user. To download .txt, .zip, and .json files, upgrade to Premium!\nContact: @SEM2JOB",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("💎 Upgrade to Premium", url="https://t.me/SEM2JOB")]
                                ])
                            )
                        # Clean up temporary files
                        for file in files:
                            if os.path.exists(file):
                                try:
                                    os.remove(file)
                                except Exception as e:
                                    logging.error(f"Error removing file {file}: {e}")
                    except Exception as batch_error:
                        logging.error(f"Error processing batch {selected_batch_name}: {batch_error}")
                        await m.reply_text(f"❌ *Error processing batch `{selected_batch_name}`: {batch_error}*")
                        continue
            else:
                raise Exception("No content found for the selected batch.")
        except Exception as e:
            keyboard = [
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                 InlineKeyboardButton("🔙 Back", callback_data="physicswallah_menu")]
            ]
            await editable.edit(f"❌ *Error: {e}*", reply_markup=InlineKeyboardMarkup(keyboard))
        finally:
            await session.close()
            await CONNECTOR.close()
# --- End Physics Wallah Functions ---
# --- Callback Query Handlers ---
@bot.on_callback_query()
async def handle_callback_query(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data
    try:
        if data == "main_menu":
            keyboard = [
                [InlineKeyboardButton("📖 CLASSPLUS EXTRACTOR", callback_data="classplus_menu")],
                [InlineKeyboardButton("🚀 PHYSICS WALLAH EXTRACTOR", callback_data="physicswallah_menu")],
                [InlineKeyboardButton("💎 PREMIUM FEATURES", url="https://t.me/SEM2JOB")],
                [InlineKeyboardButton("🛠 DEVELOPER SUPPORT", url="https://t.me/SEM2JOB_free")]
            ]
            await query.message.edit_text(WELCOME_MESSAGE, reply_markup=InlineKeyboardMarkup(keyboard))
        elif data == "classplus_menu":
            keyboard = [
                [InlineKeyboardButton("📚 Extract Single Course", callback_data="extract_single")],
                [InlineKeyboardButton("📦 Extract All Courses", callback_data="extract_all")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            await query.message.edit_text(
                "📖 **Classplus Extractor** 📚\n\n"
                "Choose an option:\n"
                "📍1. Extract a single course by selecting it.\n"
                "🎯 2. Extract all available courses from the organization.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif data == "physicswallah_menu":
            keyboard = [
                [InlineKeyboardButton("📚 Extract Batch", callback_data="extract_batch")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            await query.message.edit_text(
                "🚀 **Physics Wallah Extractor** 📚\n\n"
                "Extract content from your Physics Wallah account.\n"
                "🎗Provide an access token or ☎️ phone number to begin.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif data == "extract_single":
            await query.message.delete()
            await process_cpwp(bot, query.message, user_id)
        elif data == "extract_all":
            await query.message.delete()
            await process_extract_all(bot, query.message, user_id)
        elif data == "extract_batch":
            await query.message.delete()
            await process_pwwp(bot, query.message, user_id)
        await query.answer()
    except Exception as e:
        logging.error(f"Error handling callback query {data}: {e}")
        await query.message.edit_text(f"❌ *Error: {e}*")
        await query.answer()

# --- Start Command ---
@bot.on_message(filters.command(["start"]))
async def start(bot: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    logging.info(f"Start command received from User ID: {user_id}, Username: @{username}")
    
    # Send welcome message with random image
    random_image = random.choice(image_list)
    keyboard = [
        [InlineKeyboardButton("📖 CLASSPLUS EXTRACTOR", callback_data="classplus_menu")],
        [InlineKeyboardButton("🚀 PHYSICS WALLAH EXTRACTOR", callback_data="physicswallah_menu")],
        [InlineKeyboardButton("💎 BY PREMIUM", url="https://t.me/SEM2JOB")],
        [InlineKeyboardButton("🛠 DEVELOPER SUPPORT", url="https://t.me/SEM2JOB_free")]
    ]
    try:
        await message.reply_photo(
            photo=random_image,
            caption=WELCOME_MESSAGE,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await send_to_log_channel(bot, user_id, username, "User started the bot.")
    except Exception as e:
        logging.error(f"Error sending start message: {e}")
        await message.reply_text(WELCOME_MESSAGE, reply_markup=InlineKeyboardMarkup(keyboard))

# --- Main Bot Initialization ---
async def main():
    try:
        # Start Flask app in a separate thread for Render/Koyeb
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Start the bot
        await bot.start()
        logging.info("Bot started successfully!")
        
        # Keep the bot running
        await asyncio.Event().wait()
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        await bot.stop()
        logging.info("Bot stopped.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
