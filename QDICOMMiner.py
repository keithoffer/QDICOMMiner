#!/usr/bin/env python3
"""
    QDICOMMiner - a small program to export DICOM metadata from lots of files at once
    Copyright 2017 Keith Offer

    QDICOMMiner is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License version 3 as published by
    the Free Software Foundation.

    QDICOMMiner is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with QDICOMMiner.  If not, see <http://www.gnu.org/licenses/>.
"""
# Python standard library is PSF licenced
import os
import sys
import re
import json
from enum import Enum
# pydicom is MIT licenced
try:
    import dicom as pydicom
except ImportError:
    import pydicom
import pydicom._dicom_dict as dicom_dict  # TODO: Is this a good idea? Should I just include my own copy?
# PyQt is GPL v3 licenced
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QPushButton, QCompleter, QLineEdit, QHBoxLayout, \
    QLabel, QAbstractItemView, QListWidgetItem, QComboBox
from PyQt5.QtCore import QSettings, Qt, QThread, QStringListModel, QObject, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices
# Files from this project
from ui.mainWindow import Ui_MainWindow

# Regex to match DICOM tags (i.e. the form (XXXX,XXXX) where X are case insensitive hex digits)
# In this case, there are also match groups around each set of four hex digits
dicom_tag_regex = r'\(((?i)[\da-f]{4}),((?i)[\da-f]{4})\)'
__version__ = '1.0.1'

class AttributeOptions(Enum):
    DICOM_TAG = 'Dicom Tag'
    FILE_INFORMATION = 'File Information'

class FileOptions(Enum):
    FILE_SIZE = 'File Size (MB)'
    FILE_NAME = 'File Name'
    FILE_PATH = 'File Path'

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setWindowTitle('QDICOMMiner ' + __version__)

        # TODO: Find a better way of stopping the selection of list items. This only sortof works
        self.ui.listWidget.setSelectionMode(QAbstractItemView.NoSelection)

        # Read the settings from the settings.ini file
        system_location = os.path.dirname(os.path.realpath(__file__))
        QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, system_location)
        self.settings = QSettings("settings.ini", QSettings.IniFormat)
        if os.path.exists(system_location + "/settings.ini"):
            print("Loading settings from " + system_location + "/settings.ini")

        # Set the last used output file and analyse folder locations
        output_file = self.settings.value('main/lastOutputFile')
        if output_file is None:
            output_file = 'data.csv'
        if not os.path.isabs(output_file):
            abs_output_location = os.path.join(system_location, output_file)
            self.ui.labelOutputFile.setText(abs_output_location)
        else:
            self.ui.labelOutputFile.setText(output_file)

        folder_to_analyse = self.settings.value('main/lastAnalyseFolder')
        if folder_to_analyse is None:
            folder_to_analyse = ''
        if not os.path.isabs(folder_to_analyse):
            abs_folder_to_analyse = os.path.join(system_location, folder_to_analyse)
            self.ui.labelFolderToAnalysePath.setText(abs_folder_to_analyse)
        else:
            self.ui.labelFolderToAnalysePath.setText(folder_to_analyse)

        self.ui.labelFolderToAnalysePath.clicked.connect(
            lambda: self.open_folder_in_explorer(self.ui.labelFolderToAnalysePath.text()))
        self.ui.labelOutputFile.clicked.connect(
            lambda: self.open_folder_in_explorer(self.ui.labelOutputFile.text()))

        # Setup a dictionary of key DICOM description and value the DICOM tag
        names = []
        self.DICOM_dic = {}
        for key in dicom_dict.DicomDictionary:
            names.append(dicom_dict.DicomDictionary[key][2])
            self.DICOM_dic[dicom_dict.DicomDictionary[key][2]] = key

        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.model = QStringListModel()
        self.model.setStringList(names)
        self.completer.setModel(self.model)

        self.ui.pushButtonAddListWidget.clicked.connect(self.add_new_list_widget)

        self.ui.pushButtonBrowseFolderToAnalysePath.clicked.connect(self.browse_for_input_folder)
        self.ui.pushButtonBrowseOutputFilePath.clicked.connect(self.browse_for_output_file)
        self.ui.pushButtonDoAnalysis.clicked.connect(self.do_analysis)

        self.count_num_of_files_thread = CountFilesThread()
        self.count_num_of_files_thread.num_of_files.connect(self.update_number_of_files)
        self.count_file_number.connect(self.count_num_of_files_thread.count)
        self.count_file_number.emit(self.ui.labelFolderToAnalysePath.text())  # Using a signal to keep thread safety

        self.ui.progressBar.setFormat(' %v/%m (%p%)')
        self.ui.progressBar.hide()

        self.ui.actionSave_Template.triggered.connect(self.save_template)
        self.ui.actionLoad_Template.triggered.connect(self.load_template)
        self.ui.actionAbout.triggered.connect(self.open_about_window)

        self.analyse_and_output_data_thread = AnalyseAndOutputDataThread()

        self.show()

    @staticmethod
    def open_folder_in_explorer(location):
        if os.path.isfile(location):
            folder_location = os.path.dirname(location)
        else:
            folder_location = location
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_location))

    def save_template(self):
        dic = {'DICOM_tag': [], 'File_information': []}

        for index in range(self.ui.listWidget.count()):
            custom_widget = self.ui.listWidget.itemWidget(self.ui.listWidget.item(index))
            if custom_widget.comboBoxAttributeChoice.currentText() == AttributeOptions.DICOM_TAG.value:
                text = custom_widget.lineEdit.text()
                dic['DICOM_tag'].append(text)
            else:
                text = custom_widget.comboBoxFileOption.currentText()
                dic['File_information'].append(text)

        filepath = QFileDialog.getSaveFileName(self, 'Save template file', '.', '(*.json)')[0]
        if filepath != '':
            if not filepath.endswith('.json'):
                filepath += '.json'
            with open(filepath, 'w') as f:
                json.dump(dic, f)

    def load_template(self):
        filepath = QFileDialog.getOpenFileName(self, 'Load template file', '.', '*.json')[0]
        if filepath != '':
            with open(filepath, 'r') as f:
                try:
                    dic = json.load(f)
                except json.JSONDecodeError:
                    msg_box = QMessageBox()
                    msg_box.setWindowTitle("Error")
                    msg_box.setText('Failed to open ' + filepath + ' (not a valid JSON file)')
                    msg_box.setIcon(QMessageBox.Critical)
                    msg_box.exec()
                    return
                self.ui.listWidget.clear()
                try:
                    for tag in dic['DICOM_tag']:
                        self.add_new_list_widget(default_text=tag)
                    for file_option in dic['File_information']:
                        self.add_new_list_widget(attribute_type=AttributeOptions.FILE_INFORMATION,file_information=file_option)
                except KeyError:
                    msg_box = QMessageBox()
                    msg_box.setWindowTitle("Error")
                    msg_box.setText(
                        'Failed to apply template file ' + filepath + ' (Missing information in template file)')
                    msg_box.setIcon(QMessageBox.Critical)
                    msg_box.exec()
                    return

    @staticmethod
    def open_about_window():
        msg_box = QMessageBox()
        msg_box.setWindowTitle("About")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText("QDICOMMiner version " + __version__ +
                        "<br> Written by Keith Offer" +
                        "<br> Relies heavily on the <a href='http://www.pydicom.org/'>pydicom</a> library")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec()

    def update_number_of_files(self, num):
        self.ui.labelNumberOfFiles.setText(str(num) + ' files')
        self.ui.progressBar.setMaximum(num)

    # The checked variable is emitted from the signal, but we don't use it here
    def add_new_list_widget(self, checked=False, default_text='',attribute_type=AttributeOptions.DICOM_TAG,file_information=None):
        new_list_widget_item = QListWidgetItem()
        custom_widget = CustomListWidget()
        new_list_widget_item.setSizeHint(custom_widget.sizeHint())
        custom_widget.lineEdit.setCompleter(self.completer)
        custom_widget.lineEdit.textChanged.connect(self.line_edit_text_changed)
        custom_widget.pushButton.clicked.connect(lambda: self.remove_widget_from_list(new_list_widget_item))
        if attribute_type == AttributeOptions.DICOM_TAG:
            custom_widget.lineEdit.setText(default_text)
        else:
            # TODO: Should I throw an exception / error message if the index isn't >= 0?
            file_info_index = custom_widget.comboBoxFileOption.findText(file_information)
            if file_info_index >= 0:
                custom_widget.comboBoxFileOption.setCurrentIndex(file_info_index)
                custom_widget.comboBoxFileOption.setVisible(True)
                custom_widget.lineEdit.setVisible(False)

        attribute_index = custom_widget.comboBoxAttributeChoice.findText(attribute_type.value)
        if attribute_index >= 0:
            custom_widget.comboBoxAttributeChoice.setCurrentIndex(attribute_index)

        self.ui.listWidget.addItem(new_list_widget_item)
        self.ui.listWidget.setItemWidget(new_list_widget_item, custom_widget)

    def line_edit_text_changed(self, new_string):
        sending_line_edit = self.sender()
        if new_string != '' and (new_string in self.DICOM_dic or re.match(dicom_tag_regex, new_string)):
            sending_line_edit.setStyleSheet("QLineEdit { background: rgb(0, 255, 0); }")
        else:
            sending_line_edit.setStyleSheet("QLineEdit { background: rgb(255, 0, 0); }")

    def remove_widget_from_list(self, list_widget_item):
        self.ui.listWidget.takeItem(self.ui.listWidget.row(list_widget_item))

    def browse_for_input_folder(self):
        starting_location = self.settings.value('main/lastAnalyseFolder')
        if starting_location is None:
            starting_location = '.'
        filepath = QFileDialog.getExistingDirectory(self, 'Input directory', starting_location)
        if filepath != '':
            self.ui.labelFolderToAnalysePath.setText(filepath)
            self.count_file_number.emit(filepath)
            self.settings.setValue('main/lastAnalyseFolder', filepath)

    def browse_for_output_file(self):
        starting_location = self.settings.value('main/lastOutputFile')
        if starting_location is None:
            starting_location = '.'
        # This looks a bit strange, but filenames are the first return value of this function
        # so we need the [0] on the end to grab what we need
        filepath = QFileDialog.getSaveFileName(self, 'Output file', starting_location, '(*.csv)')[0]
        if filepath != '':
            if not filepath.endswith('.csv'):
                filepath += '.csv'
            self.ui.labelOutputFile.setText(filepath)
            self.settings.setValue('main/lastOutputFile', filepath)

    def do_analysis(self):
        if os.path.exists(self.ui.labelOutputFile.text()):
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setText("The output file " + self.ui.labelOutputFile.text() + " already exists. Are you sure you want to overwrite it?")
            overwrite_button = QPushButton('Overwrite')
            msg_box.addButton(overwrite_button, QMessageBox.YesRole)
            msg_box.addButton(QPushButton('Cancel'), QMessageBox.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() != overwrite_button:
                return
        header_DICOM = ''
        header_file_info = ''
        dicom_tags = []
        file_attributes = []
        for index in range(self.ui.listWidget.count()):
            custom_widget = self.ui.listWidget.itemWidget(self.ui.listWidget.item(index))
            if custom_widget.comboBoxAttributeChoice.currentText() == AttributeOptions.FILE_INFORMATION.value:
                # Handle file attributes (e.g. path, size etc)
                header_file_info += custom_widget.comboBoxFileOption.currentText() + ','
                file_attributes.append(custom_widget.comboBoxFileOption.currentText())
            else:
                # Handle DICOM tags
                text = custom_widget.lineEdit.text()
                try:
                    if text == '':
                        # We have to manually raise this as searching for '' won't throw an exception but won't work
                        raise KeyError
                    if re.match(dicom_tag_regex, text):
                        search_results = re.search(dicom_tag_regex, text)
                        # Note that group 0 is the whole match that we don't want
                        dicom_tags.append((search_results.group(1), search_results.group(2)))
                    else:
                        dicom_tags.append(self.DICOM_dic[custom_widget.lineEdit.text()])
                except KeyError:
                    msg_box = QMessageBox()
                    msg_box.setWindowTitle("Error")
                    msg_box.setText('"' + text + '" is not a valid attribute')
                    msg_box.setIcon(QMessageBox.Critical)
                    msg_box.exec()
                    return
                header_DICOM += text.replace(',', ' ') + ','
            # Handle file attributes

        csv_header = (header_file_info + header_DICOM)[0:-1]  # Remove the last comma

        self.ui.progressBar.show()
        self.analyse_and_output_data_thread.current_file.connect(lambda num: self.ui.progressBar.setValue(num))
        self.create_csv.connect(self.analyse_and_output_data_thread.run)
        self.analyse_and_output_data_thread.finished.connect(self.csv_making_finished)
        self.create_csv.emit(self.ui.labelOutputFile.text(), self.ui.labelFolderToAnalysePath.text(), csv_header, dicom_tags,file_attributes)

    def csv_making_finished(self):
        self.ui.progressBar.hide()

    create_csv = pyqtSignal(str, str, str, list,list)
    count_file_number = pyqtSignal(str)

# This class is the main work thread, which iterates recusviley over all the files and
# writes all the file information / DICOM data to the output csv
class AnalyseAndOutputDataThread(QObject):
    def __init__(self):
        super(AnalyseAndOutputDataThread, self).__init__()

        self.worker_thread = QThread()
        self.moveToThread(self.worker_thread)
        self.worker_thread.start()

    def run(self, output_file, folder_to_analyse, header, dicom_tags, file_attributes):
        with open(output_file, 'w') as f:
            f.write(header + '\n')

            count = 0
            for dirpath, _, filenames in os.walk(folder_to_analyse):
                for filename in filenames:
                    output_line = ''
                    full_path = os.path.join(dirpath, filename)
                    try:
                        ds = pydicom.read_file(full_path)
                    except pydicom.errors.InvalidDicomError:
                        continue # If it isn't a valid DICOM file, we'll just skip over it

                    # List the file attributes
                    for attribute in file_attributes:
                        try:
                            if attribute == FileOptions.FILE_NAME.value:
                                output_line += filename + ','
                            elif attribute == FileOptions.FILE_PATH.value:
                                output_line += full_path + ','
                            elif attribute == FileOptions.FILE_SIZE.value:
                                output_line += str(round(os.path.getsize(full_path)/(1000*1000),3)) + ','
                        except (FileNotFoundError, OSError, PermissionError):
                            pass
                    # Get the data from the tags
                    try:
                        for tag in dicom_tags:
                            output_line += get_dicom_value_from_tag(ds, tag) + ','
                        output_line = output_line[0:-1]  # Remove the last comma
                        f.write(output_line + '\n')
                    except (FileNotFoundError, OSError, PermissionError):
                        pass
                    except OSError as e:
                        if e.args[0] != 6:  # No such device or address
                            raise
                    count += 1
                    self.current_file.emit(count)
        self.finished.emit()

    current_file = pyqtSignal(int)
    finished = pyqtSignal()

# Simple worker thread for counting the number of files recursively in a folder and subfolders
class CountFilesThread(QObject):
    def __init__(self):
        super(CountFilesThread, self).__init__()

        self.worker_thread = QThread()
        self.moveToThread(self.worker_thread)
        self.worker_thread.start()

    # TODO: handle permissions issues gracefully, honestly not sure how it does it at the moment
    # From my testing it seems to handle it okay, but I'm not sure
    def count(self, path):
        count = 0
        for _, _, filenames in os.walk(path):
            for _ in filenames:
                count += 1
            self.num_of_files.emit(count)

    num_of_files = pyqtSignal(int)


class CustomListWidget(QtWidgets.QWidget):
    def __init__(self):
        super(CustomListWidget, self).__init__()

        self.layout = QHBoxLayout()
        self.lineEdit = QLineEdit()
        self.comboBoxAttributeChoice = QComboBox()
        self.comboBoxFileOption = QComboBox()
        self.comboBoxFileOption.addItems([option.value for option in FileOptions])
        self.comboBoxFileOption.setVisible(False)
        self.comboBoxAttributeChoice.addItems([attribute.value for attribute in AttributeOptions])
        self.comboBoxAttributeChoice.activated[str].connect(self.change_item_type)
        self.lineEdit.setStyleSheet("QLineEdit { background: rgb(255, 0, 0); }")
        self.pushButton = QPushButton("Delete")
        self.pushButton.setMaximumWidth(100)
        self.pushButton.setMinimumWidth(100)
        self.comboBoxAttributeChoice.setMinimumWidth(150)
        self.comboBoxAttributeChoice.setMaximumWidth(150)
        self.layout.addWidget(self.comboBoxAttributeChoice)
        self.layout.addWidget(self.comboBoxFileOption)
        self.layout.addWidget(self.lineEdit)
        self.layout.addWidget(self.pushButton)
        self.setLayout(self.layout)

    def change_item_type(self,selection):
        if selection == AttributeOptions.DICOM_TAG.value:
            self.comboBoxFileOption.setVisible(False)
            self.lineEdit.setVisible(True)
        else:
            self.comboBoxFileOption.setVisible(True)
            self.lineEdit.setVisible(False)
            self.lineEdit.setText('')


class ClickableQLabel(QLabel):
    def __init__(self, parent=None):
        super(ClickableQLabel, self).__init__(parent)

    def mousePressEvent(self, QMouseEvent):
        self.clicked.emit()

    clicked = pyqtSignal()


# Small helper function to insure we don't crash if the file dosen't have the required attribute
def get_dicom_value_from_tag(ds, tag):
    try:
        return str(ds[tag].value)
    except KeyError:
        return ''


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    GUI = MainWindow()
    sys.exit(app.exec())
