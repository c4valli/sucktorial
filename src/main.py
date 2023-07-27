#!/usr/bin/env python3

import json
from clihelper import SucktorialCliHelper
from random import randint
from datetime import datetime, timedelta
from sucktorial import Sucktorial
from pprint import pprint
from config import Config

if __name__ == "__main__":
    args = SucktorialCliHelper.parse_and_validate()

    # Load configuration
    config = Config(**vars(args))

    sucktorial = Sucktorial(config)

    if args.login:
        sucktorial.login()
    
    if args.logout:
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
    elif args.employee_data:
        pprint(sucktorial.get_employee_data())
    elif args.graphql_query:
        print(json.dumps(sucktorial.graphql_query(operationName="query", query = args.graphql_query)))