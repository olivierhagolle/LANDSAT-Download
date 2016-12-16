#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""
    Landsat Data download from earth explorer
"""
import os,sys,math,urllib2,urllib,time,math,shutil
import subprocess
import optparse
import datetime
import csv
import re

###########################################################################
class OptionParser (optparse.OptionParser):
 
    def check_required (self, opt):
      option = self.get_option(opt)
 
      # Assumes the option's 'default' is set to None!
      if getattr(self.values, option.dest) is None:
          self.error("%s option not supplied" % option)
 
#############################"Connection to Earth explorer with proxy
 
def connect_earthexplorer_proxy(proxy_info,usgs):
    print "Establishing connection to Earthexplorer with proxy..."    
    # contruction d'un "opener" qui utilise une connexion proxy avec autorisation
    cookies = urllib2.HTTPCookieProcessor()
    proxy_support = urllib2.ProxyHandler({"http" : "http://%(user)s:%(pass)s@%(host)s:%(port)s" % proxy_info,
    "https" : "http://%(user)s:%(pass)s@%(host)s:%(port)s" % proxy_info})
    opener = urllib2.build_opener(proxy_support, cookies)
 
    # installation
    urllib2.install_opener(opener)
    # deal with csrftoken required by USGS as of 7-20-2016
    data=urllib2.urlopen("https://ers.cr.usgs.gov").read()
    m = re.search(r'<input .*?name="csrf_token".*?value="(.*?)"', data)
    if m:
        token = m.group(1)
    else :
        print "Error : CSRF_Token not found"
        sys.exit(-3)
    # parametres de connection
    params = urllib.urlencode(dict(username=usgs['account'], password=usgs['passwd'], csrf_token=token))
    # utilisation

    request = urllib2.Request("https://ers.cr.usgs.gov", params, headers={})
    f = urllib2.urlopen(request)
    data = f.read()
    f.close()

    if data.find('You must sign in as a registered user to download data or place orders for USGS EROS products')>0 :        
        print "Authentification failed"
        sys.exit(-1)
    return
 
 
#############################"Connection to Earth explorer without proxy
 
def connect_earthexplorer_no_proxy(usgs):
    # mkmitchel (https://github.com/mkmitchell) solved the token issue
    cookies = urllib2.HTTPCookieProcessor()
    opener = urllib2.build_opener(cookies)
    urllib2.install_opener(opener)
    
    data=urllib2.urlopen("https://ers.cr.usgs.gov").read()
    m = re.search(r'<input .*?name="csrf_token".*?value="(.*?)"', data)
    if m:
        token = m.group(1)
    else :
        print "Error : CSRF_Token not found"
        sys.exit(-3)
        
    params = urllib.urlencode(dict(username=usgs['account'],password= usgs['passwd'], csrf_token=token))
    request = urllib2.Request("https://ers.cr.usgs.gov/login", params, headers={})
    f = urllib2.urlopen(request)

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
    #if downloaded file is html
    if (req.info().gettype()=='text/html'):
      print "error : file is in html and not an expected binary file"
      lines=req.read()
      if lines.find('Download Not Found')>0 :
            raise TypeError
      else:
	  with open("error_output.html","w") as f:
              f.write(lines)
              print "result saved in ./error_output.html"
              sys.exit(-1)
    #if file too small           
    total_size = int(req.info().getheader('Content-Length').strip())
    if (total_size<50000):
       print "Error: The file is too small to be a Landsat Image"
       print url
       sys.exit(-1)
    print nom_fic,total_size
    total_size_fmt = sizeof_fmt(total_size)

    #download
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


##################
def cycle_day(path):
    """ provides the day in cycle given the path number
    """
    cycle_day_path1  = 5
    cycle_day_increment = 7
    nb_days_after_day1=cycle_day_path1+cycle_day_increment*(path-1)
 
    cycle_day_path=math.fmod(nb_days_after_day1,16)
    if path>=98: #change date line
	cycle_day_path+=1
    return(cycle_day_path)



###################
def next_overpass(date1,path,sat):
    """ provides the next overpass for path after date1
    """
    date0_L5 = datetime.datetime(1985,5,4)
    date0_L7 = datetime.datetime(1999,1,11)
    date0_L8 = datetime.datetime(2013,5,1)
    if sat=='LT5':
        date0=date0_L5
    elif sat=='LE7':
        date0=date0_L7
    elif sat=='LC8':
        date0=date0_L8
    next_day=math.fmod((date1-date0).days-cycle_day(path)+1,16)
    if next_day!=0:
        date_overpass=date1+datetime.timedelta(16-next_day)
    else:
        date_overpass=date1
    return(date_overpass)

#############################"Get metadata files
def getmetadatafiles(destdir,option):
    print 'Verifying catalog metadata files...'
    home = 'https://landsat.usgs.gov/landsat/metadata_service/bulk_metadata_files/'
    links=['LANDSAT_8.csv','LANDSAT_ETM.csv','LANDSAT_ETM_SLC_OFF.csv','LANDSAT_TM-1980-1989.csv','LANDSAT_TM-1990-1999.csv','LANDSAT_TM-2000-2009.csv','LANDSAT_TM-2010-2012.csv']
    for l in links:
        destfile = os.path.join(destdir,l)
        url = home+l
        if option=='noupdate':
            if not os.path.exists(destfile):
                print 'Downloading %s for the first time...'%(l)
                urllib.urlretrieve (url, destfile)
        elif option=='update':	
            urllib.urlretrieve (url, destfile)
	
#############################"Unzip tgz file
	
def unzipimage(tgzfile,outputdir):
    success=0
    if (os.path.exists(outputdir+'/'+tgzfile+'.tgz')):
        print "\nunzipping..."
        try:
            if sys.platform.startswith('linux'):
                subprocess.call('mkdir '+ outputdir+'/'+tgzfile, shell=True)   #Unix			
                subprocess.call('tar zxvf '+outputdir+'/'+tgzfile+'.tgz -C '+ outputdir+'/'+tgzfile, shell=True)   #Unix
            elif sys.platform.startswith('win'):
                subprocess.call('tartool '+outputdir+'/'+tgzfile+'.tgz '+ outputdir+'/'+tgzfile, shell=True)  #W32
            success=1
        except TypeError:
            print 'Failed to unzip %s'%tgzfile
        os.remove(outputdir+'/'+tgzfile+'.tgz')
    return success

#############################"Read image metadata		
def read_cloudcover_in_metadata(image_path):
    output_list=[]
    fields = ['CLOUD_COVER']
    cloud_cover=0
    imagename=os.path.basename(os.path.normpath(image_path))
    metadatafile= os.path.join(image_path,imagename+'_MTL.txt')
    metadata = open(metadatafile, 'r')
    # metadata.replace('\r','')	
    for line in metadata:
        line = line.replace('\r', '')	
        for f in fields:
            if line.find(f)>=0:
                lineval = line[line.find('= ')+2:]
                cloud_cover=lineval.replace('\n','')
    return float(cloud_cover)

#############################"Check cloud cover limit
	
def check_cloud_limit(imagepath,limit):
    removed=0
    cloudcover=read_cloudcover_in_metadata(imagepath)
    if cloudcover>limit:
        shutil.rmtree(imagepath)
        print "Image was removed because the cloud cover value of " + str(cloudcover) + " exceeded the limit defined by the user!"	
        removed=1
    return removed		

#############################"Find image with desired specs in usgs entire collection metadata

def find_in_collection_metadata(collection_file,cc_limit,date_start,date_end,wr2path,wr2row):
    print "Searching for images in catalog..."
    cloudcoverlist = []
    cc_values = []	
    with open(collection_file) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            year_acq =int(row['acquisitionDate'][0:4])
            month_acq=int(row['acquisitionDate'][5:7])
            day_acq  =int(row['acquisitionDate'][8:10])
            acqdate=datetime.datetime(year_acq,month_acq, day_acq)
            if 	int(row['path'])==int(wr2path) and int(row['row'])==int(wr2row) and row['DATA_TYPE_L1']!='PR' and float(row['cloudCoverFull'])<=cc_limit and date_start<acqdate<date_end:
                cloudcoverlist.append(row['cloudCoverFull'] + '--' + row['sceneID'])
                cc_values.append(float(row['cloudCoverFull']))				
            else:
                sceneID=''
    for i in cloudcoverlist:
        if float(i.split('--')[0])==min(cc_values):
            sceneID = i.split('--')[1]
    return sceneID
	
#############################"Write info to logfile
	
def log(location,info):
    logfile = os.path.join(location,'log.txt')
    log = open(logfile, 'w')
    log.write('\n'+str(info))	

	
######################################################################################
###############                       main                    ########################
######################################################################################
 
################Lecture des arguments
def main():
    variable1='Teste'
    if len(sys.argv) == 1:
	    prog = os.path.basename(sys.argv[0])
	    print '      '+sys.argv[0]+' [options]'
	    print "     Aide : ", prog, " --help"
	    print "        ou : ", prog, " -h"
	    print "example (scene): python %s -o scene -d 20151001 -f 20151231 -s 199030 -u usgs.txt"%sys.argv[0]
	    print "example (scene): python %s -z unzip -b LT5 -o scene -d 20151001 -f 20151231 -s 203034 -u usgs.txt --output /outputdir/"%sys.argv[0]
	    print "example (scene): python %s -z unzip -b LT5 -o scene -d 20151001 -f 20151231 -s 203034 -u usgs.txt --output /outputdir/ -k update --outputcatalogs /outputcatalogsdir/"%sys.argv[0]		
	    print "example (scene): python %s -b LE7 -o scene -d 20151201 -f 20151231 -s 191025 -u usgs.txt --output . --dir=3373 --station SG1"%sys.argv[0]
	    print "example (liste): python %s -o liste -l /home/hagolle/LANDSAT/liste_landsat8_site.txt -u usgs.txt"%sys.argv[0]	
	    sys.exit(-1)
    else:
        usage = "usage: %prog [options] "
        parser = OptionParser(usage=usage)
        parser.add_option("-o", "--option", dest="option", action="store", type="choice", \
			    help="scene or liste", choices=['scene','liste','catalog'],default=None)
        parser.add_option("-l", "--liste", dest="fic_liste", action="store", type="string", \
			    help="list filename",default=None)
        parser.add_option("-s", "--scene", dest="scene", action="store", type="string", \
			    help="WRS2 coordinates of scene (ex 198030)", default=None)
        parser.add_option("-d", "--start_date", dest="start_date", action="store", type="string", \
			    help="start date, fmt('20131223')")
        parser.add_option("-f","--end_date", dest="end_date", action="store", type="string", \
			    help="end date, fmt('20131223')")
        parser.add_option("-c","--cloudcover", dest="clouds", action="store", type="float", \
			    help="Set a limit to the cloud cover of the image", default=None)			
        parser.add_option("-u","--usgs_passwd", dest="usgs", action="store", type="string", \
			    help="USGS earthexplorer account and password file")
        parser.add_option("-p","--proxy_passwd", dest="proxy", action="store", type="string", \
                help="Proxy account and password file")
        parser.add_option("-z","--unzip", dest="unzip", action="store", type="string", \
			    help="Unzip downloaded tgz file", default=None)			
        parser.add_option("-b","--sat", dest="bird", action="store", type="choice", \
			    help="Which satellite are you looking for", choices=['LT5','LE7', 'LC8'], default='LC8')	
        parser.add_option("--output", dest="output", action="store", type="string", \
			    help="Where to download files",default='/tmp/LANDSAT')
        parser.add_option("--outputcatalogs", dest="outputcatalogs", action="store", type="string", \
			    help="Where to download metadata catalog files",default='/tmp/LANDSAT')					
        parser.add_option("--dir", dest="dir", action="store", type="string", \
			    help="Dir number where files  are stored at USGS",default=None)
        parser.add_option("--station", dest="station", action="store", type="string", \
			    help="Station acronym (3 letters) of the receiving station where the file is downloaded",default=None)	
        parser.add_option("-k", "--updatecatalogfiles", dest="updatecatalogfiles", action="store", type="choice", \
			    help="Update catalog metadata files", choices=['update','noupdate'],default='noupdate')			



        (options, args) = parser.parse_args()
        parser.check_required("-o")
        if options.option=='scene':
	        parser.check_required("-d")
	        parser.check_required("-s")
	        parser.check_required("-u")
	    
        elif options.option=='liste' :
	        parser.check_required("-l")
    	        parser.check_required("-u")

    print options.station, options.dir
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


			
##########Telechargement des produits par scene
    if options.option=='scene':
        produit=options.bird
        path=options.scene[0:3]
        row=options.scene[3:6]
    
        year_start =int(options.start_date[0:4])
        month_start=int(options.start_date[4:6])
        day_start  =int(options.start_date[6:8])
        date_start=datetime.datetime(year_start,month_start, day_start)
        global downloaded_ids		
        downloaded_ids=[]

        if options.end_date!= None:
	        year_end =int(options.end_date[0:4])
	        month_end=int(options.end_date[4:6])
	        day_end  =int(options.end_date[6:8])
	        date_end =datetime.datetime(year_end,month_end, day_end)
        else:
	    date_end=datetime.datetime.now()
	
        if options.proxy!=None:
            connect_earthexplorer_proxy(proxy,usgs)
        else:
            connect_earthexplorer_no_proxy(usgs)	

        # rep_scene="%s/SCENES/%s_%s/GZ"%(rep,path,row)   #Original
        rep_scene="%s"%(rep)	#Modified vbnunes
        if not(os.path.exists(rep_scene)):
            os.makedirs(rep_scene)
			
        if produit.startswith('LC8'):
            repert='4923'
            stations=['LGN']
        if produit.startswith('LE7'):
            repert='3373'
            #repert='3372"
            stations=['EDC','SGS','AGS','ASN','SG1','CUB','COA']
        if produit.startswith('LT5'):
            repert='3119'
            stations=['GLC','ASA','KIR','MOR','KHC', 'PAC', 'KIS', 'CHM', 'LGS', 'MGR', 'COA', 'MPS', 'CUB']		
        
        if options.station !=None:
            stations=[options.station]
        if options.dir !=None:
            repert=options.dir
            
        check=1
		
        curr_date=next_overpass(date_start,int(path),produit)
 
        while (curr_date < date_end) and check==1:
            date_asc=curr_date.strftime("%Y%j")
            notfound = False		
            print 'Searching for images on (julian date): ' + date_asc + '...'
            curr_date=curr_date+datetime.timedelta(16)
            for station in stations:
                for version in ['00','01','02']:			
					nom_prod=produit+options.scene+date_asc+station+version
					tgzfile=os.path.join(rep_scene,nom_prod+'.tgz')
					lsdestdir=os.path.join(rep_scene,nom_prod)				
					url="https://earthexplorer.usgs.gov/download/%s/%s/STANDARD/EE"%(repert,nom_prod)
					print url
					if os.path.exists(lsdestdir):
						print '   product %s already downloaded and unzipped'%nom_prod
						downloaded_ids.append(nom_prod)
						check = 0						
					elif os.path.isfile(tgzfile):
						print '   product %s already downloaded'%nom_prod
						if options.unzip!= None:
							p=unzipimage(nom_prod,rep_scene)
							if p==1 and options.clouds!= None:					
								check=check_cloud_limit(lsdestdir,options.clouds)
								if check==0:
									downloaded_ids.append(nom_prod)							
					else:
						try:
							downloadChunks(url,"%s"%rep_scene,nom_prod+'.tgz')
						except:
							print '   product %s not found'%nom_prod
							notfound = True
						if notfound != True and options.unzip!= None:
							p=unzipimage(nom_prod,rep_scene)
							if p==1 and options.clouds!= None:					
								check=check_cloud_limit(lsdestdir,options.clouds)
								if check==0:
									downloaded_ids.append(nom_prod)								
        log(rep,downloaded_ids)

##########Telechargement des produits par catalog metadata search
    if options.option=='catalog':
        produit=options.bird
        path=options.scene[0:3]
        row=options.scene[3:6]
    
        year_start =int(options.start_date[0:4])
        month_start=int(options.start_date[4:6])
        day_start  =int(options.start_date[6:8])
        date_start=datetime.datetime(year_start,month_start, day_start)
        downloaded_ids=[]

        if options.end_date!= None:
	        year_end =int(options.end_date[0:4])
	        month_end=int(options.end_date[4:6])
	        day_end  =int(options.end_date[6:8])
	        date_end =datetime.datetime(year_end,month_end, day_end)
        else:
	        date_end=datetime.datetime.now()
	
        if options.proxy!=None:
            connect_earthexplorer_proxy(proxy,usgs)
        else:
            connect_earthexplorer_no_proxy(usgs)	

        # rep_scene="%s/SCENES/%s_%s/GZ"%(rep,path,row)   #Original
        rep_scene="%s"%(rep)	#Modified vbnunes
        if not(os.path.exists(rep_scene)):
            os.makedirs(rep_scene)

        getmetadatafiles(options.outputcatalogs, options.updatecatalogfiles)			
			
        if produit.startswith('LC8'):
            repert=['4923']
            collection_file=os.path.join(options.outputcatalogs,'LANDSAT_8.csv')
        if produit.startswith('LE7'):
            repert=['3372','3373']
            collection_file=os.path.join(options.outputcatalogs,'LANDSAT_ETM.csv')			
        if produit.startswith('LT5'):
            repert=['3119','4345']
            if 2000<=int(year_start)<=2009:
                collection_file=os.path.join(options.outputcatalogs,'LANDSAT_TM-2000-2009.csv')
            if 2010<=int(year_start)<=2012:
                collection_file=os.path.join(options.outputcatalogs,'LANDSAT_TM-2010-2012.csv')				
            
        check=1

        notfound = False		
        			
        nom_prod=find_in_collection_metadata(collection_file,options.clouds,date_start,date_end,path,row)
        if nom_prod=='':
            sys.exit('No image was found in the catalog with the given specifications! Exiting...')
        else:				
            tgzfile=os.path.join(rep_scene,nom_prod+'.tgz')
            lsdestdir=os.path.join(rep_scene,nom_prod)

        if os.path.exists(lsdestdir):
            print '   product %s already downloaded and unzipped'%nom_prod
            downloaded_ids.append(nom_prod)
            check = 0						
        elif os.path.isfile(tgzfile):
            print '   product %s already downloaded'%nom_prod
            if options.unzip!= None:
                p=unzipimage(nom_prod,rep_scene)
                if p==1:
                    downloaded_ids.append(nom_prod)	
                    check = 0						
        else:
            while check == 1:
                for collectionid in repert:
                    url="https://earthexplorer.usgs.gov/download/%s/%s/STANDARD/EE"%(collectionid,nom_prod)				
                    try:
                        downloadChunks(url,"%s"%rep_scene,nom_prod+'.tgz')
                    except:
                        print '   product %s not found'%nom_prod
                        notfound = True
                    if notfound != True and options.unzip!= None:
                        p=unzipimage(nom_prod,rep_scene)
                        if p==1 and options.clouds!= None:					
                            check=check_cloud_limit(lsdestdir,options.clouds)
                            if check==0:
                                downloaded_ids.append(nom_prod)			
        log(rep,downloaded_ids)		
		
##########Telechargement par liste
    if options.option=='liste':
        with file(options.fic_liste) as f:
	    lignes=f.readlines()
        for ligne in lignes:
            (site,nom_prod)=ligne.split(' ')
            produit=nom_prod.strip()
            print produit
            if produit.startswith('LC8'):
                repert='4923'
                stations=['LGN']
            if produit.startswith('LE7'):
                repert='3373'
                #repert='3372"
                stations=['EDC','SGS','AGS','ASN','SG1']
            if produit.startswith('LT5'):
                repert='3119'
                stations=['GLC','ASA','KIR','MOR','KHC', 'PAC', 'KIS', 'CHM', 'LGS', 'MGR', 'COA', 'MPS']	
            if not os.path.exists(rep+'/'+site):
                os.mkdir(rep+'/'+site)
            url="https://earthexplorer.usgs.gov/download/%s/%s/STANDARD/EE"%(repert,produit)
            print 'url=',url
            try:
                if options.proxy!=None :
                    connect_earthexplorer_proxy(proxy,usgs)
                else:
                    connect_earthexplorer_no_proxy(usgs)

                downloadChunks(url,rep+'/'+site,produit+'.tgz')
            except TypeError:
                print 'produit %s non trouve'%produit

if __name__ == "__main__":
    main()
