import os
from requests import get, Session
from re import sub
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from langid import classify as langid_classify
from pypinyin import pinyin, Style
from ebooklib import epub
import chardet
import cchardet
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to get the BeautifulSoup object for a given URL
def get_soup(header, session, url):
    response = session.get(url, headers=header)
    response.raise_for_status()
    content = response.content
    chardet_encoding = chardet.detect(content)['encoding']
    try:
        response.encoding = response.content.decode(chardet_encoding)
    except UnicodeDecodeError:
        for encoding in ['utf-8','gbk']:
            try:
                response.encoding = cchardet.detect(content)['encoding']
            except UnicodeEncodeError:
                continue
    return BeautifulSoup(response.text, 'html.parser')

# Function to scrape the document metadata
def scrape_metadata(soup):
    title = soup.select_one('#info h1').text.strip()
    translated_title = translate_text(title)
    author = soup.select_one('#info p:nth-of-type(1)').text.strip().split('：')[-1]
    translated_author = translate_text(author)
    description = soup.select_one('#intro p').text.strip()
    translated_description = translate_text(description)
    cover_url = soup.select_one('div img')['src']
    language_code = langid_classify(description)
    return translated_title, translated_author, translated_description, cover_url, language_code

def scrape_chapter_links(base_url, soup):
    unsorted_links = soup.select('#list dl dd a')
    chapter_links = sorted(unsorted_links, key= lambda link: translate_text(str(link)))
    return [(translate_text(link.text.strip()), base_url + link['href']) for link in chapter_links]

# Function to translate text to English
def translate_text(to_be_translated_text):
    translated_chunks = []
    chunk_size = 500  # Specify the desired chunk size

    # Split the text into chunks
    chunks = [to_be_translated_text[i:i+chunk_size] for i in range(0, len(to_be_translated_text), chunk_size)]

    # Translate each chunk
    for chunk in chunks:
        translated = GoogleTranslator(source='auto', target='en').translate(chunk)
        translated_chunks.append(translated)

    # Join the translated chunks
    translated_text = ' '.join(translated_chunks)
    if translated_text != '' and translated_text is not None:
        return translated_text

def normalize_text(text_to_normalize, paragraph_tags = False):
    normalized_list = []

    if type(text_to_normalize) == list:
        for text_item in text_to_normalize:
            cleaned_untranslated_text = sub(r'[\r\n\xa0]+', ' ', text_item).strip()
            if cleaned_untranslated_text == 'None' or cleaned_untranslated_text.replace(' ',  '') == '':
                cleaned_untranslated_text = ''
            if paragraph_tags and cleaned_untranslated_text != '':
                normalized_list.append(f'<p>{cleaned_untranslated_text}</p>')
            elif cleaned_untranslated_text != '':
                normalized_list.append(cleaned_untranslated_text)
    else:
        cleaned_untranslated_text = sub(r'[\r\n\xa0]+', ' ', text_to_normalize).strip()
        if cleaned_untranslated_text == 'None' or cleaned_untranslated_text.replace(' ',  '') == '':
            cleaned_untranslated_text = ''
        if paragraph_tags and cleaned_untranslated_text != '':
            normalized_list.append(f'<p>{cleaned_untranslated_text}</p>')
        elif cleaned_untranslated_text != '':
            normalized_list.append(cleaned_untranslated_text)

    joined_normalized_list = ''.join(normalized_list)

    return joined_normalized_list

# Function to save content as an HTML file
def save_html(content, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)

# Function to scrape a chapter and return its content
def get_chapter_content(headers, session, chapter_url):
    chapter_response = session.get(chapter_url, headers=headers)
    chapter_response.raise_for_status()
    content = chapter_response.content
    chardet_encoding = chardet.detect(content)['encoding']
    try:
        chapter_response.encoding = chapter_response.content.decode(chardet_encoding)
    except UnicodeDecodeError:
        for encoding in ['utf-8','gbk']:
            try:
                chapter_response.encoding = cchardet.detect(content)['encoding']
            except UnicodeEncodeError:
                continue
    chapter_soup =  BeautifulSoup(chapter_response.text, 'html.parser')
    chapter_content_text = []
    chap_soup_content_list = chapter_soup.select('#content *')
    for x in chap_soup_content_list:
        if x.text is None or x.text == '':
            chapter_content_text.append(x.next)
    return chapter_content_text

# Function to scrape the document content and create the EPUB book
def scrape_document(url):
    def split_url(url, separator, position=int):
        base_url = url.split(separator)
        return separator.join(base_url[:position]), separator.join(base_url[position:])

    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36',
    'Referer': 'https://www.google.com/',
    'Accept-Language': 'en-US,en;q=0.9',
    }

    logger.info('Scraping TOC document...')
    session = Session()
    soup = get_soup(headers, session, url)
    title, author, description, cover_url, language_code = scrape_metadata(soup)
    logger.debug(f'Title: {title}')
    logger.debug(f'Author: {author}')
    logger.debug(f'Description: {description}')
    logger.debug(f'Cover URL: {cover_url}')
    
    book = epub.EpubBook()
    book.set_title(title)
    book.add_author(author)
    book.set_language("en")
    book.set_language(language_code)
    
    
    book.set_cover("cover.jpg", session.get(cover_url).content)

    base_url = split_url(url, '/', 3)[0]
    chapter_links = scrape_chapter_links(base_url, soup)

    spine = []
    toc = []

    titlepage_html = f'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="en" xml:lang="en"><head><title>{novel_title}</title><link rel="stylesheet" href="stylesheet.css" type="text/css" /><meta charset = "utf-8"/></head><div epub:type="frontmatter"><body><div class="title">{novel_title}</div><div>This ebook is compiled for educational purposes only and is not to be redistributed.</div><div>Title: {novel_title}</div><div>Author: {novel_author}</div><div class="cover"><h1 id="titlepage">{novel_title}</h1><h2>by {novel_author}</h2><img src="images/cover.jpg"></img></div></body></div></html>'

    ## set title page
    title_page = book.add_item(epub.EpubItem(
        uid="title_page"
        ,file_name="titlepage.html"
        ,content=titlepage_html
        ,media_type="application/xhtml+xml"))

    spine.append("title_page")
    toc.append("title_page")
    
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
        if translated_text != '' and translated_text != 'None' and translated_text is not None:
            translated_contents.append(f'{translated_text}')

        html_ized_content = []

        if len(translated_contents) == 1:
            html_ized_content = translated_contents[0]

        else:
            for content in translated_contents:
                html_ized_content.append(content)

        if type(html_ized_content) != 'list':
            pass
        else:
            html_ized_content = " ".join(html_ized_content)
        
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

    spine.append("nav")

    book.spine = spine
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    epub.write_epub(f'{title}.epub', book)
    
    logger.info('EPUB book created successfully!')

# Example usage
url = 'https://www.shubaow.net/126_126966/'
scrape_document(url)