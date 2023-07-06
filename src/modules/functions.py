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
            except:
                try:
                    req = request.Request(url)
                    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
                    req.add_header('Referer', 'https://www.google.com/')
                    req.add_header('Accept-Language', 'en-US,en;q=0.9,ja-JP;q=0.8,ja;q=0.7')

                    response = request.urlopen(req).read().decode('gbk')
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
    title = soup.select_one('#info h1, .catalog h1').text.strip()
    translated_title = translate_text(title)
    author = soup.select_one('#info p:nth-of-type(1), .p1').text.strip().split('：')[-1]
    translated_author = translate_text(author)
    description = soup.select_one('#intro p, .jj .p2').text.strip()
    translated_description = translate_text(description)
    cover_url = soup.select_one('div img')['src']
    language_code = langid_classify(description)
    return translated_title, translated_author, translated_description, cover_url, language_code[0]

def scrape_chapter_links(base_url, header, session, soup):
    unsorted_links = soup.select('#list dl dd a, ul.p2:nth-of-type(2) li a')
    chapter_links = sorted(unsorted_links, key= lambda link: translate_text(str(link)))

    if soup.select('a.onclick'):
        not_last_toc_pg = True
        next_toc_page = base_url + soup.select('a.onclick')[0]['href']
        soup = get_soup(header, session, next_toc_page)
        
        while not_last_toc_pg:
            unsorted_links = soup.select('#list dl dd a, ul.p2:nth-of-type(2) li a')
            [chapter_links.append(x) for x in sorted(unsorted_links, key= lambda link: translate_text(str(link)))]
            
            if len(soup.select('a.onclick')) == 2:
                next_toc_page = f"{base_url}{soup.select('a.onclick')[1]['href']}"
                soup = get_soup(header, session, next_toc_page)
            else:
                not_last_toc_pg = False

    return [(translate_text(link.text.strip()), base_url + link['href']) for link in chapter_links]

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
def get_chapter_content(headers, session, chapter_url, api_key=None):
    chapter_soup = get_soup(headers, session, chapter_url, api_key)
    
    chapter_content_text = []
    if chapter_soup.select_one('#content *'):
        chap_soup_content_list = chapter_soup.select('#content *')

    else:
        chap_soup_content_list = [node.strip() for node in chapter_soup.select_one('#nr1').stripped_strings]
        
    try:
        for x in chap_soup_content_list:
            if x.text and x.text.strip():
                chapter_content_text.append(x.next)
    except AttributeError:
        chapter_content_text = chap_soup_content_list
        pass
            
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
    title, author, description, cover_url, language_code = scrape_metadata(soup)
    
    logger.info(f'Title: {title}')
    logger.info(f'Author: {author}')
    logger.info(f'Description: {description}')
    logger.info(f'Cover URL: {cover_url}')
    
    book = epub.EpubBook()
    book.set_title(title)
    book.add_author(author)
    book.set_language("en")
    book.set_language(language_code)
    
    book.set_cover("images/cover.jpg", session.get(cover_url).content)

    base_url = split_url(url, '/', 3)[0]
    chapter_links = scrape_chapter_links(base_url, headers, session, soup)

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
    
    for i, (chapter_title, chapter_url) in enumerate(chapter_links):
        logger.debug(f'Scraping Chapter {i+1} - {chapter_title}')
        
        chapter_content_list = get_chapter_content(headers, session, chapter_url)

        element_sublist = []
        to_be_normalized = False
        
        for x in chapter_content_list:
            if '\r' in x:
                to_be_normalized = True

            text_split_by_return = x.split('\r')
            
            for text_item in text_split_by_return:
                element_sublist.append(f"{text_item}")

        element_sublist[:] = [x for x in element_sublist if x != '' and x != '\n']

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
        
        chapter_html_contents = f'<h1>{chapter_title}</h1>\n<div id=\"{chapter_title}\">{html_ized_content}</p>\n'
        filename = f'chapter{i+1}.html'
        save_html(chapter_html_contents, filename)
        
        logger.info(f'Saved Chapter {i+1} as HTML file')
        
        chapter = epub.EpubHtml(title=chapter_title, file_name=filename, lang='en')
        chapter.content = chapter_html_contents

        book.add_item(chapter)
        spine.append(chapter)
        toc.append(chapter)
        
        os.remove(filename)
    
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
