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


#Ignore list - Justiciar will neither record deletions nor alert mods for domains
#domains on this list.
ignore_domains=['imgur.com', 'i.imgur.com', 'reddit.com', 'redd.it']



class Bot(object):

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def login_bot(self):

        print("logging in...")
        r.login(username, password)
        print("success")

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)    
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

        try:
            self.already_done = eval(r.get_wiki_page(master_subreddit,"justiciar_alreadydone").content_md)
            print("already done cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the justiciar_alreadydone wiki page")
            elif e.response.status_code == 404:
                print("already-done cache not loaded. Starting with blank deletions cache")
                self.already_done=deque([],maxlen=200)
            elif e.response.status_code in [502, 503, 504]:
                print("reddit's crapping out on us")
                raise e #triggers the @retry module
            else:
                raise e

    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)    
    def get_ids_of_new(self, subreddit, quantity):

        #Returns submissions as an OrderedDict of submission id's and authors

        print ('getting ids of posts in /r/'+subreddit.display_name+'/new')

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

    def break_into_100(self, ids):

        brokenlist=[]
        while len(ids)>0:
            brokenlist.append(ids[0:min(100,len(ids))])
            del ids[0:min(100,len(ids))]

        return brokenlist
        
    def find_deletions(self, subreddit):

        print ('checking for possible deletions in /r/'+subreddit.display_name)


        #Assemble the list of ids to check

        ids=[]
        for entry in self.listing[subreddit.display_name]:
            ids.append('t3_'+entry)

        idlists=self.break_into_100(ids)

        for idlist in idlists:
            for submission in r.get_info(thing_id=idlist):
                if not isinstance(submission.author, praw.objects.Redditor):
    
                    print('deletion detected: http://redd.it/'+submission.id+" by /u/"+self.listing[subreddit.display_name][submission.id])

                    if (submission.domain in ignore_domains
                        or any(item in submission.domain for item in ignore_domains)):
                        print('but domain is ignored')
                        continue
                                    
                    #set up new author if needed
                    if self.listing[submission.subreddit.display_name][submission.id] not in self.deletions:
                        self.deletions[self.listing[subreddit.display_name][submission.id]]={}

                    #set up new domain within that author, if needed
                    if submission.domain not in self.deletions[self.listing[subreddit.display_name][submission.id]]:
                        self.deletions[self.listing[subreddit.display_name][submission.id]][submission.domain]=[]
                                        
                    #and finally, append the deleted submission id, if needed
                    if entry not in self.deletions[self.listing[subreddit.display_name][submission.id]][submission.domain]:
                        self.deletions[self.listing[subreddit.display_name][submission.id]][submission.domain].append(submission.id)

                    #Pop the deletion from the listing so that the post isn't continuously re-checked
                    self.listing[subreddit.display_name].pop(submission.id)


    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def check_new_submissions(self):

        print('checking new submissions for reposts')

        for submission in r.get_subreddit('mod').get_new(limit=200):

            #Pass if /r/SEO_Killer, or if a new subreddit was added during the cycle
            if (submission.subreddit == master_subreddit
                or submission.subreddit.display_name not in self.listing):
                continue
                
            #Pass if the author has no recorded deletions (and add submission to listing if it isn't there already)
            if submission.author.name not in self.deletions:
                if submission.id not in self.listing[submission.subreddit.display_name]:
                    self.listing[submission.subreddit.display_name][submission.id]=submission.author.name
                continue

            #pass if the author has no recorded deletions from that domain,
            #or if it's a selfpost
            #(and add submission to listing if it isn't there already)
            if (submission.domain not in self.deletions[submission.author.name]
                or submission.domain == 'self.'+submission.subreddit.display_name):
                if submission.id not in self.listing[submission.subreddit.display_name]:
                    self.listing[submission.subreddit.display_name][submission.id]=submission.author.name
                continue

            #At this point we know that the user is deleting+reposting the domain,
            #but first check if the alert has already triggered

            if submission.id in self.already_done:
                continue

            print('Deletion+repost detected in /r/'+submission.subreddit.display_name+' by /u/'+submission.author.name)

            #And also make sure it isn't an ignored domain
            if submission.domain in ignore_domains:
                print('but the domain is ignored')
                continue
                
            msg=("I've caught the following user deleting and reposting a domain:"+
                 "\n\n**User:** /u/"+submission.author.name+
                 "\n\n**Domain:** ["+submission.domain+"](http://reddit.com/domain/"+submission.domain+")"+
                 "\n\n**Permalink:** ["+submission.title+"]("+submission.permalink+")"+
                 "\n\nPast [deleted] submissions by /u/"+submission.author.name+" to "+submission.domain+":\n")

            for entry in self.deletions[submission.author.name][submission.domain]:
                msg=msg+"\n* http://redd.it/"+entry

            msg=msg+"\n\n*If this domain is spam, consider reporting it to /r/SEO_Killer*"


            #Add the post to an already-done list so that the modmail won't be duplicated
            self.already_done.append(submission.id)

            #send modmail
            r.send_message(submission.subreddit,'Deletion+repost detected',msg)

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def save_caches(self):

        print('saving caches')

        #we're treating the OrderedDicts in self.listing like deques,
        #so remove the old submission entries to keep it at 1k per subreddit
        for entry in self.listing:
            while len(self.listing[entry]) > 300:
                self.listing[entry].popitem(last=False)
            
        #save the listings cache
        r.edit_wiki_page(master_subreddit,'justiciar_listing',str(self.listing))

        #save the deletions cache
        r.edit_wiki_page(master_subreddit,'deletions',str(self.deletions))

        #save the already-done cache
        r.edit_wiki_page(master_subreddit,'justiciar_alreadydone',str(self.already_done))

    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def check_for_new_subreddits(self):

        print('checking if new subreddits are in my mod list')

        for subreddit in r.get_my_moderation(limit=None):
            if subreddit.display_name not in self.listing:
                print('new subreddit: /r/'+subreddit.display_name)
                self.listing[subreddit.display_name] = OrderedDict()
                
    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)        
    def run(self):

        self.login_bot()
        self.load_caches()

        while 1:

            print('running cycle')

            self.check_for_new_subreddits()

            for subreddit in r.get_my_moderation(limit=None):

                #Ignore /r/SEO_Killer and subreddits added during cycle
                if (subreddit == master_subreddit
                    or subreddit.display_name not in self.listing):
                    continue
                
                self.find_deletions(subreddit)

            self.check_new_submissions()

            self.save_caches()
        

#Master bot process
if __name__=='__main__':    
    modbot = Bot()
    
    modbot.run()
