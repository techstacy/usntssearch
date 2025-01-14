# # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## #    
#~ This file is part of NZBmegasearch by 0byte.
#~ 
#~ NZBmegasearch is free software: you can redistribute it and/or modify
#~ it under the terms of the GNU General Public License as published by
#~ the Free Software Foundation, either version 3 of the License, or
#~ (at your option) any later version.
#~ 
#~ NZBmegasearch is distributed in the hope that it will be useful,
#~ but WITHOUT ANY WARRANTY; without even the implied warranty of
#~ MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#~ GNU General Public License for more details.
#~ 
#~ You should have received a copy of the GNU General Public License
#~ along with NZBmegasearch.  If not, see <http://www.gnu.org/licenses/>.
# # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## # ## #    

import json
from sets import Set
import decimal
import socket
import random
import string
import datetime
import requests
import time
from operator import itemgetter
from urllib2 import urlparse
from flask import render_template, Response
import SearchModule
import logging
import base64
import re
import copy

log = logging.getLogger(__name__)


def listpossiblesearchoptions():
	possibleopt = [ ['1080p', 'HD 1080p',''],
							['720p','HD 720p',''],
							['BDRIP','SD BlurayRip',''],
							['DVDRIP','SD DVDRip',''],
							['DVDSCR','SD DVDScr',''],
							['CAM','SD CAM',''],
							['OSX','Mac OSX',''],
							['XBOX360','Xbox360',''],
							['PS3','PS3',''],
							['ANDROID','Android',''],
							['MOBI','Ebook (mobi)',''],
							['EPUB','Ebook (epub)',''] ]
	return possibleopt						
#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
class DoParallelSearch:
	
	def __init__(self, conf, cgen, ds, wrp):
		
		self.results = []
		self.cfg = conf
		self.cgen = cgen
		self.svalid = 0
		self.svalid_speed = [0,0,0]
		self.qry_nologic = ''
		self.logic_items = []
		self.ds = ds			
		self.wrp = wrp
		self.sckname = self.getdomainandprotocol()
		print '>> Base domain and protocol: ' + self.sckname
	
		if(self.cfg is not None):
			for i in xrange(len(self.cfg)):
				if(self.cfg[i]['valid'] != 0):
					self.svalid_speed[ self.cfg[i]['speed_class'] ] = 1 + self.svalid_speed[ self.cfg[i]['speed_class'] ]

		if(ds.cfg is not None):
			for i in xrange(len(self.ds.cfg)):
				if(self.ds.cfg[i]['valid'] != 0):
					self.svalid_speed[ self.ds.cfg[i]['speed_class'] ] = 1 + self.svalid_speed[ self.ds.cfg[i]['speed_class'] ]

				
		if( (self.cfg is not None) or (self.cgen is not None) ):
			self.svalid_speed[1] += self.svalid_speed[0]
			self.svalid_speed[2] += self.svalid_speed[1]
			self.svalid = self.svalid_speed[2]
			self.cfg_cpy = copy.deepcopy(self.cfg)
		
		self.logic_expr = re.compile("(?:^|\s)([-+])(\w+)")
		self.possibleopt = listpossiblesearchoptions()
		self.searchopt = [ 	['Normal ['+str(self.svalid_speed[1]) + ']', 1,''],
							['Extensive ['+str(self.svalid_speed[2]) + ']', 2,'']]
		self.searchopt_cpy = self.searchopt
		self.possibleopt_cpy = self.possibleopt		
		self.collect_info = []
		self.resultsraw = None
	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 

	def getdomainandprotocol(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("8.8.8.8",80))
		hprotocol = 'http://'
		if(self.cgen['general_https']):
			hprotocol = 'https://'
		sckname = hprotocol + s.getsockname()[0]
		s.close()
		sckname = sckname+':'+ str(self.cgen['portno'])
		return sckname

	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 
	def cleancache(self):
		ntime = datetime.datetime.now()
		cinfon = []	
		for i in xrange(len(self.collect_info)):
			dt1 =  (ntime - datetime.datetime.fromtimestamp(self.collect_info[i]['tstamp']))
			dl = (dt1.days+1) * dt1.seconds
			#~ remove by overtime
			if(dl < self.cgen['max_cache_age']*60):
				cinfon.append(self.collect_info[i])
			else:
				print 'removed'	
		self.collect_info = cinfon		
			
	def chkforcache(self, qryenc, speedclass):
		rbuff = None
		if(self.cgen['cache_active'] == 1):
			#~ print len(self.collect_info)
			for i in xrange(len(self.collect_info)):
				if(self.collect_info[i]['searchstr'] == qryenc and self.collect_info[i]['speedclass'] == speedclass ):
					#~ print 'Cache hit id:' + str(i)
					rbuff = self.collect_info[i]['resultsraw']
					break
		return rbuff		
	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 

	def dosearch(self, args):
		#~ restore originals
		self.cfg = copy.deepcopy(self.cfg_cpy)
		
		if('q' not in args):
			self.results = []
			return self.results
			
			
		self.logic_items = self.logic_expr.findall(args['q'])
		self.qry_nologic = self.logic_expr.sub(" ",args['q'])
		if('selcat' in args):
			if(args['selcat'] != ""):
				self.qry_nologic += " " + args['selcat']

		#~ speed class
		speed_class_sel = 1	
		if('tm' in args):
			speed_class_sel = int(args['tm'])
		
		#~ speed class deepsearch
		self.ds.set_timeout_speedclass(speed_class_sel)
		#~ speed class Nabbased	
		for conf in self.cfg :
			if ( (conf['speed_class'] <=  speed_class_sel) and (conf['valid'])):
				conf['timeout']  = self.cgen['timeout_class'][ speed_class_sel ]
				#~ print conf['type'] + " " + str(conf['timeout'] ) + ' ' + str(speed_class_sel )
			else:
				conf['valid']  = 0
		 
					
		if( len(args['q']) == 0 ):
			if('selcat' in args):
				if(len(args['selcat'])==0):
					self.results = []
					return self.results
			else:
				self.results = []
				return self.results
		if(self.qry_nologic.replace(" ", "") == ""):
			self.results = []
			return self.results
						
		self.logic_items = self.logic_expr.findall(args['q'])
		self.cleancache()
		self.resultsraw = self.chkforcache(self.wrp.chash64_encode(self.qry_nologic), speed_class_sel)
		if( self.resultsraw is None):
			self.resultsraw = SearchModule.performSearch(self.qry_nologic, self.cfg, self.ds )
			
		if( self.cgen['smartsearch'] == 1):
			#~ smartsearch
			self.results = summary_results(self.resultsraw, self.qry_nologic, self.logic_items)
		else:
			#~ no cleaning just flatten in one array
			self.results = []
			for provid in xrange(len(self.resultsraw)):
				for z in xrange(len(self.resultsraw[provid])):
					self.results.append(self.resultsraw[provid][z])


	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 
		
	def renderit(self,params):
		params['search_opt']=  copy.deepcopy(self.searchopt)
		search_def = 1
		if('tm' in params['args']):
			for j in xrange(len(params['search_opt'])):
				if(params['search_opt'][j][1] == int(params['args']['tm'])):
					search_def = j
		params['search_opt'][ search_def ][2] = 'checked'

		params['selectable_opt']=  copy.deepcopy(self.possibleopt)
		params['motd']=self.cgen['motd']
		if('selcat' in params['args']):
			for slctg in params['selectable_opt']:
				if(slctg[0] == params['args']['selcat']):
					slctg[2] = 'selected'
		return self.cleanUpResults(params)
	
	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 
	
	def renderit_empty(self,params):	
		searchopt_local =  copy.deepcopy(self.searchopt)
		searchopt_local[0][2] = 'checked'
		
		possibleopt =  copy.deepcopy(self.possibleopt)
		for slctg in possibleopt:
			if(slctg[0] == self.cgen['search_default']):
				slctg[2] = 'selected'
		#~ params['ver']['chk'] = 1
		#~ params['ver']['os'] = 'openshift'
		return render_template('main_page.html', vr=params['ver'], nc=self.svalid, sugg = [], 
								trend_show = params['trend_show'], trend_movie = params['trend_movie'], debug_flag = params['debugflag'],
								large_server = self.cgen['large_server'],
								sstring  = "", selectable_opt = possibleopt, search_opt = searchopt_local,  motd = self.cgen['motd'], sid = params['sid'])
		
	
	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 
	def tosab(self, args, hname):		
	
		if('data' not in args):
			return 0
	
		send2sab_exist = None
		if ('sabnzbd_url' in self.cgen):
			if(len(self.cgen['sabnzbd_url'])):
				send2sab_exist = self.sckname
				#~ send2sab_exist = hname.scheme+'://'+hname.netloc
				#~ print send2sab_exist

				urlq = self.cgen['sabnzbd_url']+ '/api'
				urlParams = dict(
									mode='addurl',
									name=send2sab_exist+'/'+args['data'],
									apikey=self.cgen['sabnzbd_api'],
								)
				try:				
					http_result = requests.get(url=urlq, params=urlParams, verify=False, timeout=15)
				except Exception as e:
					print 'Error contacting SABNZBD '+str(e)
					return 0
				
				data = http_result.text
				
				#~ that's dirty but effective
				if(len(data) < 100):
					limitpos = data.find('ok')
					if(limitpos == -1):
						mssg = 'ERROR: send url to SAB fails #1'
						print mssg
						log.error (mssg)
						return 0
				else:
					mssg = 'ERROR: send url to SAB fails #2'
					print mssg
					log.error (mssg)
					return 0

				return 1

				
	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 

	def cleanUpResults(self, params):
		sugg_list = params['sugg']
		results = self.results
		svalid = self.svalid
		args = params['args']
		ver_notify = params['ver']
		niceResults = []
		existduplicates = 0

		#~ sorting
		if 'order' not in args:
			results = sorted(results, key=itemgetter('posting_date_timestamp'), reverse=True) 
		else:
			if	(args['order']=='t'):
				results = sorted(results, key=itemgetter('title'))
			if	(args['order']=='s'):
				results = sorted(results, key=itemgetter('size'), reverse=True)
			if	(args['order']=='p'):
				results = sorted(results, key=itemgetter('providertitle'))
			if	(args['order']=='d'):
				results = sorted(results, key=itemgetter('posting_date_timestamp'), reverse=True) 
			if	(args['order']=='c'):
				results = sorted(results, key=itemgetter('categ'), reverse=True) 
				
		#~ do nice 
		for i in xrange(len(results)):
			if(results[i]['ignore'] == 2):
				continue
				
			if(results[i]['ignore'] == 1):
				existduplicates = 1

			# Convert sized to smallest SI unit (note that these are powers of 10, not powers of 2, i.e. OS X file sizes rather than Windows/Linux file sizes)
			szf = float(results[i]['size']/1000000.0)
			mgsz = ' MB '
			if (szf > 1000.0): 
				szf = szf /1000
				mgsz = ' GB '
			fsze1 = str(round(szf,1)) + mgsz
			
			if (results[i]['size'] == -1):
				fsze1 = 'N/A'
			totdays = (datetime.datetime.today() - datetime.datetime.fromtimestamp(results[i]['posting_date_timestamp'])).days + 1		
			category_str = '' 
			keynum = len(results[i]['categ'])
			keycount = 0
			for key in results[i]['categ'].keys():
				category_str = category_str + key
				keycount = keycount + 1
				if (keycount < 	keynum):
					 category_str =  category_str + ' - ' 
			if (results[i]['url'] is None):
				results[i]['url'] = ""
			
			qryforwarp=self.wrp.chash64_encode(results[i]['url'])
			if('req_pwd' in results[i]):
				qryforwarp += '&m='+ results[i]['req_pwd']
			niceResults.append({
				'id':i,
				'url':results[i]['url'],
				'url_encr':'warp?x='+qryforwarp,
				'title':results[i]['title'],
				'filesize':fsze1,
				'cat' : category_str,
				'age':totdays,
				'details':results[i]['release_comments'],
				'details_deref':'http://www.derefer.me/?'+results[i]['release_comments'],
				'providerurl':results[i]['provider'],
				'providertitle':results[i]['providertitle'],
				'ignore' : results[i]['ignore']
			})
		send2sab_exist = None
		if ('sabnzbd_url' in self.cgen):
			if(len(self.cgen['sabnzbd_url'])):
				send2sab_exist = self.sckname
		speed_class_sel = 1	
		if('tm' in args):
			speed_class_sel = int(args['tm'])
		
		#~ save for caching
		if(self.cgen['cache_active'] == 1 and len(self.resultsraw)>0):
			if(len(self.collect_info) < self.cgen['max_cache_qty']):
				if(self.chkforcache(self.wrp.chash64_encode(self.qry_nologic), speed_class_sel) is None):
					collect_all = {}
					collect_all['searchstr'] = self.wrp.chash64_encode(self.qry_nologic)
					collect_all['tstamp'] =  time.time()
					collect_all['resultsraw'] = self.resultsraw		
					collect_all['speedclass'] = speed_class_sel		
					self.collect_info.append(collect_all)
					#~ print 'Result added to the cache list'
		#~ ~ ~ ~ ~ ~ ~ ~ ~ 
		if('selcat' not in params['args']):
			params['args']['selcat'] = ''
			
		return render_template('main_page.html',results=niceResults, exist=existduplicates, 
												vr=ver_notify, args=args, nc = svalid, sugg = sugg_list,
												speed_class_sel = speed_class_sel,
												send2sab_exist= send2sab_exist,
												cgen = self.cgen,
												trend_show = params['trend_show'], 
												trend_movie = params['trend_movie'], 
												debug_flag = params['debugflag'],
												sstring  = params['args']['q'],
												scat = params['args']['selcat'],
												selectable_opt = params['selectable_opt'],
												search_opt =  params['search_opt'],
												sid = params['sid'],
												large_server = self.cgen['large_server'],
												motd = params['motd'] )


#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 
def summary_results(rawResults, strsearch, logic_items=[]):

	results =[]
	titles = []
	sptitle_collection =[]

	#~ all in one array
	for provid in xrange(len(rawResults)):
		for z in xrange(len(rawResults[provid])):
			rawResults[provid][z]['title'] = SearchModule.sanitize_html(rawResults[provid][z]['title'])
			title = SearchModule.sanitize_strings(rawResults[provid][z]['title'])
			titles.append(title)
			sptitle_collection.append(Set(title.split(".")))
			results.append(rawResults[provid][z])
			
	strsearch1 = SearchModule.sanitize_strings(strsearch)
	strsearch1_collection = Set(strsearch1.split("."))	

	rcount = [0]*3
	for z in xrange(len(results)):
		findone = 0 
		results[z]['ignore'] = 0			
		intrs = strsearch1_collection.intersection(sptitle_collection[z])
		if ( len(intrs) ==  len(strsearch1_collection)):			
			findone = 1
		else:
			results[z]['ignore'] = 2

		#~ print strsearch1_collection
		#~ print intrs
		#~ print findone 
		#~ print '------------------'

		if(findone and results[z]['ignore'] == 0):
			#~ print titles[z]
			for v in xrange(z+1,len(results)):
				if(titles[z] == titles[v]):
					sz1 = float(results[z]['size'])
					sz2 = float(results[v]['size'])
					if( abs(sz1-sz2) < 5000000):
						results[z]  ['ignore'] = 1
		#~ stats
		rcount[	results[z]  ['ignore'] ] += 1			

	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 
	#~ logic params
	exclude_coll = Set([])
	include_coll = Set([])
	#~ print '*'+logic_items[0][1]+'*'
	for i in xrange(len(logic_items)):
		if(logic_items[i][0] == '-'):
			exclude_coll.add(logic_items[i][1])
		if(logic_items[i][0] == '+'):
			include_coll.add(logic_items[i][1])
	if(len(include_coll)):
		for z in xrange(len(results)):
			if(results[z]['ignore'] < 2):
				intrs_i = include_coll.intersection(sptitle_collection[z])
				if ( len(intrs_i) == 0 ):			
					results[z]['ignore'] = 2
	if(len(exclude_coll)):
		for z in xrange(len(results)):
			if(results[z]['ignore'] < 2):
				intrs_e = exclude_coll.intersection(sptitle_collection[z])
				if ( len(intrs_e) > 0 ):			
					results[z]['ignore'] = 2
	#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 
	
	mssg = '[' + strsearch1 + ']'+ ' [' + strsearch + '] ' + str(rcount[0]) + ' ' + str(rcount[1]) + ' ' + str(rcount[2])
	print mssg
	log.info (mssg)

	return results
	
#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ 

