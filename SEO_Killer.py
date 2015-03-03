import praw
import time
import os
from retrying import retry
from collections import deque
import re


#initialize reddit
r=praw.Reddit(user_agent='SEO Killer Bot by /u/captainmeta4')

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

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)    
    def load_caches(self):
        #load already-processed submissions cache and modlist cache
        print("loading caches")
        
        try:
            self.already_done = eval(r.get_wiki_page(master_subreddit,"already_done").content_md)
            print("already-done cache loaded")
            
        except:
            print("already-done cache not loaded. Starting with blank cache")
            self.already_done = deque([],maxlen=1000)
            r.edit_wiki_page(master_subreddit,'already_done',str(self.already_done))

        try:
            self.banlist = eval(r.get_wiki_page(master_subreddit,"banlist").content_md)
            print("banlist cache loaded")
        except:
            print("banlist cache not loaded. Starting with blank banlist")
            self.banlist={'banlist':{},'recent_bans':[],'unbanned':[]}
            r.edit_wiki_page(master_subreddit,'ban_list',str(self.banlist))
        
        try:
            self.whitelist = eval(r.get_wiki_page(master_subreddit,"whitelist").content_md)
            print("whitelist cache loaded")
        except:
            print("whitelist cache not loaded. Starting with blank whitelist")
            self.whitelist={}
            r.edit_wiki_page(master_subreddit,'whitelist',str(self.whitelist))

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def update_pretty_banlist(self):
            pretty_list = "The following domains are in the /u/SEO_Killer global blacklist:\n"
            raw_list = []
            for entry in self.banlist['banlist']:
                raw_list.append(entry)

            raw_list.sort()
            
            for entry in raw_list:
                pretty_list = pretty_list+"\n* "+entry

            r.edit_wiki_page(master_subreddit,"ban_list",pretty_list)

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def check_messages(self):

        print("Checking messages")

        for message in r.get_unread(limit=None):

            message.mark_as_read()
            #Just assume all messages are a mod invite, and fetch modlist if invite accepted
            try:
                r.accept_moderator_invite(message.subreddit.display_name)
                print("Accepted moderator invite for /r/"+message.subreddit.display_name)

                #make a new blank whitelist if necessary
                if message.subreddit.display_name not in self.whitelist:
                    self.whitelist[message.subreddit.display_name]=[]
                    r.edit_wiki_page(master_subreddit,'whitelist',str(self.whitelist))

                
                #send greeting
                msg=("Hello, moderators of /r/"+message.subreddit.display_name+"!\n\n"+
                     "I am a bot designed to help curb SEO spam on reddit. To that end, I keep and enforce a [global domain ban list](/r/SEO_Killer/wiki/ban_list)."+
                     "\n\nIf you would like me to automatically remove submissions to domains on my ban list, give me posts permissions."+
                     "If you would prefer that I report submissions instead, then *don't* give me posts permissions."+
                     "\n\nI will send you a weekly update with any domains that have been added to or removed from my global ban list. "+
                     "If you wish to override my global ban list for any particular domain, please make use of my per-subreddit whitelist feature."+
                     "\n\nFor more information, see my [subreddit](/r/SEO_Killer) and my [guide page](/r/SEO_Killer/wiki/guide). My code is on [GitHub](https://github.com/captainmeta4/SEO_Killer)"+
                     "\n\nFeedback may be directed to my creator, /u/captainmeta4. Thanks for using me!")
                r.send_message(message.subreddit,"Hello!",msg)
                
            except:
                pass

            #Whitelist-related commants. Enclosed in try to protect against garbage input

            try:
                if message.author in r.get_moderators(message.subject) and message.subject in self.whitelist:

                    #Read whitelist
                    if message.body == "whitelist":
                        print("whitelist query from /u/"+message.author.name+" about /r/"+message.subject)
                        msg = "The following domains are in the /r/"+message.subject+" whitelist:\n"

                        if len(self.whitelist[message.subject])==0:
                            msg=msg + "\n* *none*"
                        else:
                            for entry in self.whitelist[message.subject].sort():
                                msg = msg +"\n* "+entry

                        r.send_message(message.author,"Domain whitelist for /r/"+message.subject,msg)

                    #modify whitelist
                    else:
                        if self.is_valid_domain(message.body):

                            if message.body in self.whitelist[message.subject]:
                                self.whitelist[message.subject].remove(message.body)
                                print(message.body+" removed from whitelist for /r/"+message.subject)
                                r.send_message(message.author,"Whitelist Modified",message.body+" removed from whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"whitelist",str(self.whitelist))
                                continue
                            else:
                                self.whitelist[message.subject].append(message.body)
                                print(message.body+" added to whitelist for /r/"+message.subject)
                                r.send_message(message.author,"Whitelist Modified",message.body+" added to whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"whitelist",str(self.whitelist))
                                continue
            except:
                pass #I could respond with an error message here but I don't want to accidentally get into bot ping-pong

            #Master subreddit mods controlling global ban list
            if message.author in r.get_moderators(master_subreddit):
                print("order from /u/"+message.author.name)

                #check first to see if it's an unban
                if message.body == "unban":
                    print("unban order "+message.subject)

                    try:
                        self.banlist['recent_bans'].pop(message.subject)
                    except KeyError:
                        pass
                    
                    try:
                        self.banlist['banlist'].pop(message.subject)
                        self.banlist['unbanned'].append(message.subject)
                        print(message.subject+" unbanned")
                        r.edit_wiki_page(master_subreddit,'banlist',str(self.banlist),reason='unban '+message.subject)
                        self.update_pretty_banlist()
                    except KeyError:
                        r.send_message(message.author,"Error",message.subject+" was not banned.")
                        print(message.subject+" was not banned")

                #if it's not an unban, then it's a ban 
                else:
                    #Check for duplicate ban list entry
                    if message.subject not in self.banlist['banlist']:

                        #Check that submission id is valid
                        if isinstance(r.get_info(thing_id='t3_'+message.body), praw.objects.Submission):

                            #check that submission id points to /r/SEO_Killer
                            if r.get_info(thing_id='t3_'+message.body).subreddit.display_name == master_subreddit.display_name:
                                self.banlist['banlist'][message.subject]=message.body
                                self.banlist['recent_bans'].append(message.subject)
                                r.send_message(message.author,"Ban added",message.subject+" added to ban list with reference http://redd.it/"+message.body)
                                r.edit_wiki_page(master_subreddit,'banlist',str(self.banlist),reason="ban "+message.subject)
                                print(message.subject+" added to ban list with reference http://redd.it/"+message.body)
                                self.update_pretty_banlist()
                            else:
                                print("wrong subreddit for submission id")
                                r.send_message(message.author,"Error","The shortlink http://redd.it/"+message.body+" does not point to /r/"+master_subreddit.display_name)
                        else:
                            print("invalid submission id")
                            r.send_message(message.author,"Error","'"+message.body+"' is not a valid reddit submission id.")
                    else:
                        print("duplicate ban entry")
                        r.send_message(message.author,"Duplicate ban",message.subject+" is already banned with reference http://redd.it/"+self.banlist['banlist'][message.subject]+
                                       "\n\nTo change the reference, un-ban and re-ban "+message.subject)

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def is_valid_domain(self, domain):
        if re.search("^[a-zA-Z0-9][-.a-zA-Z0-9]*\.[-.a-zA-Z0-9]*[a-zA-Z0-9]$",domain):
            return True
        else:
            return False
        
    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def process_submissions(self):
        print('processing submissions')

        for submission in r.get_subreddit('mod').get_new(limit=100):

            #avoid duplicate work
            if submission.id in self.already_done:
                continue

            self.already_done.append(submission.id)

            #remove/report offending posts
            if (submission.domain in self.banlist['banlist'] and submission.domain not in self.whitelist[submission.subreddit.display_name]):
                try:
                    submission.remove(spam=True)
                    print("Removed submission to "+submission.domain+" in /r/"+submission.subreddit.display_name)
                except praw.errors.ModeratorOrScopeRequired:
                    submission.report(reason='Known SEO site - http://redd.it/'+self.banlist['banlist'][submission.domain])
                    print("Reported submission to "+submission.domain+" in /r/"+submission.subreddit.display_name)

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def run(self):
        self.login_bot()
        self.load_caches()

        while 1:
            print("running cycle")

            #Check if it's time for weekly update messages to go out
            #Monday morning at midnight
            if time.localtime().tm_wday==0 and time.localtime().tm_hour==0 and time.localtime().tm_min==0:
                self.weekly_update_messages()
        
            self.check_messages()
            self.process_submissions()

            #Every 5 minutes, save the already-done cache. Other caches are always saved on editing
            if time.localtime().tm_min in [0,5,10,15,20,25,30,35,40,45,50,55]:
                print("saving already-done cache")
                r.edit_wiki_page(master_subreddit,"already_done",str(self.already_done))
            
            print("sleeping..")
    
            #Run cycle on XX:XX:00
            time.sleep(1)
            while time.localtime().tm_sec != 0 :
                time.sleep(1)

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def weekly_update_messages():

        print("sending weekly update")
        msg='The following domain(s) have been banned over the last week:\n\n'

        if len(self.banlist['recent_bans'])==0:
            msg = msg+"* *none*\n"
        else:
            for item in self.banlist['recent_bans'].sort():
                msg=msg+"* "+item+"\n"

        msg = msg+"\n The following domain(s) have been removed from the ban list over the last week:\n\n"

        if len(self.banlist['unbanned'])==0:
            msg = msg+"* *none*\n"
        else:
            for item in self.banlist['unbanned'].sort():
                msg=msg+"* "+item+"\n"

        for subreddit in r.get_my_moderation():
            r.send_message(subreddit,"Weekly Ban List Update Message",msg)

        self.banlist['recent_bans']=[]
        self.banlist['unbanned']=[]
        

#Master bot process
if __name__=='__main__':    
    modbot = Bot()
    
    modbot.run()
