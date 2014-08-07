#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""
    Landsat Data download from earth explorer
    Incorporates jake-Brinkmann improvements
"""
import os,sys,math,urllib2,urllib,time
import optparse
###########################################################################
class OptionParser (optparse.OptionParser):
 
    def check_required (self, opt):
      option = self.get_option(opt)
 
      # Assumes the option's 'default' is set to None!
      if getattr(self.values, option.dest) is None:
          self.error("%s option not supplied" % option)
 
#############################"Connection à Earth explorer sans proxy
 
def connect_earthexplorer_proxy(proxy_info,usgs):
    
     # contruction d'un "opener" qui utilise une connexion proxy avec autorisation
     proxy_support = urllib2.ProxyHandler({"http" : "http://%(user)s:%(pass)s@%(host)s:%(port)s" % proxy_info,
     "https" : "http://%(user)s:%(pass)s@%(host)s:%(port)s" % proxy_info})
     opener = urllib2.build_opener(proxy_support, urllib2.HTTPCookieProcessor)
 
     # installation
     urllib2.install_opener(opener)

     # parametres de connection
     params = urllib.urlencode(dict(username=usgs['account'], password=usgs['passwd']))
 
     # utilisation
     f = opener.open('https://earthexplorer.usgs.gov/login', params)
     data = f.read()
     f.close()

     if data.find('You must sign in as a registered user to download data or place orders for USGS EROS products')>0 :        
	 print "Authentification failed"
	 sys.exit(-1)



     return
 
 
#############################"Connection à Earth explorer sans proxy
 
def connect_earthexplorer_no_proxy(usgs):
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
    urllib2.install_opener(opener)
    params = urllib.urlencode(dict(username=usgs['account'],password= usgs['passwd']))
    f = opener.open("https://earthexplorer.usgs.gov/login/", params)
    data = f.read()
    f.close()
    if data.find('You must sign in as a registered user to download data or place orders for USGS EROS products')>0 :
	print "Authentification failed"
	sys.exit(-1)
    return
#############################
 
def sizeof_fmt(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0 
#############################
def downloadChunks(url,rep,nom_fic):
  """ Downloads large files in pieces
   inspired by http://josh.gourneau.com
  """
 
  try:
    req = urllib2.urlopen(url)
    #taille du fichier
    if (req.info().gettype()=='text/html'):
      print "erreur : le fichier est au format html"
      lignes=req.read()
      if lignes.find('Download Not Found')>0 :
            raise TypeError
      else:
	  print lignes
	  print sys.exit(-1)
    total_size = int(req.info().getheader('Content-Length').strip())
    if (total_size<50000):
       print "Error: The file is too small to be a Landsat Image"
       print url
       sys.exit(-1)
    print nom_fic,total_size
    total_size_fmt = sizeof_fmt(total_size)

    downloaded = 0
    CHUNK = 1024 * 1024 *8
    with open(rep+'/'+nom_fic, 'wb') as fp:
        start = time.clock()
        print('Downloading {0} ({1}):'.format(nom_fic, total_size_fmt))
	while True:
	     chunk = req.read(CHUNK)
	     downloaded += len(chunk)
	     done = int(50 * downloaded / total_size)
	     sys.stdout.write('\r[{1}{2}]{0:3.0f}% {3}ps'
                             .format(math.floor((float(downloaded)
                                                 / total_size) * 100),
                                     '=' * done,
                                     ' ' * (50 - done),
                                     sizeof_fmt((downloaded // (time.clock() - start)) / 8)))
	     sys.stdout.flush()
	     if not chunk: break
	     fp.write(chunk)
  except urllib2.HTTPError, e:
       if e.code == 500:
            pass # File doesn't exist
       else:
            print "HTTP Error:", e.code , url
       return False
  except urllib2.URLError, e:
    print "URL Error:",e.reason , url
    return False
 
  return rep,nom_fic
 
######################################################################################
###############main
#################################################################################
 
################Lecture des arguments
if len(sys.argv) == 1:
	prog = os.path.basename(sys.argv[0])
	print '      '+sys.argv[0]+' [options]'
	print "     Aide : ", prog, " --help"
	print "        ou : ", prog, " -h"
	print "example (scene): python %s -o scene -a 2013 -d 360 -f 365 -s 199030 -u usgs.txt"%sys.argv[0]
	print "example (liste): python %s -o liste -l /home/hagolle/DOCS/TAKE5/liste_landsat8_site.txt -u usgs.txt"%sys.argv[0]
	sys.exit(-1)
else:
	usage = "usage: %prog [options] "
	parser = OptionParser(usage=usage)
        parser.add_option("-o", "--option", dest="option", action="store", type="choice", \
			help="scene or liste", choices=['scene','liste'],default=None)
	parser.add_option("-l", "--liste", dest="fic_liste", action="store", type="string", \
			help="liste filename",default=None)
        parser.add_option("-s", "--scene", dest="scene", action="store", type="string", \
			help="coordonnees WRS2 de la scene (ex 198030)", default=None)
	parser.add_option("-a", "--annee", dest="annee", action="store", type="int", \
			help="annee")
	parser.add_option("-d", "--doy_deb", dest="doy_deb", action="store", type="int", \
			help="first landsat day of year for tile ")
	parser.add_option("-f","--doy_fin", dest="doy_fin", action="store", type="int", \
			help="last day of year for tile")
	parser.add_option("-u","--usgs_passwd", dest="usgs", action="store", type="string", \
			help="USGS earthexplorer account and password file")
	parser.add_option("-p","--proxy_passwd", dest="proxy", action="store", type="string", \
			help="Proxy account and password file")
	parser.add_option("--output", dest="output", action="store", type="string", \
			help="Where to download files",default='/tmp/LANDSAT')
 
	(options, args) = parser.parse_args()
	parser.check_required("-o")
	if options.option=='scene':
	    parser.check_required("-d")
	    parser.check_required("-a")
	    parser.check_required("-f")
	    parser.check_required("-s")
	    parser.check_required("-u")
	    
	elif options.option=='liste' :
	    parser.check_required("-l")
    	    parser.check_required("-u")


rep=options.output
if not os.path.exists(rep):
    os.mkdir(rep)
    if options.option=='liste':
	if not os.path.exists(rep+'/LISTE'):
	     os.mkdir(rep+'/LISTE')
 
# read password files
try:
    f=file(options.usgs)
    (account,passwd)=f.readline().split(' ')
    if passwd.endswith('\n'):
	passwd=passwd[:-1]
    usgs={'account':account,'passwd':passwd}
    f.close()
except :
    print "error with usgs password file"
    sys.exit(-2)

if options.proxy != None :
    try:
	f=file(options.proxy)
	(user,passwd)=f.readline().split(' ')
	if passwd.endswith('\n'):
	    passwd=passwd[:-1]
	host=f.readline()
	if host.endswith('\n'):
	    host=host[:-1]
	port=f.readline()
	if port.endswith('\n'):
	    port=port[:-1]
	proxy={'user':user,'pass':passwd,'host':host,'port':port}
	f.close()
    except :
	print "error with proxy password file"
	sys.exit(-3)
############Telechargement des produits par scene
if options.option=='scene':
    produit='LC8'
    station='LGN'
    path=options.scene[0:3]
    row=options.scene[3:6]


	    
    rep_scene="%s/SCENES/%s_%s/GZ"%(rep,path,row)
    print rep_scene
    if not(os.path.exists(rep_scene)):
	os.makedirs(rep_scene)
    if produit.startswith('LC8'):repert='4923'
    if produit.startswith('LE7'):repert='3373'
 
    doy=options.doy_deb
 
    while (doy < options.doy_fin) and (doy < 366) :
       date_asc="%04d%03d"%(options.annee,doy)
       doy+=16
       for version in ['00','01']:
	   nom_prod=produit+options.scene+date_asc+station+version
	   url="http://earthexplorer.usgs.gov/download/%s/%s/STANDARD/EE"%(repert,nom_prod)
	   print url
	   if not(os.path.exists(rep_scene+'/'+nom_prod+'.tgz')):
	       if options.proxy!=None :
		       connect_earthexplorer_proxy(proxy,usgs)
	       else:
		       connect_earthexplorer_no_proxy(usgs)
	       try:
		   downloadChunks(url,"%s"%rep_scene,nom_prod+'.tgz')
	       except TypeError:
		  print '   produit %s non trouve'%nom_prod
	   else :
	       print '   produit %s deja telecharge'%nom_prod
	       break
 
############Telechargement par liste
if options.option=='liste':
    with file(options.fic_liste) as f:
	lignes=f.readlines()
    for ligne in lignes:
	(site,nom_prod)=ligne.split(' ')
	nom_prod=nom_prod.strip()
	if nom_prod.startswith('LC8'):repert='4923'
        if nom_prod.startswith('LE7'):repert='3373'
 
	if not os.path.exists(rep+'/SITES/'+site):
	    os.mkdir(rep+'/SITES/'+site)
	url="http://earthexplorer.usgs.gov/download/%s/%s/STANDARD/EE"%(repert,nom_prod)
	try:
	    if options.proxy!=None :
	       connect_earthexplorer_proxy(proxy,usgs)
	    else:
	       connect_earthexplorer_no_proxy(usgs)

	    downloadChunks(url,rep+'/SITES/'+site,nom_prod+'.tgz')
	except TypeError:
	    print 'produit %s non trouve'%nom_prod
