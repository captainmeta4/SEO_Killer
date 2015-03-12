#About the bot

/u/SEO_Killer is a set of three bots which work together to fight off spam:

* Executioner scans moderated subreddits for posts to sites known to engage in "black-hat SEO". It will remove such posts automatically, or alert subreddit moderators by reporting the post.
* Justiciar detects when a user deletes submissions and later submits to the same domain, and alerts the moderators. This helps fight spammers who delete their history to manipulate their submission statistics.
* Guardian continuously crunches analytics on domains, reporting fishy ones to /r/SEO_Killer for human review and possible addition to the Executioner blacklist.

Operational details can be found [here](http://reddit.com/r/SEO_Killer/wiki/guide)

## Can this bot be used to ban any domain from all of the bot's moderated subreddits?

Technically, yes, but it won't. The bot's global blacklist is controlled by the /r/SEO_Killer moderators, and we will only ban domains found to be engaging in black-hat SEO.

##There's a domain on the bot's blacklist that my subreddit enjoys.

There is a per-subreddit whitelist feature currently in development.

##How do I get the bot running on my subreddit?

Invite /u/SEO_Killer as moderator.

If you want the bot to remove banned sites, give it "posts" permissions.

If you would rather the bot report banned sites, then don't give it "posts" permissions.

##I'm not comfortable giving the /r/SEO_Killer moderators the ability to blacklist domains in my subreddit.

Understandable - that's why the whitelist feature exists. The per-subreddit whitelist overrides the bot's global blacklist.

Once per week, the bot will also send out a message with any additions/removals to the global blacklist, so that you can stay on top of any changes.

##How can I edit my subreddit whitelist?

[See full operational details here](http://reddit.com/r/SEO_Killer/wiki/guide)

##Can I see the blacklist?

Yes. The global blacklist is public information. It can be seen [here](http://reddit.com/r/seo_killer/wiki/ban_list). That wiki page is automatically updated whenever the blacklist is changed.

##How do I submit a SEO-spammy domain to get it blacklisted?

Submit a post to http://reddit.com/r/SEO_Killer
