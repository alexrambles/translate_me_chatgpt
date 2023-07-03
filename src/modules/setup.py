from setuptools import setup, find_packages

VERSION = '0.0.1' 
DESCRIPTION = 'Translates a web-hosted document into english and packages into an epub file.'
LONG_DESCRIPTION = 'A python package that takes a link from a webnovel (currently only Shubaow) and translates the document before compiling into an .epub.'

# Setting up
setup(
       # the name must match the folder name 'verysimplemodule'
        name="translate_me_chatgpt", 
        version=VERSION,
        author="Alexis Richard",
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        packages=find_packages(),
        install_requires=[], # add any additional packages that 
        # needs to be installed along with your package. Eg: 'caer'
        
        keywords=['python', 'first package', 'web scraper', 'ebook compiler', 'translator'],
        classifiers= [
            "Development Status :: 2 - Pre-Alpha",
            "Intended Audience :: End Users/Desktop",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 3",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: Microsoft :: Windows",
        ]
)