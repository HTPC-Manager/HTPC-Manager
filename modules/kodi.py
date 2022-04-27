#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Module for connecting to kodi """
import cherrypy
import htpc
import base64
import socket
import struct
from urllib.request import urlopen
from urllib.parse import quote, unquote
from jsonrpclib import Server
from sqlobject import SQLObject, SQLObjectNotFound
from sqlobject.col import StringCol, IntCol
from htpc.helpers import get_image, cachedprime
import logging
from htpc.auth2 import require, member_of
import os
import hashlib
import chardet
from time import sleep
import xml.etree.ElementTree as ET

try:
    import pycaption
    from pycaption import detect_format
except ImportError:
    pycaption = None
    pass

class KodiServers(SQLObject):
    """ SQLObject class for kodi_servers table """
    name = StringCol()
    host = StringCol()
    port = IntCol()
    username = StringCol(default=None)
    password = StringCol(default=None)
    mac = StringCol(default=None)

#    class sqlmeta:
#        fromDatabase = True

class Kodi(object):
    def __init__(self):
        """ Add module to list of modules on load and set required settings """
        self.logger = logging.getLogger('modules.kodi')

        KodiServers.createTable(ifNotExists=True)
        try: KodiServers.sqlmeta.addColumn(IntCol('starterport'), changeSchema=True)
        except Exception, e: pass # Will always raise if column exist
        try: KodiServers.sqlmeta.addColumn(IntCol('vlc_enabled'), changeSchema=True)
        except Exception, e: pass
        try: KodiServers.sqlmeta.addColumn(IntCol('vlc_port'), changeSchema=True)
        except Exception, e: pass
        try: KodiServers.sqlmeta.addColumn(IntCol('vlc_transcode_port'), changeSchema=True)
        except Exception, e: pass
        try: KodiServers.sqlmeta.addColumn(StringCol('vlc_password'), changeSchema=True)
        except Exception, e: pass
        KodiServers.sqlmeta.addColumnsFromDatabase()

        htpc.MODULES.append({
            'name': 'Kodi',
            'id': 'kodi',
            'fields': [
                {'type': 'bool',
                 'label': 'Enable',
                 'name': 'kodi_enable'},
                {'type': 'text',
                 'label': 'Menu name',
                 'name': 'kodi_name'},
                {'type': 'bool',
                 'label': 'Enable PVR',
                 'name': 'kodi_enable_pvr'},
                {'type': 'bool',
                 'label': 'Hide watched',
                 'name': 'kodi_hide_watched'},
                {'type': 'bool',
                 'label': 'Enable VOD',
                 'desc': 'Video on Demand is a <u>experimental feature</u> using a modified version of mediaelement.js that fallbacks to "VLC web plug-in" as additional player for exotic kinds of media.<BR>VOD is NOT supported on Internet Explorer',
                 'name': 'kodi_vod_enabled'},
                {'type': 'select',
                 'label': 'Use HTML5 player?',
                 'name': 'kodi_vod_html5_mode',
                 'options': [
                    {'name': 'Before plugins', 'value': "auto"},
                    {'name': 'After plugins', 'value': "auto_plugin"},
                    {'name': 'Always', 'value': "native"},
                    {'name': 'Never', 'value': "shim"},
                    ]
                },
                {'type': 'select',
                 'label': 'Plugin order',
                 'name': 'kodi_vod_plugin_order',
                 'options': [
                    {'name': 'Flash,Silverlight,VLC', 'value': "flash,silverlight,vlc"},
                    {'name': 'Flash,VLC,Silverlight', 'value': "flash,vlc,silverlight"},
                    {'name': 'Silverlight,Flash,VLC', 'value': "silverlight,flash,vlc"},
                    {'name': 'Silverlight,VLC,Flash', 'value': "silverlight,vlc,flash"},
                    {'name': 'VLC,Flash,Silverlight', 'value': "vlc,flash,silverlight"},
                    {'name': 'VLC,Silverlight,Flash', 'value': "vlc,silverlight,flash"},
                    ]
                },
                {'type': 'select',
                 'label': 'Video URL',
                 'name': 'kodi_vod_video_url',
                 'options': [
                    {'name': 'User/Pass on video URL', 'value': "plain"},
                    # does not work with VLC web plug-in
                    #{'name': 'Use a redirect', 'value': "redirect", 'selected': 'selected'},
                    {'name': 'Use a proxy url', 'value': "proxy"}
                    ]
                },
                {'type': 'text',
                 'label': 'Proxy URL',
                 'placeholder': 'http://someurl.com:8080/path',
                 'desc': "Passing on Kodi user & password on the video URL is unsecure and dosen't work on IE, using a proxy (apache/nginx) to hide login information is the best alternative for security and compatibility.",
                 'name': 'kodi_vod_proxy'},
                {'type': 'bool',
                 'label': 'Transcode with VLC (more experimental)',
                 'desc': 'VLC transcoding is a <u>very experimental and unsupported</u> feature that allow VOD to play media even with bandwidth limitation or absence of VOD plug-ins.',
                 'name': 'kodi_vlc_enabled'},
                {'type': 'text',
                 'label': 'HTTP interface IP/Host',
                 'name': 'kodi_vlc_ip'},
                {'type': 'text',
                 'label': 'Interface Port',
                 'name': 'kodi_vlc_port'},
                {'type': 'password',
                 'label': 'Password',
                 'desc': 'VLC must be running in background.<BR>Use command: vlc --intf http --http-port=&lt;interface-port&gt; --http-password=&lt;password&gt; --rtsp-port=&lt;transcode-port&gt;<BR>(<a href="http://wiki.videolan.org/VLC_command-line_help" target="_blank">Command Line Help</a>)<BR><BR>You can access the transcoding interface going http://vlc_ip_or_host:port/<BR>(leave user name blank)',
                 'name': 'kodi_vlc_password'},
                {'type': 'text',
                 'label': 'HTTP transcode port',
                 'value': 8001,
                 'name': 'kodi_vlc_transcode_port'},
                {'type': 'select',
                 'label': 'Default profile',
                 'name': 'kodi_vlc_default_profile',
                 'desc': 'Take a look at <a href="http://wiki.videolan.org/Documentation:Streaming_HowTo/VLM/" target="_blank">Streaming How-To</a> and <a href="http://www.videolan.org/streaming-features.html" target="_blank">Streaming Features</a>',
                 'options': [
                    {'name': 'Direct', 'value': 0},
                    {'name': 'Profile 1', 'value': 1},
                    {'name': 'Profile 2', 'value': 2},
                    {'name': 'Profile 3', 'value': 3}
                    ]
                },
                {'type': 'bool',
                 'label': 'Transcode profile 1 enabled',
                 'name': 'kodi_vlc_transcode1_enabled'},
                {'type': 'text',
                 'label': 'Name',
                 'value': 'High',
                 'name': 'kodi_vlc_transcode1_name'},
                {'type': 'text',
                 'label': 'Transcode Settings',
                 'value': 'vcodec=VP80,vb=2000,acodec=vorb,ab=128,channels=2,samplerate=44100',
                 'name': 'kodi_vlc_transcode1_settings'},
                {'type': 'select',
                 'label': 'Muxer',
                 'name': 'kodi_vlc_transcode1_muxer',
                 'options': [
                    {'name': 'Ogg', 'value': "ogg"},
                    {'name': 'Webm', 'value': "webm", 'selected': 'selected'},
                    {'name': 'Flv', 'value': "flv"},
                    {'name': 'Mkv', 'value': "mkv"},
                    {'name': 'Ts', 'value': "ts"},
                    {'name': 'Ps', 'value': "ps"},
                    {'name': 'Avi', 'value': "avi"},
                    {'name': 'Asf', 'value': "asf"}
                    ]
                },
                {'type': 'bool',
                 'label': 'Transcode profile 2 enabled',
                 'name': 'kodi_vlc_transcode2_enabled'},
                {'type': 'text',
                 'label': 'Name',
                 'value': 'Medium',
                 'name': 'kodi_vlc_transcode2_name'},
                {'type': 'text',
                 'label': 'Transcode Settings',
                 'value': 'vcodec=theo,vb=1024,fps=25,scale=0.5,acodec=vorb,ab=128,samplerate=44100,channels=2',
                 'name': 'kodi_vlc_transcode2_settings'},
                {'type': 'select',
                 'label': 'Muxer',
                 'name': 'kodi_vlc_transcode2_muxer',
                 'options': [
                    {'name': 'Ogg', 'value': "ogg", 'selected': 'selected'},
                    {'name': 'Webm', 'value': "webm"},
                    {'name': 'Flv', 'value': "flv"},
                    {'name': 'Mkv', 'value': "mkv"},
                    {'name': 'Ts', 'value': "ts"},
                    {'name': 'Ps', 'value': "ps"},
                    {'name': 'Avi', 'value': "avi"},
                    {'name': 'Asf', 'value': "asf"}
                    ]
                },
                {'type': 'bool',
                 'label': 'Transcode profile 3 enabled',
                 'name': 'kodi_vlc_transcode3_enabled'},
                {'type': 'text',
                 'label': 'Name',
                 'value': 'Low',
                 'name': 'kodi_vlc_transcode3_name'},
                {'type': 'text',
                 'label': 'Transcode Settings',
                 'value': 'vcodec=h264,vb=800,width=640,height=480,acodec=mp3,ab=128,channels=2,samplerate=44100',
                 'name': 'kodi_vlc_transcode3_settings'},
                {'type': 'select',
                 'label': 'Muxer',
                 'name': 'kodi_vlc_transcode3_muxer',
                 'desc': '<BR><a href="' + htpc.WEBDIR + 'kodi/managevlc">Manage VLC transcode instances</a>',
                 'options': [
                    {'name': 'Ogg', 'value': "ogg"},
                    {'name': 'Webm', 'value': "webm"},
                    {'name': 'Flv', 'value': "flv", 'selected': 'selected'},
                    {'name': 'Mkv', 'value': "mkv"},
                    {'name': 'Ts', 'value': "ts"},
                    {'name': 'Ps', 'value': "ps"},
                    {'name': 'Avi', 'value': "avi"},
                    {'name': 'Asf', 'value': "asf"}
                    ]
                }
            ]
        })

        htpc.MODULES.append({
            'name': 'Kodi Servers',
            'id': 'kodi_update_server',
            'action': htpc.WEBDIR + 'kodi/setserver',
            'test': htpc.WEBDIR + 'kodi/ping',
            'fields': [
                {'type': 'select',
                 'label': 'Server',
                 'name': 'kodi_server_id',
                 'options': [
                    {'name': 'New', 'value': 0}
                    ]
                },
                {'type': 'text',
                 'label': 'Name',
                 'name': 'kodi_server_name'},
                {'type': 'text',
                 'label': 'IP / Host',
                 'placeholder': 'localhost',
                 'name': 'kodi_server_host'},
                {'type': 'text',
                 'label': 'Port',
                 'placeholder': '8080',
                 'name': 'kodi_server_port'},
                {'type': 'text',
                 'label': 'Username',
                 'name': 'kodi_server_username'},
                {'type': 'password',
                 'label': 'Password',
                 'name': 'kodi_server_password'},
                {'type': 'text',
                 'label': 'Mac addr.',
                 'name': 'kodi_server_mac'},
                {'type': 'text',
                 'label': 'XBMC Starter port',
                 'placeholder': '9',
                 'name': 'kodi_server_starterport'},
                {'type': 'bool',
                 'label': 'Use local VLC transcoder?',
                 'desc': "This server must have it's own VLC installation, otherwise it will use the global setting",
                 'name': 'kodi_server_vlc_enabled'},
                {'type': 'text',
                 'label': 'Port',
                 'name': 'kodi_server_vlc_port'},
                {'type': 'password',
                 'label': 'Password',
                 'name': 'kodi_server_vlc_password'},
                {'type': 'text',
                 'label': 'HTTP transcode port',
                 'value': 8001,
                 'name': 'kodi_vlc_transcode_port'},
            ]
        })
        server = htpc.settings.get('kodi_current_server', 0)
        self.changeserver(server)

    @cherrypy.expose()
    @require()
    def index(self):
        """ Generate page from template """
        return htpc.LOOKUP.get_template('kodi.html').render(scriptname='kodi')

    @cherrypy.expose()
    @require()
    def managevlc(self):
        """ Generate page from template """
        return htpc.LOOKUP.get_template('managevlc.html').render(scriptname='managevlc')

    #used for video file redirect, currently disabled
    def _cp_dispatch(self, vpath):
        if len(vpath) == 3 and vpath[0] == 'vfs':
            self.videofile(vpath[1],vpath[2])

    #used for video file redirect, currently disabled
    @cherrypy.expose()
    @require()
    def videofile(self, server=None, videopath=None):
        if server and videopath:
            raise cherrypy.HTTPRedirect(self.url('', False, int(server)) + '/vfs/' + quote(videopath))
        else:
            return

    @cherrypy.expose()
    @require()
    def player(self, type=None, id=None, serverID=None, transcode=None, start=None):
        """ Generate page from template """
        """ Play a file in Browser """

        # get movies/episodes info
        try:
            serverInfo = KodiServers.selectBy(id=serverID).getOne()

            url = serverInfo.host + ':' + str(serverInfo.port)
            if serverInfo.username and serverInfo.password:
                url = serverInfo.username + ':' + serverInfo.password + '@' + url
            url = 'http://' + url

            kodi = Server(url + '/jsonrpc')

            if type == 'movie':
                properties = ['title', 'year', 'file', 'streamdetails']
                result = kodi.VideoLibrary.GetMovieDetails(movieid=int(id),properties=properties)
                title = result['moviedetails']['title'] + ' (' + str(result['moviedetails']['year']) + ')'
                rawFile = result['moviedetails']['file']
            elif type == 'episode':
                properties = ['showtitle', 'episode', 'season', 'file', 'streamdetails']
                result = kodi.VideoLibrary.GetEpisodeDetails(episodeid=int(id),properties=properties)
                title = result['episodedetails']['showtitle'] + ' (' + str(result['episodedetails']['season']) + 'x' + str(result['episodedetails']['episode']) + ')'
                rawFile = result['episodedetails']['file']
            else:
                return

        except Exception, e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch movie/episode info")
            return

        #set some more variables
        plugins = "'" + htpc.settings.get('kodi_vod_plugin_order').replace(',',"','") + "'"
        mode = htpc.settings.get('kodi_vod_html5_mode')
        vlcEnabled = htpc.settings.get('kodi_vlc_enabled')
        videoSrc = htpc.settings.get('kodi_vod_video_url')
        features = ""
        qualities = "0:'Direct'"
        duration = -1
        currTime = -1
        uniqueID = ''

        if start == None: start = 0
        if transcode == None: transcode = htpc.settings.get('kodi_vlc_default_profile')

        if videoSrc == 'plain':
            videoUrl = url + '/vfs/' + quote(rawFile)
        elif videoSrc == 'redirect':
            videoUrl = htpc.WEBDIR + 'kodi/vfs/' + serverID + '/' + quote(rawFile)
        elif videoSrc == 'proxy':
            videoUrl = htpc.settings.get('kodi_vod_proxy') + '/' + quote(rawFile)

        #get directory files and fetch subtitles
        try:
            separator = rawFile.rfind('/') if rawFile.rfind('/') > rawFile.rfind('\\') else rawFile.rfind('\\')
            path = rawFile[:separator + 1]
            fileList = kodi.Files.GetDirectory(directory=path)
            subtitles=[]
            for files in fileList['files']:
                x = files['file'].rfind('.')
                if x:
                    extension = files['file'][x+1:]
                    if extension in ['smi','sami','dfxp','srt','vtt','ttml','scc']:
                        y = rawFile.rfind('.')
                        if y:
                            if files['file'].find(rawFile[:y]) == 0:
                                if y+1 == x: srclang = files['file'][y+1:x]
                                else: srclang = 'unk'
                                subtitles.append({'srclang':srclang,'label':srclang.capitalize(),'type':extension,'path':quote(files['file'])})

        except Exception, e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch subtitle list")
            return

        #vlc stuff
        if vlcEnabled:

            #set player qualities
            for x in range(1, 4):
                if htpc.settings.get('kodi_vlc_transcode'+ str(x) +'_enabled'):
                    features = "'quality',"
                    qualities = qualities + "," + str(x) + ":'" + htpc.settings.get('kodi_vlc_transcode'+ str(x) +'_name') + "'"

            #transcode if needed
            if int(transcode) > 0 and htpc.settings.get('kodi_vlc_transcode' + str(transcode) + '_enabled'):

                #create a uniqueID for this session if not already set
                if cherrypy.session.get('uniqueID') is None:
                    from uuid import uuid4
                    cherrypy.session['uniqueID'] = str(uuid4())
                uniqueID = cherrypy.session.get('uniqueID')

                #check if we should use global or server VLC
                if serverInfo.vlc_enabled:
                    vlcHost = serverInfo.host
                    vlcTcPort = serverInfo.vlc_transcode_port
                else:
                    vlcHost = htpc.settings.get('kodi_vlc_ip')
                    vlcTcPort = str(htpc.settings.get('kodi_vlc_transcode_port'))

                #create VLC commands
                vlcCmd = []
                vlcMuxer = htpc.settings.get('kodi_vlc_transcode' + str(transcode) + '_muxer')
                vlcExt = vlcMuxer
                if vlcMuxer == 'flv':
                    vlcMuxer = 'ffmpeg{mux=flv}'

                #remove current transcode instance if exist
                vlcCmd.append(quote('del ' + uniqueID))
                #new transcode task
                vlcCmd.append(quote('new ' + uniqueID + ' broadcast' +
                    ' input ' + url + '/vfs/' + quote(rawFile) +
                    ' output #transcode{' + htpc.settings.get('kodi_vlc_transcode' + str(transcode) + '_settings') + '}' +
                    ':std{access=http,mux=' + vlcMuxer + ',dst=0.0.0.0:' + vlcTcPort + '/' + uniqueID + '.' + vlcExt + '}' +
                    ' unloop enabled'))
                #start the new instance
                vlcCmd.append(quote('control ' + uniqueID + ' play 1'))

                #replace video URL with vlc URL
                videoUrl = 'http://' + vlcHost + ':' + vlcTcPort + '/' + uniqueID + '.' + vlcExt

                #send the commands
                vlcResult = self.vlcSendCmd(serverID, vlcCmd)
                #if len(vlcResult['status']):
                #    raise ValueError('Unable to create new transcode task')
                duration = vlcResult['status'][uniqueID]['length']
                currTime = vlcResult['status'][uniqueID]['time']

        #return the player template with all needed variables
        return htpc.LOOKUP.get_template('kodiplayer.html').render(
            title=title,
            videoUrl=videoUrl,
            subtitles=subtitles,
            serverID=serverID,
            mode=mode,
            plugins=plugins,
            features=features,
            qualities=qualities,
            quality=int(transcode),
            duration=duration,
            currTime=currTime,
            uniqueID=uniqueID,
            start=start,
            transcode=transcode
        )

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def vlcSendCmd(self, serverID=None, vlcCmd=None, autoSelect='1'):
        #force server
        if serverID == '-1':
            vlcHost = htpc.settings.get('kodi_vlc_ip')
            vlcPwd = htpc.settings.get('kodi_vlc_password')
            vlcPort = htpc.settings.get('kodi_vlc_port')
        elif autoSelect == '0':
            serverInfo = KodiServers.selectBy(id=serverID).getOne()
            if serverInfo.vlc_enabled:
                vlcHost = serverInfo.host
                vlcPwd = serverInfo.vlc_password
                vlcPort = serverInfo.vlc_port
            else:
                return 'disabled'
        else:
            #are we using local or global vlc server?
            serverInfo = KodiServers.selectBy(id=serverID).getOne()
            if serverInfo.vlc_enabled:
                vlcHost = serverInfo.host
                vlcPwd = serverInfo.vlc_password
                vlcPort = serverInfo.vlc_port
            else:
                vlcHost = htpc.settings.get('kodi_vlc_ip')
                vlcPwd = htpc.settings.get('kodi_vlc_password')
                vlcPort = htpc.settings.get('kodi_vlc_port')

        # build url for VLC
        vlcUrl = vlcHost + ':' + str(vlcPort)
        if vlcPwd: vlcUrl = ':' + vlcPwd + '@' + vlcUrl
        vlcUrl = 'http://' + vlcUrl

        result = {'command':[],'status':{}}
        try:
            #send the commands and retrive errors
            if vlcCmd is not None:
                if isinstance(vlcCmd, basestring): vlcCmd = [vlcCmd]
                for cmd in vlcCmd:
                    c = urllib.urlopen(vlcUrl + '/requests/vlm_cmd.xml?command=' + cmd) #,None,1)
                    result['command'].append(ET.fromstring(c.read()).find('./error').text)
                    sleep(0.5)

            #get status of vlm xml and convert to json
            s = urllib.urlopen(vlcUrl + '/requests/vlm.xml')
            for broadcast in ET.fromstring(s.read()).findall('./broadcast'):
                brcEnabled = False
                brcState = None
                brcTime = None
                brcLength = None
                brcInputs = []
                for input in broadcast.findall('./inputs/input'):
                    brcInputs.append(unquote(input.text[input.text.find('/vfs/')+5:]))
                if broadcast.attrib['enabled'] == 'yes':
                    brcEnabled = True
                instance = broadcast.find("./instances/*[@name='default']")
                if instance is not None:
                    brcState = instance.attrib['state']
                    brcTime = round(int(instance.attrib['time']) / 1000000)
                    brcLength = round(int(instance.attrib['length']) / 1000000)

                result['status'][broadcast.attrib['name']] = {
                    'enabled': brcEnabled,
                    'state': brcState,
                    'time': brcTime,
                    'length': brcLength,
                    'inputs': brcInputs
                    }

            return result

        except Exception, e:
            self.logger.exception(e)
            self.logger.error("Unable to reach VLC server")
            return

    @cherrypy.expose()
    @require()
    def subtitle(self, serverID=None, subpath=None):
        f = urllib.urlopen(self.url('', True, serverID) + '/vfs/' + subpath)
        sub = f.read()
        encoding = chardet.detect(sub)
        sub = sub.decode(encoding=encoding['encoding'], errors='ignore')

        if pycaption is None:
            self.logger.debug("Subtitle: " + unquote(subpath) + ", " + encoding['encoding'] + ", " + str(encoding['confidence']))
            return sub
        else:
            reader = detect_format(sub)
            self.logger.debug("Subtitle: " + unquote(subpath) + ", " + encoding['encoding'] + ", " + str(encoding['confidence']) + ", " + str(reader))
            if reader is None:
                return sub
            else:
                if pycaption.SRTReader().detect(sub):
                    return sub
                else:
                    return pycaption.SRTWriter().write(reader().read(sub))

    @cherrypy.expose()
    @require()
    def webinterface(self):
        """ Generate page from template """
        raise cherrypy.HTTPRedirect(self.url('', True))

    @cherrypy.expose()
    @require()
    def vlcwebinterface(self, serverID=None):
        """ redirect to vlc webinterface """
        if serverID is not None:
            if int(serverID) > -1:
                serverInfo = KodiServers.selectBy(id=serverID).getOne()
                vlcHost = serverInfo.host
                vlcPort = serverInfo.vlc_port
            else:
                vlcHost = htpc.settings.get('kodi_vlc_ip')
                vlcPort = htpc.settings.get('kodi_vlc_port')
            raise cherrypy.HTTPRedirect('http://' + vlcHost + ':' + str(vlcPort))

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    @require(member_of(htpc.role_admin))
    def primecache(self, t='all', wanted_art='all', nosync=True, resize=True):
        ''' find all images and cache them, might take a while...'''
        kodi = Server(self.url('/jsonrpc', True))
        url = self.url('/image/')
        # fix headers
        _head = 'Basic %s' % self.auth()
        headers = {'Authorization': _head}

        musicprop = ['fanart', 'thumbnail']
        itemprop = ['art', 'fanart', 'thumbnail']
        addonprop = ['thumbnail']
        stuff = []

        if t == 'all':
            movie = kodi.VideoLibrary.GetMovies(properties=itemprop)
            episode = kodi.VideoLibrary.GetEpisodes(properties=itemprop)
            artist = kodi.AudioLibrary.GetArtists(properties=musicprop)
            song = kodi.AudioLibrary.GetSongs(properties=musicprop)
            tvshow = kodi.VideoLibrary.GetTVShows(properties=itemprop)
            stuff = [movie, episode, artist, song, tvshow]
        elif t == 'movie':
            movie = kodi.VideoLibrary.GetMovies(properties=itemprop)
            stuff.append(movie)
        elif t == 'episode':
            episode = kodi.VideoLibrary.GetEpisodes(properties=itemprop)
            stuff.append(episode)
        elif t == 'song':
            song = kodi.AudioLibrary.GetSongs(properties=musicprop)
            stuff.append(song)
        elif t == 'tvshow':
            tvshow = kodi.VideoLibrary.GetTVShows(properties=itemprop)
            stuff.append(tvshow)
        elif t == 'addon':
            addon = kodi.Addons.GetAddons(content='unknown', enabled='all', properties=addonprop)
            stuff.append(addon)

        imgdir = os.path.join(htpc.DATADIR, 'images/')

        imglist = []

        self.logger.debug('Fetching every image we can find from kodi')  # todo add addon images

        resize_sizes = [[225, 338], [200, 300], [675, 400], [100, 150], [375, 210], [150, 150]]

        for item in stuff:
            for k, v in list(item.items()):
                if k in ['episodes', 'movies', 'tvshows', 'songs', 'artists', 'addons']:
                    self.logger.debug('There where %s %s' % (len(item[k]), k))
                    for kk in item[k]:
                        for kkk, vvv, in list(kk.items()):
                            d = {}
                            if kkk == wanted_art or wanted_art == 'all':
                                if kkk == 'art':
                                    for z, a in list(kk['art'].items()):
                                        if z == wanted_art or wanted_art == 'all':
                                            _url = url + quote(a)
                                            h = hashlib.md5(_url).hexdigest()
                                            d['fp'] = os.path.join(imgdir, h)
                                            d['hash'] = h
                                            d['url'] = _url
                                            d['resize'] = resize_sizes
                                            imglist.append(d)

                                if kkk in ['fanart', 'thumbnail']:
                                    _url = url + quote(vvv)
                                    h = hashlib.md5(_url).hexdigest()
                                    d['fp'] = os.path.join(imgdir, h)
                                    d['hash'] = h
                                    d['url'] = _url
                                    d['resize'] = resize_sizes
                                    imglist.append(d)

        self.logger.debug('Found %s images in total' % len(imglist))

        try:
            if nosync:
                t = cachedprime(imglist, headers, resize=bool(resize))
                return t

        except Exception as e:
            self.logger.debug('%s' % e)

    @cherrypy.expose()
    @require(member_of(htpc.role_admin))
    @cherrypy.tools.json_out()
    def ping(self, kodi_server_host='', kodi_server_port='',
             kodi_server_username='', kodi_server_password='', **kwargs):
        """ Tests settings, returns MAC address on success and null on fail """
        self.logger.debug("Testing kodi connectivity")
        try:
            url = kodi_server_host + ':' + kodi_server_port
            if kodi_server_username and kodi_server_password:
                url = kodi_server_username + ':' + kodi_server_password + '@' + url
            kodi = Server('http://' + url + '/jsonrpc')
            self.logger.debug("Trying to contact kodi via %s" % url)
            return kodi.XBMC.GetInfoLabels(labels=["Network.MacAddress"])
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to contact kodi via %s", url)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def getserver(self, id=None):
        if id:
            """ Get kodi server info """
            try:
                server = KodiServers.selectBy(id=id).getOne()
                return dict((c, getattr(server, c)) for c in server.sqlmeta.columns)
            except SQLObjectNotFound:
                return

        """ Get a list of all servers and the current server """
        servers = []
        for s in KodiServers.select():
            servers.append({'id': s.id, 'name': s.name})
        if not servers:
            return
        try:
            current = self.current.name
        except AttributeError:
            current = None
        return {'current': current, 'servers': servers}

    @cherrypy.expose()
    @require(member_of(htpc.role_admin))
    @cherrypy.tools.json_out()
    def setserver(self, kodi_server_id, kodi_server_name, kodi_server_host, kodi_server_port,
                  kodi_server_username=None, kodi_server_password=None, kodi_server_mac=None, kodi_server_starterport='',
                  kodi_server_vlc_port='', kodi_server_vlc_password='', kodi_server_vlc_transcode_port='', kodi_server_vlc_enabled=''):
        """ Create a server if id=0, else update a server """
        if kodi_server_starterport == '':
            kodi_server_starterport = None
        else:
            kodi_server_starterport = int(kodi_server_starterport)
        if kodi_server_vlc_port == '':
            kodi_server_vlc_port = None
        else:
            kodi_server_vlc_port = int(kodi_server_vlc_port)
        if kodi_server_vlc_transcode_port == '':
            kodi_server_vlc_transcode_port = None
        else:
            kodi_server_vlc_transcode_port = int(kodi_server_vlc_transcode_port)

        if kodi_server_id == "0":
            self.logger.debug("Creating kodi-Server in database")
            try:
                server = KodiServers(name=kodi_server_name,
                                     host=kodi_server_host,
                                     port=int(kodi_server_port),
                                     username=kodi_server_username,
                                     password=kodi_server_password,
                                     mac=kodi_server_mac,
                                     starterport=kodi_server_starterport,
                                     vlc_enabled=int(kodi_server_vlc_enabled),
                                     vlc_port=kodi_server_vlc_port,
                                     vlc_password=kodi_server_vlc_password,
                                     vlc_transcode_port=kodi_server_vlc_transcode_port)

                self.changeserver(server.id)
                htpc.BLACKLISTWORDS.append(kodi_server_password)
                return 1
            except Exception as e:
                self.logger.debug("Exception: " + str(e))
                self.logger.error("Unable to create kodi-Server in database")
                return 0
        else:
            self.logger.debug("Updating kodi-Server " + kodi_server_name + " in database")
            try:
                server = KodiServers.selectBy(id=kodi_server_id).getOne()
                server.name = kodi_server_name
                server.host = kodi_server_host
                server.port = int(kodi_server_port)
                server.username = kodi_server_username
                server.password = kodi_server_password
                server.mac = kodi_server_mac
                server.starterport = kodi_server_starterport
                server.vlc_enabled = int(kodi_server_vlc_enabled)
                server.vlc_port = kodi_server_vlc_port
                server.vlc_password = kodi_server_vlc_password
                server.vlc_transcode_port = kodi_server_vlc_transcode_port
                return 1
            except SQLObjectNotFound as e:
                self.logger.error("Unable to update kodi-Server " + server.name + " in database")
                return 0

    @cherrypy.expose()
    @require(member_of(htpc.role_admin))
    def delserver(self, id):
        """ Delete a server """
        self.logger.debug("Deleting server " + str(id))
        KodiServers.delete(id)
        self.changeserver()
        return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def changeserver(self, id=0):
        try:
            self.current = KodiServers.selectBy(id=id).getOne()
            htpc.settings.set('kodi_current_server', str(id))
            self.logger.info("Selecting kodi server: %s", id)
            return "success"
        except SQLObjectNotFound:
            try:
                self.current = KodiServers.select(limit=1).getOne()
                self.logger.error("Invalid server. Selecting first Available.")
                return "success"
            except SQLObjectNotFound:
                self.current = None
                self.logger.warning("No configured kodi-Servers.")
                return "No valid servers"

    @cherrypy.expose()
    @require()
    def GetThumb(self, thumb=None, h=None, w=None, o=100, mode=None):
        """ Parse thumb to get the url and send to htpc.proxy.get_image """
        url = self.url('/images/DefaultVideo.png')
        if thumb:
            url = self.url('/image/' + quote(thumb))
        self.logger.debug("Trying to fetch image via %s" % url)
        return get_image(url, h, w, o, mode, self.auth())

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetMovies(self, start=0, end=0, sortmethod='title', sortorder='ascending', hidewatched=0, filter=''):
        """ Get a list of all movies """
        self.logger.debug("Fetching Movies")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            sort = {'order': sortorder, 'method': sortmethod, 'ignorearticle': True}
            properties = ['title', 'year', 'plot', 'thumbnail', 'file', 'fanart', 'studio', 'trailer',
                          'imdbnumber', 'genre', 'rating', 'playcount']
            limits = {'start': int(start), 'end': int(end)}
            filter = {'field': 'title', 'operator': 'contains', 'value': filter}
            if hidewatched == "1":
                filter = {"and": [filter, {'field': 'playcount', 'operator': 'is', 'value': '0'}]}
            return kodi.VideoLibrary.GetMovies(sort=sort, properties=properties, limits=limits, filter=filter)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch movies!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetShows(self, start=0, end=0, sortmethod='title', sortorder='ascending', hidewatched=0, filter=''):
        """ Get a list of all the TV Shows """
        self.logger.debug("Fetching TV Shows")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            sort = {'order': sortorder, 'method': sortmethod, 'ignorearticle': True}
            properties = ['title', 'year', 'plot', 'thumbnail', 'playcount']
            limits = {'start': int(start), 'end': int(end)}
            filter = {'field': 'title', 'operator': 'contains', 'value': filter}
            if hidewatched == "1":
                filter = {"and": [filter, {'field': 'playcount', 'operator': 'is', 'value': '0'}]}
            shows = kodi.VideoLibrary.GetTVShows(sort=sort, properties=properties, limits=limits, filter=filter)
            return shows
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch TV Shows")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetEpisodes(self, start=0, end=0, sortmethod='episode', sortorder='ascending', tvshowid=None, hidewatched=False, filter=''):
        """ Get information about a single TV Show """
        self.logger.debug("Loading information for TVID %s", str(tvshowid))
        try:
            kodi = Server(self.url('/jsonrpc', True))
            sort = {'order': sortorder, 'method': sortmethod, 'ignorearticle': True}
            properties = ['episode', 'season', 'thumbnail', 'plot', 'file', 'playcount', 'showtitle']
            limits = {'start': int(start), 'end': int(end)}
            filter = {'field': 'title', 'operator': 'contains', 'value': filter}
            if hidewatched == "1":
                filter = {"and": [filter, {'field': 'playcount', 'operator': 'is', 'value': '0'}]}
            episodes = kodi.VideoLibrary.GetEpisodes(sort=sort, tvshowid=int(tvshowid), properties=properties, limits=limits, filter=filter)
            return episodes
        except:
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetArtists(self, start=0, end=0, sortmethod='artist', sortorder='ascending', filter=''):
        """ Get a list of all artists """
        self.logger.debug("Fetching all artists in the music database")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            sort = {'order': sortorder, 'method': sortmethod, 'ignorearticle': True}
            properties = ['thumbnail', 'fanart']
            limits = {'start': int(start), 'end': int(end)}
            filter = {'field': 'artist', 'operator': 'contains', 'value': filter}
            return kodi.AudioLibrary.GetArtists(properties=properties, limits=limits, sort=sort, filter=filter)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch artists!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetAlbums(self, start=0, end=0, sortmethod='label', sortorder='ascending', artistid=None, filter=''):
        """ Get a list of all albums for artist """
        self.logger.debug("Loading all albums for ARTISTID %s", str(artistid))
        try:
            kodi = Server(self.url('/jsonrpc', True))
            sort = {'order': sortorder, 'method': sortmethod, 'ignorearticle': True}
            properties = ['title', 'artist', 'year', 'thumbnail']
            limits = {'start': int(start), 'end': int(end)}
            if artistid:
                filter = {'artistid': int(artistid)}
            else:
                filter = {'or': [{'field': 'album', 'operator': 'contains', 'value': filter},
                                 {'field': 'artist', 'operator': 'contains', 'value': filter}]}
            return kodi.AudioLibrary.GetAlbums(properties=properties, limits=limits, sort=sort, filter=filter)
        except Exception as e:
            self.logger.debug("Exception: %s", str(e))
            self.logger.error("Unable to fetch albums!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetSongs(self, start=0, end=0, sortmethod='title', sortorder='ascending', albumid=None, artistid=None, filter='', *args, **kwargs):
        """ Get a list of all songs """
        self.logger.debug("Fetching all artists in the music database")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            sort = {'order': sortorder, 'method': sortmethod, 'ignorearticle': True}
            properties = ['artist', 'artistid', 'album', 'albumid', 'duration', 'year', 'thumbnail']
            limits = {'start': int(start), 'end': int(end)}
            if albumid and filter == '':
                filter = {'albumid': int(albumid)}
            elif artistid and filter == '':
                filter = {'artistid': int(artistid)}
            else:
                filter = {'or': [{'field': 'album', 'operator': 'contains', 'value': filter},
                                 {'field': 'artist', 'operator': 'contains', 'value': filter},
                                 {'field': 'title', 'operator': 'contains', 'value': filter}]}

            return kodi.AudioLibrary.GetSongs(properties=properties, limits=limits, sort=sort, filter=filter)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch artists!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetChannelGroups(self, type='tv'):
        """ Get PVR channel list from kodi """
        self.logger.debug("Loading kodi PVC channel list.")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            return kodi.PVR.GetChannelGroups(channeltype=type)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch channelgroups!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetChannels(self, type='tv', group=2):
        """ Get PVR channel list from kodi """
        self.logger.debug("Loading kodi PVC channel list.")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            return kodi.PVR.GetChannels(channelgroupid=int(group), properties=['thumbnail'])
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch channels!")
            return

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def ExecuteAddon(self, addon, cmd0='', cmd1=''):
        if cmd0 == 'undefined':
            cmd0 = ''
        # cmd0 is a parameter to the addon, usual a input of some kind
        if cmd1 == 'undefined':
            cmd1 = ''
        """ Execute an kodi addon """
        self.logger.debug('Execute %s with commands cmd0 %s and cmd1 %s' % (addon, cmd0, cmd1))
        kodi = Server(self.url('/jsonrpc', True))
        if addon == 'script.artwork.downloader':
            return kodi.Addons.ExecuteAddon(addonid=addon, params=['tvshow', 'movie', 'musicvideos'])
        elif addon == 'script.cinema.experience':
            cmd = 'movieid=' + int(cmd0)
            return kodi.Addons.ExecuteAddon(addon, cmd)
        elif addon == 'plugin.video.youtube':
            cmd = 'action=play_video&videoid=' + cmd0
            return kodi.Addons.ExecuteAddon(addon, cmd)
        elif addon == 'script.cdartmanager':
            return kodi.Addons.ExecuteAddon('addonid=' + addon, cmd0)
        elif addon == 'plugin.video.twitch':
            if cmd0:  # If search
                return kodi.Addons.ExecuteAddon(addon, '/searchresults/'+ cmd0 + '/0' )
            else:  # Open plugin
                return kodi.Addons.ExecuteAddon(addon, '/')
        elif addon == 'plugin.video.nrk':
            if cmd0:
                # Does not work in kodi or via this one, think its a addon problem
                cmd = '/search/%s/1' % cmd0
                return kodi.Addons.ExecuteAddon(addon, cmd)
            else:
                return kodi.Addons.ExeceuteAddon(addonid=addon)
        elif addon == 'script.globalsearch':
            kodi.Addons.ExecuteAddon(addon, '/searchstring/'+ cmd0)
            return kodi.Input.SendText(text=cmd0)
        else:
            return kodi.Addons.ExecuteAddon(addonid=addon)

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def Enable_DisableAddon(self, addonid=None, enabled=None):
        kodi = Server(self.url('/jsonrpc', True))
        return kodi.Addons.SetAddonEnabled(addonid=addonid, enabled=bool(int(enabled)))

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetAddons(self):
        kodi = Server(self.url('/jsonrpc', True))
        prop = ['name', 'thumbnail', 'description', 'author', 'version', 'enabled', 'rating', 'summary']
        addons = kodi.Addons.GetAddons(content='unknown', enabled='all', properties=prop)['addons']
        return addons

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def PlayItem(self, item=None, type=None):
        """ Play a file in kodi """
        self.logger.debug("Playing '%s' of the type %s", item, type)
        kodi = Server(self.url('/jsonrpc', True))
        if type == 'movie':
            return kodi.Player.Open(item={'movieid': int(item)}, options={'resume': True})
        elif type == 'episode':
            return kodi.Player.Open(item={'episodeid': int(item)}, options={'resume': True})
        elif type == 'channel':
            return kodi.Player.Open(item={'channelid': int(item)})
        elif type == 'artist':
            return kodi.Player.Open(item={'artistid': int(item)})
        elif type == 'album':
            return kodi.Player.Open(item={'albumid': int(item)})
        elif type == 'song':
            return kodi.Player.Open(item={'songid': int(item)})
        else:
            return kodi.Player.Open(item={'file': item})

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def QueueItem(self, item, type):
        """ Queue a file in kodi """
        self.logger.debug("Enqueueing '%s' of the type %s", item, type)
        kodi = Server(self.url('/jsonrpc', True))
        if type == 'movie':
            return kodi.Playlist.Add(playlistid=1, item={'movieid': int(item)})
        elif type == 'episode':
            return kodi.Playlist.Add(playlistid=1, item={'episodeid': int(item)})
        elif type == 'channel':
            return kodi.Playlist.Add(playlistid=1, item={'channelid': int(item)})
        elif type == 'artist':
            return kodi.Playlist.Add(playlistid=0, item={'artistid': int(item)})
        elif type == 'album':
            return kodi.Playlist.Add(playlistid=0, item={'albumid': int(item)})
        elif type == 'song':
            return kodi.Playlist.Add(playlistid=0, item={'songid': int(item)})

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def RemoveItem(self, item, playlistid=0):
        """ Remove a file from the playlist """
        self.logger.debug("Removing '%s' from the playlist", item)
        kodi = Server(self.url('/jsonrpc', True))
        return kodi.Playlist.Remove(playlistid=playlistid, position=int(item))

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def PlaylistMove(self, position1, position2, playlistid=0):
        """ Swap files in playlist """
        playlistid = int(playlistid)
        position1 = int(position1)
        position2 = int(position2)
        i = 1 if position1 < position2 else -1
        kodi = Server(self.url('/jsonrpc', True))
        while(position1 != position2):
            kodi.Playlist.Swap(playlistid=playlistid, position1=position1, position2=position1 + i)
            position1 += i
        return "Moved from " + str(position1) + " to " + str(position2)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def Playlist(self, type='audio'):
        """ Get a playlist from kodi """
        self.logger.debug("Loading Playlist of type %s", type)
        kodi = Server(self.url('/jsonrpc', True))
        if type == 'video':
            return kodi.Playlist.GetItems(playlistid=1, properties=['year', 'showtitle', 'season', 'episode', 'runtime'])

        return kodi.Playlist.GetItems(playlistid=0, properties=['artist', 'title', 'album', 'duration'])

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def NowPlaying(self):
        """ Get information about current playing item """
        self.logger.debug("Fetching currently playing information")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            player = kodi.Player.GetActivePlayers()[0]
            playerid = player['playerid']

            if player['type'] == 'video':
                playerprop = ['speed', 'position', 'time', 'totaltime',
                              'percentage', 'subtitleenabled', 'currentsubtitle',
                              'subtitles', 'currentaudiostream', 'audiostreams']

                itemprop = ['title', 'season', 'episode', 'duration', 'showtitle',
                            'fanart', 'tvshowid', 'plot', 'thumbnail', 'year']

            elif player['type'] == 'audio':
                playerprop = ['speed', 'position', 'time', 'totaltime', 'percentage']
                itemprop = ['title', 'duration', 'fanart', 'artist', 'albumartist', 'album', 'track', 'artistid', 'albumid', 'thumbnail', 'year']

            app = kodi.Application.GetProperties(properties=['muted', 'volume'])
            player = kodi.Player.GetProperties(playerid=playerid, properties=playerprop)
            item = kodi.Player.GetItem(playerid=playerid, properties=itemprop)

            return {'playerInfo': player, 'itemInfo': item, 'app': app}
        except IndexError:
            return
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch currently playing information!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def ControlPlayer(self, action, value=''):
        """ Various commands to control kodi Player """
        self.logger.debug("Sending control to kodi %s", action)
        try:
            kodi = Server(self.url('/jsonrpc', True))
            if action == 'seek':
                player = kodi.Player.GetActivePlayers()[0]
                return kodi.Player.Seek(playerid=player['playerid'], value=float(value))
            elif action == 'jump':
                player = kodi.Player.GetActivePlayers()[0]
                return kodi.Player.GoTo(playerid=player['playerid'], to=int(value))
            elif action == 'party':
                return kodi.Player.Open(item={'partymode': 'audio'})
            elif action == 'getsub':
                try:
                    # Frodo
                    return kodi.Addons.ExecuteAddon(addonid='script.kodi.subtitles')
                except:
                    pass
                try:
                    # Gotham
                    return kodi.GUI.ActivateWindow(window='subtitlesearch')
                except:
                    pass
            elif action == 'volume':
                return kodi.Application.SetVolume(volume=int(value))
            else:
                return kodi.Input.ExecuteAction(action=action)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to control kodi with action: %s", action)
            return 'error'

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def SendText(self, text):
        """ Send text to kodi """
        self.logger.debug("Sending text to kodi: %s", text)
        kodi = Server(self.url('/jsonrpc', True))
        return kodi.Input.SendText(text=text)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def Subtitles(self, subtitle='off'):
        """ Change the subtitles """
        self.logger.debug("Changing subtitles to %s", subtitle)
        try:
            kodi = Server(self.url('/jsonrpc', True))
            playerid = kodi.Player.GetActivePlayers()[0]['playerid']
            try:
                subtitle = int(subtitle)
                kodi.Player.SetSubtitle(playerid=playerid, subtitle=subtitle, enable=True)
                return "success"
            except ValueError:
                kodi.Player.SetSubtitle(playerid=playerid, subtitle='off')
                return "Disabling subtitles."
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to set subtitle to specified value %s", subtitle)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def Audio(self, audio):
        """ Change the audio stream  """
        self.logger.debug("Chaning audio stream to %s", audio)
        try:
            kodi = Server(self.url('/jsonrpc', True))
            playerid = kodi.Player.GetActivePlayers()[0]['playerid']
            return kodi.Player.SetAudioStream(playerid=playerid, stream=int(audio))
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to change audio stream to specified value %s", audio)
            return

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def System(self, action=''):
        """ Various system commands """
        kodi = Server(self.url('/jsonrpc', True))
        if action == 'Quit':
            self.logger.info("Exiting kodi")
            kodi.Application.Quit()
            return 'Exiting kodi.'
        if action == 'Shutdown':
            self.logger.info("Shutting down kodi")
            kodi.System.Shutdown()
            return 'Shutting down kodi.'
        elif action == 'Suspend':
            self.logger.info("Suspending kodi")
            kodi.System.Suspend()
            return 'Suspending kodi.'
        elif action == 'Reboot':
            self.logger.info("Rebooting kodi")
            kodi.System.Reboot()
            return 'Rebooting kodi.'

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def Wake(self):
        """ Send WakeOnLan package """
        self.logger.info("Waking up kodi-System")
        try:
            addr_byte = self.current.mac.split(':')
            hw_addr = struct.pack('BBBBBB',
                                  int(addr_byte[0], 16),
                                  int(addr_byte[1], 16),
                                  int(addr_byte[2], 16),
                                  int(addr_byte[3], 16),
                                  int(addr_byte[4], 16),
                                  int(addr_byte[5], 16))

            msg = '\xff' * 6 + hw_addr * 16
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(msg, ("255.255.255.255", 9))
            self.logger.info("WOL package sent to %s", self.current.mac)
            return "WOL package sent"
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to send WOL packet")
            return "Unable to send WOL packet"

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def Run(self):
        """ Send XBMC Starter packet """
        self.logger.info("Sending XBMC Starter packet")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto("YatseStart-Xbmc", (self.current.host, self.current.starterport))
            self.logger.info("XBMC Starter package sent to %s:%s", self.current.host, self.current.starterport)
            return "XBMC Starter packet sent"
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to send XBMC Starter packet")
            self.logger.debug('Have you installed http://yatse.leetzone.org/redmine/projects/androidwidget/wiki/XbmcStarter?')
            return "Unable to send XBMC Starter packet"

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def Notify(self, text):
        """ Create popup in kodi """
        self.logger.debug("Sending notification to kodi: %s" % text)
        kodi = Server(self.url('/jsonrpc', True))
        image = '../interfaces/default/img/kodi-logo.png'
        return kodi.GUI.ShowNotification(title='HTPC manager', message=text, image=image)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetRecentMovies(self, limit=5):
        """ Get a list of recently added movies """
        self.logger.debug("Fetching recently added movies")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            properties = ['title', 'year', 'runtime', 'plot', 'thumbnail', 'file',
                          'fanart', 'trailer', 'imdbnumber', 'studio', 'genre', 'rating']
            limits = {'start': 0, 'end': int(limit)}
            return kodi.VideoLibrary.GetRecentlyAddedMovies(properties=properties, limits=limits)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch recently added movies!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetRecentShows(self, limit=5):
        """ Get a list of recently added TV Shows """
        self.logger.debug("Fetching recently added TV Shows")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            properties = ['showtitle', 'season', 'episode', 'title', 'runtime',
                          'thumbnail', 'plot', 'fanart', 'file']
            limits = {'start': 0, 'end': int(limit)}
            return kodi.VideoLibrary.GetRecentlyAddedEpisodes(properties=properties, limits=limits)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch recently added TV Shows")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetRecentAlbums(self, limit=5):
        """ Get a list of recently added music """
        self.logger.debug("Fetching recently added Music")
        try:
            kodi = Server(self.url('/jsonrpc', True))
            properties = ['artist', 'albumlabel', 'year', 'description', 'thumbnail']
            limits = {'start': 0, 'end': int(limit)}
            return kodi.AudioLibrary.GetRecentlyAddedAlbums(properties=properties, limits=limits)
        except Exception as e:
            self.logger.exception(e)
            self.logger.error("Unable to fetch recently added Music!")
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def Library(self, do='scan', lib='video'):
        kodi = Server(self.url('/jsonrpc', True))
        if lib == 'video':
            if do == 'clean':
                return kodi.VideoLibrary.Clean()
            else:
                return kodi.VideoLibrary.Scan()
        else:
            if do == 'clean':
                return kodi.AudioLibrary.Clean()
            else:
                return kodi.AudioLibrary.Scan()

    def url(self, path='', auth=False, server=False):
        """ Generate a URL for the RPC based on kodi settings """
        self.logger.debug("Generate URL to call kodi")
        if server:
            try:
                serverinfo = KodiServers.selectBy(id=server).getOne()
            except SQLObjectNotFound:
                return
            url = serverinfo.host + ':' + str(serverinfo.port)
            if auth and serverinfo.username and serverinfo.password:
                url = serverinfo.username + ':' + serverinfo.password + '@' + url
            return 'http://' + url
        else:
            url = self.current.host + ':' + str(self.current.port) + path
            if auth and self.current.username and self.current.password:
                url = self.current.username + ':' + self.current.password + '@' + url
            self.logger.debug("URL: http://%s", url)
            return 'http://' + url

    def auth(self):
        """ Generate a base64 HTTP auth string based on settings """
        if self.current.username and self.current.password:
            return base64.encodestring('%s:%s' % (self.current.username, self.current.password)).strip('\n')
