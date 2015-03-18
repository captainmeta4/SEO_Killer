import praw
import time
import os
from retrying import retry
from collections import deque
import re
from requests.exceptions import HTTPError
import requests


#initialize reddit
user_agent='SEO_Killer - Guardian Module by /u/captainmeta4 - see /r/SEO_Killer'
r=praw.Reddit(user_agent=user_agent)
headers={'User-Agent': user_agent}

#set globals
username = 'SEO_Killer'
password = os.environ.get('password')

master_subreddit=r.get_subreddit('SEO_Killer')

class Bot(object):

    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def analyze_domain(self, domain, action):
        print('Analyzing domain: '+domain)
        
        total_posts=0
        authors=[]
        author_total_posts=[]
        author_domain_posts=[]
        shadowbanned_users=0
        throwaway_users=0
        spamming_users=0

        #calculate # unique users
        
        for submission in r.get_domain_listing(domain,sort='new',limit=1000):
            total_posts=total_posts+1
            try:
                if submission.author.name not in authors:
                    authors.append(submission.author.name)
            except AttributeError:
                pass

        print(str(total_posts)+" submissions by "+str(len(authors))+" unique users")

        #new domains don't get a free pass with easy analytics until there's several posts
        if total_posts <10:
            self.already_done['domains'].remove(domain)
            return
        
        #if there are enough unique authors, don't bother doing full analytics because the domain is probably legit
        #(unless the analysis was ordered instead of automatic)
        if (len(authors) > float(os.environ.get('author_count_threshold'))
            and action=='submit'):
            return
            
        author_total_posts=[0]*len(authors)
        author_domain_posts=[0]*len(authors)

        x=0
        total_users=len(authors)
        while x < len(authors): #not doing for x in range() because len(authors) can change as SB users are removed


            try:
                print ("checking: /u/"+authors[x])
                for submission in r.get_redditor(authors[x]).get_submitted(sort='new', limit=100):
                    author_total_posts[x]=author_total_posts[x]+1
                    if submission.domain in domain or domain in submission.domain:
                        author_domain_posts[x]=author_domain_posts[x]+1

            except HTTPError as e:
                if e.response.status_code == 404:
                    print ("shadowbanned: /u/"+authors[x])
                    shadowbanned_users=shadowbanned_users+1
                    authors.pop(x)
                    author_total_posts.pop(x)
                    author_domain_posts.pop(x)
                    continue
                elif e.response.status_code in [502, 503, 504]:
                    print("reddit's crapping out on us")
                    raise e #triggers the @retry module
                else:
                    raise e
                

            #Check if account is throwaway or spammy
            if author_total_posts[x]<2:
                throwaway_users = throwaway_users+1
            if (author_domain_posts[x]/author_total_posts[x]>float(os.environ.get('spam_threshold'))
                and author_total_posts[x] > 5):
                spamming_users = spamming_users+1

            x=x+1


        #determine if message needs to be assembled
        #variables here are taken from config parameters to avoid giving too much info to spammers
        #(also allows for easy on-the-fly adjustment of parameters)
        if (action=='return'                                                            #If this was a request,
            or total_users < int(float(os.environ.get('user_ratio')) * total_posts)     #or if number of unique authors is low compared to number of total posts
            or total_users * float(os.environ.get('sb_ratio')) < shadowbanned_users     #or if number of shadowbanned users is a high fraction of total unique authors
            or throwaway_users >= float(os.environ.get('throwaway_ratio'))*len(authors) #or if there are too many submissions by throwaway accounts
            or spamming_users >= float(os.environ.get('spammer_threshold'))):           #or if this domain is being spammed by too many users

            print('assembling message')
            
            msg=("["+domain+"](http://reddit.com/domain/"+domain+") has "+str(total_posts)+" submissions by at least "+str(total_users)+" unique users, of whom "+str(shadowbanned_users)+" are shadowbanned."
                 "\n\nThe users who submitted to "+domain+" have the following data:\n\n"+
                 "|User|Total Submissions|Submissions to "+domain+"|% to "+domain+"|\n|-|-|-|-|\n")

            #If there are few enough authors (3 or less) that the post would generate username mentions, do u/username instead of /u/username
            if len(authors)>3:
                for x in range(0,len(authors)):

                    #Prevent a possible ZeroDivisionError if reddit is derping up
                    try:
                        percent=str(int(100*author_domain_posts[x]/author_total_posts[x]))
                    except ZeroDivisionError:
                        percent='-'
                    
                    msg=msg+"| /u/"+authors[x]+"|"+str(author_total_posts[x])+"|"+str(author_domain_posts[x])+"|"+percent+"% |\n"
            else:
                for x in range(0,len(authors)):

                    #Prevent a possible ZeroDivisionError if reddit is derping up
                    try:
                        percent=str(int(100*author_domain_posts[x]/author_total_posts[x]))
                    except ZeroDivisionError:
                        percent='-'
                        
                    msg=msg+"| u/"+authors[x]+"|"+str(author_total_posts[x])+"|"+str(author_domain_posts[x])+"|"+percent+"% |\n"
                
            if action == 'submit':
                print('submitting to /r/SEO_Killer')
                r.submit("SEO_Killer","overview for "+domain,text=msg, send_replies=False)
            elif action == 'return':
                return msg

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
            self.already_done = eval(r.get_wiki_page(master_subreddit,"guardian_alreadydone").content_md)
            print("already-done cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the guardian_alreadydone wiki page")
            elif e.response.status_code == 404:
                print("already-done cache not loaded. Starting with blank cache")
                self.already_done = {'domains':[],'submissions':deque([],maxlen=100)}
                r.edit_wiki_page(master_subreddit,'already_done',str(self.already_done))
            elif e.response.status_code in [502, 503, 504]:
                print("reddit's crapping out on us")
                raise e #triggers the @retry module
            else:
                raise e

        try:
            self.banlist = eval(r.get_wiki_page(master_subreddit,"banlist").content_md)
            print("banlist cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the banlist wiki page")
            elif e.response.status_code == 404:
                print("banlist cache not loaded. Starting with blank banlist")
                self.banlist={'banlist':{},'recent_bans':[],'unbanned':[]}
                r.edit_wiki_page(master_subreddit,'ban_list',str(self.banlist))
            elif e.response.status_code in [502, 503, 504]:
                print("reddit's crapping out on us")
                raise e #triggers the @retry module
            else:
                raise e
        
        try:
            self.whitelist = eval(r.get_wiki_page(master_subreddit,"whitelist").content_md)
            print("whitelist cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the whitelist wiki page")
            elif e.response.status_code == 404:
                print("whitelist cache not loaded. Starting with blank whitelist")
                self.whitelist={}
                r.edit_wiki_page(master_subreddit,'whitelist',str(self.whitelist))
            elif e.response.status_code in [502, 503, 504]:
                print("reddit's crapping out on us")
                raise e #triggers the @retry module
            else:
                 raise e

    
        
    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def process_submissions(self):
        print('processing submissions')

        for submission in r.get_subreddit('mod').get_new(limit=100):


        
            #avoid duplicate work, whitelisted sites, and selfposts
            
            if (any(entry in submission.domain for entry in self.already_done['domains'])
                or submission.domain in self.already_done['domains']
                or submission.id in self.already_done['submissions']
                or submission.domain in self.banlist['banlist']
                or submission.is_self):
                continue

            self.already_done['domains'].append(submission.domain)
            self.analyze_domain(submission.domain, 'submit')

            #check to see if the domain was popped for low submission count, and if so, record the id
            if submission.domain not in self.already_done['domains']:
                self.already_done['submissions'].append(submission.id)
            
            break #just do one submission and then rerun cycle to check messages

        else:
            #If there were no entries to check, wait 60 seconds
            print ('waiting 60 seconds')
            time.sleep(60)


    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def run(self):
        self.login_bot()
        self.load_caches()

        while 1:
            print("running cycle")
        
            self.check_messages()
            self.process_submissions()
            
            r.edit_wiki_page(master_subreddit,"guardian_alreadydone",str(self.already_done))
            print("cache saved to reddit")
                
    def is_valid_domain(self, domain):
        if re.search("^[a-zA-Z0-9][-.a-zA-Z0-9]*\.[-.a-zA-Z0-9]*[a-zA-Z0-9]$",domain):
            return True
        else:
            return False

    def check_messages(self):
        print('checking messages')
        for message in r.get_unread(limit=None):
            
            #Ignore messages intended for Executioner or Guardian
            #Justiciar handles only analytics messages so this part is easy
            if message.body != "analyze":
                print('ignoring a message')
                continue

            message.mark_as_read()
            
            print('analysis message')
            if self.is_valid_domain(message.subject):
                msg=self.analyze_domain(message.subject,'return')
                r.send_message(message.author,"Analytics: "+message.subject,msg)
            else:
                r.send_message(message.author,"Error",message.subject+" does not appear to be a valid domain.")
            
        
        

#Master bot process
if __name__=='__main__':    
    modbot = Bot()
    
    modbot.run()
