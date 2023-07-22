#!/usr/bin/env python3

import contextlib
import hashlib
import logging
import os
import pickle
import sys
from datetime import datetime, timedelta
from pprint import pformat, pprint
from random import randint
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values


class Factorial:
    # Hidden folder where sessions files are stored
    SESSIONS_PATH: str = os.path.join(os.path.dirname(__file__), ".sessions")
    # Default user agent
    DEFAULT_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        user_agent: Optional[str] = None,
        env: Optional[str] = None,
        debug: bool = False,
        **kwargs,
    ):
        """Factorial client.

        Args:
            email (str, optional): your email. Defaults to None.
            password (str, optional): your password. Defaults to None.
            user_agent (str, optional): custom user agent. Defaults to None.
            env (Optional[str], optional): custom .<user>.env file with credentials. Defaults to None.
            debug (bool, optional): enable debug mode. Defaults to False.

        Raises:
            ValueError: if none or only one between email and password were specified,
                here or in the .env file
        """

        # Check if both email and password are  (CLI usage)
        if (email and not password) or (password and not email):
            raise ValueError("Specify both email and password")

        # Load config from .env file
        self.config = dotenv_values()

        # If a custom .env file is specified, load it
        if env or kwargs.get("env"):
            self.config.update(dotenv_values(f".{env or kwargs.get('env')}.env"))

        # If email and password are specified, override the config
        if email and password:
            self.config["EMAIL"] = email
            self.config["PASSWORD"] = password
        # Check if email and password are correctly specified in the .env file
        elif not self.config.get("EMAIL") or not self.config.get("PASSWORD"):
            raise ValueError("Both email and password are required, fix your .env file")

        # Setup internal stuffs
        logging.basicConfig(
            # Set the logging level to DEBUG if --debug is specified in the CLI
            level=logging.DEBUG if debug or kwargs.get("debug") else logging.INFO,
            format="%(asctime)s | %(name)s | %(levelname)s - %(message)s",
        )
        # Create a logger for the current class with the name "factorial"
        self.logger = logging.getLogger("factorial")

        # Debug-print the config
        self.logger.debug(pformat({**self.config, "PASSWORD": "********"}))

        # Create a session for the requests
        self.session = requests.Session()
        # Load the session from the cookie file
        self.__load_session()
        # Set the user agent
        self.session.headers.update(
            {
                "User-Agent": user_agent
                or kwargs.get("user_agent")
                or self.config.get("USER_AGENT", self.DEFAULT_USER_AGENT)
            }
        )

        self.logger.info("Factorial client initialized")

    def login(self):
        """Login to Factorial. If the user is already logged in, do nothing."""
        # Check if the user is already logged in by trying to get the open shift
        with contextlib.suppress(ValueError):
            self.is_clocked_in()
            # If no exception is raised, the user is already logged in
            self.logger.warning(f"Already logged in as {self.config.get('EMAIL')}")
            return

        # Get a valid authenticity token from the login page
        authenticity_token = self.__get_authenticity_token()
        self.logger.debug(f"Authenticity token: {authenticity_token}")

        payload = {
            "authenticity_token": authenticity_token,
            "user[email]": self.config.get("EMAIL"),
            "user[password]": self.config.get("PASSWORD"),
            "user[remember_me]": 1,
            # "commit": "Accedi"
        }
        self.logger.debug(pformat({**payload, "user[password]": "********"}))

        response = self.session.post(
            url=self.config.get("LOGIN_URL"),
            data=payload,
            hooks=self.__hook_factory("Failed to login", {200, 302}),
        )

        self.__save_session()
        self.logger.info(f"Successfully logged in as {self.config.get('EMAIL')}")

    def logout(self):
        """Logout from Factorial."""
        response = self.session.delete(
            url=self.config.get("SESSION_URL"),
            hooks=self.__hook_factory("Failed to logout", {204}),
        )
        self.__delete_session()
        self.logger.info(f"Successfully logout from {self.config.get('EMAIL')}")

    def clock_in(self, clock_in_time: Optional[datetime] = None):
        """Clock in. If the user is already clocked in, do nothing. If no clock in time is specified,
        clock in at the current time.

        Args:
            clock_in_time (datetime, optional): clock-in time. Defaults to None.
        """
        if self.is_clocked_in():
            self.logger.warning("Already clocked in")
            return

        if clock_in_time is None:
            clock_in_time = datetime.now()

        payload = {
            "now": clock_in_time.isoformat(),
            "source": "desktop",
        }
        response = self.session.post(
            url=self.config.get("CLOCK_IN_URL"),
            data=payload,
            hooks=self.__hook_factory("Failed to clock in", {200, 201}),
        )
        self.logger.info(f"Successfully clocked in at {clock_in_time.isoformat()}")

    def clock_out(self, clock_out_time: Optional[datetime] = None):
        """Clock out. If the user is not clocked in, do nothing. If no clock out time is specified,
        clock out at the current time.

        Args:
            clock_out_time (datetime, optional): clock-out time. Defaults to None.
        """
        if not self.is_clocked_in():
            self.logger.warning("Not clocked in")
            return

        if clock_out_time is None:
            clock_out_time = datetime.now()

        payload = {
            "now": clock_out_time.isoformat(),
            "source": "desktop",
        }
        response = self.session.post(
            url=self.config.get("CLOCK_OUT_URL"),
            data=payload,
            hooks=self.__hook_factory("Failed to clock out", {200, 201}),
        )
        self.logger.info(f"Successfully clocked out at {clock_out_time.isoformat()}")

    def is_clocked_in(self) -> bool:
        """Check if the user is clocked in. If it is, open_shift() will return a non-empty dict.

        Returns:
            bool: True if the user is clocked in, False otherwise.
        """
        return len(self.open_shift()) > 0

    def open_shift(self) -> dict:
        """Get the current eventually open shift. If the user is not clocked in, return an empty dict.

        Returns:
            dict: the current open shift (if any) or an empty dict.
        """
        response = self.session.get(
            url=self.config.get("OPEN_SHIFT_URL"),
            hooks=self.__hook_factory("Failed to get open shift", {200}),
        )
        self.logger.info("Successfully retrieved open shift")
        return response.json()

    def get_shifts(
        self,
        period_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> list[dict]:
        """Get the shifts for the specified period.
        If no period is specified, get the shifts for the current month. (?)


        Args:
            period_id (int, optional): period ID. Defaults to None.
            year (int, optional): filter by year, requires month. Defaults to None.
            month (int, optional): filter by month, requires year.  Defaults to None.

        Raises:
            ValueError: if both period_id and (year or month) are specified
                or if only one between year and month is specified.

        Returns:
            list[dict]: list of shifts.
        """

        if period_id and (year or month):
            raise ValueError("Specify either period_id or year and month")

        if (year and not month) or (month and not year):
            raise ValueError("Specify both year and month")

        params = {}
        if period_id:
            params["period_id"] = period_id
        if year:
            params["year"] = year
        if month:
            params["month"] = month

        response = self.session.get(
            url=self.config.get("SHIFTS_URL"),
            params=params,
            hooks=self.__hook_factory("Failed to get shifts", {200}),
        )
        shifts = response.json()

        self.logger.info(f"Successfully retrieved {len(shifts)} shifts")
        return shifts

    def update_shift(self, shift_id: int, **kwargs):
        # clock_in, clock_out, period_id
        response = self.session.patch(
            url=self.config.get("SHIFTS_URL") + f"/{shift_id}",
            data=kwargs,
            hooks=self.__hook_factory("Failed to update shift", {200}),
        )
        self.logger.info(f"Successfully updated shift {shift_id}")

    def delete_shift(self, shift_id: int):
        response = self.session.delete(
            url=self.config.get("SHIFTS_URL") + f"/{shift_id}",
            hooks=self.__hook_factory("Failed to delete shift", {204}),
        )
        self.logger.info(f"Successfully deleted shift {shift_id}")

    def delete_last_shift(self):
        shifts = self.get_shifts()
        if len(shifts) == 0:
            self.logger.warning("No shifts to delete")
            return
        last_shift = shifts[-1]
        self.delete_shift(last_shift["id"])

    def get_periods(self, **kwargs):
        # (start_on, end_on), (year, month)
        response = self.session.get(
            url=self.config.get("PERIODS_URL"),
            params=kwargs,
            hooks=self.__hook_factory("Failed to get periods", {200}),
        )
        periods = response.json()
        self.logger.info(f"Successfully retrieved {len(periods)} periods")
        return periods

    def __save_session(self):
        if not os.path.exists(self.SESSIONS_PATH):
            self.logger.debug(f"Creating sessions folder at {self.SESSIONS_PATH}")
            os.mkdir(self.SESSIONS_PATH)

        email_sha256 = self.__get_email_sha256()
        current_session_file = os.path.join(self.SESSIONS_PATH, email_sha256)
        with open(current_session_file, "wb") as session_file:
            pickle.dump(self.session.cookies, session_file)
            self.logger.info(f"Session saved for {self.config.get('EMAIL')}")
            self.logger.debug(f"Email session ID: {email_sha256}")

    def __load_session(self):
        email_sha256 = self.__get_email_sha256()
        current_session_file = os.path.join(self.SESSIONS_PATH, email_sha256)
        if os.path.exists(current_session_file):
            with open(current_session_file, "rb") as file:
                self.session.cookies.update(pickle.load(file))
                self.logger.info(f"Session loaded for {self.config.get('EMAIL')}")
                self.logger.debug(f"Email session ID: {email_sha256}")

    def __delete_session(self):
        email_sha256 = self.__get_email_sha256()
        current_session_file = os.path.join(self.SESSIONS_PATH, email_sha256)
        if os.path.exists(current_session_file):
            os.remove(current_session_file)
            self.logger.info(f"Session deleted for {self.config.get('EMAIL')}")
            self.logger.debug(f"Email session ID: {email_sha256}")
        del self.session
        self.session = requests.Session()

    def __get_email_sha256(self):
        return hashlib.sha256(self.config.get("EMAIL").encode()).hexdigest()

    def __get_authenticity_token(self):
        response = self.session.get(
            url=self.config.get("LOGIN_URL"),
            hooks=self.__hook_factory("Failed to retrieve the login page", {200}),
        )
        html_content = BeautifulSoup(response.text, "html.parser")
        auth_token = html_content.find("input", attrs={"name": "authenticity_token"}).get("value")
        if not auth_token:
            raise ValueError("Can't retrieve the authenticity token")
        return auth_token

    def __hook_factory(self, error_msg: str, ok_codes: set[int]):
        def __after_request(response: requests.Response, **kwargs):
            if response.status_code not in ok_codes:
                message = f"({response.status_code} {response.reason}) {error_msg}"
                self.logger.error(message)
                self.logger.debug(response.text)
                raise ValueError(message)
            return response

        return {"response": [__after_request]}

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

        if not (args.login or args.logout or args.clock_in or args.clock_out or args.clocked_in):
            parser.error("Specify at least one action")

        if (
            int(args.login)
            + int(args.logout)
            + int(args.clock_in)
            + int(args.clock_out)
            + int(args.clocked_in)
        ) > 1:
            parser.error("Specify only one action")

    @staticmethod
    def run_from_cli():
        parser = Factorial.get_args_parser()
        args, _ = parser.parse_known_args()
        Factorial.validate_args(args, parser)

        factorial = Factorial(**vars(args))

        if args.login:
            factorial.login()
        elif args.logout:
            factorial.logout()
        elif args.clock_in:
            factorial.clock_in(
                datetime.now() + timedelta(minutes=randint(-args.random_clock, args.random_clock))
                if args.random_clock is not None
                else None
            )
        elif args.clock_out:
            factorial.clock_out(
                datetime.now() + timedelta(minutes=randint(-args.random_clock, args.random_clock))
                if args.random_clock is not None
                else None
            )
        elif args.clocked_in:
            print(factorial.is_clocked_in())


if __name__ == "__main__":
    Factorial.run_from_cli()
