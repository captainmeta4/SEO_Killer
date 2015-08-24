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

    def load_options(self):
        try:
            self.options = eval(r.get_wiki_page(master_subreddit,"options").content_md)
            print("options cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the options wiki page")
            elif e.response.status_code == 404:
                print("already-done cache not loaded. Starting with blank options cache")
                self.options={}
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

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
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

                    #check whitelists
                    if (any(domain in submission.domain for domain in self.options[submission.subreddit.display_name]['domain_whitelist'])
                        or self.listing[submission.subreddit.display_name][submission.id] in self.options[submission.subreddit.display_name]['user_whitelist']):
                        print('but user or domain is whitelisted')
                        self.listing[subreddit.display_name].pop(submission.id)
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

            #pass if alert has been triggered
            if submission.id in self.already_done:
                continue

            #pass if OP deleted their reddit account
            if not isinstance(submission.author, praw.objects.Redditor):
                continue

            #Pass if /r/SEO_Killer, or if a new subreddit that was added during the cycle
            #or if subreddit is ignored
            if (submission.subreddit == master_subreddit
                or submission.subreddit.display_name not in self.listing
                or self.options[submission.subreddit.display_name]['justiciar_ignore']):
                continue

            #add submission to listing if its not already there
            if submission.id not in self.listing[submission.subreddit.display_name]:
                self.listing[submission.subreddit.display_name][submission.id]=submission.author.name
                
            #Pass if the author has no recorded deletions
            #or if auhor is whitelisted
            if (submission.author.name in self.options[submission.subreddit.display_name]['user_whitelist']
                or submission.author.name not in self.deletions):
                continue

            #pass if the author has no recorded deletions from that domain,
            #or if it's a selfpost
            #or if domain is whitelisted
            if (submission.domain not in self.deletions[submission.author.name]
                or submission.domain == 'self.'+submission.subreddit.display_name
                or any(domain in submission.domain for domain in self.options[submission.subreddit.display_name]['domain_whitelist'])):
                continue

            #At this point we know that the user is deleting+reposting the domain,
            #but first check if the alert has already triggered

            

            self.already_done.append(submission.id)

            print('Deletion+repost detected in /r/'+submission.subreddit.display_name+' by /u/'+submission.author.name)
                
            msg=("I've caught the following user deleting and reposting a domain:"+
                 "\n\n**User:** /u/"+submission.author.name+
                 "\n\n**Domain:** ["+submission.domain+"](http://reddit.com/domain/"+submission.domain+")"+
                 "\n\n**Permalink:** ["+submission.title+"]("+submission.permalink+")"+
                 "\n\nPast [deleted] submissions by /u/"+submission.author.name+" to "+submission.domain+":\n")

            for entry in self.deletions[submission.author.name][submission.domain]:
                msg=msg+"\n* http://redd.it/"+entry

            msg=msg+"\n\n*If this domain is spam, consider reporting it to /r/SEO_Killer*"


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

    def check_messages(self):

        print("Checking messages")

        for message in r.get_unread(limit=None):

            #Ignore post replies
            if message.subject == "comment reply":
                message.mark_as_read()
                continue

            #Just assume all messages are a mod invite, and fetch modlist if invite accepted
            try:

                #Don't accept mod invites for over-18 subreddits
                if message.subreddit.over18:
                    message.mark_as_read()
                    message.reply("Sorry, I don't moderate over-18 subreddits.")
                    continue
                
                r.accept_moderator_invite(message.subreddit.display_name)
                print("Accepted moderator invite for /r/"+message.subreddit.display_name)

                #make a new options set if necessary
                if message.subreddit.display_name not in self.options:
                    self.options[message.subreddit.display_name]={"remove_blacklisted":False, 'domain_whitelist':[], 'user_whitelist':[], 'justiciar_ignore': False}
                    r.edit_wiki_page(master_subreddit,'options',str(self.options))
                
                #send greeting
                msg=("Hello, moderators of /r/"+message.subreddit.display_name+"!\n\n"+
                     "I am a collection of three bots designed to help curb SEO spam on reddit."+
                     "Executioner maintains a global blacklist of sites known to engage in SEO spam."+
                     "To toggle Executioner's global ban list between Report mode and Remove mode, send me a PM with the subreddit name as the subject and `remove_blacklisted' as the message body. "+
                     "\n\n('Posts' permissions is necessary for Remove mode. The default mode is Report.)"+
                     "\n\nExecutioner will also send you a weekly update with any domains that have been added to or removed from my global ban list. "+
                     "If you wish to override the global ban list for any particular domain, please make use of my per-subreddit whitelist feature."+
                     "\n\nJusticiar will alert you when a user is detected deleting-and-reposting to a particular domain. "+
                     "It needs 'posts' permissions (to view the /about/spam page), though; otherwise deletion detection will be too inefficient to operate on your subreddit."+
                     "\n\nFinally, Guardian will quietly analyze domain submission statistics, and post possible spam domains to /r/SEO_Killer for human review."+
                     "\n\nFor more information, see my [subreddit](/r/SEO_Killer) and my [guide page](/r/SEO_Killer/wiki/guide). My code is on [GitHub](https://github.com/captainmeta4/SEO_Killer)"+
                     "\n\nFeedback may be directed to my creator, /u/captainmeta4. Thanks for using me!")
                r.send_message(message.subreddit,"Hello!",msg)

                message.mark_as_read()
                
                continue
            except:
                pass

            #Whitelist-related commands. Enclosed in try to protect against garbage input

            try:
                if message.author in r.get_moderators(message.subject):

                    if message.subject not in self.options:
                        msg=("I don't have options data for that subreddit. Either I'm not a moderator there, or you mistyped the subreddit name."+
                             '\n\nNote that you must correctly capitalize the subreddit name - for example, "SEO_Killer" would be correct, while "seo_killer" would not be.')
                        r.send_message(message.author, "Error", msg)
                        message.mark_as_read()
                        continue

                    #Read whitelist
                    if message.body == "whitelist":
                        print("whitelist query from /u/"+message.author.name+" about /r/"+message.subject)
                        msg = "The following domains are in the /r/"+message.subject+" domain whitelist:\n"

                        self.options[message.subject]['domain_whitelist'].sort()
                        self.options[message.subject]['user_whitelist'].sort()
                            
                        if len(self.options[message.subject]['domain_whitelist'])==0:
                            msg=msg + "\n* *none*"
                        else:
                            for entry in self.options[message.subject]['domain_whitelist']:
                                msg = msg +"\n* "+entry

                        msg=msg+"\n\nThe following users are in the /r/"+message.subject+" user whitelist:\n"

                        if len(self.options[message.subject]['user_whitelist'])==0:
                            msg=msg + "\n* *none*"
                        else:
                            for entry in self.options[message.subject]['user_whitelist']:
                                msg = msg +"\n* "+entry
                               

                        r.send_message(message.author,"Whitelist for /r/"+message.subject,msg)

                        message.mark_as_read()

                        continue

                    #modify whitelist
                    else:
                        #domain whitelist
                        if self.is_valid_domain(message.body):

                            if message.body in self.options[message.subject]['domain_whitelist']:
                                self.options[message.subject]['domain_whitelist'].remove(message.body)
                                print(message.body+" removed from domain whitelist for /r/"+message.subject)
                                message.reply(message.body+" removed from domain whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"options",str(self.options),reason=message.body+" removed from domain whitelist for /r/"+message.subject+"by /u/"+message.author.name)
                                message.mark_as_read()
                                continue
                            else:
                                self.options[message.subject]['domain_whitelist'].append(message.body)
                                print(message.body+" added to domain whitelist for /r/"+message.subject)
                                message.reply(message.author,"Domain Whitelist Modified",message.body+" added to domain whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"options",str(self.options),reason=message.body+" added to domain whitelist for /r/"+message.subject+"by /u/"+message.author.name)
                                message.mark_as_read()
                                continue
                        #user whitelist
                        elif self.is_valid_username(message.body):
                            if message.body in self.options[message.subject]['user_whitelist']:
                                self.options[message.subject]['user_whitelist'].remove(message.body)
                                print("/u/"+message.body+" removed from user whitelist for /r/"+message.subject)
                                message.reply(message.body+" removed from user whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"options",str(self.options),reason=message.body+" removed from user whitelist for /r/"+message.subject+"by /u/"+message.author.name)
                                message.mark_as_read()
                                continue
                            else:
                                self.options[message.subject]['user_whitelist'].append(message.body)
                                print(message.body+" added to user whitelist for /r/"+message.subject)
                                message.reply(message.body+" added to user whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"options",str(self.options),reason=message.body+" added to domain whitelist for /r/"+message.subject+"by /u/"+message.author.name)
                                message.mark_as_read()
                        else:
                            print("garbage message from /u/"+message.author.name)
                            r.send_message(message.author,"Error","This doesn't look like a valid username or domain:\n\n"+message.body)
                            message.mark_as_read()
                else:
                    print("invalid message from /u/"+message.author.name)
                    r.send_message(message.author,"Error","You are not a moderator of /r/"+message.subject)
                    message.mark_as_read()
            except:
                pass
            
    def is_valid_domain(self, domain):
        if re.search("^[a-zA-Z0-9][-.a-zA-Z0-9]*\.[-.a-zA-Z0-9]*[a-zA-Z0-9]$",domain):
            return True
        else:
            return False

    def is_valid_username(self, username):
        
        if re.search("^/?u/[A-Za-z0-9_-]{3,20}$",username):
            return True
        else:
            return False
                
    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)        
    def run(self):

        self.login_bot()
        self.load_caches()

        while 1:

            print('running cycle')

            self.check_for_new_subreddits()
            self.load_options()

            for subreddit in r.get_my_moderation(limit=None):

                #Ignore /r/SEO_Killer and subreddits added during cycle
                #also ignore subreddits ignored by justiciar
                if (subreddit == master_subreddit
                    or subreddit.display_name not in self.listing
                    or self.options[subreddit.display_name]['justiciar_ignore']):
                    continue
                
                self.find_deletions(subreddit)

            self.check_new_submissions()

            self.save_caches()
        

#Master bot process
if __name__=='__main__':    
    modbot = Bot()
    
    modbot.run()
