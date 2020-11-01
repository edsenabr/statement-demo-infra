#!/usr/bin/env python3
import sys
import os
import json
sys.path.insert(
	0, '%s/lib' % os.path.dirname(os.path.realpath(__file__))
)
from kafka.admin import KafkaAdminClient, NewTopic

def handler(event, context):
	print("*** called with event=%s ***" % event)
	action = event['RequestType']
	bootstrap = event['ResourceProperties']['bootstrap']
	name = event['ResourceProperties']['topic']
	partitions = int(event['ResourceProperties']['partitions'])
	replicas = int(event['ResourceProperties']['replicas'])

	admin_client = KafkaAdminClient(
    bootstrap_servers=bootstrap.split(","), 
    client_id='test',
		security_protocol="SSL",
		ssl_check_hostname=False
	)

	if action == "Create":
		create_topic(admin_client, name, partitions, replicas)

	if action == "Update":
		delete_topic(admin_client, name)
		create_topic(admin_client, name, partitions, replicas)

	if action == "Delete":
		delete_topic(admin_client, name)

def create_topic(client: KafkaAdminClient, name:str, partitions:int, replicas:int): 
		topic = NewTopic(name=name, num_partitions=partitions, replication_factor=replicas)
		client.create_topics(new_topics=[topic], validate_only=False)

def delete_topic(client: KafkaAdminClient, name:str):
		client.delete_topics([name])

if __name__ == '__main__':
	handler(json.loads(sys.argv[1]), None)