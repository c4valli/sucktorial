from typing import Optional
from dotenv import dotenv_values

class Config:
    BASE_URL = "https://api.factorialhr.com/"
    CLOCK_IN_URL = f"{BASE_URL}/attendance/shifts/clock_in"
    CLOCK_OUT_URL = f"{BASE_URL}/attendance/shifts/clock_out"
    GRAPHQL_URL = f"{BASE_URL}/graphql"
    LEAVES_URL = f"{BASE_URL}/leaves"
    OPEN_SHIFT_URL = f"{BASE_URL}/attendance/shifts/open_shift"
    PERIODS_URL = f"{BASE_URL}/attendance/periods"
    SESSION_URL = f"{BASE_URL}/sessions"
    SHIFTS_URL = f"{BASE_URL}/attendance/shifts"

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        user_agent: Optional[str] = None,
        envfile: Optional[str] = None,
        **kwargs,
    ):
        self.env = dotenv_values()

        # If a custom .env file is specified, load it
        if envfile:
            self.env.update(dotenv_values(f".{envfile}.env"))

        # Check if both email and password are provided (CLI usage)
        if (email and not password) or (password and not email):
            raise ValueError("Specify both email and password")

        # If email and password are specified, override the env
        if email and password:
            self.env["EMAIL"] = email
            self.env["PASSWORD"] = password
        # Check if email and password are correctly specified in the .env file
        elif not self.env.get("EMAIL") or not self.env.get("PASSWORD"):
            raise ValueError("Both email and password are required, fix your env file")
        
        # If user agent is specified, override the env
        if user_agent:
            self.env["USER_AGENT"] = user_agent

        self.LOGIN_URL = f"{self.BASE_URL}/{self.env.get('LANG')}/users/sign_in"
    
    def get(self, key: str, default: str = None) -> Optional[str]:
        return self.env.get(key, default)
