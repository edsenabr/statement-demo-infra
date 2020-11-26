#!/usr/bin/env python3
from aws_cdk import (
		aws_ec2 as ec2,
		aws_eks as eks,
		aws_msk as msk,
		custom_resources as cr,
		aws_logs as logs,
		aws_lambda as lbd,
		core
)
import pip

class KafkaConfig(core.Stack):

	def __init__(self, scope: core.Construct, id: str, cluster: eks.Cluster, kafka: msk.CfnCluster, vpc: ec2.Vpc, **kwargs) -> None:
		super().__init__(scope, id, **kwargs)

		pip.main([
			"install", 
			"--system",
			"--target", "custom_resources/kafka/lib",
			"kafka-python"
		])
		arn = cr.AwsCustomResource(
			self, 'clusterArn',
			policy=cr.AwsCustomResourcePolicy.from_sdk_calls(resources=['*']), 
			on_create=cr.AwsSdkCall(
				action='listClusters', 
				service='Kafka', 
				physical_resource_id=cr.PhysicalResourceId.of("ClusterNameFilter"), 
				parameters={
					"ClusterNameFilter": kafka.cluster_name,
					"MaxResults": 1
				}, 
			), 
		)

		bootstraps = cr.AwsCustomResource(
			self, 'clusterBootstraps',
			policy=cr.AwsCustomResourcePolicy.from_sdk_calls(resources=["*"]),
			on_create=cr.AwsSdkCall(
				action='getBootstrapBrokers', 
				service='Kafka', 
				physical_resource_id=cr.PhysicalResourceId.of("ClusterArn"), 
				parameters={
					"ClusterArn": arn.get_response_field("ClusterInfoList.0.ClusterArn")
				},
			), 
		)

		manifests = []
		for namespace in self.node.try_get_context("kubernetes")['namespaces']:
			manifests.append({
				"apiVersion": "v1",
				"kind": "ConfigMap",
				"metadata": {
					"name": "kafka",
					"namespace": namespace
				},
				"data": {
					"bootstrap":  bootstraps.get_response_field('BootstrapBrokerStringTls'),
				}
			})
		eks.KubernetesManifest(
			self, 
			"kafka-config", 
			cluster=cluster,
			manifest=manifests
		)

		function = lbd.SingletonFunction(
			self,
			"KafkaConfigFunction",
			uuid="b09329a3-5206-46f7-822f-337da714aeac",
			code=lbd.Code.from_asset(
				"custom_resources/kafka/"
			),
			handler="config.handler",
			runtime=lbd.Runtime.PYTHON_3_7,
			function_name="kafkaConfig",
			log_retention=logs.RetentionDays.ONE_DAY,
			security_group=ec2.SecurityGroup.from_security_group_id(self, "lambdaKafkaVPC", vpc.vpc_default_security_group),
			timeout=core.Duration.seconds(30),
			vpc=vpc,
			vpc_subnets=ec2.SubnetSelection(
				one_per_az=True
			)
		)

		provider = cr.Provider(
			self, "KafkaConfigProvider",
    	on_event_handler=function,
    	log_retention=logs.RetentionDays.ONE_DAY
		)

		core.CustomResource(
			self, "KafkaLoadTopic", 
			service_token=provider.service_token,
			properties={
				"bootstrap": bootstraps.get_response_field('BootstrapBrokerStringTls'),
				"topic": "load",
				"partitions": 150,
				"replicas": 1
			}
		)

		core.CustomResource(
			self, "KafkaGenerateTopic", 
			service_token=provider.service_token,
			properties={
				"bootstrap": bootstraps.get_response_field('BootstrapBrokerStringTls'),
				"topic": "generate",
				"partitions": 200,
				"replicas": 1
			}
		)