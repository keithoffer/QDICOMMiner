import numpy as np
from yapsy.IPlugin import IPlugin
import pydicom


class MinMaxMean(IPlugin):
    def __init__(self):
        super(IPlugin, self).__init__()

    @staticmethod
    def column_headers():
        headers = "Max pixel value,Min pixel value,Mean pixel value,"
        return headers

    @staticmethod
    def generate_values(filepath: str, ds: pydicom.Dataset):
        try:
            pixel_array = ds.pixel_array
            try:
                pixel_values = pixel_array * ds.RescaleSlope + ds.RescaleIntercept
            except AttributeError:
                pixel_values = ds.pixel_array
            max_value = np.max(pixel_values)
            min_value = np.min(pixel_values)
            mean_value = np.mean(pixel_values)
            return f"{max_value},{min_value},{mean_value},"
        except (NotImplementedError, TypeError,AttributeError):
            # TODO: Perhaps we should flash a message on the case of NotImplementedError, rather than silently failing
            # Type error is different, as it means there is no pixel data
            return "NaN,NaN,NaN,"
