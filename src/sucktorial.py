import contextlib
import hashlib
import logging
import os
import pickle
from datetime import datetime
from pprint import pformat
from typing import Optional

import requests
from bs4 import BeautifulSoup
from config import Config

class Sucktorial:
    # Hidden folder where sessions files are stored
    SESSIONS_PATH: str = os.path.join(os.getcwd(), ".sessions")
    # Default user agent
    DEFAULT_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

    def __init__(
        self,
        config: Config
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

        # Store configuration
        self.config = config

        # Setup internal stuffs
        logging.basicConfig(
            # Set the logging level to DEBUG if --debug is specified in the CLI
            level=logging.DEBUG if self.config.get("DEBUG") else logging.INFO,
            format="%(asctime)s | %(name)s | %(levelname)s - %(message)s",
        )
        # Create a logger for the current class with the name "sucktorial"
        self.logger = logging.getLogger("sucktorial")

        # Debug-print the env
        self.logger.debug(pformat({**self.config.env, "PASSWORD": "********"}))

        # Create a session for the requests
        self.session = requests.Session()
        # Load the session from the cookie file
        self.__load_session()
        # Set the user agent
        self.session.headers.update(
            {
                "User-Agent": self.config.get("USER_AGENT", self.DEFAULT_USER_AGENT)
            }
        )

        self.logger.info("Factorial client initialized")

    def login(self, save_session: bool = True):
        """Login to Factorial. If the user is already logged in, do nothing.

        Args:
            save_session (bool, optional): save the session to a cookie file. Defaults to True.
        """
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
            url=self.config.LOGIN_URL,
            data=payload,
            hooks=self.__hook_factory("Failed to login", {200, 302}),
        )

        if save_session:
            self.__save_session()
        self.logger.info(f"Successfully logged in as {self.config.get('EMAIL')}")

    def logout(self, delete_session: bool = True):
        """Logout from Factorial.

        Args:
            delete_session (bool, optional): delete the session cookie file. Defaults to True.
        """
        response = self.session.delete(
            url=self.config.SESSION_URL,
            hooks=self.__hook_factory("Failed to logout", {204}),
        )
        if delete_session:
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

        # If the user is on leave, do nothing
        if clock_in_time.date() == datetime.now().date() and self.on_leave():
            self.logger.error("Today you're on leave, go back to sleep")
            return

        payload = {
            "now": clock_in_time.isoformat(),
            "source": "desktop",
        }
        response = self.session.post(
            url=self.config.CLOCK_IN_URL,
            data=payload,
            hooks=self.__hook_factory("Failed to clock in", {200, 201}),
        )
        self.logger.info(f"Successfully clocked in at {clock_in_time.isoformat()}")


    def graphql_query(
        self,
        operationName: Optional[str],
        query: str,
        variables: Optional[dict] = None
    ) -> dict:
        """Send a GraphQL query.

        Args:
            operationName (Optional[str]): GraphQL operation name.
            query (str): GraphQL query.
            variables (dict, optional): GraphQL variables. Defaults to None.

        Returns:
            dict: GraphQL response.
        """
        payload = {
            "operationName": operationName,
            "query": query,
            "variables": variables,
        }

        response = self.session.post(
            url=self.config.GRAPHQL_URL,
            json=payload,
            hooks=self.__hook_factory(f"Failed to send GraphQL query ({operationName})", {200}),
        )

        graphql_response = response.json()
        self.logger.info("Successfully sent GraphQL query")
        return graphql_response

    def get_employee_data(self, idx: int = -1) -> dict:
        """Get the employee data.

        Returns:
            dict: employee data.
        """

        # TODO: use introspection to check for more fields
        currents = self.graphql_query(
            operationName = "GetCurrent",
            query = """
                query GetCurrent {
                    apiCore {
                        currents {
                            employee {
                                id
                                __typename
                            }   
                        }
                        __typename
                    }
                }
            """,
            variables = {}
        ).get("data").get("apiCore").get("currents")
        
        if currents:
            return currents[idx].get("employee")
        else:
            return None

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
            url=self.config.CLOCK_OUT_URL,
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
            url=self.config.OPEN_SHIFT_URL,
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
            url=self.config.SHIFTS_URL,
            params=params,
            hooks=self.__hook_factory("Failed to get shifts", {200}),
        )
        shifts = response.json()

        self.logger.info(f"Successfully retrieved {len(shifts)} shifts")
        return shifts

    def update_shift(self, shift_id: int, **kwargs):
        # clock_in, clock_out, period_id
        response = self.session.patch(
            url=self.config.SHIFTS_URL + f"/{shift_id}",
            data=kwargs,
            hooks=self.__hook_factory("Failed to update shift", {200}),
        )
        self.logger.info(f"Successfully updated shift {shift_id}")

    def delete_shift(self, shift_id: int):
        """Delete a shift.

        Args:
            shift_id (int): shift ID.
        """
        response = self.session.delete(
            url=self.config.SHIFTS_URL + f"/{shift_id}",
            hooks=self.__hook_factory("Failed to delete shift", {204}),
        )
        self.logger.info(f"Successfully deleted shift {shift_id}")

    def delete_last_shift(self):
        """Delete the last shift, if any."""
        shifts = self.get_shifts()
        if len(shifts) == 0:
            self.logger.warning("No shifts to delete")
            return
        last_shift = shifts[-1]
        self.delete_shift(last_shift["id"])

    def get_periods(self, **kwargs):
        # (start_on, end_on), (year, month)
        response = self.session.get(
            url=self.config.PERIODS_URL,
            params=kwargs,
            hooks=self.__hook_factory("Failed to get periods", {200}),
        )
        periods = response.json()
        self.logger.info(f"Successfully retrieved {len(periods)} periods")
        return periods

    def get_leaves(
        self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None
    ) -> list[dict]:
        """Get the leaves for the specified period. If no period is specified, get the all the leaves. (?)

        Args:
            from_date (datetime, optional): from date. Defaults to None.
            to_date (datetime, optional): to date. Defaults to None.

        Returns:
            list[dict]: list of leaves.
        """
        params = {"employee_id": self.config.get("EMPLOYEE_ID")}
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")

        response = self.session.get(
            url=self.config.LEAVES_URL,
            params=params,
            hooks=self.__hook_factory("Failed to get leaves", {200}),
        )
        leaves = response.json()

        self.logger.info(f"Successfully retrieved {len(leaves)} leaves")
        return leaves

    def on_leave(self) -> bool:
        """Check if the user is on leave.

        Returns:
            bool: True if the user is on leave, False otherwise.
        """
        today = datetime.now()
        return len(self.get_leaves(from_date=today, to_date=today)) > 0

    def __save_session(self):
        """Save the session cookie file."""
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
        """Load the session cookie file."""
        email_sha256 = self.__get_email_sha256()
        current_session_file = os.path.join(self.SESSIONS_PATH, email_sha256)
        if os.path.exists(current_session_file):
            with open(current_session_file, "rb") as file:
                self.session.cookies.update(pickle.load(file))
                self.logger.info(f"Session loaded for {self.config.get('EMAIL')}")
                self.logger.debug(f"Email session ID: {email_sha256}")

    def __delete_session(self):
        """Delete the session cookie file."""
        email_sha256 = self.__get_email_sha256()
        current_session_file = os.path.join(self.SESSIONS_PATH, email_sha256)
        if os.path.exists(current_session_file):
            os.remove(current_session_file)
            self.logger.info(f"Session deleted for {self.config.get('EMAIL')}")
            self.logger.debug(f"Email session ID: {email_sha256}")
        del self.session
        self.session = requests.Session()

    def __get_email_sha256(self) -> str:
        """Get the SHA256 hash of the email."""
        return hashlib.sha256(self.config.get("EMAIL").encode()).hexdigest()

    def __get_authenticity_token(self) -> str:
        """Get a valid authenticity token from the login page.

        Raises:
            ValueError: if the authenticity token can't be retrieved.

        Returns:
            str: authenticity token.
        """
        response = self.session.get(
            url=self.config.LOGIN_URL,
            hooks=self.__hook_factory("Failed to retrieve the login page", {200}),
        )
        html_content = BeautifulSoup(response.text, "html.parser")
        auth_token = html_content.find("input", attrs={"name": "authenticity_token"}).get("value")
        if not auth_token:
            raise ValueError("Can't retrieve the authenticity token")
        return auth_token

    def __hook_factory(self, error_msg: str, ok_codes: set[int]) -> dict:
        """Create a hook to be used in the requests.

        Args:
            error_msg (str): error message to be logged.
            ok_codes (set[int]): set of valid status codes.

        Returns:
            dict: hook to be used in the requests.
        """

        def __after_request(response: requests.Response, **kwargs) -> requests.Response:
            """Check if the response status code is in the ok_codes set. If not, log the error message
            and raise a ValueError. Otherwise, return the response. This function is used as a hook
            in the requests.

            Args:
                response (requests.Response): response object.

            Raises:
                ValueError: if the response status code is not in the ok_codes set.

            Returns:
                requests.Response: response object.
            """
            if response.status_code not in ok_codes:
                message = f"({response.status_code} {response.reason}) {error_msg}"
                self.logger.error(message)
                self.logger.debug(response.text)
                raise ValueError(message)
            # Success
            self.logger.debug(f"({response.status_code} {response.reason}) {response.url}")
            self.logger.debug(response.text)
            return response

        return {"response": [__after_request]}
