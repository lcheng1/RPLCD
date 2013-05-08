# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import time
from collections import namedtuple

import RPIO


# Commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# Flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# Flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# Flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00

# Flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# Flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# Flags for RS pin modes
RS_INSTRUCTION = 0x00
RS_DATA = 0x01


# Namedtuples
PinConfig = namedtuple('PinConfig', 'rs rw e d0 d1 d2 d3 d4 d5 d6 d7 mode')
LCDConfig = namedtuple('LCDConfig', 'rows cols dotsize')


def msleep(milliseconds):
    """Sleep the specified amount of milliseconds."""
    time.sleep(milliseconds / 1000.0)


def usleep(microseconds):
    """Sleep the specified amount of microseconds."""
    time.sleep(microseconds / 1000000.0)


class CharLCD(object):

    # Init, setup, teardown

    def __init__(self, pin_rs=15, pin_rw=18, pin_e=16, pins_data=[21, 22, 23, 24],
                       numbering_mode=RPIO.BOARD):
        """
        Character LCD controller.

        The default pin numbers are based on the BOARD numbering scheme (1-26).

        You can save 1 pin by not using RW. Set ``pin_rw`` to ``None`` if you
        want this.

        Args:
            pin_rs:
                Pin for register select (RS). Default: 15.
            pin_rw:
                Pin for selecting read or write mode (R/W). Set this to
                ``None`` for read only mode. Default: 18.
            pin_e:
                Pin to start data read or write (E). Default: 16.
            pins_data:
                List of data bus pins in 8 bit mode (DB0-DB7) or in 8 bit mode
                (DB4-DB7) in ascending order. Default: [21, 22, 23, 24].
            numbering_mode:
                Which scheme to use for numbering the GPIO pins.
                Default: RPIO.BOARD (1-26).

        Returns:
            A :class:`CharLCD` instance.

        """
        # Set attributes
        self.numbering_mode = numbering_mode
        if len(pins_data) == 4:  # 4 bit mode
            self.display_mode = LCD_4BITMODE
            block1 = [None] * 4
        elif len(pins_data) == 8:  # 8 bit mode
            self.display_mode = LCD_8BITMODE
            block1 = pins_data[:4]
        else:
            raise ValueError('There should be exactly 4 or 8 data pins.')
        block2 = pins_data[-4:]
        self.pins = PinConfig(rs=pin_rs, rw=pin_rw, e=pin_e,
                              d0=block1[0], d1=block1[1], d2=block1[2], d3=block1[3],
                              d4=block2[0], d5=block2[1], d6=block2[2], d7=block2[3],
                              mode=numbering_mode)

        # Setup GPIO
        RPIO.setmode(self.numbering_mode)
        for pin in filter(None, self.pins)[:-1]:
            RPIO.setup(pin, RPIO.OUT)

    def setup(self, rows=4, cols=20, dotsize=8):
        """Initialize display with the specified configuration.

        Args:
            rows:
                Number of display rows (usually 1, 2 or 4). Default: 4.
            cols:
                Number of columns per row (usually 16 or 20). Default 20.
            dotsize:
                Some 1 line displays allow a font height of 10px.
                Allowed: 8 or 10. Default: 8.

        """
        # Set attributes
        self.lcd = LCDConfig(rows=rows, cols=cols, dotsize=dotsize)
        displayfunction = self.display_mode | LCD_1LINE | LCD_5x8DOTS

        # LCD only uses two lines on 4 row displays
        if rows == 4:
            displayfunction |= LCD_2LINE

        # For some 1 line displays you can select a 10px font.
        assert dotsize in [8, 10], 'The ``dotsize`` argument should be either 8 or 10.'
        if dotsize == 10:
            displayfunction |= LCD_5x10DOTS

        # Initialization
        msleep(50)
        RPIO.output(self.pins.rs, 0)
        RPIO.output(self.pins.e, 0)
        if self.pins.rw is not None:
            RPIO.output(self.pins.rw, 0)

        # Choose 4 or 8 bit mode
        if self.display_mode == LCD_4BITMODE:
            # Hitachi manual page 46
            self._write4bits(0x03)
            msleep(4.5)
            self._write4bits(0x03)
            msleep(4.5)
            self._write4bits(0x03)
            usleep(100)
            self._write4bits(0x02)
        elif self.display_mode == LCD_8BITMODE:
            # Hitachi manual page 45
            self._write8bits(0x30)
            msleep(4.5)
            self._write8bits(0x30)
            usleep(100)
            self._write8bits(0x30)
        else:
            raise ValueError('Invalid display mode: {}'.format(self.display_mode))

        # Write configuration to display
        self.command(LCD_FUNCTIONSET | displayfunction)

        # Turn on and clear display
        self.turn_on()
        self.clear()

        # Configure entry mode
        self.command(LCD_ENTRYMODESET | LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT)

    def close(self, clear=False):
        RPIO.cleanup()
        if clear:
            self.clear()

    # High level commands

    def turn_on(self):
        """Turn display on."""
        self.command(LCD_DISPLAYCONTROL | LCD_DISPLAYON)

    def turn_off(self):
        """Turn display off."""
        self.command(LCD_DISPLAYCONTROL | LCD_DISPLAYOFF)

    def clear(self):
        """Overwrite display with blank characters."""
        self.command(LCD_DISPLAYCONTROL | LCD_CLEARDISPLAY)
        msleep(2)

    # Mid level commands

    def command(self, value):
        self._send(value, RS_INSTRUCTION)

    def write(self, value):
        self._send(value, RS_DATA)

    # Low level commands

    def _send(self, value, mode):
        """Send the specified value to the display with automatic 4bit / 8bit
        selection. The rs_mode is either ``RS_DATA`` or ``RS_INSTRUCTION``."""

        # Choose instruction or data mode
        RPIO.setup(self.pins.rs, mode)

        # If the RW pin is used, set it to low in order to write.
        if self.pins.rw is not None:
            RPIO.output(self.pins.rw, 0)

        # Write data out in chunks of 4 or 8 bit
        if self.display_mode == LCD_8BITMODE:
            self._write8bits(value)
        else:
            self._write4bits(value >> 4)
            self._write4bits(value)

    def _write4bits(self, value):
        """Write 4 bits of data into the data bus."""
        for i in xrange(4):
            bit = (value >> i) & 0x01
            RPIO.output(self.pins[i + 7], bit)
        self._pulse_enable()

    def _write8bits(self, value):
        """Write 8 bits of data into the data bus."""
        for i in xrange(8):
            bit = (value >> i) & 0x01
            RPIO.output(self.pins[i + 3], bit)
        self._pulse_enable()

    def _pulse_enable(self):
        """Pulse the `enable` flag to process data."""
        RPIO.output(self.pins.e, 0)
        usleep(1)
        RPIO.output(self.pins.e, 1)
        usleep(1)
        RPIO.output(self.pins.e, 0)
        usleep(100)  # commands need > 37us to settle
