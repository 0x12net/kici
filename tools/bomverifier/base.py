from collections import OrderedDict

from abc import ABC, abstractmethod

from bomverifier.exceptions import ArgsException

class BaseProvider(ABC):
    """Base class for a data provider"""

    # BOM column holding this provider's part number (sku). Overridden in subclasses.
    sku_column = None

    @property
    @abstractmethod
    def required_keys(self):
        """Keys used to update the data"""
        pass

    @abstractmethod
    def validate(self):
        """Validate the input data"""
        pass

    @abstractmethod
    def update_with_data(self):
        """Fetch data from the provider"""
        pass

    def _update(self, data):
        """Update the row with new data"""
        item = OrderedDict(zip(self.required_keys, data))
        self.item.update(item)

    def fill_with_empty_values(self):
        """Fill the row with empty values"""
        data = ['' for _ in range(len(self.required_keys))]
        self._update(data)

    def _rewrite(self, sku, mpn):
        """Overwrite a BOM column with fresh data from the provider.

        The mode is set by `self.rewrite`:
          'sku' -> write the found sku into the provider's part-number column (sku_column)
          'mpn' -> write the found mpn into the 'mpn' column
        """
        if not getattr(self, 'rewrite', None):
            return
        targets = {'sku': (self.sku_column, sku), 'mpn': ('mpn', mpn)}
        column, value = targets[self.rewrite]
        if column not in self.item:
            raise ArgsException('No column to rewrite')
        self.item[column] = value
