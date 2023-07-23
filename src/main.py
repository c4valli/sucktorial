#!/usr/bin/env python3

from clihelper import SucktorialCliHelper
from random import randint
from datetime import datetime, timedelta
from sucktorial import Sucktorial
from pprint import pprint

if __name__ == "__main__":
    args = SucktorialCliHelper.parse_and_validate()

    sucktorial = Sucktorial(**vars(args))

    if args.login:
        sucktorial.login()
    elif args.logout:
        sucktorial.logout()
    elif args.clock_in:
        sucktorial.clock_in(
            datetime.now() + timedelta(minutes=randint(-args.random_clock, args.random_clock))
            if args.random_clock is not None
            else None
        )
    elif args.clock_out:
        sucktorial.clock_out(
            datetime.now() + timedelta(minutes=randint(-args.random_clock, args.random_clock))
            if args.random_clock is not None
            else None
        )
    elif args.clocked_in:
        print(sucktorial.is_clocked_in())
    elif args.shifts:
        pprint(sucktorial.get_shifts())
    elif args.leaves:
        pprint(sucktorial.get_leaves())