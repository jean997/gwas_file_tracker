## Introduction

This repository contains a python utility for documenting large datasets that are 
downloaded from the internet. It was originally developed to manage collections of 
GWAS summary statistics and other products of scientific studies but should be 
flexible enough to use for other applications. 


## Installation

To install, simply clone this repository to the directory you would like to track.
The only necessary files is `track_downloads.py`. `get_stats.py` is an older version
in which all of the features are hardcoded. Files `config.yaml` and `new_studies.csv`
are used in the examples below. You may want to keep `config.yaml` or a 
modified version of it while `new_studies.csv` is purely exemplary.

Detailed installation insructions:
```angular2html
git clone https://github.com/jean997/gwas_file_tracker.git
```
will create a directory called `gwas_file_tracker`. You can then copy `gwas_file_tracker/track_downloads.py`
and `gwas_file_tracker/config.yaml` to your working directory. 
If you would like to run examples in this readme, also copy `new_studies.csv`.


Using the utility requires the `wget` and `pyyaml` python packages 
which can be installed with 

```
pip install wget
pip install pyyaml
```


## Overview

The intention of this utility is that it will be used to simultaneously download files and
document them in a master reference file.
The reference file will contain one line for each file 
recording the url, date of download, filename, and md5 checksum. Optionally, additional
features can be stored in the reference file such as pmid for the accompanying publication, 
trait or topic, sample size, etc.

Data are organized in two levels. The first level "subject" determines the directory sub-structure -- 
all files belonging to the same subject will be kept in a directory named for the subject ID.
For my purposes, I like to have subject correspond to the study or paper that data are from.
The second level "unit" corresponds to the major data unit (in the case of 
GWAS summary stiatistcs, usually trait). Each unit can contain one "main" file and any number 
of "associated" files such as readmes or index files.
Each subject can contain any number of units.

## Usage

To view function help:
```angular2html
python track_downloads.py -h
```

`track_downloads` can be used in four modes:

1. Download and document files for a single new unit
2. Update feature information for an existing unit and/or add associated files for an existing unit.
3. Add new units or update existing units in bulk using information stored in a .csv file.
4. Check that the contents of the directory and the reference file are in agreement.

The following examples use tiny files and made up feature annotations. There is an example using 
GWAS summary statistics at the end.

### 1. Add files for a single new unit

The minimum information to add an entry is a url and a name of a reference file.
```angular2html
python track_downloads.py my_reference.csv \
      --url https://github.com/jean997/gwas_file_tracker/blame/main/test_files/one.txt
```

Since no other information is supplied, the program will create a random subject and unit id. 
It will then download the file from the provided URL, create a reference file called
`my_reference.csv` if it does not already exist, 
and store information the downloaded file.

If the reference file does not exist when you run the utility, it will be 
created. If it does exist, some basic checks will be performed. The reference
will then be copied to a backup which can be used in case something goes wrong. 
Backups need not be kept long-term.

#### Features

Features are additional information stored in the reference file. Features can be supplied with the
`--features` argument. The `--features` argument takes a white space separated list with elements of the
form feature:value. If value contains whitespace, surround the entire entry in quotes. Feature
names may not contain whitespace.

Here we add features for author, trait and sample_size to a new unit: 

```angular2html
python track_downloads.py my_reference.csv \
--url https://github.com/jean997/gwas_file_tracker/blame/main/test_files/two.txt \
--features author:Sunday "trait:example trait two" sample_size:1000
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
Using this config file, if these features are present, 
then the subject ID will be formed as author_year_pmid and the 
unit id will be trait. Spaces are replaced by `-` when forming IDs in this way. If the above text is
saved to config.yaml, then we can run the following:

```angular2html
python track_downloads.py my_reference.csv \
--url https://github.com/jean997/gwas_file_tracker/blame/main/test_files/three.txt \
--config config.yaml \
--features author:Jean "trait:example trait three" year:2021 pmid:0
```

```angular2html
cat my_reference.csv
```

This has created a new unit with subject ID `Jean_2021_0` and unit id `example-trait-three`. 
Note that some of the features we just added (author and trait) already existed as columns in the
reference because we added them previously but year and pmid are new. When new features are added,
the value of the new feature for all existing units is set to missing in the reference file.
This can be changed later using `--update-entry`.

### Updating and adding files to a unit
Units can be updated to add new associated files, or add or change feature information. 
Note that subject and unit IDs are fixed and cannot be changed later, even if the feature
information they were based on changes. The main file for each unit is also fixed. Units 
can only have one file designated as main.

To update an entry, you must supply subject and unit id. 

```angular2html
python track_downloads.py my_reference.csv \
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
Even though we changed the author name, the subject ID is fixed.


### Adding and updating units from a spreadsheet

Data can be added in bulk from a spreadsheet. The spreadsheet at a minimum should contain
the `url` column. It may also contain columns `url_assoc` for a comma separated list of urls
for associated files, `study_id`, `unit_id` and columns corresponding to any features. 

If the url column is left blank, the program will assume it should update features for an 
existing entry. You will get an error message if you try to add a new main file for 
an existing unit.

The file `new_studies.csv` contains three lines. The first two correspond to new units to be added
so they have a non-missing value in the url column. The unit added on the second line has two 
associated files. The third line is updating information for `example-trait-three` again. 

Using the file `new_studies.csv`

```angular2html
python track_downloads.py my_reference.csv \
--from-file new_studies.csv \
--config config.yaml
```



### Checking the directory

Finally, the utility can check the contents of the directory against the reference file and write a report

```angular2html
python track_downloads.py my_reference.csv --check-directory
```

The `--check-directory` command can be combined with other commands. The result of this command
will be a report file named `report.<datetime>` and some summary output to the screen.
This command will ignore files in the top level directory.


## Examples with GWAS Summary Statistics

Below are some examples which will download and track GWAS summary statistics from various locations.

From IEU Open GWAS Project:
```angular2html
python track_downloads gwas_reference.csv \
--url https://gwas.mrcieu.ac.uk/files/ieu-b-40/ieu-b-40.vcf.gz \
--url-assoc https://gwas.mrcieu.ac.uk/files/ieu-b-40/ieu-b-40.vcf.gz.tbi \
--config config.yaml \
--features: author:GIANT pmid:30124842 year:2018 "note: European ancestry" sample_size:681275 trait:BMI
```
Note that for IEU data, you need both the `vcv.gz` file and the index `.tbi` file.


From the GWAS catalog:

```angular2html
python track_downloads gwas_reference.csv \
--url http://ftp.ebi.ac.uk/pub/databases/gwas/summary_statistics/GCST007001-GCST008000/GCST007557/BW3_EUR_summary_stats.txt.gz \
--url-assoc http://ftp.ebi.ac.uk/pub/databases/gwas/summary_statistics/GCST007001-GCST008000/GCST007557/Horikoshi_27680694_readme_file.docx \
--config config.yaml \
--features: author:Horikoshi pmid:27680694 year:2016 "note: European ancestry" "trait:birth weight"
```

Here we downloaded the readme as an associated file.


## Notes for Jean
To do: 
+ Add directory checker to check consistency of directory contents and index file. (done)
+ Add `--from-file` option for get\_stats (done)
+ Make file features more flexible (done)
+ Add directory name prefix (done)
