# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import hotel,services

__all__ = ['register']


def register():
    Pool.register(
        hotel.Guest,
        hotel.Room,
        hotel.RoomReservations,
        hotel.RoomReservationsGuest,
        services.Services,
        services.ServicesLines,
        module='hotel', type_='model')
    Pool.register(
        module='hotel', type_='wizard')
    Pool.register(
        module='hotel', type_='report')
