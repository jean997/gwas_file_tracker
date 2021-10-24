This is a set of python utilities for tracking a directory of dowloaded GWAS summary statistics. Studies can be added by calling the script `get_stat.py` with various options. This script will create and maintain a directory of studies that have been downloaded including date of download, urls, and md5 checksums. 

Using the utility requires the `wget` python package which can be installed with 

```
pip install wget
```

To do: 
+ Add directory checker to check consistency of directory contents and index file. (done)
+ Add `--from-file` option for get\_stats (done)
+ Make file features more flexible (in progres)
