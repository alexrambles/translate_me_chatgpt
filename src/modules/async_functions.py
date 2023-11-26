import logging
from requests_html import HTMLSession, AsyncHTMLSession
from os import open
from bs4 import BeautifulSoup
from functools import partial
from deep_translator import GoogleTranslator
import logging
import asyncio


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def scrape_urls(directory, url, returnvar, i):
    try: 
        session = HTMLSession()
        current_page = session.get(url[1])
        page_content = current_page.text

        filename = f"page_{str(i)}.txt"
        save_location = f'{directory}/{filename}'

        returnvar[str(i)] = filename

        #create file for current url's content
        with open(save_location, 'w', encoding='utf-8') as file:
            file.write(page_content)
    except:
        print('Error with async function.')
        
    page += 1

    current_page.close()
    session.close()

def async_scrape(directory, url_list):
    threads = [3]
    manager = multiprocessing.Manager()
    returndict = manager.dict()
    for i in range(len(url_list)):
        try:
            process = multiprocessing.Process(target = scrape_urls, args = (directory, url_list[i], returndict, i))
            process.start()
            threads.append(process)
        except Exception as e:
            print('Async Error:' + e)

    for t in threads:
        t.join()

    return returndict


## Function to asynchronously retrieve chapter HTML and save it to a file.
def async_retrieve_chapter_html(directory, test_url_list):
    asession = AsyncHTMLSession()
    
    async def get_content(url):
        index = test_url_list.index(url)
        
        logger.info(f'Retrieving url {index}: {url}')
        r = await asession.get(url)

        logger.info(f'Retrieved url {index}: {url}')

        #create save location for chapter file
        filename = f"page_{str(index)}.txt"
        save_location = f'{directory}/{filename}'

        #get page content
        page_content = r.html.html
        
        #create file for current url's content
        with open(save_location, 'w', encoding='utf-8') as file:
            await file.write(page_content)

        return save_location

    save_locations = asession.run(*[lambda url=url: get_content(url) for url in test_url_list])

    save_locations = sorted(save_locations)

    return save_locations

def translate(to_be_translated_text):
    chunk_size = 500
    
    translated_chunks = []

    # Split the text into chunks
    chunks = [f'translate_chunk("{to_be_translated_text[i:i+chunk_size]}")' for i in range(0, len(to_be_translated_text), chunk_size)]

    async def translate_chunk(chunk):
        index = chunks.index(chunk)
        translated = await GoogleTranslator(source='auto', target='en').translate(chunk)

        if translated is None and chunk:
            translated_chunks.append(chunk)
        else:
            translated_chunks.append(index, translated)

    async def execute_translation():
        logger.info("Executing translation...")

        translated_chunks = await asyncio.gather(*[translate_chunk(chunk) for chunk in chunks])
        
        logger.info("Translation finished..")
        
        return translated_chunks


    
    translated_chunks = asyncio.run(execute_translation())

    sorted_chunks = sorted(translated_chunks)

    translated_chunks = [x[1] for x in sorted_chunks]

    # Join the translated chunks
    translated_text = ' '.join([x for x in translated_chunks if x])

    if translated_text != '' and translated_text is not None:
        return translated_text
