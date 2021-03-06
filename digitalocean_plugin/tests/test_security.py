########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

# Built-in imports
import os
import random

# Third party imports
import testtools
import responses

# Cloudify imports
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import NonRecoverableError

from digitalocean_plugin.security import DigitalOceanSecurity


class TestSecurity(testtools.TestCase):

    test_pubkey_filename = 'testkey.pub'
    badkey_path = 'xyzpdq.pub'
    test_random = random

    test_instance = DigitalOceanSecurity()

    @staticmethod
    def mock_ctx(test_name):

        test_node_id = test_name
        test_properties = {}

        ctx = MockCloudifyContext(node_id=test_node_id,
                                  properties=test_properties)

        return ctx

    @staticmethod
    def make_url(end_of_url):
        return "https://api.digitalocean.com/v2/%s" % end_of_url

    @staticmethod
    def load_response(fixture_filename):

        cwd = os.path.dirname(__file__)
        fix_path = "%s/fixtures/" % cwd
        fixture_file_path = os.path.join(fix_path, fixture_filename)

        if not os.path.isfile(fixture_file_path):
            raise AssertionError(
                "No such fixture file: %s ." % fixture_file_path)

        with open(fixture_file_path, 'r') as fix:
            return fix.read()

    @responses.activate
    def test_add_pubkey_to_digitalocean_account(self):
        """
        Tests that:
            + bad input results in a NonRecoverableError
            + good input is processed correctly
            + DigitalOcean service reponses are returned
              to the caller as a tuple of (key_id, key_fingerprint)
        """
        ctx = self.mock_ctx('test_add_pubkey_to_digitalocean_account')

        # raising when garbage input is provided
        oops = self.assertRaises(
            NonRecoverableError,
            self.test_instance.
            add_pubkey_to_digitalocean_account,
            self.badkey_path,
            None,
            ctx=ctx
        )

        self.assertIn(
            "Unknown public key file: '{0}'.".format(self.badkey_path),
            oops.message
        )

        pubkey_path = os.path.join(os.path.dirname(__file__),
                                   self.test_pubkey_filename)

        responses.add(
            responses.POST,
            self.make_url('account/keys'),
            self.load_response('account.keys.json')
        )

        result = self.test_instance.add_pubkey_to_digitalocean_account(
            pubkey_path,
            None,
            ctx=ctx
        )

        self.assertEqual(512190, result[0])

        result_fingerprint = result[1]
        self.assertEqual(47, len(result_fingerprint))
        expected_fingerprint \
            = '3b:16:bf:e4:8b:00:8b:b8:59:8c:a9:d3:f0:19:45:fa'
        self.assertEqual(expected_fingerprint, result_fingerprint)

    @responses.activate
    def test_add_pubkey_to_digitalocean_account_needs_2xx(self):
        """
        a NonRecoverableError should be raised if the DigitalOcean server
        returns a non-200 response code
        """
        error_code = 505

        responses.add(
            responses.POST,
            self.make_url('account/keys'),
            status=error_code
        )

        pubkey_path = os.path.join(os.path.dirname(__file__),
                                   self.test_pubkey_filename)

        oops = self.assertRaises(
            NonRecoverableError,
            self.test_instance.
            add_pubkey_to_digitalocean_account,
            pubkey_path,
            "a name"
        )

        msg = oops.message
        self.assertIn("Error on server for ", msg)
        self.assertIn(str(error_code), msg)

    def test_make_key_name(self):
        """
            Tests that a helper method works as expected.
        """
        test_input = "a key name"
        self.assertEqual(self.test_instance._make_key_name(test_input),
                         test_input)

        strip_me = " key "
        actual = self.test_instance._make_key_name(strip_me)
        self.assertEqual(actual, strip_me.strip())

        actual0 = self.test_instance._make_key_name(None)
        self.assertEqual(actual0 is None, False,
                         "Generated key name should be non-None.")

        actual1 = self.test_instance._make_key_name(None)
        actual2 = self.test_instance._make_key_name(None)

        self.assertEqual(actual1 == actual2, False,
                         "Generated key names should be different.")

    def test_build_url(self):
        """
            Tests that:
                + consecutive forward slashes are dealt with correctly
                + urls are constructed from input as expected
        """
        hi_mom = 'hi/mom'

        act = self.test_instance._build_url(hi_mom)
        self.assertEqual(True, act.endswith(hi_mom))
        self.assertEqual(act, "https://api.digitalocean.com/v2/hi/mom")

        act = self.test_instance._build_url("/%s" % hi_mom)
        self.assertEqual(True, act.endswith(hi_mom))
        self.assertEqual(False, act.startswith("/"))

        act = self.test_instance._build_url("/////%s" % hi_mom)
        self.assertEqual(True, act.endswith(hi_mom))
        self.assertEqual(False, act.startswith("/"))

        hi_mom = "/hi/mommy/"
        act = self.test_instance._build_url(hi_mom)
        self.assertEqual("https://api.digitalocean.com/v2/hi/mommy/", act)

    def test_common_headers(self):
        """
            Tests that a helper method works as expected.
        """
        act = self.test_instance._common_headers()

        self.assertEqual(
            'application/json',
            act['Content-Type'],
            "Json should be specified as the preferred content type."
        )

        auth = act['Authorization']
        self.assertEqual(True, auth.startswith('Bearer '))
        self.assertEqual(
            True,
            auth.endswith(self.test_instance.digitalocean_security_token)
        )

    def random_test_id(self):
        return str(self.test_random.randint(1, 100))

    @responses.activate
    def test_delete_pubkey_from_account_by_keyid(self):
        """
            Tests that:
                + test_id makes it into to the request url
                + method returns true, when a 204 is returned
        """
        test_id = self.random_test_id()

        responses.add(
            responses.DELETE,
            self.make_url("account/keys/%s" % test_id),
            status=204
        )

        act = self.test_instance\
            .delete_pubkey_from_account_by_keyid(test_id)

        self.assertEqual(True, act)

    @responses.activate
    def test_delete_pubkey_from_account_by_keyid_needs_204(self):
        """
            Tests that:
                + a non-204 response code from the server
                  results in a NonRecoverableError
        """
        test_id = self.random_test_id()
        test_status = 200

        responses.add(
            responses.DELETE,
            self.make_url("account/keys/%s" % test_id),
            status=test_status
        )

        oops = self.assertRaises(
            NonRecoverableError,
            self.test_instance.
            delete_pubkey_from_account_by_keyid,
            test_id
        )

        self.assertIn("Error on server", oops.message)
        self.assertIn("Expected status code = '204'", oops.message)
        self.assertIn(str(test_status), oops.message)

    @staticmethod
    def random_fingerprint():
        return "3b:16:bf:e4:8b:00:8b:b8:59:8c:a9:d3:f0:19:45:fa"

    @responses.activate
    def test_delete_pubkey_from_account_by_fingerprint(self):
        """
            Tests that:
                + test_fingerprint makes it into to the request url
                + method returns true, when a 204 is returned
        """
        test_fingerprint = self.random_fingerprint()

        responses.add(
            responses.DELETE,
            self.make_url("account/keys/%s" % test_fingerprint),
            status=204
        )

        self.assertEqual(
            True,
            self.test_instance.
            delete_pubkey_from_account_by_fingerprint(
                test_fingerprint
            )
        )

    @responses.activate
    def test_delete_pubkey_from_account_by_fingerprint_needs_204(self):
        """
            Tests that:
                + a non-204 response code from the server
                  results in a NonRecoverableError
        """
        error_code = 200
        test_fingerprint = self.random_fingerprint()

        responses.add(
            responses.DELETE,
            self.make_url("account/keys/%s" % test_fingerprint),
            status=error_code
        )

        oops = self.assertRaises(
            NonRecoverableError,
            self.test_instance.delete_pubkey_from_account_by_fingerprint,
            test_fingerprint
        )

        self.assertIn("Error on server", oops.message)
        self.assertIn("Expected status code = '204'", oops.message)
        self.assertIn(str(error_code), oops.message)
