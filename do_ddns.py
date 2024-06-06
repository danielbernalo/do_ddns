#!/usr/bin/env python3
# by dbernal@serviberza.com
# This script is used to update DigitalOcean DNS records with the external IP address of the machine it is running on.

import argparse
import ipaddress
import json
import time
import os
import urllib.request, urllib.error
import logging
import sys


class NotFound(Exception):
    pass


class do_ddns():
    def __init__(self, args):
        self.args = args
        self.external_ip_url = os.environ.get('EXTERNAL_IP_URL')
        self.api_do = os.environ.get('API_DO')

    def get_url(self, url, headers=None):
        try:
            if headers:
                req = urllib.request.Request(url, headers=headers)
            else:
                req = urllib.request.Request(url)
            # with urllib.request.urlopen(req) as file:
            #     data = file.read()
            # return data.decode('utf8')
            request = urllib.request.urlopen(req)
            return request.read().decode('utf8')
        except urllib.error.HTTPError as e:
            logging.exception(f"HTTP error: {e.code} - {e.reason}")
        except Exception as e:
            if e.code == 404:
                raise NotFound("Domain not found")
            elif e.code != 200:
                raise Exception("Error in request")

    def get_ip(self):
        assert self.external_ip_url
        external_ip = self.get_url(self.external_ip_url).rstrip()
        ip = ipaddress.ip_address(external_ip)
        logging.info("Detected external ip address: %s", external_ip)
        if (ip.version == 4 and self.args.type_record != 'A') or (ip.version == 6 and self.args.type_record != 'AAAA'):
            raise Exception(
                'Expected record type no compatible, expect {} but got {}'.format(self.args.type_record, external_ip))
        return external_ip

    def compare_last_ip(self, ip_external, record, domain_records):
        for domain_record in domain_records:
            if domain_record['name'] == record:
                if ip_external != domain_record['data']:
                    self.update_record(ip_external, domain_record['id'])
                else:
                    logging.info("Record %s with ip %s no require update", domain_record['name'], domain_record['data'])
                return
        self.create_record(ip_external, record)

    def update_record(self, ip_external, record_id):
        logging.info("Updating records %s with ip %s", record_id, ip_external)
        headers = {'Authorization': "Bearer %s" % (self.args.token), 'Content-Type': 'application/json'}
        data = {
            'data': ip_external
        }
        data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request("{}/domains/{}/records/{}".format(self.api_do, self.args.domain, record_id),
                                     data=data,
                                     headers=headers, method='PATCH')
        with urllib.request.urlopen(req) as file:
            data = file.read()
            data = json.loads(data.decode('utf8'))
            logging.info("Record updated: %s with ip %s", data['domain_record']['name'],
                         data['domain_record']['data'])

    def create_record(self, ip_external, record):
        logging.info("Creating record %s with ip %s", record, ip_external)
        headers = {'Authorization': "Bearer %s" % self.args.token, 'Content-Type': 'application/json'}
        data = {
            'type': self.args.type_record,
            'name': record,
            'data': ip_external,
            'ttl': self.args.ttl
        }
        data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request("{}/domains/{}/records".format(self.api_do, self.args.domain), data=data,
                                     headers=headers, method='POST')
        with urllib.request.urlopen(req) as file:
            data = file.read()
            data = json.loads(data.decode('utf8'))
            logging.info("Record created: %s with ip %s", data['domain_record']['name'],
                         data['domain_record']['data'])

    def compare_record(self, ip_external):

        url = "{}/domains/{}/records?type={}".format(self.api_do, self.args.domain, self.args.type_record)
        records = []
        while True:
            headers = {'Authorization': "Bearer %s" % (self.args.token)}
            result = self.get_url(url, headers=headers)
            if not result: break
            result = json.loads(result)
            records += result['domain_records']
            logging.info("Appends Records: %s", records)
            if 'pages' in result['links'] and 'next' in result['links']['pages']:
                url = result['links']['pages']['next']
                url = url.replace("http://", "https://")
            else:
                break

        if not records:
            raise NotFound("Records not found")

        for record in self.formatting_records():
            logging.info("Searching for this record %s", record)
            self.compare_last_ip(ip_external, record, records)
            logging.info("========================= %s", record)

    def formatting_records(self):
        records = self.args.records.replace(' ', '')
        records = self.args.records.split(',')
        return records

    def run(self):
        if self.args.silent:
            logging.disable(logging.INFO)
        try:
            ip_external = self.get_ip()
            assert ip_external
            self.compare_record(ip_external)
            return 0
        except Exception as e:
            logging.exception(e)
            return 1


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", type=str, default=os.environ.get('DOMAIN'))
    parser.add_argument("records", type=str, default=os.environ.get('RECORDS'))
    parser.add_argument("-t", "--token", type=str, default=os.environ.get('DO_API_TOKEN'))
    parser.add_argument("--type_record", choices=['A', 'AAAA'], default='A')
    parser.add_argument("--ttl", default='60', type=str)
    parser.add_argument("-s", "--silent", type=bool, default=False, help="Do not log to stdout")
    return parser.parse_args()


if __name__ == "__main__":
    sys.tracebacklimit = 0
    logging.getLogger().setLevel(logging.INFO)
    logging.basicConfig(format='%(asctime)sZ %(levelname)s %(message)s')
    logging.Formatter.converter = time.gmtime
    args = parse_args()
    app = do_ddns(args=args)
    sys.exit(app.run())
