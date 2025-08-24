# -*- coding: utf-8 -*-
from collections import namedtuple

Button = namedtuple('Button', ['text', 'data'])


class Paginator:
    _keyboard_before = None
    _keyboard = None
    _keyboard_after = None

    first_page_label = '« {}'
    previous_page_label = '‹ {}'
    next_page_label = '{} ›'
    last_page_label = '{} »'
    current_page_label = '·{}·'

    def __init__(self, page_count, current_page=1, data_pattern='{page}'):
        self._keyboard_before = list()
        self._keyboard_after = list()

        if current_page is None or current_page < 1:
            current_page = 1
        if current_page > page_count:
            current_page = page_count
        self.current_page = current_page

        self.page_count = page_count

        self.data_pattern = data_pattern

    @staticmethod
    def _format(text, data):
        return Button(text, data)

    def _build(self):
        row = dict()

        if self.page_count == 1:
            self._keyboard = list()
            return

        elif self.page_count <= 5:
            for page in range(1, self.page_count + 1):
                row[page] = page

        else:
            row = self._build_for_multi_pages()

        row[self.current_page] = self.current_page_label.format(self.current_page)

        self._keyboard = self._to_button_array(row)

    def _build_for_multi_pages(self):
        if self.current_page <= 3:
            return self._build_start_row()

        elif self.current_page > self.page_count - 3:
            return self._build_finish_row()

        else:
            return self._build_middle_row()

    def _build_start_row(self):
        row = dict()

        for page in range(1, 4):
            row[page] = page

        row[4] = self.next_page_label.format(4)
        row[self.page_count] = self.last_page_label.format(self.page_count)

        return row

    def _build_finish_row(self):
        row = dict()

        row[1] = self.first_page_label.format(1)
        row[self.page_count - 3] = self.previous_page_label.format(self.page_count - 3)

        for page in range(self.page_count - 2, self.page_count + 1):
            row[page] = page

        return row

    def _build_middle_row(self):
        row = dict()

        row[1] = self.first_page_label.format(1)
        row[self.current_page - 1] = self.previous_page_label.format(self.current_page - 1)
        row[self.current_page] = self.current_page
        row[self.current_page + 1] = self.next_page_label.format(self.current_page + 1)
        row[self.page_count] = self.last_page_label.format(self.page_count)

        return row

    def _to_button_array(self, row):
        keyboard = list()

        keys = list(row.keys())
        keys.sort()

        for key in keys:
            keyboard.append(
                self._format(
                    text=str(row[key]),
                    data=self.data_pattern.format(page=key)
                )
            )

        return keyboard

    def keyboard(self):
        if self._keyboard is None:
            self._build()

        return self._keyboard

    def create(self):
        """
        Useful when you want to customize buttons.
        For example, json needs to be returned.
        """
        return self._markup()

    def _markup(self):
        """InlineKeyboard_markup"""
        keyboards = list()

        keyboards.extend(self._keyboard_before)
        
        keyboards.append(self.keyboard())
        keyboards.extend(self._keyboard_after)

        keyboards = list(filter(bool, keyboards))
        
        if not keyboards:
            return None

        return keyboards

    def add_before(self, *buttons):
        """
        Add buttons as line above pagination buttons.

        Args:
            inline_buttons (:object:`iterable`): List of object with attributes `text` and `data`.

        Returns:
            None
        """
        self._keyboard_before.append([button for button in buttons])
        
    def add_after(self, *buttons):
        """
        Add buttons as line under pagination buttons.

        Args:
            inline_buttons (:object:`iterable`): List of object with attributes 'text' and 'data'.

        Returns:
            None
        """
        self._keyboard_after.append([button for button in buttons])


from telethon import Button


class TelethonPaginator(Paginator):
    def _format(self, text, data):
        return Button.inline(text, data)