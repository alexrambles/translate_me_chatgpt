from __init__ import find_source
from pathlib import Path


url = input('Please enter the URL of the document or TOC of the document to be translated.\n')
directory = input('Where would you like to save your book?\n')

if directory != '' and directory[-1] != '/':
    directory += '/'

if directory == '':
    directory = Path.home().joinpath('Documents', 'Books')
    
find_source('D:/alexi/Documents/Books/', url)
