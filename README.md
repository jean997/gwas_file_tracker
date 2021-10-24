## Introduction

This repository contains a python utility for documenting large datasets that are 
downloaded from the internet. It was originally developed to manage collections of 
GWAS summary statistics and other products of scientific studies but should be 
flexible enough to use for other applications. 


## Overview

The intention of this utility is that it will be used to simultaneously download files and
document them in a master reference which documents the contents of its directory. 
Data are organized into subjects and units. Each subject may contain multiple units. 
Each unit contains one "main" file and any number of associated files. When `track_dir` is 
used to add files to the directory, files will be downloaded and an entry added to the reference
file containing the url, date of download, filename, and md5 checksum. Optionally, additional 
features can be stored in the reference file such as pmid for the accompanying publication, 
trait or topic, etc.

## Usage

`track_dir` can be used in four modes:

1. Add files for a single new unit
2. Update feature information for an existing unit and/or add associated files for an existing unit.
3. Add new units or update existing units for many units using information stored in a .csv file.
4. Check that the contents of the directory are documented in the reference file.


### 1. Add files for a single new unit

The minimum information to add an entry is a url and a name of a reference file.
```angular2html
python track_dir.py my_reference.csv \
      --url https://github.com/jean997/gwas_file_tracker/blame/main/test_files/one.txt
```

This will create a random subject and unit id, download the file and create a reference file called
my_reference.csv containing the relevant information.  Data are always saved in a directory 
corresponding to the subject ID.

#### Features
Features are additional information stored in the reference file. Features can be supplied with the
`--features` argument. The `--features` argument takes a white space separated list with elements of the
form feature:value. If value contains whitespace, surround the entire entry in quotes. Feature
names may not contain whitespace.

```angular2html
python track_dir.py my_reference.csv \
--url https://github.com/jean997/gwas_file_tracker/blame/main/test_files/two.txt \
--features author:Jean "trait:example trait two" sample_size:1000
```

```angular2html
cat my_reference.csv
```
Note that additional columns author,trait, and sample_size have been added to the reference. 

#### Subject and Unit IDs

If we wish to have more informative subject and unit IDs there are two options: 
1. Supply them with --subject-id and --unit-id
2. Base subject and unit IDs on features using a configuration file. The configuration 
file has a YAML format and contains lists of features that will be used to construct each ID.
For example: 
```angular2html
---
subject_id: 
        - author
        - year
        - pmid
unit_id: 
        - trait
```
If these features are present, then the subject ID will be formed as author_year_pmid and the 
unit id will be trait. Spaces are replaced by - when forming IDs in this way. If the above text is
saved to config.yaml, then we can run the following

```angular2html
python track_dir.py my_reference.csv \
--url https://github.com/jean997/gwas_file_tracker/blame/main/test_files/three.txt \
--config config.yaml \
--features author:Jean "trait:example trait three" year:2021 pmid:0
```

```angular2html
cat my_reference.csv
```

This has created a new unit with subject ID `Jean_2021_0` and unit id `example-trait-three`. 

### Updating an Entry
Units can be updated to add new associated files or add or change feature information. 
Note that subject and unit IDs are fixed and cannot be changed later, even if the feature
information they were based on changes.

To update an entry, you must supply subject and unit id. 

```angular2html
python track_dir.py my_reference.csv \
--update-entry \
--subject-id Jean_2021_0 \
--unit-id example-trait-three \
--url-assoc https://github.com/jean997/gwas_file_tracker/blame/main/test_files/four.txt \
--features "author:Tooth Fairy" "note:an example"
```

```angular2html
cat my_reference.csv
```

Note that an additional line has been added for the associated file and features have been
updated for all the files in the unit.


### Adding and updating units from a spreadsheet


### Checking the directory



Using the utility requires the `wget` python package which can be installed with 

```
pip install wget
```

To do: 
+ Add directory checker to check consistency of directory contents and index file. (done)
+ Add `--from-file` option for get\_stats (done)
+ Make file features more flexible (in progres)
