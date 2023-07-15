import datetime
import logging
import os
import pickle
import sys

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values


class Factorial:
    def __init__(self):
        self.config = dotenv_values()

        if not self.config.get("EMAIL") or not self.config.get("PASSWORD"):
            raise ValueError("Email and password are required")
        logging.basicConfig(
            level=logging.DEBUG if "--debug" in sys.argv else logging.INFO,
            format="%(asctime)s | %(name)s | %(levelname)s - %(message)s",
        )

        self.session = requests.Session()

        self.logger = logging.getLogger("factorial")
        self.logger.info("Factorial client initialized")

    def login(self):
        # TODO: Controllare se l'utente è già loggato
        authenticity_token = self.__get_authenticity_token()
        self.logger.debug(f"Authenticity token: {authenticity_token}")
        payload = {
            "authenticity_token": authenticity_token,
            "user[email]": self.config.get("EMAIL"),
            "user[password]": self.config.get("PASSWORD"),
            "user[remember_me]": 0,
            "commit": "Accedi",
        }
        self.logger.debug(f"Payload: {payload}")
        response = self.session.post(url=self.config.get("LOGIN_URL"), data=payload)
        if response.status_code != 200:
            self.logger.error(f"Can't login ({response.status_code})")
            self.logger.debug(response.text)
            raise ValueError("Can't login")
        self.logger.info("Login successful")
        with open(self.config.get("COOKIE_FILE"), "wb") as file:
            pickle.dump(self.session.cookies, file)
            self.logger.info("Sessions saved")
        return True

    def logout(self):
        response = self.session.delete(url=self.config.get("SESSION_URL"))
        logout_correcty = response.status_code == 204
        self.logger.info("Logout successfully {}".format(logout_correcty))
        self.session = requests.Session()
        path_file = self.config.get("COOKIE_FILE")
        if os.path.exists(path_file):
            os.remove(path_file)
            self.logger.info("Logout: Removed cookies file")
        # self.mates.clear()
        # self.current_user = {}
        return logout_correcty

    def clock_in(self):
        # TODO: Controllare se e' gia' in clock in
        payload = {
            # {"now":"2023-07-10T00:10:58+02:00","source":"desktop"}
            "now": datetime.now().isoformat(),
            "source": "desktop",
        }
        response = self.session.post(url=self.config.get("CLOCK_IN_URL"), data=payload)
        if response.status_code not in {200, 201}:
            self.logger.error(f"Can't clock in ({response.status_code})")
            self.logger.debug(response.text)
            raise ValueError("Can't clock in")
        self.logger.info("Clock in successful at {}".format(datetime.now().isoformat()))
        return True

    def clock_out(self):
        # TODO: Controllare se e' gia' in clock out
        payload = {
            # {"now":"2023-07-10T00:10:58+02:00","source":"desktop"}
            "now": datetime.now().isoformat(),
            "source": "desktop",
        }
        response = self.session.post(url=self.config.get("CLOCK_OUT_URL"), data=payload)
        if response.status_code not in {200, 201}:
            self.logger.error(f"Can't clock in ({response.status_code})")
            self.logger.debug(response.text)
            raise ValueError("Can't clock in")
        self.logger.info("Clock in successful at {}".format(datetime.now().isoformat()))
        return True

    def is_clocked_in(self) -> bool:
        return len(self.open_shift()) == 0

    def open_shift(self) -> dict:
        response = self.session.get(url=self.config.get("OPEN_SHIFT_URL"))
        if response.status_code != 200:
            self.logger.error(f"Can't get open shift ({response.status_code})")
            self.logger.debug(response.text)
            raise ValueError("Can't get open shift")
        self.logger.info("Open shift successful")
        return response.json()

    def __get_authenticity_token(self):
        response = self.session.get(url=self.config.get("LOGIN_URL"))
        if response.status_code != 200:
            self.logger.error(f"Can't retrieve the login page ({response.status_code})")
            self.logger.debug(response.text)
            raise ValueError("Can't retrieve the login page")
        html_content = BeautifulSoup(response.text, "html.parser")
        auth_token = html_content.find("input", attrs={"name": "authenticity_token"}).get("value")
        if not auth_token:
            raise ValueError("Can't retrieve the authenticity token")
        return auth_token


if __name__ == "__main__":
    from time import sleep

    factorial = Factorial()
    print(factorial.config)
    factorial.login()
    sleep(3)
    factorial.clock_in()
    sleep(10)
    factorial.clock_out()
    sleep(3)
    factorial.logout()
