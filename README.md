#### Python 3 compatible fork of [Hellowlol's HTPC Manager fork](https://github.com/Hellowlol/HTPC-Manager)

We made this an [organization](https://github.com/HTPC-Manager) repository to be more independent from single developers. If you want to join the team or contributed to HTPC Manager before, please open an issue (or PR) as we need more hands to polish Python 3 compatibility and keep modules with their software backends.

[![Join the chat at https://gitter.im/Hellowlol/HTPC-Manager](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/Hellowlol/HTPC-Manager?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

[![CodeFactor](https://www.codefactor.io/repository/github/htpc-manager/htpc-manager/badge)](https://www.codefactor.io/repository/github/htpc-manager/htpc-manager)

=====

A python based web application to manage the software on your HTPC. HTPC Manager combines all your favorite software into one slick interface.

![Screenshot](http://i.imgur.com/6QEWPFf.png)

Requires Python 3.x (3.5 minimum, most likely) and crapload of Python libs. Just make sure that CherryPy version is < 9.0 (as stated in requirements.txt).

Start with ```python3 Htpc.py```

A [virtual environment](https://docs.python.org/3/library/venv.html) is strongly encouraged.

#### [New modules]
- Sonarr
- Headphones
- Samsung TV remote
- SickRage module
- Torrent search (BTN, Norbits, KAT, strike, rarbg and PTP)
- vnStat
- Mylar

#### [Modules]
- Couchpotato
- Deluge
- kodi
- NZBGet
- Plex
- qBittorrent
- SABnzbd
- nzb search (newznab)
- Sickbeard
- squeezebox
- Stats
- Transmission
- uTorrent

#### [Improvements]
- Pretty much every module has been improved in some way or another
- NZBGet module (rewritten)
- qBittorrent module (rewritten)
- Transmission (add url, upload local torrent)
- Deluge (add url/magnet, pause/remove, set limit)
- SABnzbd (drag & drop to edit queue, pause for x min, purge history)
- Stats module (Hardware info, S.M.A.R.T report, execute scripts)
- CouchPotato (Suggestions and moar..)
- Plex (Filter, search, fix duplicated, images, play to device and more)
- KODI/XBMC addons tab, where you can search/execute/enable/disable addons and a volume slider instead of a progress bar
- Send a nzb from NZB search to NZBGet in addition to SABnzbd.
- Usenet (Multi search indexers, support nzedb and spotweb in addition to newznab)

#### [Misc]
- Notification if a update is available and autoupdate
- Htpc manager is now fluid. (Looks much better on high res screens)
- Delete cache folder from the settings page
- The brave and bold can choose which branch they want to use.
- Added a option for robots.txt for bot crawlers
- Make ssl cert and key automatically if you don't add a path for it
- Mask sensitive stuff from the log (username, api key, password etc)
- Reduced size on static files
- Docker support
- Various fixes
- Download log
- Added argsparse (to support python 2.6)
- And a shit load of other stuff i dont remember

If you're missing something don't be afraid to make a request :)

See here for full list:
https://github.com/Hellowlol/HTPC-Manager/compare/styxit:master...master2

#### SO YOU FOUND A BUG? GREAT!

Before you open a new issue, make sure you:
- Check if this issue has been solved before
- Are using the master2 branch (all other branches should be considered experimental)
- Update to the lastest version
- Have restart HTPC Manager

If you still have problems: INCLUDE THIS IN YOUR ISSUE
 - Screenshot of the about page
 - What did you do?
 - What happened?
 - What did you expect to happen?
 - If it's a visual bug, screenshot or it didn't happen!
 - Which browser, including version
 - Link to a copy/paste of your ENTIRE logfile (with loglevel debug!), please write the linenumber where the error occured [PASTEBIN](http://www.pastebin.com) NO logs == NO help

#### How to enable detailed logs
1. Shutdown HTPC Manager
2. Start Htpc.py --loglevel debug (Do NOT start with --dev)
3. Start HTPC Manager and wait for error to occur again/reproduce it

#### Installation

See the [wiki](https://github.com/Hellowlol/HTPC-Manager/wiki)
