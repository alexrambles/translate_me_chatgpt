# translate_me_chatgpt is a WIP. It's probably broken--I make no promises. I'm constantly updating it. It'll have a version once it's up and running properly!
Using ChatGPT and google translate to translate scraped webnovels in other languages into english (for now).

## Current State:
### Not currently using chatgpt
- [x] using google translate instead of chatgpt. I'm going to concentrate on getting it functional before integrating ChatGPT. 
Hopefully I can build this in a way that allows users to use either chatGPT or google translate. 
That way the API isn't necessary, and it can stay free.
- [x] translates text scraped from Shubaow
- [x] supports both mobile and desktop versions of the site
- [x] detects character encoding and tries most common substitutes where applicable 
(gbk for GB2312 is the one I see most often for simplified Chinese characters.)

## Features Planned:
- [ ] translate strings
- [ ] translate html files
- [ ] reduce the calls to whatever translation API is being used... Maybe concatenate with a special divider string, translate, then return before slicing into a new list?
- [ ] integrate training feature where you can correct translations
- [ ] the ability to correct the dictionary (custom dictionary that takes precedence over transator's dict?)

## Current Bugs
