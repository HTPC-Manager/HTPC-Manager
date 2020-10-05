#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cherrypy
import htpc
import requests
from cherrypy.lib.auth2 import require, member_of
import logging
import hashlib
from htpc.helpers import fix_basepath, get_image, striphttp, comp_table
import json
import os
import re
import datetime


class Watcher3(object):
    def __init__(self):
        self.logger = logging.getLogger('modules.watcher3')
        htpc.MODULES.append({
            'name': 'Watcher',
            'id': 'watcher3',
            'test': htpc.WEBDIR + 'watcher3/ping',
            'fields': [
                {'type': 'bool', 'label': 'Enable', 'name': 'watcher3_enable'},
                {'type': 'text', 'label': 'Menu name', 'name': 'watcher3_name'},
                {'type': 'text', 'label': 'IP / Host *', 'name': 'watcher3_host'},
                {'type': 'text', 'label': 'Port', 'placeholder': '9090', 'name': 'watcher3_port'},
                {'type': 'text', 'label': 'Basepath', 'placeholder': '/watcher3', 'name': 'watcher3_basepath'},
                {'type': 'text', 'label': 'API key', 'name': 'watcher3_apikey'},
                {'type': 'bool', 'label': 'Use SSL', 'name': 'watcher3_ssl'},
                {'type': 'text', 'label': 'Reverse proxy link', 'placeholder': '', 'desc': 'Reverse proxy link ex: https://watcher3.domain.com', 'name': 'watcher3_reverse_proxy_link'},

            ]
        })

    @cherrypy.expose()
    @require()
    def index(self):
        return htpc.LOOKUP.get_template('watcher3.html').render(scriptname='watcher3', webinterface=self.webinterface())

    def url(self, watcher3_host=None, watcher3_port=None, watcher3_basepath=None, watcher3_ssl=None):
        if watcher3_host is None:
            watcher3_host = htpc.settings.get('watcher3_host', '')
        if watcher3_port is None:
            watcher3_port = htpc.settings.get('watcher3_port', '')
        if watcher3_basepath is None:
            watcher3_basepath = htpc.settings.get('watcher3_basepath', '')
        if watcher3_ssl is None:
            watcher3_ssl = htpc.settings.get('watcher3_ssl', False)

        watcher3_basepath = fix_basepath(watcher3_basepath)
        watcher3_host = striphttp(watcher3_host)

        ssl = 's' if watcher3_ssl else ''
        return 'http%s://%s:%s%s' % (ssl, watcher3_host, watcher3_port, watcher3_basepath)

    def api_url(self, mode, watcher3_host=None, watcher3_port=None, watcher3_basepath=None, watcher3_ssl=None, watcher3_apikey=None, **kwargs):
        if watcher3_apikey is None:
            watcher3_apikey = htpc.settings.get('watcher3_apikey', '')
        params = 'mode={}&apikey={}'.format(mode, watcher3_apikey)
        for key, value in kwargs.iteritems():
            params += '&{}={}'.format(key, value)

        return '{}/api?{}'.format(self.url(watcher3_host, watcher3_port, watcher3_basepath, watcher3_ssl), params)

    def webinterface(self):
        ''' Generate page from template '''

        if htpc.settings.get('watcher3_reverse_proxy_link'):
            url = htpc.settings.get('watcher3_reverse_proxy_link')
        else:
            url = self.url()

        return url

    def ctrl_c(self, filt):
        ctrl_char = ''
        if '!=' in filt:
            ctrl_char = '!='
        elif '==' in filt:
            ctrl_char = '=='
        elif '<=' in filt:
            ctrl_char = '<='
        elif '>=' in filt:
            ctrl_char = '>='
        elif '<=' in filt:
            ctrl_char = '=='
        elif '!' in filt:
            ctrl_char = '!'
        elif '<' in filt:
            ctrl_char = '<'
        elif '>' in filt:
            ctrl_char = '>'
        elif '=' in filt:
            ctrl_char = '='
        return ctrl_char

    def cp_filter(self, filt, collection):
        self.logger.debug('Called cp_filter %s' % filt)
        before = len(collection.get('movies', 0))
        results = []
        if collection.get('movies', ''):
            check = self.ctrl_c(filt)
            if filt:
                # default to fuzzy title search "16 blocks"
                if check == '':
                    pat = '.*?'.join(map(re.escape, filt))
                    regex = re.compile(pat, flags=re.I)
                    for m in collection['movies']:
                        f = regex.search(m['title'])
                        if f:
                            results.append(m)
                else:
                    # default to normal search
                    if check:
                        filt = filt.split(check)

                    for m in collection['movies']:
                        for k, v in m.iteritems():
                            if k.lower() == filt[0].lower():
                                if isinstance(v, dict):
                                    # actor roles='Jack Bauer'
                                    for kk, vv in v.iteritems():
                                        if v == kk:
                                            results.append(m)
                                elif isinstance(v, list):
                                    # genres=action
                                    if filt[1].lower() in [z.lower() for z in v]:
                                        results.append(m)
                                elif isinstance(v, (int, float)):
                                    # for year!=1337 rating<=5.0
                                    if check and check != '=':
                                        if comp_table[check](float(v), float(filt[1])):
                                            results.append(m)
                                elif isinstance(v, basestring):
                                    # plot='some string'
                                    if filt[1].lower() in v.lower():
                                        results.append(m)

                self.logger.debug('Filter out %s' % (before - len(results)))
                return results

    @cherrypy.expose()
    @require(member_of(htpc.role_admin))
    @cherrypy.tools.json_out()
    def ping(self, watcher3_host, watcher3_port, watcher3_apikey, watcher3_basepath, watcher3_ssl=False, **kwargs):
        self.logger.debug('Testing connectivity to watcher3')

        url = self.api_url('version', watcher3_host, watcher3_port, watcher3_basepath, watcher3_ssl, watcher3_apikey)
        try:
            f = requests.get(url, timeout=10)
            result = f.json()
            return result if result.get('response') else None
        except:
            self.logger.error('Unable to connect to watcher3')
            self.logger.debug('connection-URL: %s' % url)
            return

    @cherrypy.expose()
    @require()
    def GetImage(self, h=None, w=None, o=100, *args, **kwargs):
        if 'imdbid' in kwargs:
            url = self.api_url('poster', imdbid = kwargs['imdbid'])
        elif 'url' in kwargs:
            url = kwargs['url']
        else:
            self.logger.error('GetImage without imdbid or url')
            return
        return get_image(url, h, w, o)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetMovieList(self, status='', f=''):
        self.logger.debug('Fetching Movies')
        if status in ['active', 'done', '']:
            data = self.fetch('liststatus')
            if status == 'done':
                data['movies'] = [movie for movie in data['movies'] if movie['status'] in ['Disabled', 'Finished']]
            elif status == 'active':
                data['movies'] = [movie for movie in data['movies'] if movie['status'] not in ['Disabled', 'Finished']]
        elif status == 'soon':
            data = self.fetch('liststatus', status = 'Waiting')
            cutoff = datetime.datetime.today() + datetime.timedelta(days=30)
            data['movies'] = [i for i in data['movies'] if i['media_release_date'] and datetime.datetime.strptime(i['release_date'], '%Y-%m-%d') < cutoff]
        else:
            data = self.fetch('liststatus', status = status)

        if f:
            data['movies'] = self.cp_filter(f, data)

        data['total'] = len(data['movies'])
        return data

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetNotificationList(self, limit='20'):
        self.logger.debug('Fetching Notification')
        data = self.fetch('notification.list/?limit_offset=' + limit)
        self.fetch('notification.markread')
        return data

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def SearchMovie(self, q=''):
        self.logger.debug('Searching for movie')
        result = self.fetch('search_movie', q = q)
        if result.get('response') and result.get('results'):
            for movie in result['results']:
                if 'tmdbid' not in movie:
                    movie['tmdbid'] = movie.get('id')
                if 'plot' not in movie:
                    movie['plot'] = movie.get('overview')
                if 'year' not in movie:
                    movie['year'] = movie.get('release_date', '')[:4]
                if 'poster_url' not in movie and movie.get('poster_path'):
                    movie['poster_url'] = 'https://image.tmdb.org/t/p/original' + movie.get('poster_path')

        return result

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def AddMovie(self, movieid, profile, title, category=''):
        self.logger.debug('Adding movie')
        params = {'tmdbid': movieid, 'quality': profile} # add title
        if category:
            params['category'] = category
        return self.fetch('addmovie', **params)

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def EditMovie(self, imdbid, profile=None, title=None):
        self.logger.debug('Editing movie')
        params = {'imdbid': imdbid}
        if profile:
            params['quality'] = profile
        if title:
            params['title'] = title
        return self.fetch('update_movie_options', **params)

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def RefreshMovie(self, imdbid, tmdbid = None):
        self.logger.debug('Refreshing movie')
        params = {'imdbid': imdbid}
        if tmdbid:
            params['tmdbid'] = tmdbid
        return self.fetch('update_metadata', **params)

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def DeleteMovie(self, imdbid, delete_file):
        self.logger.debug('Deleting movie')
        return self.fetch('removemovie', imdbid = imdbid, delete_file = delete_file)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetReleases(self, id=''):
        self.logger.debug('Downloading movie')
        return self.fetch('search_results', imdbid = id)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def DownloadRelease(self, id='', kind=''):
        self.logger.debug('Downloading movie')
        return self.fetch('manual_download', guid = id, kind = kind)

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def IgnoreRelease(self, id=''):
        self.logger.debug('Downloading movie')
        return self.fetch('release.ignore/?id=' + id)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetProfiles(self):
        self.logger.debug('Fetching available profiles')
        response = self.fetch('getconfig')
        if response and response.get('config'):
            profiles = response.get('config').get('Quality').get('Profiles')
            default = [key for key, profile in profiles.iteritems() if profile.get('default')]
            return {'list': profiles.keys(), 'default': default[0] if len(default) > 0 else None}
        else:
            return {'list': [], 'default': None}

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetCategories(self):
        self.logger.debug('Feching categories')
        response = self.fetch('getconfig')
        if response and response.get('config'):
            return ['Default'] + response.get('config').get('Categories').keys()
        else:
            return ['Default']

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def Restart(self):
        result = self.fetch('server_restart')
        if result and result.get('response'):
            return 'Success'
        else:
            return 'Error'

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def Shutdown(self):
        result = self.fetch('server_shutdown')
        if result and result.get('response'):
            return 'Success'
        else:
            return 'Error'

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def Update(self):
        return self.fetch('update_check')

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def SearchAllWanted(self):
        result = self.fetch('task', task = 'Movie Search')
        if result and result.get('response'):
            return 'Success'
        else:
            return 'Error'

    @cherrypy.expose()
    @require(member_of(htpc.role_user))
    @cherrypy.tools.json_out()
    def Postprocess(self):
        return self.fetch('task', task = 'PostProcessing Scan')

    def fetch(self, mode, **kwargs):
        try:
            url = self.api_url(mode, **kwargs)
            self.logger.debug('Fetching information from: %s' % url)

            f = requests.get(url, timeout=60, verify=False)

            return f.json()

        except Exception as e:
            self.logger.debug('Exception: %s' % e)
            self.logger.error('Unable to fetch information')
            return
