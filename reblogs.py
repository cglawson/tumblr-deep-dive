#!/usr/bin/python2
from collections import defaultdict
from time import sleep
import pytumblr
import json
import threading
import argparse
import progressbar

# Please generate and enter your own API key/secret and OAuth token/secret below.
# You are using this script for your own purposes, and may have added your own customizations.
# You agree to follow Tumblr's API License Agreement and ToS in utilizing any part of the following code.
#   https://www.tumblr.com/policy/en/terms-of-service
#   https://www.tumblr.com/docs/en/api_agreement

# Prior to your first run, register your own application with Tumblr's API to obtain a key.
#   https://www.tumblr.com/oauth/apps
# Obtain your OAuth token/secret from Tumblr's API Console and enter the details below.
#   https://api.tumblr.com/console/calls/user/info

client = pytumblr.TumblrRestClient(
    '',  # consumer_key
    '',  # consumer_secret
    '',  # oauth_token
    '')  # oauth_secret

http_error_codes = defaultdict(int)


class GetPostsThread (threading.Thread):
    def __init__(self, reblogged_from_list, blog_name, offset, limit, delay):
        threading.Thread.__init__(self)
        self.reblogged_from_list = reblogged_from_list
        self.blog_name = blog_name
        self.offset = offset
        self.limit = limit
        self.delay = delay

    def run(self):

        if self.delay > 0:
            sleep(self.delay)

        response = client.posts(self.blog_name + '.tumblr.com',
                                reblog_info=True, notes_info=True, offset=self.offset, limit=self.limit)

        try:
            for post in response['posts']:
                if post.get('reblogged_from_name'):
                    if post['reblogged_from_name'] in self.reblogged_from_list.keys():
                        self.reblogged_from_list[post['reblogged_from_name']] += 1
                    else:
                        self.reblogged_from_list[post['reblogged_from_name']] = 1
        except:
            error = str(response['meta']['status']) + \
                " - " + response['meta']['msg'] + ";"
            if error in http_error_codes.keys():
                http_error_codes[error] += 1
            else:
                http_error_codes[error] = 1


class ReturnOnlyExistingBlogsThread (threading.Thread):
    def __init__(self, results, blog_name, delay):
        threading.Thread.__init__(self)
        self.results = results
        self.blog_name = blog_name
        self.delay = delay

    def run(self):

        if self.delay > 0:
            sleep(self.delay)

        self.results.append(client.blog_info(self.blog_name + '.tumblr.com'))


def getPosts(blog_name, max_posts):
    reblogged_from_list = defaultdict(int)
    threads = []
    offset = 0
    iteration = 1
    while max_posts - offset > 0:
        # Tumblr will return a max of 20 posts per API call
        # Used to set limit when max_posts is not evenly divisible by 20
        limit = max_posts - offset

        if limit > 20 or limit <= 0:
            limit = 20

        if args.rate_limit != None:
            delay = (args.rate_limit * iteration) / 1000.0
        else:
            delay = 0

        thread = GetPostsThread(reblogged_from_list,
                                blog_name, offset, limit, delay)
        threads += [thread]
        thread.start()

        offset += 20
        iteration += 1

    if args.verbose:
        print "Retrieving posts..."

        bar = progressbar.ProgressBar()
        for t in bar(threads):
            t.join()
    else:
        for t in threads:
            t.join()

    return reblogged_from_list


def returnOnlyExistingBlogs(dictionary):

    threads = []
    results = []
    clean_dict = defaultdict(int)
    iteration = 1

    if len(dictionary) > 0:
        for blog_name in dictionary:

            if args.rate_limit != None:
                delay = (args.rate_limit * iteration) / 1000.0
            else:
                delay = 0

            thread = ReturnOnlyExistingBlogsThread(results, blog_name, delay)
            threads += [thread]
            thread.start()

            iteration += 1

        if args.verbose:
            print "Checking existance of blogs..."
            bar = progressbar.ProgressBar()
            for t in bar(threads):
                t.join()
        else:
            for t in threads:
                t.join()

        for result in results:
            if result.get('meta') and result['meta']['status'] != 200:
                pass
            else:
                blog_name = result['blog']['name']
                clean_dict[blog_name] = dictionary[blog_name]

    return clean_dict


def printInOrder(dictionary, descending, limit):
    if len(dictionary) > 0:
        print ""

        if limit == 0:
            limit = len(dictionary)

        count = 0
        for i in sorted(dictionary, key=dictionary.__getitem__, reverse=descending):

            if args.threshold == None:  # Then, the option is not used.
                pass
            # Then, the item is above the threshold.
            elif args.threshold < dictionary[i]:
                pass
            elif ";" in i:  # Then, it is an HTTP Error code and we should display anyway.
                pass
            else:  # The item violates the threshold.
                break

            if (count <= limit):
                print(i + " " + str(dictionary[i]))
                count += 1
            else:
                break

        print ""


# CONTROL CENTER
parser = argparse.ArgumentParser()
parser.add_argument(
    "blog_name", help="the name of the blog you are searching on")
parser.add_argument(
    "max_posts", help="the maximum amount of posts to take into consideration", type=int)
parser.add_argument(
    "--rate_limit", help="delay in milliseconds between requests", type=int)
parser.add_argument(
    "--max_print", help="maximum blogs to print", type=int)
parser.add_argument(
    "--threshold", help="blogs must have a equal or greater than this number",  type=int)
parser.add_argument(
    "--existing", help="only print existing blogs", action="store_true")
parser.add_argument(
    "--verbose", help="indicate progress", action="store_true")
parser.add_argument(
    "--ascending", help="print blogs in ascending order", action="store_true")
args = parser.parse_args()

result = getPosts(args.blog_name, args.max_posts)

if args.existing:
    result = returnOnlyExistingBlogs(result)

if len(http_error_codes) > 0:
    print "\nHTTP Error Codes Occured: "
    printInOrder(http_error_codes, True, 0)

printInOrder(result, False if args.ascending == True else True,
             0 if args.max_print == None else args.max_print)
