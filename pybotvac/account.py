"""Account access and data handling for beehive endpoint."""

import binascii
import os
import shutil
import requests

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

from .robot import Robot


class BasicAuthProvider:
    def __init__(self, access_token):
        self.access_token = access_token

    def generate_headers(self):
        headers = {
            'Accept': 'application/vnd.neato.nucleo.v1',
            'Authorization': 'Token token={}'.format(self.access_token),
        }
        return headers


class OAuthProvider:
    def __init__(self, oauth_token):
        self.oauth_token = oauth_token

    def generate_headers(self):
        headers = {
            'Accept' : 'application/vnd.neato.beehive.v1+json',
            'Authorization': 'Bearer {}'.format(self.oauth_token),
        }
        return headers


class Session:
    def __init__(self, auth_provider):
        self.auth_provider = auth_provider
        self._robots = set()
        self.robot_serials = {}
        self._maps = {}
        self._headers = self.auth_provider.generate_headers()
        self._persistent_maps = {}

    @property
    def robots(self):
        """
        Return set of robots for logged in account.

        :return:
        """
        if not self._robots:
            self.refresh_robots()

        return self._robots

    @property
    def maps(self):
        """
        Return set of userdata for logged in account.

        :return:
        """
        self.refresh_maps()

        return self._maps

    def refresh_maps(self):
        """
        Get information about maps of the robots.

        :return:
        """
        for robot in self.robots:
            resp2 = (
                requests.get(urljoin(Account.ENDPOINT, 'users/me/robots/{}/maps'.format(robot.serial)),
                             headers=self._headers))
            resp2.raise_for_status()
            self._maps.update({robot.serial: resp2.json()})

    def refresh_robots(self):
        """
        Get information about robots connected to account.

        :return:
        """
        resp = requests.get(urljoin(Account.ENDPOINT, 'users/me/robots'),
                            headers=self._headers)
        resp.raise_for_status()

        for robot in resp.json():
            self._robots.add(Robot(name=robot['name'],
                                   serial=robot['serial'],
                                   secret=robot['secret_key'],
                                   traits=robot['traits'],
                                   auth_provider=self.auth_provider,))

    @staticmethod
    def get_map_image(url, dest_path=None):
        """
        Return a requested map from a robot.

        :return:
        """
        image = requests.get(url, stream=True, timeout=10)

        if dest_path:
            image_url = url.rsplit('/', 2)[1] + '-' + url.rsplit('/', 1)[1]
            image_filename = image_url.split('?')[0]
            dest = os.path.join(dest_path, image_filename)
            image.raise_for_status()
            with open(dest, 'wb') as data:
                image.raw.decode_content = True
                shutil.copyfileobj(image.raw, data)

        return image.raw

    @property
    def persistent_maps(self):
        """
        Return set of persistent maps for logged in account.

        :return:
        """
        return {robot.serial:robot.persistent_maps for robot in self.robots}


class Account:
    """
    Class with data and methods for interacting with a pybotvac cloud session.

    :param email: Email for pybotvac account
    :param password: Password for pybotvac account

    """

    ENDPOINT = 'https://beehive.neatocloud.com/'

    @classmethod
    def login_basic(cls, email, password):
        """
        Login to pybotvac account using provided email and password.

        :param email: email for pybotvac account
        :param password: Password for pybotvac account
        :return:
        """
        headers = {'Accept': 'application/vnd.neato.nucleo.v1'}

        response = requests.post(urljoin(cls.ENDPOINT, 'sessions'),
                             json={'email': email,
                                   'password': password,
                                   'platform': 'ios',
                                   'token': binascii.hexlify(os.urandom(64)).decode('utf8')},
                             headers=headers)

        response.raise_for_status()
        access_token = response.json()['access_token']

        auth_provider = BasicAuthProvider(access_token)
        return Session(auth_provider)

    @classmethod
    def login_oauth(cls, oauth_token):
        auth_provider = OAuthProvider(oauth_token)
        return Session(auth_provider)
