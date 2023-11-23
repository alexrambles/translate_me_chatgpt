import os
import logging
from requests import get, Session
from requests.adapters import HTTPAdapter, Retry
from urllib import request
from urllib.error import HTTPError
from re import sub
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from langid import classify as langid_classify
from ebooklib import epub
import chardet
import cchardet


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants

CHUNK_SIZE = 500

# Function to get the BeautifulSoup object for a given URL
def get_soup(header, session, url, api_key=None):
    try_again = True
    if api_key is not None:
        payload = {'api_key': api_key, 'url': url}
        response = session.get('http://api.scraperapi.com', params=payload)
        response.raise_for_status()
        content = response.content
        chardet_encoding = chardet.detect(content)['encoding']

    else:
        while try_again:
            try:
                response = session.get(url, headers=header)
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

#scrape metadata from TOC page
def scrape_metadata(soup):
    title = soup.select_one('h1').text.strip()
    translated_title = translate_text(title)
    
    if 'Author:' in translated_title:
        translated_title, translated_author = translated_title.split('Author:')
        translated_author = translated_author.strip()
        translated_title = translated_title.strip()
    else:
        author = soup.select_one('#info p:nth-of-type(1), .p1').text.strip().split('：')[-1]
        translated_author = translate_text(author)
    
    return translated_title, translated_author

#get chapter links
def scrape_chapter_links(base_url, header, session, soup):
    unsorted_anchors = soup.select('div.paginator a')
    unsorted_links = []
    link_text = []
    for link in unsorted_anchors:
        if link.get('href'):
            link_text.append(link.text)
            unsorted_links.append(link.get('href'))
    chapter_links = sorted(unsorted_links, key= lambda link: translate_text(str(link)))

    return [(link_text, base_url + link) for link in chapter_links]

#translate text into english. Currently assumes that language is Chinese.
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

#clean up text and remove superfluous linebreaks
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
def get_chapter_content(headers, session, chapter_url, api_key=None):
    chapter_soup = get_soup(headers, session, chapter_url)
    
    chapter_content_text = []
    chap_soup_content_list = chapter_soup.select('#BookContent')[0].text
        
    chapter_content_text = [chap_soup_content_list]
            
    return chapter_content_text

# Function to scrape the document content and create the EPUB book
def scrape_document(directory, url, api_key=None):
    def split_url(url, separator, position=int):
        base_url = url.split(separator)
        return separator.join(base_url[:position]), separator.join(base_url[position:])

    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Referer': 'https://www.google.com/',
    'Accept-Language': 'en-US,en;q=0.9,ja-JP;q=0.8,ja;q=0.7',
    }

    logger.info('Scraping TOC document...')
    
    session = Session()
    soup = get_soup(headers, session, url)
    title, author = scrape_metadata(soup)
    
    logger.info(f'Title: {title}')
    logger.info(f'Author: {author}')
    
    book = epub.EpubBook()
    book.set_title(title)
    book.add_author(author)
    book.set_language("en")

    base_url = split_url(url, '/', 3)[0]
    current_link = [("1",url)]

    spine = []
    toc = ["nav"]

    titlepage_html = f'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="en" xml:lang="en"><head><title>{title}</title><link rel="stylesheet" href="stylesheet.css" type="text/css" /><meta charset = "utf-8"/></head><div epub:type="frontmatter"><body><div class="title">{title}</div><div>This ebook is compiled for educational purposes only and is not to be redistributed.</div><div>Title: {title}</div><div>Author: {author}</div><div class="cover"><h1 id="titlepage">{title}</h1><h2>by {author}</h2><img src="images/cover.jpg"></img></div></body></div></html>'

    title_page = book.add_item(epub.EpubItem(
        uid="title_page"
        ,file_name="titlepage.html"
        ,content=titlepage_html
        ,media_type="application/xhtml+xml"
        ))

    spine.append(title_page)
    toc.append(title_page)

    page_num=1

    chapter_url = url

    try:
        while soup.find_all('a', href = True, text = '下壹頁')[0].get('href'):
            logger.debug(f"Scraping Page {page_num} of {soup.find('a', href = True, text = '最末頁').get('href').split('-')[2].split('.')[0]}")
            
            chapter_content_list = get_chapter_content(headers, session, chapter_url)

            element_sublist = []
            to_be_normalized = False
            
            for x in chapter_content_list:
                to_be_normalized = True
                text_split_by_return = sub('\r', '', sub('\n', '', x)).split('\u3000\u3000')
                
                for text_item in text_split_by_return:
                    element_sublist.append(f"{text_item}")

            element_sublist[:] = [x for x in element_sublist if x != '' and x != '\n' and x != '\r']

            chapter_content = '</p><p>'.join(element_sublist)
                
            translated_contents = []
            if to_be_normalized:
                normalized_content = normalize_text(chapter_content, paragraph_tags= True)
                translated_text = translate_text(normalized_content)
            else:
                translated_text = translate_text(chapter_content)
                
            if translated_text and translated_text.strip():
                translated_contents.append(f'{translated_text}')

            html_ized_content = " ".join(translated_contents)

            if not isinstance(html_ized_content, str):
                html_ized_content = ''
            
            chapter_html_contents = f'<h1>Page {page_num}</h1>\n<div id=\"{page_num}\">{html_ized_content}</p>\n'
            filename = f'page{page_num}.html'
            save_html(chapter_html_contents, filename)
            
            logger.info(f"Saved Page {page_num} of {soup.find('a', href = True, text = '最末頁').get('href').split('-')[2].split('.')[0]} as HTML file")
            
            chapter = epub.EpubHtml(title='Page ' + str(page_num), file_name=filename, lang='en')
            chapter.content = chapter_html_contents

            book.add_item(chapter)
            spine.append(chapter)
            toc.append(chapter)
            
            os.remove(filename)

            part_chapter_url = soup.find('a', href = True, text = '下壹頁').get('href')
            chapter_url = base_url + part_chapter_url
            page_num += 1
    except:
        print('Done scraping')
        pass
    
    style = 'BODY {color: white;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    
    book.add_item(nav_css)

    book.spine = spine
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    novel_filename =  sub(r'[^\w]', '_', title).lower()
    
    epub.write_epub(f'{directory}{novel_filename}.epub', book)
    
    logger.info(f'Saved ebook: {directory}{title}.epub')
