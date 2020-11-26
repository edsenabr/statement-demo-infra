#!/usr/bin/env python3
import boto3
from aws_cdk import (
		aws_ec2 as ec2,
		aws_elasticsearch as es,
		custom_resources as sdk,
		core
)
acm = boto3.client('acm')

class UltraWarm(core.Stack):
	def __init__(self, scope: core.Construct, id: str, domain: es.CfnDomain, **kwargs) -> None:
		super().__init__(scope, id, **kwargs)
		arn = sdk.AwsCustomResource(
			self, 'esConfig',
			policy=sdk.AwsCustomResourcePolicy.from_sdk_calls(resources=[domain.domain_arn]), 
			on_create=sdk.AwsSdkCall(
				action='updateElasticsearchDomainConfig', 
				service='ES', 
				physical_resource_id=sdk.PhysicalResourceId.of("updateElasticsearchDomainConfig"), 
				output_path="DomainConfig.ElasticsearchClusterConfig",
				parameters={
					"DomainName": domain.domain_name,
					"ElasticsearchClusterConfig": {
						"WarmCount": self.node.try_get_context("elastic")["warm"]["count"],
						"WarmEnabled": True,
						"WarmType": self.node.try_get_context("elastic")["warm"]["type"]
					}
				},
			),
		)
		arn.node.add_dependency(domain)