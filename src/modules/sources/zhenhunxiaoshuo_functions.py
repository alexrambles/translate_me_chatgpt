import os
from pathlib import Path
import shutil
import logging
from requests import get, Session
from requests.adapters import HTTPAdapter, Retry
from urllib import request
from urllib.error import HTTPError
from re import sub, compile
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from langid import classify as langid_classify
from ebooklib import epub
import chardet
import cchardet
from .. import async_functions


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants

CHUNK_SIZE = 500

# Function to get the BeautifulSoup object for a given URL
def get_soup(header, s, url, api_key=None):
    try_again = True
    if api_key is not None:
        payload = {'api_key': api_key, 'url': url}
        response = s.get('http://api.scraperapi.com', params=payload)
        response.raise_for_status()
        content = response.content
        chardet_encoding = chardet.detect(content)['encoding']    
    else:
        while try_again:
            try:
                response = s.get(headers = header, url = url)
                response.raise_for_status()
                content = response.content
                chardet_encoding = chardet.detect(content)['encoding']
                try_again = False
            except:
                try:
                    logging.info("Couldn't use Session--trying to use Request.")
                    req = request.Request(url)
                    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
                    req.add_header('Referer', 'https://www.google.com/')
                    req.add_header('Accept-Language', 'en-US,en;q=0.9,ja-JP;q=0.8,ja;q=0.7')

                    response = request.urlopen(req).read().decode('gbk')
                    try_again = False
                except:
                    pass
        
    try:
        if b'charset=gbk' in content or b'charset="gbk"' in content:
            response.encoding = 'gbk'
        else:
            response.encoding = response.content.decode(chardet_encoding)
    except UnicodeDecodeError:
        for encoding_type in ['utf-8','gbk']:
            try:
                response.encoding = cchardet.detect(content)[encoding_type]
            except UnicodeEncodeError:
                continue
            
    return BeautifulSoup(response.text, 'html.parser')

def scrape_metadata(soup):
    title = soup.select_one('h1.focusbox-title').text.strip()
    translated_title = translate_text(title)
    
    author = soup.select_one('div.focusbox-text p').contents[0].split('：')[-1].strip()
    translated_author = translate_text(author)
    
    description = soup.select_one('div.focusbox-text p br').next.strip()
    translated_description = translate_text(description)
    language_code = langid_classify(description)
    
    return translated_title, translated_author, translated_description, language_code[0]

def scrape_chapter_links(base_url, header, s, soup):
    unsorted_links = soup.select('body section div.excerpts-wrapper div article a')
    chapter_links = sorted(unsorted_links, key= lambda link: async_functions.translate(str(link)))

    return [(link.text.strip(), link['href']) for link in chapter_links]

def translate_text(to_be_translated_text):
    translated_chunks = []

    # Split the text into chunks
    chunks = [to_be_translated_text[i:i+CHUNK_SIZE] for i in range(0, len(to_be_translated_text), CHUNK_SIZE)]

    # Translate each chunk
    for chunk in chunks:
        translated = GoogleTranslator(source='auto', target='en').translate(chunk)

        if translated is None and chunk:
            translated_chunks.append(chunk)
        else:
            translated_chunks.append(translated)

    # Join the translated chunks
    translated_text = ' '.join([x for x in translated_chunks if x])

    if translated_text != '' and translated_text is not None:
        return translated_text

def normalize_text(text_to_normalize, paragraph_tags = False):
    normalized_list = []

    if isinstance(text_to_normalize, list):
        for text_item in text_to_normalize:
            cleaned_untranslated_text = sub(r'[\r\n\xa0]+', ' ', text_item).strip()
            if cleaned_untranslated_text == 'None' or cleaned_untranslated_text.replace(' ',  '') == '':
                cleaned_untranslated_text = ''
            if paragraph_tags and cleaned_untranslated_text:
                normalized_list.append(f'<p>{cleaned_untranslated_text}</p>')
            elif cleaned_untranslated_text:
                normalized_list.append(cleaned_untranslated_text)
    else:
        cleaned_untranslated_text = sub(r'[\r\n\xa0]+', ' ', text_to_normalize).strip()
        if cleaned_untranslated_text == 'None' or cleaned_untranslated_text.replace(' ',  '') == '':
            cleaned_untranslated_text = ''
        if paragraph_tags and cleaned_untranslated_text:
            normalized_list.append(f'<p>{cleaned_untranslated_text}</p>')
        elif cleaned_untranslated_text:
            normalized_list.append(cleaned_untranslated_text)

    joined_normalized_list = ''.join(normalized_list)

    return joined_normalized_list

# Function to save content as an HTML file
def save_html(content, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)

# Function to scrape a chapter and return its content
def get_chapter_content(chapter_html, api_key = None, file_soup = None):
    chapter_content_text = []

    if file_soup is None:
        chapter_soup = BeautifulSoup(chapter_html, 'html.parser')
    else:
        chapter_soup = file_soup
        
    if chapter_soup.select_one('div.content-wrap div.content article.article-content p'):
        chap_soup_content_list = chapter_soup.select('div.content-wrap div.content article.article-content p')
    else:
        logger.debug("Can't detect chapter content")
        
    for x in chap_soup_content_list:
        chapter_content_text.append(x.text)
            
    return chapter_content_text
    

# Function to scrape the document content and create the EPUB book
def scrape_document(directory, url, api_key=None):
    def split_url(url, separator, position=int):
        base_url = url.split(separator)
        return separator.join(base_url[:position]), separator.join(base_url[position:])

    element_sublist = []
    to_be_normalized = False
    spine = []    
    translated_contents = []
    chapter_title_list = []
    chapter_url_list = []
    file_list = []
    chapter_content_list = []
    toc = ["nav"]
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Referer': 'https://www.google.com/',
    'Accept-Language': 'en-US,en;q=0.9,ja-JP;q=0.8,ja;q=0.7',
    }
    ch_num = 1
    
    base_url = split_url(url, '/', 3)[0]

    logger.info('Scraping TOC document...')
    
    s = Session()
    soup = get_soup(headers, s, url)
    title, author, description, language_code = scrape_metadata(soup)
    
    logger.info(f'Title: {title}')
    logger.info(f'Author: {author}')
    logger.info(f'Description: {description}')
    
    book = epub.EpubBook()
    book.set_title(title)
    book.add_author(author)
    book.set_language("en")
    book.set_language(language_code)

    #if description and cover url are present, add them to the book
    if description is not None:
        book.add_metadata('DC','description', description)

    logger.info('Acquiring TOC.')

    chapter_links = scrape_chapter_links(base_url, headers, s, soup)

    logger.info('TOC Acquired.')

    titlepage_html = f'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="en" xml:lang="en"><head><title>{title}</title><link rel="stylesheet" href="stylesheet.css" type="text/css" /><meta charset = "utf-8"/></head><div epub:type="frontmatter"><body><div class="title">{title}</div><div>This ebook is compiled for educational purposes only and is not to be redistributed.</div><div>Title: {title}</div><div>Author: {author}</div><div class="cover"><h1 id="titlepage">{title}</h1><h2>by {author}</h2><img src="images/cover.jpg"></img></div></body></div></html>'

    title_page = book.add_item(epub.EpubItem(
        uid="title_page"
        ,file_name="titlepage.html"
        ,content=titlepage_html
        ,media_type="application/xhtml+xml"
        ))

    spine.append(title_page)
    toc.append(title_page)

    temp_directory = f'{directory}temp_book_files'

    #If the temporary directory doesn't already exist, create it. 
    #If it does exist, then delete all files found within.
    if os.path.exists(temp_directory):
        for root, dirs, files in os.walk(temp_directory):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))
        pass
    else:
        os.mkdir(temp_directory)

    for i, (chapter_title, chapter_url) in chapter_links:
        chapter_title_list.append(chapter_title)
        chapter_url_list.append(chapter_url)

    #asynchronously scrape every url and save them to file
    filename_list = async_functions.async_retrieve_chapter_html(temp_directory, chapter_url_list)

    for filename in filename_list:
        contents = Path(filename).read_text()
        chapter_content_list.append(contents)



    # --------- next job is to clean up the get_chapter_content function to work off of a list of strings, interpreting that into a bs4 obj.










    for i, ch_file in enumerate(chapter_content_list):
        logger.debug(f'Processing Chapter {i} of {len(chapter_content_list)}.')

        #this was a single chapter retrieval that returned the chapter content. Replaced with async function.
        ##chapter_content_list = get_chapter_content(headers, session, chapter_url)

        chapter_content_list = get_chapter_content(ch_file)
        
        logger.info('Content acquired.')

        for x in chapter_content_list:
            if '\r' in x:
                to_be_normalized = True

            text_split_by_return = x.split('\r')
            
            for text_item in text_split_by_return:
                element_sublist.append(f"{text_item}")

        element_sublist[:] = [x for x in element_sublist if x != '' and x != '\n']

        chapter_content = '</p><p>'.join(element_sublist)
        
        logger.info('Starting translation')
        
        if to_be_normalized:
            normalized_content = normalize_text(chapter_content, paragraph_tags= True)
            translated_text = async_functions.translate(normalized_content)
        else:
            translated_text = async_functions.translate(chapter_content)
            
        if translated_text and translated_text.strip():
            translated_contents.append(f'{translated_text}')

        logger.info('Translation finished')

        html_ized_content = " ".join(translated_contents)

        if not isinstance(html_ized_content, str):
            html_ized_content = ''
        
        chapter_html_contents = f'<h1>{chapter_title}</h1>\n<div id=\"{chapter_title}\">{html_ized_content}</p>\n'
        filename = f'chapter{i+1}.html'
        save_html(chapter_html_contents, filename)
        
        logger.info(f'Saved Chapter {i+1} as HTML file')

        file_list.append((chapter_title, filename))










'''
    async def translate_urls(file_list):
        chapter_title, filename = file_list
        
        file = open(filename, 'r')
        file_content = file.read()


        chapter = epub.EpubHtml(title=chapter_title, file_name=filename, lang='en')

            
        file.close()
        chapter.content = chapter_file_content

        book.add_item(chapter)
        spine.append(chapter)
        toc.append(chapter)
        
        os.remove(filename)
    
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    
    book.add_item(nav_css)

    book.spine = spine
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    novel_filename =  sub(r'[^\w]', '_', title).lower()
    
    epub.write_epub(f'{directory}{novel_filename}.epub', book)
    
    logger.info(f'Saved ebook: {directory}{title}.epub')
'''