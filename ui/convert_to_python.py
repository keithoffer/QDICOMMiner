#!/usr/bin/env python3
# Converts all files ending in .ui to python files via pyuic5
import os
files = [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.ui')]
for file in files:
    os.system('pyuic5 '+ file + ' > ' + file[0:-3] + '.py')
