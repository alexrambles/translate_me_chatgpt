This originally was a scraper that mostly utilized Shubaow, but since Shubaow has since been shut down, I'm diversifying. Also, originally was going to integrate ChatGPT because I found that gave the best translation results. But that feature is being delayed for now in favor of hammering out the kinks of the google translate version.

## Current State:
#### Not currently using chatgpt
- [x] using google translate instead of chatgpt. I'm going to concentrate on getting it functional before integrating ChatGPT. 
Hopefully I can build this in a way that allows users to use either chatGPT or google translate. 
That way the API isn't necessary, and it can stay free.
- [x] translates text scraped from Shubaow
- [x] supports both mobile and desktop versions of the site
- [x] support for other websites is being added.
- [x] detects character encoding and tries most common substitutes where applicable 
(gbk for GB2312 is the one I see most often for simplified Chinese characters.)

## Features Planned:
- [ ] translate html files
- [ ] reduce the calls to whatever translation API is being used... Maybe concatenate with a special divider string, translate, then return before slicing into a new list?
- [ ] create a queue so you can concurrently scrape and translate websites or scrape one after another.
- [ ] integrate training feature where you can correct translations
- [ ] the ability to correct the dictionary (custom dictionary that takes precedence over translator's dict?)
- [ ] import api key from a txt file in the directory

## Current Bugs

## Notes:
    So I want to integrate proxies into the project so that we can change our IP. There is proxy={}, and the api key method for some vpns.