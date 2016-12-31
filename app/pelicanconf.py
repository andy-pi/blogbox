#!/usr/bin/env python
# -*- coding: utf-8 -*- #
# Blogbox settings

#### SYSTEM FIXED SETTINGS####
LOAD_CONTENT_CACHE = False
# This sets the location of the pages - creating clean urls
ARTICLE_SAVE_AS = '{slug}/index.html'
ARTICLE_URL = '{slug}/'
AUTHOR_SAVE_AS = ''
# Puts the blog articles into reverse order, most recent first - default for blogs
REVERSE_ARTICLE_ORDER = True

DIRECT_TEMPLATES = ['index', 'tags', 'archives']
PAGINATED_DIRECT_TEMPLATES = ['index']
RELATIVE_URLS = True

# Enable pages in the menu
# Set clean urls for pages as well
MAIN_MENU = True
DISPLAY_PAGES_ON_MENU = True
PAGE_URL = '{slug}'
PAGE_SAVE_AS = '{slug}/index.html'

DELETE_OUTPUT_DIRECTORY = False
OUTPUT_PATH='pelioutput'
# DISABLE ALL FEEDS
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

#### USER DEFINED SETTINGS ####

#SITELOGO_SIZE=


