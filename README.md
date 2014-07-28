LANDSAT-Download
================

The routine provided below enables to automatically download LANDSAT data, using the current (April 2014) version of EartExplorer.


It works for LANDSAT 8 and LANDSAT 5&7, but needs that the data be already online. It seems to be systematically the case for LANDSAT 8, but for the older LANDSAT, it may be necessary to first order for the production of L1T products, on the earthexplorer site http://earthexplorer.usgs.gov. And of course, you will need to have an accont and password on the Earthexplorer website, to store on the usgs.txt file. If you have an access through a proxy, you might try the -p option. it works through CNES proxy at least but was only tested there.

This routine may be used in two ways :

- by providing the WRS-2 coordinates of the LANDSAT scene, for instance, (198,030) for Toulouse. And, as LANDSAT passes every 16 days, you also have to provide with the -d option, the exact value of a LANDSAT overpass. Example:

`        python download_landsat_scene.py -o scene -t LC8 -a 2013 -d 113 -f 365 -s 199030 -u usgs.txt`

- by providing a list of products to download, as in the example below:

`        python download_landsat_scene.py -o liste -l list2_landsat8.txt -u usgs.txt`

with a file list2_landsat8.txt as provide below (the landsat references must exist in the earthexplorer catalog) :

 `        Tunisie LC81910352013160LGN00`

  `       Tunisie LC81910362013160LGN00`

The usgs.txt must contain your username and password on the same line separated by a blank.

The files will be downloaded to /tmp/Landsat. 

To see all the options : 
       ` download_landsat_scene.py -h`

