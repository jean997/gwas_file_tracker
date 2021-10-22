import argparse
import os
import pandas as pd
import numpy as np
import random
import string
import subprocess
import wget
from datetime import date
from datetime import datetime


def get_args():
    parser = argparse.ArgumentParser(description='Download and document GWAS summary statistics and associated files. \
                              There are three ways to use this utility: \
                              1) Add a single new trait by using at least --url and as many other options as desired. \
                              2) Update an existing entry using --update-entry, --study-id, --trait-id \
                              and relevant other options. 3) Add new traits in bulk from a csv file using --from-file. In all cases \
                              a single positional argument specifying the file name of the catalog is required.')
    parser.add_argument('index', nargs=1, help='Name of csv file cataloging the contents of the directory. \
                                                   If the named file does not exist, it will be created.')
    parser.add_argument('--url', dest='url', default='',
                        help='Single URL location of the data.')
    parser.add_argument('--url-assoc', dest='url_plus', nargs='+', default=[],
                        help='URL location(s) of associated files such as readmes or .tbi files.')
    parser.add_argument('--trait', dest='trait', default='',
                        help='Trait name. Spaces will be converted to underscores.')
    parser.add_argument('--pmid', dest='pmid', default='',
                        help='PubMed ID for associated publication. For un-published data, publications without a \
                              PubMed ID, or other cases, you can choose any string instead or leave out \
                              (see --study-id)')
    parser.add_argument('--author', dest='author', default='',
                        help='First author of publication or consortium (or similar for data not \
                              associated with a publication).')
    parser.add_argument('--year"', dest='year', default='',
                        help='Year of publication.')
    parser.add_argument('--sample-size', dest='sample_size', default='',
                        help='Publication sample size. (Usually this is max sample size over SNPs).')
    parser.add_argument('--note', dest='note', default='',
                        help='Additional information')
    parser.add_argument('--study-id', dest='study_id', default='',
                        help='Study ID string. If not provided, study_id will default to <auth>_<year>_<pmid> or \
                             a random string.')
    parser.add_argument('--trait-id', dest='trait_id', default='',
                        help='Unique trait id. The combination of study ID and trait ID must be unique \
                        (not already present in the index). Trait ID will default to trait name or random string.')
    parser.add_argument('--update-entry', dest='upd', action='store_true',
                        help='This argument can be used to add associated files to an existing entry or to add or \
                             update information such as author, year, and PMID without re-downloading data. Adding \
                             this information will not change the study or trait id which cannot be modified.')
    parser.add_argument('--from-file', dest='csv', default='',
                        help='Add files from information stored in a csv. The file should contain at minimum a column \
                              url for main url.  Optional additional columns are: url_assoc, pmid, author, year, trait, \
                              sample_size, note, study_id, trait_id. \
                              All other columns will be ignored. url_assoc can contain a comma separated list of \
                              urls with or without white space. \
                              If --from-file is used, no other options may be supplied. Lines with url_main empty \
                              will  be interpreted as updates to existing entries.')
    parser.add_argument('--check-directory', dest='check', action='store_true',
                        help='Check the contents of the directory against the index file. Results will be written \
                               to a file named report.datetime. If used in combination with other options, directory \
                               check will be performed first')

    args = parser.parse_args()
    return args


# Read index or create if not existing
def read_index(file, upd, create_backup=True):
    if not os.path.exists(file):
        if upd:
            raise Exception("Index file must exist if using --update-entry.")
        print(f'Creating new index in file {file}')
        tab = {'pmid': [],
               'author': [],
               'year': [],
               'trait': [],
               'sample_size': [],
               'study_id': [],
               'trait_id': [],
               'full_id': [],
               'file': [],
               'url': [],
               'date_downloaded': [],
               'md5': [],
               'type': [],
               'note': []}
        tab = pd.DataFrame(tab)
    else:
        if create_backup:
            save_file = f'{file}.{"_".join(str(datetime.now()).split())}'
            print(
                f'Backing up {file} to {save_file}. If you are satisfied with \
                  the results of this operation, you may delete the backup.\n')
            subprocess.run(f'cp {file} {save_file}', shell=True)
        tab = pd.read_csv(file, header=0, dtype='str')
    validate_index(tab)
    return tab


def read_add(file, features):
    new_dat = pd.read_csv(file, header=0, dtype='str')
    if 'url' not in new_dat.columns:
        raise Exception('url_main must be present in {file}')
    new_dat.replace(np.nan, '', inplace=True)
    my_vars = ["study_id", "trait_id", "url_assoc"] + features
    for v in my_vars:
        if v not in new_dat.columns:
            new_dat[f'{v}'] = ''
    return new_dat


def check_args(args, ref):
    if args.url == '' and args.csv == '' and not args.upd and not args.check:
        raise Exception('You must specify one of --url, --from-file, --update-entry, or --check-directory.')

    if args.upd and len(args.url) > 0:
        raise Exception('If using --update-entry you may not add a main file.')

    # Check that files don't already exist
    if args.url in ref.url.values:
        raise Exception(
            f'A file has already been downloaded from {args.url}. \
            To replace it, delete the file and the entry in the index.')

    for u in args.url_plus:
        if u in ref.url.values:
            raise Exception(
                f'A file has already been downloaded from {u}. To replace it, delete the file and the entry in the index.')

    if args.upd:
        if args.study_id == '' or args.trait_id == '':
            raise Exception('To update an entry, please supply study id and trait id.')


def init_entry(args, ref):
    if args.study_id != '':
        study_id = args.study_id
    elif args.author != '' and args.year != '' and args.pmid != '':
        study_id = f'{args.author}_{args.year}_{args.pmid}'
    else:
        study_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    study_id = study_id.replace(' ', '')

    if args.trait_id != "":
        trait_id = args.trait_id.replace(' ', '_')
    elif args.trait != '':
        trait_id = args.trait.replace(' ', '_')
    else:
        trait_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    full_id = f'{study_id}__{trait_id}'

    # Check if unique name is used already
    if full_id in ref.full_id.values:
        raise Exception(f'{full_id} has already been used.')

    # Check if study_id directory exists
    dirs = os.listdir()
    if study_id not in dirs:
        print(f'Creating directory {study_id}\n')
        os.system(f'mkdir {study_id}')

    print(f'Unique ID: {full_id}')
    return study_id, trait_id, full_id


def check_and_replace(df, var, value):
    if value == '':
        return df, df[f'{var}'][0]
    if any(df[f'{var}'].notnull()):
        print(f'{var} already contains non-missing values. These will be over-written.')
    df[f'{var}'] = value
    return df, df[f'{var}'][0]


def get_files(urls, dest_dir):
    dirs = os.listdir()
    if dest_dir not in dirs:
        raise Exception("Cannot find study ID directory. Is something wrong?")
    file_names = [wget.download(u, dest_dir) for u in urls]
    res = [subprocess.run(f'md5sum "{f}"', capture_output=True, text=True, shell=True) for f in file_names]
    m5 = [r.stdout.split()[0] for r in res]
    return file_names, m5



def update_entry(ref, full_id, args): #pmid, auth, year, trait, ss, note, full_id):
    if full_id not in ref.full_id.values:
        raise Exception(f'{full_id} is not present in the index.')
    my_ref = ref.query(f'full_id == "{full_id}"')
    # print(len())
    other_ref = ref.query(f'full_id != "{full_id}"')
    # print(len(other_tab))
    my_ref, args.pmid = check_and_replace(my_ref, "pmid", args.pmid)
    my_ref, args.author = check_and_replace(my_ref, "author", args.author)
    my_ref, args.year = check_and_replace(my_ref, "year", args.year)
    my_ref, args.trait = check_and_replace(my_ref, "trait", args.trait)
    my_ref, args.sample_size = check_and_replace(my_ref, "sample_size", args.sample_size)
    my_ref, args.note = check_and_replace(my_ref, "note", args.note)
    # print("Done checking")
    ref_full = pd.concat([other_ref, my_ref])
    return ref_full, args


def check_directory(ref, dir=".", report_file=''):
    dirs = os.listdir(dir)
    doc_dirs = []
    undoc_dirs = []
    while len(dirs) > 0:
        x = dirs.pop(0)
        if os.path.isdir(x) and not x.startswith(".") and not x.startswith("_"):
            if x in ref.study_id.values:
                doc_dirs.append(x)
            else:
                print(f'{x} is undocumented')
                undoc_dirs.append(x)
    doc_files_ok = []
    doc_files_notok = []
    undoc_files = []
    for d in doc_dirs:
        fls = []
        for root, dirs, files in os.walk(d):
            my_fls = [f'{root}/{f}' for f in files]
            fls.extend(my_fls)
        for f in fls:
            if not f in ref.file.values:
                print(f'{f} is undocumented')
                undoc_files.append(f)
            else:
                m5out = subprocess.run(f'md5sum "{f}"', capture_output=True, text=True, shell=True)
                m5 = m5out.stdout.split()[0]
                i = list(ref.file.values).index(f)
                if m5 == ref.md5[i]:
                    doc_files_ok.append(f)
                else:
                    doc_files_notok.append(f)
                    print(f'{f} is documented but md5 sums do not match')
    missing_files = list(set(ref.file) - set(doc_files_ok))
    if len(missing_files) > 0:
        print(f'Some files are documented but not present.')
    if len(report_file) >0:
        with open(report_file, "w") as f:
            f.writelines([f'Directory report written on {str(date.today())}\n\n',
                          f'I found {len(doc_dirs) + len(undoc_dirs)} directories.\n',
                          f'There are {len(undoc_dirs)} undocumented directories:\n'])
            f.writelines([f'{d}\n' for d in undoc_dirs])
            f.writelines([f'\nWithin documented directories, I found \n',
                          f'{len(doc_files_ok)} files which are documented with matching md5 checksums\n',
                          f'{len(doc_files_notok)} files which are documented but have non-matching md5 checksums:\n'])
            f.writelines([f'{d}\n' for d in doc_files_notok])
            f.writelines([f'{len(undoc_files)} file which are undocumented:\n'])
            f.writelines([f'{d}\n' for d in undoc_files])



def add_files(urls, pmid, auth, year, trait, ss, note, sid, tid, ft):
    n = len(urls)
    if len(ft) != n:
        raise Exception('file type list should be the same length as url list.')
    full_id = f'{sid}__{tid}'
    file_names, m5 = get_files(urls, sid)
    new_ref = pd.DataFrame({'pmid': [pmid] * n,
                            'author': [auth] * n,
                            'year': [year] * n,
                            'trait': [trait] * n,
                            'sample_size': [ss] * n,
                            'study_id': [sid] * n,
                            'trait_id': [tid] * n,
                            'full_id': [full_id] * n,
                            'file': file_names,
                            'url': urls,
                            'date_downloaded': [str(date.today())] * n,
                            'md5': m5,
                            'type': ft,
                            'note': [note] * n})
    return new_ref

def run_one_study(args, ref):
    if args.upd:
        full_id = f'{args.study_id}__{args.trait_id}'
        ref, args = update_entry(ref, full_id, args)
        if len(args.url_plus)>0:
            ft = ["associated"]*len(args.url_plus)
            new_ref = add_files(args.url_plus, args.pmid, args.author, args.year, args.trait, args.sample_size,args.note,
                                args.study_id, args.trait_id, ft)
            ref = pd.concat([ref, new_ref])
    else:
        sid, tid, fid = init_entry(args, ref)
        urls = [args.url] + args.url_plus
        ft = ["main"] + ["associated"]*len(args.url_plus)
        new_ref = add_files(urls, args.pmid, args.author, args.year, args.trait, args.sample_size, args.note, sid, tid, ft)
        ref = pd.concat([ref, new_ref])
    return ref

def validate_index(ref):
    req_vars = ['study_id', 'trait_id', 'full_id', 'file', 'date_downloaded', 'md5', 'type']
    if any([i not in ref.columns for i in req_vars]):
        raise Exception(f'Reference file is missing at least one of the required columns: study_id, trait_id, full_id, \
                          file, date_downloaded md5, and type.')
    for v in req_vars:
        if any(ref[f'{v}'].isnull()):
            raise Exception(f'Reference file has missing information in {v} which is a required column.')
    #Check for duplicated files or uls
    if not len(ref.file) == len(set(ref.file)):
        raise Exception("There are duplicated files.")
    if not len(ref.url) == len(set(ref.url)):
        raise Exception("There are duplicated urls.")

if __name__ == '__main__':
    args = get_args()
    ref = read_index(args.index[0], args.upd)
    check_args(args, ref)
    if args.check:
        report_file = f'report.{"_".join(str(datetime.now()).split())}'
        check_directory(ref, dir = ".", report_file=report_file)
    if not args.csv:
        ref = run_one_study(args, ref)
        ref.to_csv(args.index[0], index=False)
    elif args.csv:
        features = ['pmid', 'author', 'year', 'trait', 'sample_size', 'note']
        add_ref = read_add(args.csv, features)
        for i in range(len(add_ref)):
            my_args = add_ref.loc[i, :]
            if my_args.url_assoc == '':
                my_args.url_plus = []
            else:
                my_args.url_plus = [i.strip() for i in my_args.url_assoc.split(',')]
            my_args.csv = False
            my_args.upd = my_args.url == ''
            my_args.check = False
            check_args(my_args, ref)
            ref = run_one_study(my_args, ref)
            ref.to_csv(args.index[0], index=False)
