import praw
import re
import time
import requests

agentstring="Domain analytics script tools version 1.0 by /u/captainmeta4"
r = praw.Reddit(user_agent=agentstring)
headers = {'User-Agent': agentstring}


username = input("user: ")
r.login(username, input("pass: "))

print ("login successful. ")

def analyze_domain(domain):
        print('Analyzing domain: '+domain)
        i=0
        authors=[]
        author_total_posts=[]
        author_domain_posts=[]
        shadowbanned_users=0

        #calculate # unique users
        
        for submission in r.get_domain_listing(domain,sort='new',limit=1000):
            i=i+1
            try:
                if submission.author.name not in authors:
                    authors.append(submission.author.name)
            except AttributeError:
                pass

        print(str(i)+" submissions by "+str(len(authors))+" unique users")

        author_total_posts=[0]*len(authors)
        author_domain_posts=[0]*len(authors)

        x=0
        total_users=len(authors)
        while x < len(authors): #not doing for x in range() because len(authors) can change as SB users are removed

            #Check shadowban
            u = requests.get("http://reddit.com/user/"+authors[x]+"/?limit=1", headers=headers)

            #If shadowbanned...
            if u.status_code==404:
                print ("shadowbanned: /u/"+authors[x])
                shadowbanned_users=shadowbanned_users+1
                authors.pop(x)
                author_total_posts.pop(x)
                author_domain_posts.pop(x)
                x=x-1

            
            else:
                print ("checking: /u/"+authors[x])

                #calculate submissions to that domain
                for submission in r.get_redditor(authors[x]).get_submitted(sort='new', limit=100):
                    author_total_posts[x]=author_total_posts[x]+1
                    if submission.domain in domain or domain in submission.domain:
                        author_domain_posts[x]=author_domain_posts[x]+1
            x=x+1
                        
        msg=(domain+" has "+str(i)+" submissions by at least "+str(total_users)+" unique users, of whom "+str(shadowbanned_users)+" are shadowbanned."+
             "\n\nThe users who submitted to "+domain+" have the following data:\n\n"+
             "|User|Total Submissions|Submissions to "+domain+"|% to "+domain+"|\n|-|-|-|-|\n")

        for x in range(0,len(authors)):
            msg=msg+"| /u/"+authors[x]+"|"+str(author_total_posts[x])+"|"+str(author_domain_posts[x])+"|"+str(int(100*author_domain_posts[x]/author_total_posts[x]))+"% |\n"

        r.send_message(username,"Analyze "+domain, msg)

def compare_domains(domain1, domain2):

        domain1_posts=0
        domain2_posts=0

        authors1=[]
        authors2=[]

        #get author lists for each domain

        print('examining '+domain1)
        for submission in r.get_domain_listing(domain1,sort='new',limit=1000):
            domain1_posts=domain1_posts+1
            try:
                if submission.author.name not in authors1:
                    authors1.append(submission.author.name)
            except AttributeError:
                pass

        print('examining '+domain2)
        for submission in r.get_domain_listing(domain2,sort='new',limit=1000):
            domain2_posts=domain2_posts+1
            try:
                if submission.author.name not in authors2:
                    authors2.append(submission.author.name)
            except AttributeError:
                pass

        #get authors in common to both domains
        common_authors = list(set(authors1).intersection(authors2))

        print(domain1+" has "+str(len(authors1))+" unique authors")
        print(domain2+" has "+str(len(authors2))+" unique authors")
        print("they have the following "+str(len(common_authors))+" in common:")
        print(common_authors)
