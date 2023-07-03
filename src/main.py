from __init__ import scrape_document
from pathlib import Path


url = input('Please enter the URL of the document or TOC of the document to be translated.\n')
directory = input('Where would you like to save your book?\n')

if directory != '' and directory[-1] != '/':
    directory += '/'

if directory == '':
    directory = Path.home().joinpath('Documents', 'Books')
    
scrape_document('D:/alexi/Documents/Books/', url)
