
import argparse
import os
import sys
import pandas as pd
import random
import string
import subprocess
import wget
from datetime import date 
from datetime import datetime 


parser = argparse.ArgumentParser(description='Download and docuent GWAS summary statistics and associated files. \
					      There are three ways to use this utility: 1) Add a single new trait by using at least --url-main \
                                              and as many other options as desired. 2) Update an existing entry using --update-entry, --study-id, --trait-id \
					      and relevant other options. 3) Add new traits in bulk from a csv file using --from-file. In all cases \
	 				      a single positional argument specifying the file name of the catalog is required.') 
parser.add_argument('index',  nargs=1, help='Name of csv file cataloging the contents of the directory. \
                                               If the named file does not exist, it will be created.')
parser.add_argument('--url-main', dest='url',  default='',
                    help='Single URL location of the data.')
parser.add_argument('--url-assoc', dest='url_plus',  nargs='+', default=[],
                    help='URL location(s) of associated files such as readmes or .tbi files.')
parser.add_argument('--trait', dest='trait', default='',
                    help='Trait name. Spaces will be converted to underscores.')
parser.add_argument('--pmid', dest='pmid', default='',
                    help='PubMed ID for associated publication. For un-published data, publications without a PubMed ID, or other cases, you can choose any string instead or leave out (see --study-id)')
parser.add_argument('--author', dest='auth', default='',
                    help='First author of publication or consortium (or similar for data not associated with a publication).')
parser.add_argument('--year"', dest='year', default='', 
                    help='Year of publication.')
parser.add_argument('--sample-size', dest='ss', default='', 
                    help='Publication sample size. (Usually max sample size over SNPs).')
parser.add_argument('--note', dest='note', default='',
                    help='Additional information')
parser.add_argument('--study-id', dest='study_id', 
                    help='Study ID string. If not provided, study_id will default to <auth>_<year>_<pmid> or a random string.')
parser.add_argument('--trait-id', dest='trait_id', 
                    help='Unique trait id. The combination of study ID and trait ID must be unique (not already present in the index). Trait ID will default to trait name or random string.')
parser.add_argument('--update-entry', dest='upd', action='store_true',
                    help='This argument can be used to add associated files to an existing entry or to add or update information such as author, year, and PMID without re-downloading data. Adding this information will not change the study or trait id which cannot be modified.')
parser.add_argument('--from-file', dest='csv', default='',
                    help='Add files from information stored in a csv. The file should contain at minimum a column url_main.  \
			  Optional additional columns are: url_assoc, pmid, author, year, trait, sample_size, note, study_id, trait_id. \
                          All other columns will be ignored. url_assoc can contain a comma separated list of urls with or without white space. \
			  If --from-file is used, no other options may be supplied. \
                          This option cannot be used to update existing entires. ')

args = parser.parse_args()


#Check arguments
if args.url=='' and args.csv == '' and args.upd is False: 
	raise Exception('You must specify one of --url-main, --from-file or --update-entry.')

# Read index or create if not existing
if not os.path.exists(args.index[0]):
	if args.upd:
		raise Exception("Index file must exist if using --update-entry.")
	print(f'Creating new index in file {args.index[0]}')
	tab = {'pmid': [], \
	   'author': [], \
	   'year': [], \
	   'trait': [], \
	   'sample_size': [], \
	   'study_id': [], \
	   'trait_id': [], \
	   'full_id': [], \
           'file':[], \
           'url': [], \
	   'date_downloaded': [], \
	   'md5' : [], \
	   'type': [], \
	   'note': []}
	tab = pd.DataFrame(tab)	
else:
	save_file = f'{args.index[0]}.{"_".join(str(datetime.now()).split())}' 
	print(f'Backing up {args.index[0]} to {save_file}. If you are satisfied with the results of this opperation, you may delete the backup.\n')
	subprocess.run(f'cp {args.index[0]} {save_file}', shell=True)
	tab = pd.read_csv(args.index[0], header = 0, dtype = 'str' )
# Index columns:
# pmid, author, year, trait, study_id, trait_id, full_id,  file, url,date_dowloaded, md5, type
# There will be one row per file, type is either "main" or "associated"

# Check that files don't already exist
if args.url in tab.url.values:
	raise Exception(f'A file has already been downloaded from {args.url}. To replace it, delete the file and the entry in the index.')
for u in args.url_plus:
	if u in tab.url.values:
		raise Exception(f'A file has already been downloaded from {u}. To replace it, delete the file and the entry in the index.')


def check_and_replace(df, var, value):
	if value == '':
		return df, df[f'{var}'][0]
	if any(df[f'{var}'].notnull()):
		print(f'{var} already contains non-missing values. These will be over-written.')
	df[f'{var}'] = value
	return df, df[f'{var}'][0]

def get_files(urls, dest_dir):
	file_names = [wget.download(u, dest_dir) for u in urls]
	res = [subprocess.run(f'md5sum "{f}"', capture_output = True, text = True, shell = True) for f in file_names]
	m5 = [r.stdout.split()[0] for r in res]
	return file_names, m5

# Updating an entry
if args.upd:
	if  args.study_id is None or args.trait_id is None:
		raise Exception('To update an entry, please supply study id and trait id.')
	full_id = f'{args.study_id}__{args.trait_id}'
	if full_id not in tab.full_id.values:
		raise Exception(f'{full_id} is not present in the index.')
	dirs = os.listdir()
	if args.study_id not in dirs:
		raise Exception("Cannot find study ID directory. Is something wrong?")
	# Retrieve entry, update then exit
	my_tab = tab.query(f'full_id == "{full_id}"')
	#print(len(my_tab))
	other_tab = tab.query(f'full_id != "{full_id}"')
	#print(len(other_tab))
	my_tab, args.pmid = check_and_replace(my_tab, "pmid", args.pmid)
	my_tab, args.auth = check_and_replace(my_tab, "author", args.auth)
	my_tab, args.year = check_and_replace(my_tab, "year", args.year)
	my_tab, args.trait = check_and_replace(my_tab, "trait", args.trait)
	my_tab, args.ss  = check_and_replace(my_tab, "sample_size", args.ss)
	my_tab, args.note = check_and_replace(my_tab, "note", args.note)
	#print("Done checking")
	if len(args.url_plus)>0:
		tab_full = pd.concat([other_tab, my_tab])
		tab_full.to_csv(args.index[0], index = False)
		sys.exit()

	n = len(args.url_plus)	
	file_names, m5 = get_files(args.url_plus, args.study_id)
	new_tab = pd.DataFrame({'pmid': [args.pmid]*n, 
	   'author': [args.auth]*n, \
	   'year': [args.year]*n, \
	   'trait': [args.trait]*n, \
	   'sample_size': [args.ss]*n, \
	   'study_id': [args.study_id]*n, \
	   'trait_id': [args.trait_id]*n, \
	   'full_id': [full_id]*n, \
           'file': file_names, \
           'url': args.url_plus, \
	   'date_downloaded': [str(date.today())]*n,  \
	   'md5' : m5, 
	   'type': ["associated"]*n,
	   'note': [args.note]*n})
	
	my_tab = pd.concat([my_tab, new_tab]) 
	tab_full = pd.concat([other_tab, my_tab])
	tab_full.to_csv(args.index[0], index = False)
	sys.exit()
	


# Making a new entry	
# Assign directory name  to be study id
if args.study_id is not None:
	study_id =  args.study_id[0]
elif len(args.auth)>0  and len(args.year)>0 and len(args.pmid)>0:
	study_id = f'{args.auth}_{args.year}_{args.pmid}'
else:
	study_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Assign unique trait ID
if len(args.trait)>0:
	trait_id = "_".join(args.trait.split())
else:
	trait_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

full_id = f'{study_id}__{trait_id}'

# Check if unique name is used already
if full_id in tab.full_id.values:
	raise Exception(f'{full_id} has already been used.')


# Check if study_id directory exists
dirs = os.listdir()
if study_id not in dirs:
	os.system(f'mkdir {study_id}')

print(f'Unique ID: {full_id}')

ft = ["main"]
if len(args.url_plus)>0:
	urls = [args.url]  + args.url_plus
	ft.extend(["associated"]*len(args.url_plus))	

n = len(args.url)

#Download files to directory
file_names, m5 = get_files(args.url, study_id)


#Store info in spreadsheet
# pmid, first_author, year, trait_name, study_id, trait_id, full_id,  file_path, url,date_dowloaded, md5, type
# There will be one row per file, type is either "main" or "associated"
new_tab = pd.DataFrame({'pmid': [args.pmid]*n,  \
	   'author': [args.auth]*n, \
	   'year': [args.year]*n, \
	   'trait': [args.trait]*n, \
	   'sample_size': [args.ss]*n, \
	   'study_id': [study_id]*n, \
	   'trait_id': [trait_id]*n, \
	   'full_id': [full_id]*n, \
           'file': file_names, \
           'url': args.url, \
	   'date_downloaded': [str(date.today())]*n,  \
	   'md5' : m5, 
	   'type': ft, 
	   'note': [args.note]*n})

tab_full = pd.concat([tab, new_tab])

tab_full.to_csv(args.index[0], index = False)

