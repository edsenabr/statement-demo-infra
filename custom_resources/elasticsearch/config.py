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
	shards = event['ResourceProperties']['shards']
	replicas = event['ResourceProperties']['replicas']

	password = secretsmanager.get_secret_value(
			SecretId=secret
	)['SecretString']
	
	host = es.describe_elasticsearch_domain(
			DomainName=domain
	)['DomainStatus']['Endpoints']['vpc']

	config = ElasticsearchConfig(host, password)

	print ("*** Will %s Elasticsearch config with secret={%s}, domain={%s}, roles={%s}, shards={%s}, replicas={%s} " % (action, secret, domain, roles, shards, replicas))

	if (action in ['Create','Update']): 
		roles = Path("role_mapping.json").read_text().replace(
			"{{iam_roles}}",
			'","'.join(roles)
		) 

		template = Path("template.json").read_text().replace(
			"{{shards}}",
			shards
		).replace(
			"{{replicas}}",
			replicas
		)

		config.request(
			"PUT",
			"/_opendistro/_security/api/roles/extrato",
			Path("role.json").read_text()
		)
		config.request(
			"PUT",
			"/_opendistro/_security/api/rolesmapping/extrato",
			roles
		)
		config.request(
			"PUT",
			"/_template/extrato_template",
			template
		)

		if action == 'Create': 
			config.request(
				"POST",
				"extrato-2020-10/_doc",
				Path("sample.json").read_text()
			)

		if action == 'Update': 
			# old_shards = shards
			# old_replicas = replicas
			# try:
			# 	old_shards = event['OldResourceProperties']['shards']
			# 	old_replicas = event['OldResourceProperties']['replicas']
			# except:
			# 	old_shards = 0
			# 	old_replicas = 0

			indices = json.loads(
				config.request(
					"GET",
					"/extrato-*/_settings/index.number_of_*"
				)
			)

			for name in indices:
				old_shards = indices[name]['settings']['index']['number_of_shards']
				old_replicas = indices[name]['settings']['index']['number_of_replicas']
				if old_shards != shards:
					config.request(
						"DELETE",
						"/%s" % name
					)
				elif old_replicas != replicas:
					config.request(
						"PUT",
						"/%s/_settings" % name,
						'{"index":{"number_of_replicas":"%s"} }' % replicas
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