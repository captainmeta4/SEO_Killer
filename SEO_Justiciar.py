import praw
import time
import os
from retrying import retry
from collections import deque
from collections import OrderedDict
import re
from requests.exceptions import HTTPError
import requests

#initialize reddit
user_agent='SEO_Killer - Justiciar Module by /u/captainmeta4 - see /r/SEO_Killer'
r=praw.Reddit(user_agent=user_agent)
headers={'User-Agent': user_agent}

#set globals
username = 'SEO_Killer'
password = os.environ.get('password')

master_subreddit=r.get_subreddit('SEO_Killer')


class Bot(object):

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def login_bot(self):

        print("logging in...")
        r.login(username, password)
        print("success")

    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)    
    def load_caches(self):
        #load already-processed submissions cache and modlist cache
        print("loading caches")
        
        try:
            self.listing = eval(r.get_wiki_page(master_subreddit,"justiciar_listing").content_md)
            print("justiciar listing cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the justiciar_listing wiki page")
            elif e.response.status_code == 404:
                print("justiciar_listing cache not loaded. Starting with blank listing")
                self.listing={}
                for subreddit in r.get_my_moderation():
                    self.listing[subreddit.display_name]=OrderedDict()
                
                r.edit_wiki_page(master_subreddit,'justiciar_listing',str(self.listing))
            elif e.response.status_code in [502, 503, 504]:
                print("reddit's crapping out on us")
                raise e #triggers the @retry module
            else:
                raise e

        try:
            self.deletions = eval(r.get_wiki_page(master_subreddit,"deletions").content_md)
            print("deletions cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the deletions wiki page")
            elif e.response.status_code == 404:
                print("deletions cache not loaded. Starting with blank deletions cache")
                self.deletions={}
            elif e.response.status_code in [502, 503, 504]:
                print("reddit's crapping out on us")
                raise e #triggers the @retry module
            else:
                raise e
        
    def get_ids_of_new(self, subreddit, quantity):

        #Returns submissions as an OrderedDict of submission id's and authors

        print ('getting ids of new posts in /r/'+subreddit.display_name)

        self.new=OrderedDict()
            
        for submission in subreddit.get_new(limit=quantity):

            try:
                self.new[submission.id]=submission.author.name
            except AttributeError:
                #This error happens wherever there's a [deleted] post in the /new queue.
                #[deleted] in /new only happens when the owner deleted their reddit account.
                #So we can safely ignore these.
                pass

        return self.new

    def is_deleted(self, thing_id):

        print ('confirming deletion on http://redd.it/'+thing_id)

        #Checks that a submission's .author attribute is a Redditor.
        #If a submission is [deleted], the .author attribute is a NoneType.
        if not isinstance(r.get_info(thing_id='t3_'+thing_id).author, praw.objects.Redditor):
            print('http://redd.it/'+thing_id+' is deleted.')
            return True
        else:
            print('http://redd.it/'+thing_id+' is not deleted.')
            return False

    def find_deletions(self, subreddit):

        print ('checking for possible deletions in /r/'+subreddit.display_name)

        current_posts = self.get_ids_of_new(subreddit, 1000)

        for entry in self.listing[subreddit.display_name]:

            #if it's not in current_posts, then check to see if it's deleted, and if it is, remember it
            if (entry not in current_posts
                and is_deleted(entry)):

                print('deleteion detected: http://redd.it/'+entry+" by /u/"+self.listing[subreddit.display_name][entry])

                #set up new author if needed
                if self.listing[subreddit.display_name][entry] not in self.deletions:
                    self.deletions[self.listing[subreddit.display_name][entry]]={}

                #get the deleted submission domain
                domain = r.get_info(thing_id='t3_'+item).domain

                #set up new domain within that author, if needed
                if domain not in self.deletions[self.listing[subreddit.display_name][entry]]:
                    self.deletions[self.listing[subreddit.display_name][entry]][domain]=[]
                    
                #and finally, append the deleted submission id
                self.deletions[self.listing[subreddit.display_name][entry]][domain].append(entry)

    def check_new_submissions(self):

        print('checking new submissions for reposts')

        for submission in r.get_subreddit('mod').get_new(limit=100):
                
            #Pass if the author has no recorded deletions (and add submission to listing)
            if submission.author.name not in self.deletions:
                if submission.id not in self.listing[submission.subreddit.display_name]:
                    self.listing[submission.subreddit.display_name][submission.id]=submission.author.name
                continue

            #pass if the author has no recorded deletions from that domain,
            #or if it's a selfpost
            #(and add submission to listing)
            if (submission.domain not in self.deletions[submission.author.name]
                or submission.domain == 'self.'+submission.subreddit.display_name):
                if submission.id not in self.listing[submission.subreddit.display_name]:
                    self.listing[submission.subreddit.display_name][submission.id]=submission.author.name
                continue

            #At this point we know that the user is deleting+reposting the domain

            print('Deletion+repost detected in /r/'+submission.subreddit.display_name+'by /u/'+submission.author.name)
                
            msg=("I've caught the following user deleting and reposting a domain:"+
                 "\n\n**User:** /u/"+submission.author.name+
                 "\n\n**Domain:** "+submission.domain+
                 "\n\n**Permalink:** ["+submission.title+"]("+submission.permalink+")"+
                 "\n\nPast [deleted] submissions by /u/"+submission.author.name+" to "+submission.domain+":\n")

            for entry in self.deletions[submission.author.name][submission.domain]:
                msg=msg+"\n* http://redd.it/"+entry

            msg=msg+"\n\n*If this domain is spam, consider reporting it to /r/SEO_Killer*"

            try:
                submission.remove()
            except praw.errors.ModeratorOrScopeRequired:
                pass
                
            r.send_message(submission.subreddit,'Deletion+repost detected',msg)


    def save_caches(self):

        print('saving caches')

        #we're treating the OrderedDicts in self.listing like deques,
        #so remove the old submission entries to keep it at 1k per subreddit
        for entry in self.listing:
            while len(self.listing[entry]) > 1000:
                self.listing[entry].popitem(last=False)
            
        #save the listings cache
        r.edit_wiki_page(master_subreddit,'justiciar_listing',str(self.listing))

        #save the deletions cache
        r.edit_wiki_page(master_subreddit,'deletions',str(self.deletions))

    def check_for_new_subreddits(self):

        print('checking if new subreddits are in my mod list')

        for subreddit in r.get_my_moderation():
            if subreddit.display_name not in self.listing:
                self.listing[subreddit.display_name] = OrderedDict()
            
    def run(self):

        self.login_bot()
        self.load_caches()

        while 1:

            print('running cycle')

            for subreddit in r.get_my_moderation():
                self.find_deletions(subreddit)

            self.check_new_submissions()

            self.save_caches()

            #Run cycle on XX:XX:00
            while time.localtime().tm_sec != 0 :
                time.sleep(1)
        

#Master bot process
if __name__=='__main__':    
    modbot = Bot()
    
    modbot.run()
