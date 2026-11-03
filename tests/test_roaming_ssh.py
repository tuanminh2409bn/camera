import unittest
from scripts.validate_roaming_ssh import validate_policy


EFFECTIVE = '''port 2222
listenaddress 0.0.0.0:2222
allowusers devone-air
permitrootlogin no
authenticationmethods publickey
pubkeyauthentication yes
passwordauthentication no
kbdinteractiveauthentication no
permitemptypasswords no
allowtcpforwarding remote
allowstreamlocalforwarding no
permitopen none
permitlisten 127.0.0.1:18554 127.0.0.1:19996
gatewayports no
maxsessions 0
permittty no
permittunnel no
x11forwarding no
allowagentforwarding no
permituserrc no
permituserenvironment no
strictmodes yes
authorizedkeysfile .ssh/authorized_keys
'''


class RoamingPolicyTest(unittest.TestCase):
    def test_key_only_tunnel_with_no_user_session(self):
        self.assertEqual(validate_policy(EFFECTIVE)['reverseLoopbackPorts'], [18554, 19996])

    def test_root_password_shell_and_wildcard_users_rejected(self):
        for old, new in [('allowusers devone-air', 'allowusers *'),
                         ('permitrootlogin no', 'permitrootlogin yes'),
                         ('passwordauthentication no', 'passwordauthentication yes'),
                         ('maxsessions 0', 'maxsessions 1')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                validate_policy(EFFECTIVE.replace(old, new))

    def test_public_listener_forward_and_direct_forward_rejected(self):
        for old, new in [('permitlisten 127.0.0.1:18554 127.0.0.1:19996', 'permitlisten any'),
                         ('allowtcpforwarding remote', 'allowtcpforwarding yes'),
                         ('permitopen none', 'permitopen any'),
                         ('gatewayports no', 'gatewayports yes')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                validate_policy(EFFECTIVE.replace(old, new))

    def test_missing_or_duplicate_constraints_fail_closed(self):
        for text in (EFFECTIVE.replace('allowusers devone-air\n', ''), EFFECTIVE + 'allowusers root\n'):
            with self.assertRaises(ValueError):
                validate_policy(text)
