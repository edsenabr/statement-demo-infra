#!/usr/bin/env python3
import boto3
from es import Elastic
from pathlib import Path
from aws_cdk import (
		aws_eks as eks,
		aws_ec2 as ec2,
		aws_iam as iam,
		aws_elasticsearch as es,
		custom_resources as cr,
		aws_logs as logs,
		aws_lambda as lbd,
		core
)

class ElastiSearchConfig(core.Stack):
	def __init__(self, scope: core.Construct, id: str, elastic: Elastic, vpc: ec2.Vpc, roles: list, cluster: eks.Cluster, **kwargs) -> None:
		super().__init__(scope, id, **kwargs)

		sm_policy = iam.PolicyStatement(
			actions=["secretsmanager:GetSecretValue"], 
			effect=iam.Effect.ALLOW, 
			resources=[elastic.secret.secret_arn]
		)

		es_policy = iam.PolicyStatement(
			actions=["es:DescribeElasticsearchDomain"], 
			effect=iam.Effect.ALLOW, 
			resources=[elastic.domain.domain_arn]
		)

		function = lbd.SingletonFunction(
			self,
			"ElasticsearchConfigFunction",
			uuid="e579d5f9-1709-43ea-b75f-9d1452ca7690",
			code=lbd.Code.from_asset(
				"custom_resources/elasticsearch/"
			),
			handler="config.handler",
			runtime=lbd.Runtime.PYTHON_3_7,
			function_name="elasticsearchConfig",
			initial_policy=[sm_policy,es_policy],
			log_retention=logs.RetentionDays.ONE_DAY,
			security_group=ec2.SecurityGroup.from_security_group_id(self, "lambdaVPC", vpc.vpc_default_security_group),
			timeout=core.Duration.seconds(30),
			vpc=vpc,
			vpc_subnets=ec2.SubnetSelection(
				one_per_az=True
			)
		)

		provider = cr.Provider(
			self, "ElasticsearchConfigProvider",
    	on_event_handler=function,
    	log_retention=logs.RetentionDays.ONE_DAY
		)

		core.CustomResource(
			self, "ElasticSearchConfig", 
			service_token=provider.service_token,
			properties={
				"domain": elastic.domain.domain_name,
				"secret": elastic.secret.secret_arn,
				"roles": [role.role_arn for role in roles],
				"shards": self.node.try_get_context("elastic")['shards'],
				"replicas": self.node.try_get_context("elastic")['replicas']
			}
		)

		manifests = []
		for namespace in self.node.try_get_context("kubernetes")['namespaces']:
			manifests.append({
				"apiVersion": "v1",
				"kind": "ConfigMap",
				"metadata": {
					"name": "elasticsearch",
					"namespace": namespace
				},
				"data": {
					"url": elastic.domain.domain_endpoint
				}
			})
		eks.KubernetesManifest(
			self, 
			"elastic-search-cm", 
			cluster=cluster,
			manifest=manifests
		)		