import praw
import time
import os
from retrying import retry
from collections import deque
import re
from requests.exceptions import HTTPError
import requests


#initialize reddit
user_agent='SEO Killer - Executioner Module by /u/captainmeta4 - see /r/SEO_Killer'
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

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)    
    def load_caches(self):
        #load already-processed submissions cache and modlist cache
        print("loading caches")
        
        try:
            self.already_done = eval(r.get_wiki_page(master_subreddit,"already_done").content_md)
            print("already-done cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the already_done wiki page")
            elif e.response.status_code == 404:
                print("already-done cache not loaded. Starting with blank cache")
                self.already_done = deque([],maxlen=1000)
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
            self.options = eval(r.get_wiki_page(master_subreddit,"options").content_md)
            print("options cache loaded")
        except HTTPError as e:
            if e.response.status_code == 403:
                print("incorrect permissions")
                r.send_message(master_subreddit,"Incorrect permissions","I don't have access to the options wiki page")
            elif e.response.status_code == 404:
                print("options cache not loaded. Starting with blank options")
                self.options={}
                for subreddit in r.get_my_moderation(limit=None):
                    self.options[subreddit.display_name]={"remove_blacklisted":False, 'domain_whitelist':[], 'user_whitelist':[]}
                r.edit_wiki_page(master_subreddit,'options',str(self.options))
            elif e.response.status_code in [502, 503, 504]:
                print("reddit's crapping out on us")
                raise e #triggers the @retry module
            else:
                 raise e

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def update_pretty_banlist(self):
            pretty_list = "The following domains are in the /u/SEO_Killer global blacklist. Clicking one will take you to the corresponding /r/SEO_Killer report.\n"
            raw_list = []
            for entry in self.banlist['banlist']:
                raw_list.append(entry)

            raw_list.sort()
            
            for entry in raw_list:
                pretty_list = pretty_list+"\n* ["+entry+"](http://redd.it/"+self.banlist['banlist'][entry]+")"

            r.edit_wiki_page(master_subreddit,"ban_list",pretty_list)

    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def check_messages(self):

        print("Checking messages")

        for message in r.get_unread(limit=None):

            #Ignore messages intended for Justiciar or Guardian
            if message.body == "analyze":   
                continue

            #Ignore post replies
            if message.subject == "comment reply":
                message.mark_as_read()
                continue

            #Just assume all messages are a mod invite, and fetch modlist if invite accepted
            try:
                r.accept_moderator_invite(message.subreddit.display_name)
                print("Accepted moderator invite for /r/"+message.subreddit.display_name)

                #make a new options set if necessary
                if message.subreddit.display_name not in self.options:
                    self.options[message.subreddit.display_name]={"remove_blacklisted":False, 'domain_whitelist':[], 'user_whitelist':[]}
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


            #Options update

            try:
                #Toggle remove blacklist option
                if message.body=='remove_blacklisted' and message.author in r.get_moderators(message.subject):
                    if self.options[message.subject]['remove_blacklisted']==True:
                        print('Switching to report mode on /r/'+message.subject)
                        self.options[message.subject]['remove_blacklisted']=False
                        r.send_message(message.author,"Options Updated","SEO Executioner now operating in Report mode in /r/"+message.subject)
                        
                    else:
                        print('Switching to remove mode on /r/'+message.subject)
                        self.options[message.subject]['remove_blacklisted']=True
                        r.send_message(message.author,"Options Updated","SEO Executioner now operating in Remove mode in /r/"+message.subject)

                    message.mark_as_read()
                    r.edit_wiki_page(master_subreddit,'options',str(self.options))
                    continue
            except:
                pass

            #Whitelist-related commands. Enclosed in try to protect against garbage input

            #try:
            if True:
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
                                r.send_message(message.author,"Domain Whitelist Modified",message.body+" removed from domain whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"options",str(self.options),reason=message.body+" removed from domain whitelist for /r/"+message.subject+"by /u/"+message.author.name)
                                message.mark_as_read()
                                continue
                            else:
                                self.options[message.subject]['domain_whitelist'].append(message.body)
                                print(message.body+" added to domain whitelist for /r/"+message.subject)
                                r.send_message(message.author,"Domain Whitelist Modified",message.body+" added to domain whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"options",str(self.options),reason=message.body+" added to domain whitelist for /r/"+message.subject+"by /u/"+message.author.name)
                                message.mark_as_read()
                                continue
                        #user whitelist
                        elif self.is_valid_username(message.body):
                            if message.body in self.options[message.subject]['user_whitelist']:
                                self.options[message.subject]['user_whitelist'].remove(message.body)
                                print("/u/"+message.body+" removed from user whitelist for /r/"+message.subject)
                                r.send_message(message.author,"User Whitelist Modified",message.body+" removed from user whitelist for /r/"+message.subject)
                                r.edit_wiki_page(master_subreddit,"options",str(self.options),reason=message.body+" removed from user whitelist for /r/"+message.subject+"by /u/"+message.author.name)
                                message.mark_as_read()
                                continue
                            else:
                                self.options[message.subject]['user_whitelist'].append(message.body)
                                print(message.body+" added to user whitelist for /r/"+message.subject)
                                r.send_message(message.author,"User Whitelist Modified",message.body+" added to user whitelist for /r/"+message.subject)
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
            #except:
                #pass

            #Master subreddit mods controlling global ban list
            if message.author in r.get_moderators(master_subreddit):
                print("order from /u/"+message.author.name)

                #check first to see if it's an unban
                if message.body == "unban":
                    print("unban order "+message.subject)

                    try:
                        self.banlist['recent_bans'].remove(message.subject)
                    except KeyError:
                        pass
                    
                    try:
                        del self.banlist['banlist'][message.subject]
                        self.banlist['unbanned'].append(message.subject)
                        print(message.subject+" unbanned")
                        r.edit_wiki_page(master_subreddit,'banlist',str(self.banlist),reason='unban '+message.subject+" by /u/"+message.author.name)
                        self.update_pretty_banlist()
                    except KeyError:
                        r.send_message(message.author,"Error",message.subject+" was not banned.")
                        print(message.subject+" was not banned")
                        

                #if it's not an unban, then it's a ban 
                else:
                    
                    #Check for duplicate ban list entry - this is done as nested Ifs rather than "if... and... and... :" to prevent erroring on r.get_info
                    if message.subject not in self.banlist['banlist']:

                        #Check that submission id is valid
                        if isinstance(r.get_info(thing_id='t3_'+message.body), praw.objects.Submission):

                            #check that submission id points to /r/SEO_Killer
                            if r.get_info(thing_id='t3_'+message.body).subreddit.display_name == master_subreddit.display_name:

                                #add ban entry, update wikis
                                self.banlist['banlist'][message.subject]=message.body
                                self.banlist['recent_bans'].append(message.subject)
                                r.send_message(message.author,"Ban added",message.subject+" added to ban list with reference http://redd.it/"+message.body)
                                r.edit_wiki_page(master_subreddit,'banlist',str(self.banlist),reason="ban "+message.subject+" by /u/"+message.author.name)
                                print(message.subject+" added to ban list with reference http://redd.it/"+message.body)
                                self.update_pretty_banlist()

                                #Clear already_done so that any recent submissions will be removed
                                self.already_done = deque([],maxlen=200)
                                
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
            message.mark_as_read()
            
    def is_valid_domain(self, domain):
        if re.search("^[a-zA-Z0-9][-.a-zA-Z0-9]*\.[-.a-zA-Z0-9]*[a-zA-Z0-9]$",domain):
            return True
        else:
            return False

    def is_valid_username(self, username):
        
        if re.search("^[A-Za-z0-9_-]{3,20}$",username):
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
            if (any(entry in submission.domain for entry in self.banlist['banlist'])
                and submission.domain not in self.options[submission.subreddit.display_name]['domain_whitelist']
                and submission.author.name not in self.options[submission.subreddit.display_name]['user_whitelist']):

                #if options say to Remove, then try removing
                if self.options[submission.subreddit.display_name]['remove_blacklisted']:
                    try:
                        submission.remove(spam=True)
                        print("Removed submission to "+submission.domain+" in /r/"+submission.subreddit.display_name)
                    except praw.errors.ModeratorOrScopeRequired:
                        submission.report(reason='Known SEO site - http://redd.it/'+self.banlist['banlist'][submission.domain])
                        print("Reported submission to "+submission.domain+" in /r/"+submission.subreddit.display_name+" by /u/"+submission.author.name)
                else:
                    submission.report(reason='Known SEO site - http://redd.it/'+self.banlist['banlist'][submission.domain])
                    print("Reported submission to "+submission.domain+" in /r/"+submission.subreddit.display_name+" by /u/"+submission.author.name)

    #@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
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
    def weekly_update_messages(self):

        print("assembling weekly wiki update")
        wiki='The following domain(s) have been banned over the last week. Click any entry to view the corresponding /r/SEO_Killer submission.\n\n'

        self.banlist['recent_bans'].sort()
        self.banlist['unbanned'].sort()

        if len(self.banlist['recent_bans'])==0:
            wiki = wiki+"* *none*\n"
        else:
            for item in self.banlist['recent_bans']:
                wiki=wiki+"* ["+item+"](http://redd.it/"+self.banlist['banlist'][item]+")\n"

        wiki = wiki+"\n The following domain(s) have been removed from the ban list over the last week:\n\n"

        if len(self.banlist['unbanned'])==0:
            wiki = wiki+"* *none*\n"
        else:
            for item in self.banlist['unbanned']:
                wiki=wiki+"* "+item+"\n"

        r.edit_wiki_page(master_subreddit,'recent',wiki)

        for subreddit in r.get_my_moderation():
            print('sending message to /r/'+subreddit.display_name)
            msg=("The wiki page of my recent domain global bans/unbans has been updated, and can be seen at http://reddit.com/r/SEO_Killer/wiki/recent."+
             "\n\nIf you wish to exempt your subreddit from my ban on any of these domains, [click here]"+
             "(http://www.reddit.com/message/compose/?to=SEO_Killer&subject="+subreddit.display_name+"), fill in the domain name for the message subject, and click Send."+
             "This will toggle whitelist status for that domain within /r/"+subreddit.display_name)
            r.send_message(subreddit,"Weekly Ban List Update Message",msg)
            

        self.banlist['recent_bans']=[]
        self.banlist['unbanned']=[]
        r.edit_wiki_page(master_subreddit,'banlist',str(self.banlist),reason='clear the recent bans and unbanned lists')

#Master bot process
if __name__=='__main__':    
    modbot = Bot()
    
    modbot.run()
