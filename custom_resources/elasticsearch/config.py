import json
import boto3
import os
from http.client import HTTPSConnection
from base64 import b64encode
from pathlib import Path
import datetime


secretsmanager = boto3.client('secretsmanager')
es = boto3.client('es')

class ElasticsearchConfig:
	def __init__(self, host, password) -> None:
		self.connection = HTTPSConnection(host)
		userAndPass = b64encode(str.encode("admin:%s" % password)).decode("ascii")
		self.headers = { 
				'Authorization' : 'Basic %s' %  userAndPass,
				'Content-type': 'application/json'
		}

	def request (self, method, url, template = None): 
		self.connection.request(
				method, 
				url, 
				body=template,
				headers=self.headers
		)
		response = self.connection.getresponse().read()
		print ("*** %s on %s with %s: %s *** " % (method, url, template, response))
		return response

def handler(event, context):
	#parameters:
	action = event['RequestType']
	secret = event['ResourceProperties']['secret']
	domain = event['ResourceProperties']['domain']
	roles = event['ResourceProperties']['roles']

	password = secretsmanager.get_secret_value(
			SecretId=secret
	)['SecretString']
	
	host = es.describe_elasticsearch_domain(
			DomainName=domain
	)['DomainStatus']['Endpoints']['vpc']

	config = ElasticsearchConfig(host, password)

	print ("*** Will %s Elasticsearch config" % action)

	if (action in ['Create','Update']): 
		config.request(
			"PUT",
			"/_opendistro/_security/api/roles/extrato",
			Path("role.json").read_text()
		)
		config.request(
			"PUT",
			"/_opendistro/_security/api/rolesmapping/extrato",
			Path("role_mapping.json").read_text().replace(
				"{{iam_roles}}",
				'","'.join(roles)
			)
		)
		config.request(
			"PUT",
			"/_template/extrato_template",
			Path("template.json").read_text()
		)
		config.request(
			"POST",
			"extrato-2020-10/_doc",
			Path("sample.json").read_text()
		)

	elif action == 'Delete':
		config.request(
			"DELETE",
			"/_opendistro/_security/api/rolesmapping/extrato"
		)
		config.request(
			"DELETE",
			"/_opendistro/_security/api/roles/extrato"
		)
		config.request(
			"DELETE",
			"/_template/extrato_template"
		)

	return {
			'statusCode': 200
	}