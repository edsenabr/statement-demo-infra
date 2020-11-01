#!/usr/bin/env python3
from aws_cdk import (
	custom_resources as cr,
	aws_ecr as ecr,
	aws_eks as eks,
	aws_iam as iam,
	aws_lambda as lbd,
	aws_logs as logs,
	core
)
from pathlib import Path

class KubernetesConfig(core.Stack):

	def __init__(self, scope: core.Construct, id: str, cluster: eks.Cluster, **kwargs) -> None:
		super().__init__(scope, id, **kwargs)

		maps= []
		self.roles=[]

		ecr_policy = iam.PolicyStatement(
			actions=[
				"ecr:DescribeImages",
				"ecr:ListImages",
				"ecr:BatchDeleteImage"
			], 
			effect=iam.Effect.ALLOW, 
			resources=[
				"arn:aws:ecr:%s:%s:repository/%s" % (core.Stack.of(self).region, core.Stack.of(self).account, namespace) for namespace in self.node.try_get_context("kubernetes")['namespaces']
			]
		)

		function = lbd.SingletonFunction(
			self,
			"ECRDeleteImagesFunction",
			uuid="19411b0e-0e80-4ad4-a316-3235940775e4",
			code=lbd.Code.from_asset(
				"custom_resources/kubernetes/"
			),
			handler="config.handler",
			runtime=lbd.Runtime.PYTHON_3_7,
			function_name="kubernetesConfig",
			initial_policy=[ecr_policy],
			log_retention=logs.RetentionDays.ONE_DAY,
			timeout=core.Duration.seconds(30)
		)

		provider = cr.Provider(
			self, "ECRDeleteImagesFunctionProvider",
    	on_event_handler=function,
    	log_retention=logs.RetentionDays.ONE_DAY
		)


		repositores = []
		for namespace in self.node.try_get_context("kubernetes")['namespaces']: 
			manifest = cluster.add_manifest(
				"eksConfigNamespace-%s" % namespace,
				{
					"apiVersion": "v1",
					"kind": "Namespace",
					"metadata": {
						"name": namespace
					}
				}
			)

			sa = cluster.add_service_account(
				"service-account-%s" % namespace,
				name="statement-demo",
				namespace=namespace
			)
			sa.node.add_dependency(manifest)
			self.roles.append(sa.role)

			repository = ecr.Repository(
				self, ("repository-%s" % namespace),
				removal_policy=core.RemovalPolicy.DESTROY,
				repository_name=namespace,
				lifecycle_rules=[ecr.LifecycleRule(max_image_count=1)]
			)

			repositores.append(repository.repository_arn)

			maps.append({
				"apiVersion": "v1",
				"kind": "ConfigMap",
				"metadata": {
					"name": "application.properties",
					"namespace": namespace
				},
				"data": {
					"application-aws.properties":  Path("../%s/src/main/resources/application-aws.properties" % namespace).read_text()
				}
			})

			core.CustomResource(
				self, "ECRDeleteImagesFunction-%s" % namespace, 
				service_token=provider.service_token,
				properties={
					"repository": namespace
				}
			).node.add_dependency(repository)

		eks.KubernetesManifest(
			self, 
			"eksConfigMaps", 
			cluster=cluster, 
			manifest=maps
		)

		iam.Policy(
			self, "saPolicy", 
			force=True, 
			policy_name="EKSSAPolicy", 
			roles=self.roles, 
			statements=[
				iam.PolicyStatement(
					actions=["cloudwatch:PutMetricData"], 
					conditions={
						"StringEquals": {
							"cloudwatch:namespace": "statement12"
						},
					},
					resources=["*"]
				)
			]
		)
