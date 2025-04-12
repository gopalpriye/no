import requests
import asyncio
import aiohttp
import json
import zipfile
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import os
import base64
from pyrogram import Client, filters
import sys
import re
import requests
import uuid
import random
import string
import hashlib
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
from pyromod import listen
from pyromod.exceptions.listener_timeout import ListenerTimeout
from pyrogram.types import Message
import pyrogram
from pyrogram import Client, filters
from pyrogram.types import User, Message
from pyrogram.enums import ChatMemberStatus
from pyrogram.raw.functions.channels import GetParticipants
from config import api_id, api_hash, bot_token, auth_users
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
THREADPOOL = ThreadPoolExecutor(max_workers=1000)
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

image_list = [
"https://graph.org/file/8b1f4146a8d6b43e5b2bc-be490579da043504d5.jpg",
"https://graph.org/file/b75dab2b3f7eaff612391-282aa53538fd3198d4.jpg",
"https://graph.org/file/38de0b45dd9144e524a33-0205892dd05593774b.jpg",
"https://graph.org/file/be39f0eebb9b66d7d6bc9-59af2f46a4a8c510b7.jpg",
"https://graph.org/file/8b7e3d10e362a2850ba0a-f7c7c46e9f4f50b10b.jpg",
]
print(4321)
bot = Client(
    "bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token)

@bot.on_message(filters.command(["start"]))
async def start(bot, message):
  random_image_url = random.choice(image_list)

  keyboard = [
    [
      InlineKeyboardButton("📘 Classplus without Purchase 📘", callback_data="cpwp")
    ]
  ]

  reply_markup = InlineKeyboardMarkup(keyboard)

  await message.reply_photo(
    photo=random_image_url,
    caption="PLEASE👇PRESS👇HERE",
    quote=True,
    reply_markup=reply_markup
  )
@bot.on_message(group=2)
#async def account_login(bot: Client, m: Message):
#    try:
#        await bot.forward_messages(chat_id=chat_id, from_chat_id=m.chat.id, message_ids=m.id)
#    except:
#        pass
            
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
         #   logging.exception(f"Unexpected error fetching signed URL for {name}: {e}. Attempt {attempt + 1}/{MAX_RETRIES}")
            pass

        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(2 ** attempt)

    logging.error(f"Failed to fetch signed URL for {name} after {MAX_RETRIES} attempts.")
    return None

async def process_cpwp_url(url_val: str, name: str, session: aiohttp.ClientSession, headers: Dict[str, str]) -> str | None:
    try:
        signed_url = await fetch_cpwp_signed_url(url_val, name, session, headers)
        if not signed_url:
            logging.warning(f"Failed to obtain signed URL for {name}: {url_val}")
            return None

        if "testbook.com" in url_val or "classplusapp.com/drm" in url_val or "media-cdn.classplusapp.com/drm" in url_val:
        #    logging.info(f"{name}:{url_val}")
            return f"{name}:{url_val}\n"

        async with session.get(signed_url) as response:
            response.raise_for_status()
       #     logging.info(f"{name}:{url_val}")
            return f"{name}:{url_val}\n"
            
    except Exception as e:
    #    logging.exception(f"Unexpected error processing {name}: {e}")
        pass
    return None


async def get_cpwp_course_content(session: aiohttp.ClientSession, headers: Dict[str, str], Batch_Token: str, folder_id: int = 0, limit: int = 9999999999, retry_count: int = 0) -> Tuple[List[str], int, int, int]:
    MAX_RETRIES = 3
    fetched_urls: set[str] = set()
    results: List[str] = []
    video_count = 0
    pdf_count = 0
    image_count = 0
    content_tasks: List[Tuple[int, asyncio.Task[str | None]]] = []
    folder_tasks: List[Tuple[int, asyncio.Task[List[str]]]] = []

    try:
        content_api = f'https://api.classplusapp.com/v2/course/preview/content/list/{Batch_Token}'
        params = {'folderId': folder_id, 'limit': limit}

        async with session.get(content_api, params=params, headers=headers) as res:
            res.raise_for_status()
            res_json = await res.json()
            contents: List[Dict[str, Any]] = res_json['data']

            for content in contents:
                if content['contentType'] == 1:
                    folder_task = asyncio.create_task(get_cpwp_course_content(session, headers, Batch_Token, content['id'], retry_count=0))
                    folder_tasks.append((content['id'], folder_task))

                else:
                    name: str = content['name']
                    url_val: str | None = content.get('url') or content.get('thumbnailUrl')

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
                        url_val = f'https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/b08bad9ff8d969639b2e43d5769342cc62b510c4345d2f7f153bec53be84fe35/{url_val.split('/')[-1].split('.')[0]}/master.m3u8'
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
                        headers2 = { 'x-access-token': 'eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9'}
                        task = asyncio.create_task(process_cpwp_url(url_val, name, session, headers2))
                        content_tasks.append((content['id'], task))
                        
                    else:
                        name: str = content['name']
                        url_val: str | None = content.get('url')
                        if url_val:
                            fetched_urls.add(url_val)
                        #    logging.info(f"{name}:{url_val}")
                            results.append(f"{name}:{url_val}\n")
                            if url_val.endswith('.pdf'):
                                pdf_count += 1
                            else:
                                image_count += 1
                                
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        if retry_count < MAX_RETRIES:
            logging.info(f"Retrying folder {folder_id} (Attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(2 ** retry_count)
            return await get_cpwp_course_content(session, headers, Batch_Token, folder_id, limit, retry_count + 1)
        else:
            logging.error(f"Failed to retrieve folder {folder_id} after {MAX_RETRIES} retries.")
            return [], 0, 0, 0
            
    content_results = await asyncio.gather(*(task for _, task in content_tasks), return_exceptions=True)
    folder_results = await asyncio.gather(*(task for _, task in folder_tasks), return_exceptions=True)
    
    for (folder_id, result) in zip(content_tasks, content_results):
        if isinstance(result, Exception):
            logging.error(f"Task failed with exception: {result}")
        elif result:
            results.append(result)
            video_count += 1
            
    for folder_id, folder_result in folder_tasks:
        try:
            nested_results, nested_video_count, nested_pdf_count, nested_image_count = await folder_result
            if nested_results:
                results.extend(nested_results)
            else:
            #    logging.warning(f"get_cpwp_course_content returned None for folder_id {folder_id}")
                pass
            video_count += nested_video_count
            pdf_count += nested_pdf_count
            image_count += nested_image_count
        except Exception as e:
            logging.error(f"Error processing folder {folder_id}: {e}")

    return results, video_count, pdf_count, image_count
    
@bot.on_callback_query(filters.regex("^cpwp$"))
async def cpwp_callback(bot, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.answer()
    
    if user_id not in auth_users:
        await bot.send_message(callback_query.message.chat.id, f"**You Are Not Subscribed To This Bot\nContact - @pwextractowner**")
        return
            
    THREADPOOL.submit(asyncio.run, process_cpwp(bot, callback_query.message, user_id))
    
async def process_cpwp(bot: Client, m: Message, user_id: int):
    
    headers = {
        'accept-encoding': 'gzip',
        'accept-language': 'EN',
        'api-version'    : '35',
        'app-version'    : '1.4.73.2',
        'build-number'   : '35',
        'connection'     : 'Keep-Alive',
        'content-type'   : 'application/json',
        'device-details' : 'Xiaomi_Redmi 7_SDK-32',
        'device-id'      : 'c28d3cb16bbdac01',
        'host'           : 'api.classplusapp.com',
        'region'         : 'IN',
        'user-agent'     : 'Mobile-Android',
        'webengage-luid' : '00000187-6fe4-5d41-a530-26186858be4c'
    }

    loop = asyncio.get_event_loop()
    CONNECTOR = aiohttp.TCPConnector(limit=1000, loop=loop)
    async with aiohttp.ClientSession(connector=CONNECTOR, loop=loop) as session:
        try:
            editable = await m.reply_text("**Enter ORG Code Of Your Classplus App**")
            
            try:
                input1 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                org_code = input1.text.lower()
                await input1.delete(True)
            except ListenerTimeout:
                await editable.edit("**Timeout! You took too long to respond**")
                return
            except Exception as e:
                logging.exception("Error during input1 listening:")
                try:
                    await editable.edit(f"**Error: {e}**")
                except:
                    logging.error(f"Failed to send error message to user: {e}")
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
                    
                    async with session.get(f"https://api.classplusapp.com/v2/course/preview/similar/{token}?limit=20", headers=headers) as response:
                        if response.status == 200:
                            res_json = await response.json()
                            courses = res_json.get('data', {}).get('coursesData', [])

                            if courses:
                                text = ''
                                for cnt, course in enumerate(courses):
                                    name = course['name']
                                    price = course['finalPrice']
                                    text += f'{cnt + 1}. ```\n{name} 💵₹{price}```\n'

                                await editable.edit(f"**Send index number of the Category Name\n\n{text}\nIf Your Batch Not Listed Then Enter Your Batch Name**")
                            
                                try:
                                    input2 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                                    raw_text2 = input2.text
                                    await input2.delete(True)
                                except ListenerTimeout:
                                    await editable.edit("**Timeout! You took too long to respond**")
                                    return
                                except Exception as e:
                                    logging.exception("Error during input1 listening:")
                                    try:
                                        await editable.edit(f"**Error : {e}**")
                                    except:
                                        logging.error(f"Failed to send error message to user : {e}")
                                    return

                                if input2.text.isdigit() and len(input2.text) <= len(courses):
                                    selected_course_index = int(input2.text.strip())
                                    course = courses[selected_course_index - 1]
                                    selected_batch_id = course['id']
                                    selected_batch_name = course['name']
                                    price = course['finalPrice']
                                    clean_batch_name = selected_batch_name.replace("/", "-").replace("|", "-")
                                    clean_file_name = f"{user_id}_{clean_batch_name}"

                                else:
                                    search_url = f"https://api.classplusapp.com/v2/course/preview/similar/{token}?search={raw_text2}"
                                    async with session.get(search_url, headers=headers) as response:
                                        if response.status == 200:
                                            res_json = await response.json()
                                            courses = res_json.get("data", {}).get("coursesData", [])

                                            if courses:
                                                text = ''
                                                for cnt, course in enumerate(courses):
                                                    name = course['name']
                                                    price = course['finalPrice']
                                                    text += f'{cnt + 1}. ```\n{name} 💵₹{price}```\n'
                                                await editable.edit(f"**Send index number of the Batch to download.\n\n{text}**")
                                            
                                                try:
                                                    input3 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                                                    raw_text3 = input3.text
                                                    await input3.delete(True)
                                                except ListenerTimeout:
                                                    await editable.edit("**Timeout! You took too long to respond**")
                                                    return
                                                except Exception as e:
                                                    logging.exception("Error during input1 listening:")
                                                    try:
                                                        await editable.edit(f"**Error : {e}**")
                                                    except:
                                                        logging.error(f"Failed to send error message to user : {e}")
                                                    return


                                                if input3.text.isdigit() and len(input3.text) <= len(courses):
                                                    selected_course_index = int(input3.text.strip())
                                                    course = courses[selected_course_index - 1]
                                                    selected_batch_id = course['id']
                                                    selected_batch_name = course['name']
                                                    price = course['finalPrice']
                                                    clean_batch_name = selected_batch_name.replace("/", "-").replace("|", "-")
                                                    clean_file_name = f"{user_id}_{clean_batch_name}"
                                                
                                                else:
                                                    raise Exception("Wrong Index Number")
                                            else:
                                                raise Exception("Didn't Find Any Course Matching The Search Term")
                                        else:
                                            raise Exception(f"{response.text}")
                                            
                                download_price = int(price * 0.10)
                                batch_headers = {
                                    'Accept': 'application/json, text/plain, */*',
                                    'region': 'IN',
                                    'accept-language': 'EN',
                                    'Api-Version': '22',
                                    'tutorWebsiteDomain': f'https://{org_code}.courses.store'
                                }
                                    
                                params = {
                                    'courseId': f'{selected_batch_id}',
                                }

                                async with session.get(f"https://api.classplusapp.com/v2/course/preview/org/info", params=params, headers=batch_headers) as response:
                                    if response.status == 200:
                                        res_json = await response.json()
                                        Batch_Token = res_json['data']['hash']
                                        App_Name = res_json['data']['name']

                                        await editable.edit(f"**Extracting course : {selected_batch_name} ...**")

                                        start_time = time.time()
                                        course_content, video_count, pdf_count, image_count = await get_cpwp_course_content(session, headers, Batch_Token)
                                    
                                        if course_content:
                                            file = f"{clean_file_name}.txt"

                                            with open(file, 'w') as f:
                                                f.write(''.join(course_content))

                                            end_time = time.time()
                                            response_time = end_time - start_time
                                            minutes = int(response_time // 60)
                                            seconds = int(response_time % 60)

                                            if minutes == 0:
                                                if seconds < 1:
                                                    formatted_time = f"{response_time:.2f} seconds"
                                                else:
                                                    formatted_time = f"{seconds} seconds"
                                            else:
                                                formatted_time = f"{minutes} minutes {seconds} seconds"

                                            await editable.delete(True)
                                        
                                            caption = f"**App Name : ```\n{App_Name}({org_code})```\nBatch Name : ```\n{selected_batch_name}``````\n🎬 : {video_count} | 📁 : {pdf_count} | 🖼  : {image_count}``````\nTime Taken : {formatted_time}```**"
                                        
                                            with open(file, 'rb') as f:
                                                doc = await m.reply_document(document=f, caption=caption, file_name=f"{clean_batch_name}.txt")

                                            os.remove(file)

                                        else:
                                            raise Exception("Didn't Find Any Content In The Course")
                                    else:
                                        raise Exception(f"{response.text}")
                            else:
                                raise Exception("Didn't Find Any Course")
                        else:
                            raise Exception(f"{response.text}")
                else:
                    raise Exception('No App Found In Org Code')
                    
        except Exception as e:
            await editable.edit(f"**Error : {e}**")
            
        finally:
            await session.close()
            await CONNECTOR.close()

                                        
bot.run()