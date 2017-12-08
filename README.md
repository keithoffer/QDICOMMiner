QDICOMMiner 1.1.0
=================

A small cross-platform program to extract DICOM metadata from a large number of DICOM files at once. I've only tested under Linux and Windows, but macOS should work aswell. If you don't want to run the python script itself, Windows [binary releases](https://github.com/keithoffer/QDICOMMiner/releases) are available through github.

![Screenshot showing_program](Screenshots/animated_preview.gif?raw=true)

Prerequisites
-------------
- python 3.6+

Python modules

- PyQt5 (5.9 tested)
- pydicom (0.9.9 and 1.0.0a1 tested)

Both are available through pip, however the version of pydicom on pypi is [rather out of date](https://github.com/darcymason/pydicom/issues/240), so moving to the unreleased 1.0.0 branch solves atleast one crash on a file I found in the wild. You can install the 1.0.0 branch of pydicom from github: 
```
pip install https://github.com/darcymason/pydicom/archive/master.zip 
```
Usage
-----

1) Choose the input folder which will be traversed recursively for all valid DICOM files. Note the file count given is for ALL files, not just valid DICOM files.
2) Choose an output file location.
3) Choose what information you want saved from each file. Basic file information can be saved (filename, path or size), along with DICOM metadata or more advanced data extracted via custom plugins. You can either manually enter DICOM tags in the form (XXXX,XXXX) or type the description of the field if it is registered in the DICOM standard (autocomplete will help fill in entries of this form).
4) Once you have all the attributes you want listed, hit the Go! button.

You can also save and load lists of attributes with the `File -> Save Template` and `File -> Load Template` options

Plugins
-------

### Installing Plugins

Plugins go in the `Plugins` folder in the main root installation of the application.

### Writing Plugins

Plugins are handled via the `Yapsy` Python package. Each plugin needs two files:

1) plugin.py: The main logic of your plugin
2) plugin.yapsy-plugin: Metadata about your plugin. More information about the format of this file can be found in the [Yapsy documentation](http://yapsy.readthedocs.io/en/latest/PluginManager.html#plugin-info-file-format)

### Plugin API

Custom plugins can be written and dropped in the `Plugins` folder. Plugins should implement two static methods:

#### column_headers
Takes no arguments, and returns a list of column headers to go at the top of the csv file related to this plugin. This should be a single strong, column headers separated with commas and terminated with a comma.

e.g. `return "Max pixel value,Min pixel value,Mean pixel value,"`

#### generate_values(filepath,ds)

Has two arguments:

- filepath: string of the full filepath to the file (including filename) incase raw work needs to be done on the file
- ds: pydicom dataset containing the metadata and pixel values from the file.

Should return the values for the csv as a string, with a comma at the end.

e.g. `return f"{max_value},{min_value},{mean_value},"`


License
-------

QDICOMMiner is copyrighted free software made available under the terms of the GPLv3

Copyright: (C) 2017 by Keith Offer. All Rights Reserved.