class SucktorialCliHelper:
    @staticmethod
    def get_args_parser():
        from argparse import ArgumentParser

        parser = ArgumentParser(description="Sucktorial CLI")

        credentials_group = parser.add_argument_group("Credentials")
        credentials_group.add_argument(
            "--email",
            "-e",
            type=str,
            help="Email to login with",
        )
        credentials_group.add_argument(
            "--password",
            "-p",
            type=str,
            help="Password to login with",
        )

        action_group = parser.add_argument_group("Actions")
        action_group.add_argument(
            "--login",
            action="store_true",
            help="Login to Factorial",
        )
        action_group.add_argument(
            "--logout",
            action="store_true",
            help="Logout from Factorial",
        )
        action_group.add_argument(
            "--clock-in",
            action="store_true",
            help="Clock in",
        )
        action_group.add_argument(
            "--clock-out",
            action="store_true",
            help="Clock out",
        )
        action_group.add_argument(
            "--clocked-in",
            action="store_true",
            help="Check if you are clocked in",
        )
        action_group.add_argument(
            "--shifts",
            action="store_true",
            help="Get the shifts",
        )
        action_group.add_argument(
            "--leaves",
            action="store_true",
            help="Get the leaves",
        )

        customization_group = parser.add_argument_group("Customization")
        customization_group.add_argument(
            "--random-clock",
            type=int,
            nargs="?",
            const=15,
            help="Clock in/out at a random time (+/- X minutes from now)",
        )
        customization_group.add_argument(
            "--user-agent",
            type=str,
            help="User agent to use for the requests",
        )
        customization_group.add_argument(
            "--env",
            type=str,
            help="Name of the user custom .env file (.<user>.env)",
        )
        customization_group.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug logging",
        )

        return parser

    @staticmethod
    def validate_args(args, parser):
        if (args.email and not args.password) or (args.password and not args.email):
            parser.error("Specify both email and password")

        if args.random_clock and not (args.clock_in or args.clock_out):
            parser.error("Specify --clock-in or --clock-out with --random-clock")

        if not (
            args.login
            or args.logout
            or args.clock_in
            or args.clock_out
            or args.clocked_in
            or args.shifts
            or args.leaves
        ):
            parser.error("Specify at least one action")

        if (
            int(args.login)
            + int(args.logout)
            + int(args.clock_in)
            + int(args.clock_out)
            + int(args.clocked_in)
            + int(args.shifts)
            + int(args.leaves)
        ) > 1:
            parser.error("Specify only one action")

    @staticmethod
    def parse_and_validate():
        parser = SucktorialCliHelper.get_args_parser()
        args, _ = parser.parse_known_args()
        SucktorialCliHelper.validate_args(args, parser)
        return args
