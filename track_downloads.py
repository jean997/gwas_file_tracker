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
import yaml
from yaml.loader import SafeLoader


def get_args():
    parser = argparse.ArgumentParser(description='Download and document GWAS summary statistics and associated files. \
                              There are three ways to use this utility: \
                              1) Add a single new trait by using at least --url and as many other options as desired. \
                              2) Update an existing entry using --update-entry, --subject-id, --unit-id \
                              and relevant other options. 3) Add new traits in bulk from a csv file using --from-file. In all cases \
                              a single positional argument specifying the file name of the catalog is required.')
    parser.add_argument('index', nargs=1, help='Name of csv file cataloging the contents of the directory. \
                                                   If the named file does not exist, it will be created.')
    parser.add_argument('--url', dest='url', default='',
                        help='Single URL location of the data.')
    parser.add_argument('--url-assoc', dest='url_plus', nargs='+', default=[],
                        help='URL location(s) of associated files such as readmes or .tbi files.')
    parser.add_argument('--subject-id', dest='subject_id', default='',
                        help='Subject ID string. This ID will also be used as a directory name. \
                              A default value for directory_id can be provided in a yml file. \
                              If no default is provided or not all features are present, subject_id will be assigned \
                              a random string')
    parser.add_argument('--unit-id', dest='unit_id', default='',
                        help='Unique unit id. The combination of subject ID and unit ID must be unique \
                        (not already present in the index for new units). \
                        The default for unit ID can be specified in a yml file or will be a random string.')
    parser.add_argument('--features', dest='features', nargs='+', default=[],
                        help='Specify additional features in the format feature:value. If value contains white space, \
                              use quotes as in --features "trait:body mass index"')
    parser.add_argument('--update-entry', dest='upd', action='store_true',
                        help='This argument can be used to add associated files to an existing entry or to add and/or \
                             update or add features. Modifying features will not change the subject or unit id which \
                             cannot be modified.')
    parser.add_argument('--from-file', dest='csv', default='',
                        help='Add files from information stored in a csv. The file should contain at minimum a column \
                              url for main url.  Optional additional columns are: url_assoc, pmid, author, year, trait, \
                              sample_size, note, subject_id, unit_id. \
                              All other columns will be ignored. url_assoc can contain a comma separated list of \
                              urls with or without white space. \
                              If --from-file is used, no other options may be supplied. Lines with url_main empty \
                              will  be interpreted as updates to existing entries.')
    parser.add_argument('--remove', dest='remove', action='store_true',
                        help='Remove supplied unit and individual ID. Files will be deleted and corresponding lines removed \
                        from reference file')
    parser.add_argument('--check-directory', dest='check', action='store_true',
                        help='Check the contents of the directory against the index file. Results will be written \
                               to a file named report.datetime. If used in combination with other options, directory \
                               check will be performed first')
    parser.add_argument('--remove-missing', dest='check_remove', action='store_true',
                        help='If checking directory, remove entries with no existing files.')
    parser.add_argument('--config', dest='config', help="YAML formatted configuration file")
    #args = parser.parse_args()
    #return args
    return parser

def req_vars():
    req_vars = ['subject_id', 'unit_id', 'full_id', 'file', 'date_downloaded', 'md5', 'type', 'url']
    return req_vars

def parse_features(flist):
    #print(flist)
    if len(flist) == 0:
        d = {}
        return(d)
    d = []
    for entry in flist:
        entry = entry.split(":")
        if len(entry) != 2:
            raise Exception('Something is wrong with features option. Each option should have exactly one : symbol')
        entry = tuple([e.strip() for e in entry])
        d.append(entry)
    return dict(d)


def read_config(file):
    if file is None:
        config = {'subject_id':[], 'unit_id':[], 'ignore_dirs':[]}
        return config
    with open(file) as f:
        config = yaml.load(f, Loader=SafeLoader)

    if any([k not in ["subject_id", "unit_id", "ignore_dirs"] for k in config.keys()]):
        raise Exception("Unrecognized features in config file.")
    if "subject_id" in config.keys():
        if not isinstance(config["subject_id"], list):
            raise Exception("subject_id should be a list in config file.")
    else:
        config["subject_id"] = []
    if "unit_id" in config.keys():
        if not isinstance(config["unit_id"], list):
            raise Exception("unit_id should be a list in config file.")
    else:
        config["unit_id"] = []
    if "ignore_dirs" in config.keys():
        if not isinstance(config["ignore_dirs"], list):
            raise Exception("ignore_dirs should be a list in config file.")
    else:
        config["ignore_dirs"] = []
    return config


# Read index or create if not existing
def read_index(file, new_ok, create_backup=True, default_features=()):
    if not os.path.exists(file):
        if not new_ok:
            raise Exception("Index file must exist if using --update-entry or --remove.")
        print(f'Creating new index in file {file}')
        tab = {'subject_id': [],
               'unit_id': [],
               'full_id': [],
               'file': [],
               'url': [],
               'date_downloaded': [],
               'md5': [],
               'type': []}
        for f in default_features:
            tab[f] = []
        tab = pd.DataFrame(tab)
    else:
        if create_backup:
            save_file = f'{file}.{"_".join(str(datetime.now()).split())}'
            print(
                f'Backing up {file} to {save_file}. If you are satisfied with' \
                  'the results of this operation, you may delete the backup.\n')
            subprocess.run(f'cp {file} {save_file}', shell=True)
        tab = pd.read_csv(file, header=0, dtype='str')
    validate_index(tab)
    return tab


def read_add(file, req_feats):
    new_dat = pd.read_csv(file, header=0, dtype='str')
    if 'url' not in new_dat.columns:
        raise Exception('url_main must be present in {file}')
    new_dat.replace(np.nan, '', inplace=True)
    my_vars = ["subject_id", "unit_id", "url_assoc"] + req_feats
    for v in my_vars:
        if v not in new_dat.columns:
            new_dat[v] = ''
    return new_dat

def check_args(args, ref):
    if args.url == '' and args.csv == '' and not args.upd and not args.check and not args.remove:
        raise Exception('You must specify one of --url, --from-file, --update-entry, or --check-directory.')

    if args.upd and len(args.url) > 0:
        raise Exception('If using --update-entry you may not add a main file.')

    # Check that files don't already exist
    if args.url in ref.url.to_list():
        raise Exception(
            f'A file has already been downloaded from {args.url}. \
            To replace it, delete the file and the entry in the index.')

    for u in args.url_plus:
        if u in ref.url.to_list():
            raise Exception(
                f'A file has already been downloaded from {u}. To replace it, delete the file and the entry in the index.')

    if args.upd:
        if args.subject_id == '' or args.unit_id == '':
            raise Exception('To update an entry, please supply subject id and unit id.')

    if args.remove:
        if args.subject_id == '' or args.unit_id == '':
            raise Exception('To remove an entry, please supply subject id and unit id.')
        full_id = f'{args.subject_id}__{args.unit_id}'
        if full_id not in ref.full_id.to_list():
            raise Exception('Requested IDs are not present in reference file.')

    if args.check_remove and not args.check:
        raise Exception('--remove-missing can only be used with --check-directory option.')


def remove_entry(subject_id, unit_id, ref):
    full_id = f'{subject_id}__{unit_id}'
    my_idx = ref.query(f'full_id == "{full_id}"').index.to_list()
    for i in my_idx:
        if os.path.exists(ref.file[i]):
            print(f'Deleting {ref.file[i]}')
            os.remove(ref.file[i])
        ref = ref.drop(i)
    if os.path.exists(subject_id):
        if len(os.listdir(subject_id)) == 0:
            os.rmdir(subject_id)
    return ref



def init_entry(args, ref, inp_features, subj_feats=(), unit_feats=()):
    if args.subject_id == '':
        if len(subj_feats) > 0:
            if all([f in inp_features.keys() for f in subj_feats]):
                if all([inp_features[f] != '' for f in subj_feats]):
                    args.subject_id = '_'.join([inp_features[f] for f in subj_feats])
    if args.subject_id == '':
       args.subject_id = 'download_' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    args.subject_id = args.subject_id.replace(' ', '-')

    if args.unit_id == "":
        if len(unit_feats) > 0:
            if all([f in inp_features.keys() for f in unit_feats]):
                if all([inp_features[f] != '' for f in unit_feats]):
                    args.unit_id = '_'.join([inp_features[f'{f}'] for f in unit_feats])
    if args.unit_id == '':
        args.unit_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    args.unit_id = args.unit_id.replace(' ', '-')

    full_id = f'{args.subject_id}__{args.unit_id}'

    # Check if unique name is used already
    if full_id in ref.full_id.to_list():
        raise Exception(f'{full_id} has already been used.')

    # Check if subject_id directory exists
    dirs = os.listdir()
    if args.subject_id not in dirs:
        print(f'Creating directory {args.subject_id}\n')
        os.system(f'mkdir {args.subject_id}')

    print(f'Unique ID: {full_id}')
    return args.subject_id, args.unit_id, full_id


def check_and_replace(df, idx, var, value):
    if value == '':
        return df
    if var in df.columns:
        if any(df[var].notnull()):
            print(f'{var} already contains non-missing values. These will be over-written.')
    df.loc[idx, var] = value
    return df


def get_files(urls, dest_dir):
    dirs = os.listdir()
    if dest_dir not in dirs:
        raise Exception("Cannot find study ID directory. Is something wrong?")
    cwd = os.getcwd()
    file_names = [cwd + '/' + wget.download(u, dest_dir) for u in urls]
    res = [subprocess.run(f'md5sum "{f}"', capture_output=True, text=True, shell=True) for f in file_names]
    m5 = [r.stdout.split()[0] for r in res]
    return file_names, m5


# Updates existing features, adds new features
# ref should have already been validated by the time it gets here
# vals should be a dictionary of supplementary features
def update_entry(ref, full_id, vals):
    my_idx = ref.query(f'full_id == "{full_id}"').index.to_list()
    # required variables can't be changed by update entry
    # other_ref = ref.query(f'full_id != "{full_id}"')
    # Only supplementary information can be changed
    new_feats = set(vals.keys()) - set(req_vars())
    for f in new_feats:
        ref = check_and_replace(ref, my_idx, f, vals[f])
    # ref_full = pd.concat([other_ref, my_ref], ignore_index=True)
    ref = ref.replace(np.nan, '')
    return ref

def check_directory(ref, dir=".", report_file='', remove_missing = False, ignore_dirs = []):
    dirs = list(set(os.listdir(dir)) - set(ignore_dirs))
    doc_dirs = []
    undoc_dirs = []
    while len(dirs) > 0:
        x = dirs.pop(0)
        if os.path.isdir(x) and not x.startswith(".") and not x.startswith("_"):
            if x in ref.subject_id.to_list():
                doc_dirs.append(x)
            else:
                print(f'{x} is undocumented')
                undoc_dirs.append(x)
    doc_files_ok = []
    doc_files_notok = []
    undoc_files = []
    cwd = os.getcwd()
    for d in doc_dirs:
        fls = []
        for root, dirs, files in os.walk(d):
            my_fls = [f'{root}/{f}' for f in files]
            fls.extend(my_fls)
        for f in fls:
            if not f in ref.file.to_list() and not f'{cwd}/{f}' in ref.file.to_list():
                print(f'{f} is undocumented')
                undoc_files.append(f)
            else:
                m5out = subprocess.run(f'md5sum "{f}"', capture_output=True, text=True, shell=True)
                m5 = m5out.stdout.split()[0]
                i = list(ref.file).index(f)
                if m5 == ref.md5[i]:
                    doc_files_ok.append(f)
                else:
                    doc_files_notok.append(f)
                    print(f'{f} is documented but md5 sums do not match')
    missing_files = list(set(ref.file) - set(doc_files_ok))
    if len(missing_files) > 0:
        print(f'Some files are documented but not present.')
        missing_idx = ref.query('file in @missing_files').index.to_list()
    else:
        missing_idx = []
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
            f.writelines([f'\n{len(undoc_files)} file which are undocumented:\n'])
            f.writelines([f'{d}\n' for d in undoc_files])
            f.writelines([f'\n{len(missing_files)} are documented but not present in directory:\n'])
            f.writelines([f'{ref.subject_id[i]}, {ref.unit_id[i]}: {ref.file[i]} \n' for i in missing_idx])
        print(f'Full report saved in {report_file}')
    if remove_missing and len(missing_idx) > 0:
        print('Removing entries for missing files.')
        for i in missing_idx:
            ref = remove_entry(ref.subject_id[i], ref.unit_id[i], ref)
        ref.to_csv(args.index[0], index=False)


def add_files(urls, ft, sid, uid, fid, vals):
    n = len(urls)
    if len(ft) != n:
        raise Exception('file type list should be the same length as url list.')
    # full_id = f'{sid}__{tid}'
    file_names, m5 = get_files(urls, sid)
    new_ref = {'subject_id': [sid] * n,
               'unit_id': [uid] * n,
               'full_id': [fid] * n,
               'file': file_names,
               'url': urls,
               'date_downloaded': [str(date.today())] * n,
               'md5': m5,
               'type': ft}
    feats = set(vals.keys()) - set(req_vars())
    for f in feats:
        new_ref[f'{f}'] = [vals[f'{f}']] * n
    new_ref = pd.DataFrame(new_ref)
    return new_ref

def run_one_study(args, ref, inp_features, config):
    if args.upd:
        full_id = f'{args.subject_id}__{args.unit_id}'
        ref = update_entry(ref, full_id, inp_features)
        if len(args.url_plus)>0:
            ft = ["associated"]*len(args.url_plus)
            new_features = inp_features.keys()
            #print(new_features)
            #print(req_vars())
            other_features = (set(ref.columns) - set(req_vars())) - set(new_features)
            # print(other_features)
            my_ref = ref.query(f'full_id == "{full_id}"')
            for f in other_features:
                inp_features[f'{f}'] = my_ref[f'{f}'].iloc[0]
            new_ref = add_files(args.url_plus, ft, args.subject_id, args.unit_id, full_id, inp_features)
            ref = pd.concat([ref, new_ref], ignore_index=True)
            ref = ref.replace(np.nan, '')
    else:
        sid, uid, fid = init_entry(args, ref, inp_features, config['subject_id'], config['unit_id'])
        urls = [args.url] + args.url_plus
        ft = ["main"] + ["associated"]*len(args.url_plus)
        new_ref = add_files(urls, ft, sid, uid, fid, inp_features)
        ref = pd.concat([ref, new_ref], ignore_index=True)
        ref = ref.replace(np.nan, '')
    return ref

def validate_index(ref):
    rv = req_vars()
    if any([i not in ref.columns for i in rv]):
        raise Exception(f'Reference file is missing at least one of the required columns: subject_id, unit_id, full_id, \
                          file, date_downloaded md5, and type.')
    for v in rv:
        if any(ref[f'{v}'].isnull()):
            raise Exception(f'Reference file has missing information in {v} which is a required column.')
    #Check for duplicated files or uls
    if not len(ref.file) == len(set(ref.file)):
        raise Exception("There are duplicated files.")
    if not len(ref.url) == len(set(ref.url)):
        raise Exception("There are duplicated urls.")

if __name__ == '__main__':
    parser = get_args()
    args = parser.parse_args()
    new_ok = (not args.upd) and (not args.remove)
    ref = read_index(args.index[0], new_ok) # validate is called at the end of read_index so we can now assume index is valid
    check_args(args, ref)
    config = read_config(args.config)
    if args.remove:
        full_id = f'{args.subject_id}__{args.unit_id}'
        ref = remove_entry(args.subject_id, args.unit_id, ref)
        ref.to_csv(args.index[0], index=False)
    elif args.check:
        report_file = f'report.{"_".join(str(datetime.now()).split())}'
        check_directory(ref, dir=".", report_file=report_file, remove_missing=args.check_remove, ignore_dirs=config['ignore_dirs'])
    elif args.upd or args.url != '':
        #print(args.features)
        inp_feats = parse_features(args.features)
        ref = run_one_study(args, ref, inp_features=inp_feats, config=config)
        ref.to_csv(args.index[0], index=False)
    elif args.csv:
        rv_in = ['subject_id', 'unit_id', 'full_id', 'url', 'url_assoc']
        add_ref = read_add(args.csv, rv_in)
        adtl_features = set(add_ref.columns) - set(rv_in)
        illegal_vars = set(req_vars()) - set(rv_in)
        if any([i in illegal_vars for i in adtl_features]):
            raise Exception("Illegal features present in {args.csv}.")
        for i in range(len(add_ref)):
            my_line = add_ref.loc[i, :]
            my_args = my_line[rv_in]
            if my_args.url_assoc == '':
                my_args.url_plus = []
            else:
                my_args.url_plus = [i.strip() for i in my_args.url_assoc.split(',')]
            my_args.csv = False
            my_args.upd = my_args.url == ''
            my_args.check = False
            check_args(my_args, ref)
            inp_features = my_line[adtl_features].to_dict()
            ref = run_one_study(my_args, ref, inp_features=inp_features, config=config)
            ref.to_csv(args.index[0], index=False)
    print()
