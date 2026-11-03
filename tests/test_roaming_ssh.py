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

    def test_management_principals_have_separate_forward_permissions(self):
        base = EFFECTIVE.replace('allowusers devone-air', 'allowusers devone-air camera-maint-relay camera-maint-jump')
        for principal, forwarding, listen, destination in [
            ('devone-air', 'remote', '127.0.0.1:18554 127.0.0.1:19996', 'none'),
            ('camera-maint-relay', 'remote', '127.0.0.1:19022', 'none'),
            ('camera-maint-jump', 'local', 'none', '127.0.0.1:19022'),
        ]:
            policy = base.replace('allowtcpforwarding remote', 'allowtcpforwarding '+forwarding).replace(
                'permitlisten 127.0.0.1:18554 127.0.0.1:19996', 'permitlisten '+listen).replace('permitopen none', 'permitopen '+destination)
            with self.subTest(principal=principal):
                self.assertEqual(validate_policy(policy, principal, management=True)['user'], principal)

    def test_management_rejects_cross_role_and_unknown_access(self):
        base = EFFECTIVE.replace('allowusers devone-air', 'allowusers devone-air camera-maint-relay camera-maint-jump')
        for principal in ('camera-maint-relay', 'camera-maint-jump', 'root', 'unknown'):
            with self.subTest(principal=principal), self.assertRaises(ValueError):
                validate_policy(base, principal, management=True)
        with self.assertRaises(ValueError):
            validate_policy(base.replace('allowusers devone-air camera-maint-relay camera-maint-jump', 'allowusers *'), management=True)

    def test_live_policy_cannot_gain_maintenance_listener(self):
        base = EFFECTIVE.replace('allowusers devone-air', 'allowusers devone-air camera-maint-relay camera-maint-jump')
        with self.assertRaises(ValueError):
            validate_policy(base.replace('127.0.0.1:19996', '127.0.0.1:19996 127.0.0.1:19022'), management=True)

    def test_openssh_repeated_allowusers_lines_are_aggregated_strictly(self):
        base = EFFECTIVE.replace('allowusers devone-air', 'allowusers devone-air\nallowusers camera-maint-relay\nallowusers camera-maint-jump')
        self.assertEqual(validate_policy(base, management=True)['user'], 'devone-air')
        for extra in ('allowusers root\n', 'allowusers devone-air\n', 'allowusers *\n'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_policy(base+extra, management=True)
