#!/usr/bin/env python3

import hashlib
import logging
import os
import pickle
import sys
from datetime import datetime
from pprint import pformat, pprint
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values


class Factorial:
    # Hidden folder where sessions files are stored
    SESSIONS_PATH: str = os.path.join(os.path.dirname(__file__), ".sessions")

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        # Check if both email and password are  (CLI usage)
        if (email and not password) or (password and not email):
            raise ValueError("Specify both email and password")

        # Load config from .env file
        self.config = dotenv_values()

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
            level=logging.DEBUG if "--debug" in sys.argv else logging.INFO,
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

        self.logger.info("Factorial client initialized")

    def login(self):
        # TODO: Controllare se l'utente è già loggato
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
        response = self.session.delete(
            url=self.config.get("SESSION_URL"),
            hooks=self.__hook_factory("Failed to logout", {204}),
        )
        self.__delete_session()
        self.logger.info(f"Successfully logout from {self.config.get('EMAIL')}")

    def clock_in(self, clock_in_time: Optional[datetime] = None):
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
        return len(self.open_shift()) > 0

    def open_shift(self) -> dict:
        response = self.session.get(
            url=self.config.get("OPEN_SHIFT_URL"),
            hooks=self.__hook_factory("Failed to get open shift", {200}),
        )
        self.logger.info("Successfully retrieved open shift")
        return response.json()

    def shifts(self):
        response = self.session.get(
            url=self.config.get("SHIFTS_URL"),
            hooks=self.__hook_factory("Failed to get shifts", {200}),
        )
        self.logger.info("Shifts successful")
        return response.json()

    def delete_last_shift(self):
        shifts = self.shifts()
        if len(shifts) == 0:
            self.logger.warning("No shifts to delete")
            return False
        last_shift = shifts[-1]
        response = self.session.delete(
            url=self.config.get("SHIFTS_URL") + f"/{last_shift['id']}",
            hooks=self.__hook_factory("Failed to delete shift", {204}),
        )
        self.logger.info("Shift deleted")
        return True

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


if __name__ == "__main__":
    from time import sleep

    f = Factorial()
    f.open_shift()
    breakpoint()
