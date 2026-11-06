#!/usr/bin/env python3
"""Restore a streamed metadata dump into an owned disposable database only."""
import hashlib
import json
import re
import secrets
import subprocess
import sys


def command(args, **kwargs):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60, **kwargs)
    if result.returncode:
        raise RuntimeError('Restore check command failed')
    return result.stdout


def main():
    header = sys.stdin.buffer.readline(65537)
    if len(header) > 65536 or not header.endswith(b'\n'):
        raise ValueError('Invalid restore header')
    data = json.loads(header)
    key, expected = data['encryptionKey'], data['dumpSha256']
    if not re.fullmatch(r'[a-f0-9]{64}', key) or not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise ValueError('Invalid restore metadata')
    name = 'camera_restore_' + secrets.token_hex(12)
    created = False
    try:
        command(['runuser', '-u', 'postgres', '--', 'createdb', '--owner=devone', '--template=template0', name])
        created = True
        child = subprocess.Popen(['runuser', '-u', 'devone', '--', 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl', '-d', name], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        digest = hashlib.sha256()
        try:
            while True:
                chunk = sys.stdin.buffer.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
                child.stdin.write(chunk)
            child.stdin.close()
            if child.wait(timeout=60) or digest.hexdigest() != expected:
                raise RuntimeError('Dump restore or checksum failed')
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
        source = r'''
import { createRequire } from 'node:module';
import { decrypt } from '/opt/devone/current/apps/api/dist/crypto.js';
const require=createRequire('/opt/devone/current/package.json');
const {Client}=require('pg');let input='';for await(const chunk of process.stdin)input+=chunk;
const data=JSON.parse(input),db=new Client({host:'/var/run/postgresql',user:'devone',database:data.database});
try{await db.connect();
 const users=(await db.query('SELECT role,totp_secret FROM users')).rows;
 const admins=users.filter(x=>x.role==='ADMIN');
 if(!admins.length||!admins.every(x=>/^[A-Z2-7]{16,128}$/.test(decrypt(x.totp_secret,data.key))))throw Error('MFA restore invalid');
 const intent=(await db.query('SELECT desired,revision FROM recording_intent WHERE id=1')).rows;
 if(intent.length!==1)throw Error('Recording intent missing');
 const audit=Number((await db.query('SELECT count(*) FROM audit_events')).rows[0].count);
 console.log(JSON.stringify({restored:true,users:users.length,admins:admins.length,mfaDecrypt:true,auditEvents:audit,productionDatabaseModified:false}));
}finally{await db.end();}
'''
        result = command(['runuser', '-u', 'devone', '--', '/usr/local/bin/node', '--input-type=module', '-e', source], input=json.dumps({'database': name, 'key': key}).encode())
        print(result.decode().strip())
    finally:
        if created:
            command(['runuser', '-u', 'postgres', '--', 'dropdb', '--force', name])


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError):
        sys.exit('Isolated metadata restore check failed; production database was not a restore target.')
