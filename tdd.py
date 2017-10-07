#!/usr/bin/python2
from collections import defaultdict
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


class GetPostsThread (threading.Thread):
    def __init__(self, results, blog_name, offset, limit):
        threading.Thread.__init__(self)
        self.results = results
        self.blog_name = blog_name
        self.offset = offset
        self.limit = limit

    def run(self):
        response = client.posts(self.blog_name + '.tumblr.com',
                                         reblog_info=True, notes_info=True, offset=self.offset, limit=self.limit)
        self.results.append(response)


class GetLikesThread (threading.Thread):
    def __init__(self, results, blog_name, offset, limit):
        threading.Thread.__init__(self)
        self.results = results
        self.blog_name = blog_name
        self.offset = offset
        self.limit = limit

    def run(self):
        self.results.append(client.blog_likes(
            self.blog_name + '.tumblr.com', offset=self.offset, limit=self.limit))


class ReturnOnlyExistingBlogsThread (threading.Thread):
    def __init__(self, results, blog_name):
        threading.Thread.__init__(self)
        self.results = results
        self.blog_name = blog_name

    def run(self):
        self.results.append(client.blog_info(self.blog_name + '.tumblr.com'))

def threadThrottler(threads): #This may not be necessary...
    threadsAwait = []

    while len(threads) > 0:
        limit = 10000 if len(threads) >= 100 else len(threads)
        for t in range(limit):
            thread = threads.pop()
            threadsAwait += [thread]
            thread.start()

        for t in threadsAwait:
            t.join()

        threadsAwait = []

def getPosts(blog_name, max_posts):
    results = []
    threads = []
    offset = 0
    while offset + 20 <= max_posts or max_posts == 0:
        # Tumblr will return a max of 20 posts per API call
        # Used to set limit when max_posts is not evenly divisible by 20
        limit = max_posts - (len(results) * 20)
        if limit > 20 or limit <= 0:
            limit = 20

        thread = GetPostsThread(results, blog_name, offset, limit)
        threads += [thread]
        thread.start()

        # 404 status means blog does not exist
        if len(results) > 0 and results[0].get('meta') and results[0]['meta']['status'] != 200:
            break

        if len(results) > 0 and max_posts == 0:
            max_posts = results[0]['blog']['total_posts']

        offset += 20

    if args.verbose:
        print "Retrieving posts..."

        bar = progressbar.ProgressBar()
        for t in bar(threads):
            t.join()
    else:
        for t in threads:
            t.join()

    return results

def getLikes(blog_name, max_posts):
    results = []
    threads = []
    offset = 0
    while offset + 20 <= max_posts or max_posts == 0:
        # Tumblr will return a max of 20 posts per API call
        # Used to set limit when max_posts is not evenly divisible by 20
        limit = max_posts - (len(results) * 20)
        if limit > 20 or limit <= 0:
            limit = 20

        thread = GetLikesThread(results, blog_name, offset, limit)
        threads += [thread]
        thread.start()

        if len(results) > 0 and results[0].get('meta') and results[0]['meta']['status'] != 200:
            break

        if len(results) > 0 and max_posts == 0:
            max_posts = results[0]['liked_count']

        offset += 20

    if args.verbose:
        print "Retrieving likes..."

        bar = progressbar.ProgressBar()
        for t in bar(threads):
            t.join()
    else:
        for t in threads:
            t.join()

    return results


def blogInPostsFrequency(blog_name, max_posts):
    reblogged_from_list = defaultdict(int)

    results = getPosts(blog_name, max_posts)

    if results[0].get('meta') and results[0]['meta']['status'] != 200:
        print "HTTP Status Code: " + results[0]['meta']['status']
        return

    for result in results:
        for post in result['posts']:
            if post.get('reblogged_from_name'):
                if post['reblogged_from_name'] in reblogged_from_list.keys():
                    reblogged_from_list[post['reblogged_from_name']] += 1
                else:
                    reblogged_from_list[post['reblogged_from_name']] = 1

    if args.verbose:
        print "Done calculating frequency."

    return reblogged_from_list


def tagInPostsFrequency(blog_name, max_posts):
    tags_list = defaultdict(int)

    results = getPosts(blog_name, max_posts)

    # 404 status means blog does not exist
    if results[0].get('meta') and results[0]['meta']['status'] == 404:
        print "Blog not found."
        return

    for result in results:
        for post in result['posts']:
            for tag in post['tags']:
                if tag in tags_list.keys():
                    tags_list[tag] += 1
                else:
                    tags_list[tag] = 1

    return tags_list


def comparePosts(source, destination, max_posts):
    # Get post data
    sourceResults = getPosts(source, max_posts)

    # 404 status means blog does not exist
    if sourceResults[0].get('meta') and sourceResults[0]['meta']['status'] == 404:
        print "Source blog not found"
        return

    destinationResults = getPosts(destination, max_posts)

    # 404 status means blog does not exist
    if destinationResults[0].get('meta') and destinationResults[0]['meta']['status'] == 404:
        print "Destination blog not found"
        return

    # Retrieve list of root reblog URLs to use as unique identifiers
    sourceRootReblogURLs = []
    for sourceResult in sourceResults:
        for post in sourceResult['posts']:
            if post.get('reblogged_root_url'):
                sourceRootReblogURLs.append(post['reblogged_root_url'])
            # For capturing source original posts that destination reblogged
            else:
                sourceRootReblogURLs.append(post['post_url'])

    destinationRootReblogURLs = []
    for destinationResult in destinationResults:
        for post in destinationResult['posts']:
            if post.get('reblogged_root_url'):
                destinationRootReblogURLs.append(post['reblogged_root_url'])
            # For capturing destination original posts that source reblogged
            else:
                destinationRootReblogURLs.append(post['post_url'])

    # Actual compare happens here, returns matches out of # of sources
    return [{'matches': len(set(sourceRootReblogURLs).intersection(destinationRootReblogURLs))}, {'num_sources': len(sourceRootReblogURLs)}]


def compareLikes(source, destination, max_posts):
    # Get post data
    sourceResults = getLikes(source, max_posts)

    # 404 status means blog does not exist
    if sourceResults[0].get('meta') and sourceResults[0]['meta']['status'] == 404:
        print "Source blog not found"
    elif sourceResults[0].get('meta') and sourceResults[0]['meta']['status'] == 403:
        print "Source blog not sharing likes"

    destinationResults = getLikes(destination, max_posts)

    # 404 status means blog does not exist
    if destinationResults[0].get('meta') and destinationResults[0]['meta']['status'] == 404:
        print "Destination blog not found"
    elif destinationResults[0].get('meta') and sourceResults[0]['meta']['status'] == 403:
        print "Source blog not sharing likes"

    # Retrieve list of root reblog URLs to use as unique identifiers
    sourceLikeURLs = []
    for sourceResult in sourceResults:
        for like in sourceResult['liked_posts']:
            if like.get('source_url'):
                sourceLikeURLs.append(like['source_url'])
            # Else, we're gonna try imperfect matching
            else:
                sourceLikeURLs.append(like['reblog_key'])

    destinationLikeURLs = []
    for destinationResult in destinationResults:
        for like in destinationResult['liked_posts']:
            if like.get('source_url'):
                destinationLikeURLs.append(like['source_url'])
            else:
                destinationLikeURLs.append(like['reblog_key'])

    # Actual compare happens here, returns matches out of # of sources
    return [{'matches': len(set(sourceLikeURLs).intersection(destinationLikeURLs))}, {'num_sources': len(sourceLikeURLs)}]


def blogInLikesFrequency(blog_name, max_posts):
    liked_blog_list = defaultdict(int)

    results = getLikes(blog_name, max_posts)

    # 404 status means blog does not exist
    if results[0].get('meta') and results[0]['meta']['status'] == 404:
        return ["Blog not found"]
    elif results[0].get('meta') and results[0]['meta']['status'] == 403:
        return ["Blog not sharing likes"]

    for result in results:
        for post in result['liked_posts']:
            if post['blog_name'] in liked_blog_list.keys():
                liked_blog_list[post['blog_name']] += 1
            else:
                liked_blog_list[post['blog_name']] = 1

    return liked_blog_list


def tagInLikesFrequency(blog_name, max_posts):
    tags_list = defaultdict(int)

    results = getLikes(blog_name, max_posts)

    # 404 status means blog does not exist
    if results[0].get('meta') and results[0]['meta']['status'] == 404:
        return ["Blog not found"]
    elif results[0].get('meta') and results[0]['meta']['status'] == 403:
        return ["Blog not sharing likes"]

    for result in results:
        for post in result['liked_posts']:
            for tag in post['tags']:
                if tag in tags_list.keys():
                    tags_list[tag] += 1
                else:
                    tags_list[tag] = 1

    return tags_list


def blogInNotesFrequency(blog_name, note_type, max_posts):
    accepted_note_type_params = ['reblog', 'like', 'both']
    if note_type not in accepted_note_type_params:
        return ['Only \'reblog\', \'like\', or \'both\' note_type accepted.']

    note_list = defaultdict(int)

    results = getPosts(blog_name, max_posts)

    # 404 status means blog does not exist
    if results[0].get('meta') and results[0]['meta']['status'] == 404:
        return ["Blog not found"]

    for result in results:
        for post in result['posts']:
            for note in post['notes']:
                if note['type'] == note_type or "both" == note_type:
                    if note['blog_name'] in note_list.keys():
                        note_list[note['blog_name']] += 1
                    else:
                        note_list[note['blog_name']] = 1

    return note_list


def returnOnlyExistingBlogs(dictionary):
    threads = []
    results = []
    clean_dict = defaultdict(int)

    for blog_name in dictionary:
        thread = ReturnOnlyExistingBlogsThread(results, blog_name)
        threads += [thread]
        thread.start()

    print "Checking existance of blogs..."
    bar = progressbar.ProgressBar()
    for t in bar(threads):
        t.join()

    for result in results:
        if result.get('meta') and result['meta']['status'] != 200:
            pass
        else:
            blog_name = result['blog']['name']
            clean_dict[blog_name] = dictionary[blog_name]

    if args.verbose:
        print "Done filtering blog names."
    return clean_dict


def printInOrder(dictionary, descending, limit):
    print ""

    if limit == 0:
        limit = len(dictionary)

    count = 0
    for i in sorted(dictionary, key=dictionary.__getitem__, reverse=descending):
        if count <= limit:
            print(i + " " + str(dictionary[i]))
            count += 1
        else:
            break

    print ""


# CONTROL CENTER
parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
parser.add_argument(
    "blog_name", help="the name of the blog you are searching on")
parser.add_argument(
    "max_posts", help="the maximum amount of posts to take into consideration", type=int)
parser.add_argument(
    "--existing", help="only print existing blogs", action="store_true")
parser.add_argument(
    "--verbose", help="indicate progress", action="store_true")
group.add_argument("--reblogs", help="blog reblog frequency",
                   action="store_true")
group.add_argument("--likes", help="blog like frequency", action="store_true")
group.add_argument(
    "--notes", help="blog appears in notes frequency", action="store_true")
group.add_argument(
    "--posttags", help="tag appears on post frequency", action="store_true")
group.add_argument(
    "--liketags", help="tag appears on like frequency", action="store_true")
group.add_argument(
    "--compareposts", help="compare posts shared between two blogs", action="store_true")
group.add_argument(
    "--comparelikes", help="compage likes shared between two blogs", action="store_true")
args = parser.parse_args()

result = None
if args.reblogs:
    result = blogInPostsFrequency(args.blog_name, args.max_posts)
if args.likes:
    result = blogInLikesFrequency(args.blog_name, args.max_posts)
if args.notes:
    result = blogInNotesFrequency(args.blog_name, "both", args.max_posts)
if args.posttags:
    result = tagInPostsFrequency(args.blog_name, args.max_posts)
if args.liketags:
    result = tagInLikesFrtequency(args.blog_name, args.max_posts)
if args.compareposts:
    pass
if args.comparelikes:
    pass

if args.existing and not (args.posttags or args.liketags or args.compareposts or args.comparelikes):
    result = returnOnlyExistingBlogs(result)
else:
    print "Argument --existing is not compatible with arguments --posttags, --liketags, --compareposts, or --comparelikes."

printInOrder(result, True, 0)
