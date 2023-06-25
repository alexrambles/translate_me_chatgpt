import os
import requests
from bs4 import BeautifulSoup
from googletrans import Translator
from epubwriter import EPUB
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to get the BeautifulSoup object for a given URL
def get_soup(url):
    response = requests.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')

# Function to scrape the document metadata
def scrape_metadata(soup):
    title = soup.select_one('.bookname h1').text.strip()
    author = soup.select_one('.bookinfo p:nth-of-type(1)').text.strip()
    description = soup.select_one('#intro p').text.strip()
    cover_url = soup.select_one('.picborder img')['src']
    return title, author, description, cover_url

def scrape_chapter_links(base_url, soup):
    chapter_links = soup.select('.listmain dd a')
    sorted_links = sorted(chapter_links, key=lambda link: int(link.text))
    return [(link.text.strip(), base_url + link['href']) for link in sorted_links]

# Function to scrape a chapter and return its content
def scrape_chapter(chapter_url):
    chapter_response = requests.get(chapter_url)
    chapter_response.raise_for_status()
    chapter_soup = BeautifulSoup(chapter_response.text, 'html.parser')
    chapter_content = chapter_soup.select_one('#content').text.strip()
    return chapter_content

# Function to translate text to English
def translate_text(text):
    translator = Translator()
    translated_text = translator.translate(text, dest='en').text
    return translated_text

# Function to save content as an HTML file
def save_html(content, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)

# Function to scrape the document content and create the EPUB book
def scrape_document(url):
    def split_url(url, separator, position=int):
        base_url = url.split(separator)
        return separator.join(base_url[:position]), separator.join(base_url[position:])

    base_url = split_url(url, '/', 3)
    logger.info('Scraping TOC document...')
    soup = get_soup(url)
    title, author, description, cover_url = scrape_metadata(soup)
    logger.debug(f'Title: {title}')
    logger.debug(f'Author: {author}')
    logger.debug(f'Description: {description}')
    logger.debug(f'Cover URL: {cover_url}')
    
    epub = EPUB(title, author)
    epub.set_description(description)
    epub.set_cover_image(cover_url)
    
    chapter_links = soup.select('.listmain dd a')
    
    for i, link in enumerate(chapter_links):
        chapter_title = link.text.strip()
        chapter_url = base_url + link['href']
        logger.debug(f'Scraping Chapter {i+1} - {chapter_title}')
        
        chapter_content = scrape_chapter(chapter_url)
        translated_content = translate_text(chapter_content)
        
        filename = f'chapter{i+1}.html'
        save_html(f'<h1>{chapter_title}</h1>\n<p>{translated_content}</p>\n', filename)
        
        logger.debug(f'Saved Chapter {i+1} as HTML file')
        epub.add_html(filename, chapter_title)
        os.remove(filename)
    
    epub.save(f'{title}.epub')
    logger.info('EPUB book created successfully!')
